from __future__ import annotations

import re

from sqlalchemy.orm import Session

from app import models
from app.services.admin.settings import get_effective_setting
from app.services.articles.normalizer import normalize_whitespace
from app.services.images.candidates import link_image_candidates_to_issue_with_previous
from app.services.images.selector import select_representative_image
from app.services.issues.matcher import find_similar_issue
from app.services.issues.page_builder import refresh_issue_cache
from app.services.issues.scoring import score_issue_candidate
from app.services.topics import normalize_topic
from app.utils import new_id


def slugify(value: str) -> str:
    cleaned = re.sub(r"[^0-9a-zA-Z가-힣]+", "-", normalize_whitespace(value).lower()).strip("-")
    return cleaned[:160] or new_id("issue")


def issue_title_from_articles(articles: list[models.Article]) -> str:
    if not articles:
        return "새 이슈 후보"
    return normalize_whitespace(articles[0].title)[:180]


def _link_article_images_and_select(
    db: Session,
    *,
    articles: list[models.Article],
    issue_id: str,
) -> None:
    if not articles:
        return
    previous_issue_ids: set[str] = set()
    for article in articles:
        _, previous = link_image_candidates_to_issue_with_previous(db, article_id=article.id, issue_id=issue_id)
        previous_issue_ids.update(previous)
    select_representative_image(db, issue_id=issue_id)
    for previous_issue_id in previous_issue_ids:
        if previous_issue_id != issue_id:
            select_representative_image(db, issue_id=previous_issue_id)


def ensure_issue_candidate(db: Session, *, articles: list[models.Article]) -> models.AdminQueueItem | None:
    scoring = score_issue_candidate(articles)
    issue_candidate_threshold = get_effective_setting(db, "issue_candidate_threshold")
    issue_auto_publish_threshold = get_effective_setting(db, "issue_auto_publish_threshold")
    if scoring["score"] < issue_candidate_threshold:
        return None
    title = issue_title_from_articles(articles)
    similar_issue, _ = find_similar_issue(
        db,
        summary=" ".join(article.summary for article in articles[:5]),
        title=title,
        topic=scoring["topic"],
    )
    if similar_issue:
        for article in articles:
            article.issue_id = similar_issue.id
        similar_issue.issue_score = max(similar_issue.issue_score, int(scoring["score"]))
        similar_issue.updated_at = models.now_utc()
        _link_article_images_and_select(db, articles=articles, issue_id=similar_issue.id)
        refresh_issue_cache(db, issue_id=similar_issue.id)
        db.flush()
        return None
    issue_id = f"issue_{slugify(title)[:52]}"
    existing = db.get(models.AdminQueueItem, issue_id)
    if existing:
        existing.article_count = max(existing.article_count, len(articles))
        existing.reason = f"이슈 점수 {scoring['score']} · 출처 {scoring['signals']['publisher_count']}개 · 수치 {scoring['signals']['number_count']}개"
        db.flush()
        return existing
    item = models.AdminQueueItem(
        article_count=len(articles),
        id=issue_id,
        priority="높음" if scoring["score"] >= 80 else "보통",
        reason=f"이슈 점수 {scoring['score']} · 출처 {scoring['signals']['publisher_count']}개 · 수치 {scoring['signals']['number_count']}개",
        status="자동 공개 가능" if scoring["score"] >= issue_auto_publish_threshold else "검토 대기",
        title=title,
        topic=normalize_topic(scoring["topic"]),
    )
    db.add(item)
    db.flush()
    return item


def publish_issue_from_candidate(db: Session, *, candidate_id: str, is_public: bool = True) -> models.Issue:
    candidate = db.get(models.AdminQueueItem, candidate_id)
    if not candidate:
        raise ValueError("issue candidate not found")
    issue = db.get(models.Issue, candidate.id)
    if not issue:
        issue = models.Issue(
            article_count=candidate.article_count,
            id=candidate.id,
            is_public=is_public,
            issue_score=80 if candidate.priority == "높음" else 60,
            risk="고영향" if candidate.priority == "높음" else "일반",
            slug=slugify(candidate.title),
            status="검증 진행",
            summary="수집된 기사와 근거를 주장 단위로 검증 중입니다.",
            title=candidate.title,
            topic=normalize_topic(candidate.topic),
        )
        db.add(issue)
    issue.is_public = is_public
    issue.status = "검증 진행"
    candidate.status = "출고 승인" if is_public else "숨김"
    assigned_articles: list[models.Article] = []
    for article in db.query(models.Article).filter(models.Article.issue_id.is_(None)).all():
        if slugify(article.title)[:24] in issue.id or issue.title[:18] in article.title:
            article.issue_id = issue.id
            assigned_articles.append(article)
    _link_article_images_and_select(db, articles=assigned_articles, issue_id=issue.id)
    refresh_issue_cache(db, issue_id=issue.id)
    db.flush()
    return issue
