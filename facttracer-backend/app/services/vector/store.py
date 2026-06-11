from __future__ import annotations

import math

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.services.ai.openai_embeddings import OpenAIEmbeddingService


def cosine_similarity(left: list[float] | None, right: list[float] | None) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=False))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)


def embed_claim_if_possible(db: Session, claim: models.Claim) -> None:
    if claim.embedding:
        return
    try:
        embedding = OpenAIEmbeddingService(db).embed_text(claim.sanitized_text or claim.claim_text)
    except Exception:
        embedding = None
    if embedding:
        claim.embedding = embedding


def similar_claims_by_embedding(
    db: Session,
    *,
    claim: models.Claim,
    limit: int = 5,
) -> list[tuple[models.Claim, float]]:
    if not claim.embedding:
        return []
    rows = db.scalars(
        select(models.Claim).where(
            models.Claim.issue_id == claim.issue_id,
            models.Claim.id != claim.id,
            models.Claim.embedding.is_not(None),
        ),
    ).all()
    scored = [(row, cosine_similarity(claim.embedding, row.embedding)) for row in rows]
    return sorted(scored, key=lambda item: item[1], reverse=True)[:limit]
