from __future__ import annotations

import re
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app import models
from app.collectors.base import CollectedArticle
from app.services.articles.normalizer import hash_text, normalize_whitespace, token_set
from app.services.issues.matcher import incident_similarity


GENERIC_TITLE_PATTERNS = (
    "untitled",
    "문서뷰어",
    "공공데이터포털",
    "국가법령정보센터",
    "전체 제정·개정이유",
    "이달의 건강정보",
    "직원소개",
)
GENERIC_PUBLISHERS = {
    "공공데이터포털",
    "대한민국 정책브리핑",
    "국가법령정보센터",
    "국가건강정보포털",
}
CORE_STOPWORDS = {
    "ai",
    "관련",
    "감시",
    "검증",
    "공식",
    "기록",
    "논란",
    "뉴스",
    "대책",
    "발표",
    "보고서",
    "사건",
    "사고",
    "서비스",
    "전국",
    "정부",
    "주의보",
    "추진",
    "후속",
}


def _text_attr(value: Any, name: str) -> str:
    return str(getattr(value, name, "") or "")


def _compact(value: str) -> str:
    return re.sub(r"[^0-9a-zA-Z가-힣]+", "", value).lower()


def article_text(article: CollectedArticle | models.Article | Any) -> str:
    return normalize_whitespace(
        " ".join(
            [
                _text_attr(article, "title"),
                _text_attr(article, "summary"),
                _text_attr(article, "body_text")[:700],
                _text_attr(article, "publisher"),
            ],
        ),
    )


def is_generic_article_page(*, publisher: str = "", title: str = "", url: str = "") -> bool:
    normalized_title = normalize_whitespace(title).lower()
    normalized_publisher = normalize_whitespace(publisher)
    normalized_url = str(url or "").lower()
    if not normalized_title:
        return True
    if normalized_title in {"title", "untitled", "-", "뉴스"}:
        return True
    if any(pattern in normalized_title for pattern in GENERIC_TITLE_PATTERNS):
        return True
    if normalized_publisher in GENERIC_PUBLISHERS and len(token_set(normalized_title)) <= 3:
        return True
    if "data.go.kr" in normalized_url and (
        "공공데이터포털" in title or "filedata.do" in normalized_url or "datasearch" in normalized_url
    ):
        return True
    return False


def _issue_core_tokens(issue: models.Issue) -> set[str]:
    text = normalize_whitespace(
        " ".join(
            [
                issue.title or "",
                issue.event_group_name or "",
                issue.major_topic_name or "",
            ],
        ),
    )
    tokens: set[str] = set()
    for token in token_set(text):
        if token in CORE_STOPWORDS or token.isdigit():
            continue
        if len(token) < 2:
            continue
        tokens.add(token)
    return tokens


def _substring_hits(core_tokens: set[str], value: str) -> set[str]:
    compact_value = _compact(value)
    hits: set[str] = set()
    for token in core_tokens:
        compact_token = _compact(token)
        if not compact_token:
            continue
        if compact_token in compact_value:
            hits.add(token)
            continue
        if len(compact_token) >= 5 and any(compact_token.startswith(_compact(part)) for part in token_set(value)):
            hits.add(token)
    return hits


def article_matches_issue(issue: models.Issue, article: CollectedArticle | models.Article | Any) -> bool:
    title = _text_attr(article, "title")
    publisher = _text_attr(article, "publisher")
    url = _text_attr(article, "url")
    if is_generic_article_page(publisher=publisher, title=title, url=url):
        return False

    text = article_text(article)
    if not text:
        return False
    compact_issue_title = _compact(issue.title or "")
    compact_article = _compact(text)
    if compact_issue_title and compact_issue_title in compact_article:
        return True

    core_tokens = _issue_core_tokens(issue)
    if not core_tokens:
        return incident_similarity(issue.title or "", text) >= 0.42

    hits = _substring_hits(core_tokens, text)
    if len(hits) >= 2:
        return True
    if len(hits) == 1 and len(core_tokens) <= 2 and incident_similarity(issue.title or "", text) >= 0.18:
        return True
    return incident_similarity(issue.title or "", text) >= 0.42


def _content_hash_for_article(article: CollectedArticle | models.Article | Any) -> str:
    body_text = _text_attr(article, "body_text")
    title = _text_attr(article, "title")
    return hash_text(body_text or title)


def has_cross_issue_content_duplicate(
    db: Session,
    *,
    content_hash: str,
    issue_id: str,
    article_id: str | None = None,
) -> bool:
    if not content_hash or not issue_id:
        return False
    query = select(models.Article.id).where(
        models.Article.content_hash == content_hash,
        models.Article.issue_id.is_not(None),
        models.Article.issue_id != "",
        models.Article.issue_id != issue_id,
    )
    if article_id:
        query = query.where(models.Article.id != article_id)
    return bool(db.scalar(query.limit(1)))


def should_attach_article_to_issue(
    db: Session,
    *,
    article: CollectedArticle | models.Article | Any,
    content_hash: str | None = None,
    issue: models.Issue | None,
) -> tuple[bool, str]:
    if not issue:
        return True, "no_issue"
    title = _text_attr(article, "title")
    publisher = _text_attr(article, "publisher")
    url = _text_attr(article, "url")
    if is_generic_article_page(publisher=publisher, title=title, url=url):
        return False, "generic_page"
    effective_hash = content_hash or _content_hash_for_article(article)
    article_id = _text_attr(article, "id") or None
    if has_cross_issue_content_duplicate(db, content_hash=effective_hash, issue_id=issue.id, article_id=article_id):
        return False, "cross_issue_content_duplicate"
    if not article_matches_issue(issue, article):
        return False, "low_relevance"
    return True, "matched"


def relevant_issue_articles(issue: models.Issue, articles: list[models.Article]) -> list[models.Article]:
    return [article for article in articles if article_matches_issue(issue, article)]


def issue_relevance_stats(issue: models.Issue, articles: list[models.Article]) -> dict[str, Any]:
    relevant = relevant_issue_articles(issue, articles)
    total = len(articles)
    generic = [
        article
        for article in articles
        if is_generic_article_page(publisher=article.publisher, title=article.title, url=article.url)
    ]
    return {
        "genericArticleCount": len(generic),
        "relevanceRatio": round(len(relevant) / total, 4) if total else 0.0,
        "relevantArticleCount": len(relevant),
        "totalArticleCount": total,
    }


def cleanup_redundant_parse_jobs(db: Session) -> dict[str, int]:
    rows = db.scalars(
        select(models.JobAttempt)
        .join(models.Article, models.Article.id == models.JobAttempt.target_id)
        .where(
            models.JobAttempt.job_type == "parse_article",
            models.JobAttempt.status == "queued",
            models.Article.parse_status.in_(["parsed", "completed", "ok"]),
        ),
    ).all()
    if not rows:
        return {"completed": 0}
    now = models.now_utc()
    db.execute(
        update(models.JobAttempt)
        .where(models.JobAttempt.id.in_([row.id for row in rows]))
        .values(
            last_error="",
            output_json={"status": "skipped", "reason": "article_already_parsed"},
            status="completed",
            updated_at=now,
        ),
        execution_options={"synchronize_session": False},
    )
    return {"completed": len(rows)}
