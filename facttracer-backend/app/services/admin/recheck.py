from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.services.issues.page_builder import refresh_issue_cache
from app.services.perspectives.mapper import rebuild_perspectives
from app.services.verification.verifier import verify_claim


def reverify_issue_claims(db: Session, *, issue_id: str) -> int:
    claims = db.scalars(select(models.Claim).where(models.Claim.issue_id == issue_id)).all()
    for claim in claims:
        verify_claim(db, claim=claim)
    rebuild_perspectives(db, issue_id=issue_id)
    refresh_issue_cache(db, issue_id=issue_id)
    db.flush()
    return len(claims)


def reverify_single_claim(db: Session, *, claim_id: str) -> models.Claim:
    claim = db.get(models.Claim, claim_id)
    if not claim:
        raise ValueError("claim not found")
    verify_claim(db, claim=claim)
    if claim.issue_id:
        rebuild_perspectives(db, issue_id=claim.issue_id)
        refresh_issue_cache(db, issue_id=claim.issue_id)
    db.flush()
    return claim
