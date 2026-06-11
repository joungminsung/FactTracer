from __future__ import annotations

from sqlalchemy.orm import Session

from app import models


def update_source_policy(
    db: Session,
    *,
    credibility: float | None = None,
    collection_interval_minutes: int | None = None,
    source_id: str,
    status: str | None = None,
) -> models.SourceDomain:
    source = db.get(models.SourceDomain, source_id)
    if not source:
        raise ValueError("source not found")
    if status is not None:
        source.status = status
    if credibility is not None:
        source.credibility = max(0.0, min(1.0, credibility))
    if collection_interval_minutes is not None:
        source.collection_interval_minutes = max(1, collection_interval_minutes)
    source.last_reviewed_at = models.now_utc()
    db.flush()
    return source
