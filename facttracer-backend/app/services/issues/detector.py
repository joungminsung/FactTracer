from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.services.admin.settings import get_effective_setting
from app.services.issues.matcher import incident_similarity, match_article_to_issue
from app.services.issues.page_builder import refresh_issue_cache
from app.services.issues.publisher import ensure_issue_candidate, publish_issue_from_candidate
from app.services.issues.scoring import score_issue_candidate


def detect_or_match_issue(db: Session, *, article: models.Article) -> models.Issue | None:
    if article.issue_id:
        return db.get(models.Issue, article.issue_id)
    matched, _ = match_article_to_issue(db, article=article)
    if matched:
        article.issue_id = matched.id
        refresh_issue_cache(db, issue_id=matched.id)
        db.flush()
        return matched

    recent_unmatched = db.scalars(
        select(models.Article)
        .where(models.Article.issue_id.is_(None), models.Article.publisher != "")
        .order_by(models.Article.collected_at.desc())
        .limit(20),
    ).all()
    article_text = f"{article.title} {article.summary} {article.body_text[:700]}"
    similar_articles = [
        candidate
        for candidate in recent_unmatched
        if candidate.id == article.id
        or incident_similarity(
            article_text,
            f"{candidate.title} {candidate.summary} {candidate.body_text[:700]}",
        )
        >= 0.42
    ]
    if article not in similar_articles:
        similar_articles.insert(0, article)
    candidate = ensure_issue_candidate(db, articles=similar_articles or [article])
    if article.issue_id:
        issue = db.get(models.Issue, article.issue_id)
        if issue:
            return issue
    if not candidate:
        return None
    scoring = score_issue_candidate(similar_articles or [article])
    if scoring["score"] >= get_effective_setting(db, "issue_auto_publish_threshold"):
        issue = publish_issue_from_candidate(db, candidate_id=candidate.id, is_public=True)
        article.issue_id = issue.id
        refresh_issue_cache(db, issue_id=issue.id)
        return issue
    return None
