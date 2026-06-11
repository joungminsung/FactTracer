from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.services.articles.normalizer import article_dedup_hash, hash_text, normalize_url
from app.services.articles.parser import ParsedArticle
from app.services.images.candidates import persist_parsed_image_candidates
from app.utils import new_id


def upsert_article(
    db: Session,
    *,
    issue_id: str | None = None,
    parsed: ParsedArticle,
    source_id: str | None = None,
    source_type: str = "news",
    url: str,
) -> tuple[models.Article, bool]:
    normalized_url = normalize_url(url)
    dedup_hash = article_dedup_hash(title=parsed.title, url=normalized_url, body_text=parsed.body_text)
    existing = db.scalar(select(models.Article).where(models.Article.dedup_hash == dedup_hash))
    if existing:
        if issue_id and not existing.issue_id:
            existing.issue_id = issue_id
        existing.updated_at = models.now_utc()
        persist_parsed_image_candidates(
            db,
            article=existing,
            issue_id=issue_id,
            parsed=parsed,
            source_type=source_type,
            source_url=url,
        )
        db.flush()
        return existing, False

    article = models.Article(
        body_text=parsed.body_text,
        content_hash=hash_text(parsed.body_text or parsed.title),
        dedup_hash=dedup_hash,
        id=new_id("article"),
        issue_id=issue_id,
        normalized_url=normalized_url,
        parse_status=parsed.parse_status,
        published_at=parsed.published_at if isinstance(parsed.published_at, datetime) else None,
        publisher=parsed.publisher,
        source_id=source_id,
        source_type=source_type,
        summary=parsed.summary,
        title=parsed.title,
        url=url,
    )
    db.add(article)
    db.flush()
    persist_parsed_image_candidates(
        db,
        article=article,
        issue_id=issue_id,
        parsed=parsed,
        source_type=source_type,
        source_url=url,
    )
    return article, True
