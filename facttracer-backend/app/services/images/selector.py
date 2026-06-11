from __future__ import annotations

from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.services.articles.normalizer import token_set


LOW_QUALITY_URL_TERMS = (
    "favicon",
    "logo",
    "sprite",
    "profile",
    "avatar",
    "icon",
    "blank",
    "spacer",
)

PREFERRED_SOURCE_TYPES = {"official", "public", "statistics", "law"}
PREFERRED_SOURCE_HINTS = (
    ".go.kr",
    ".gov",
    "go.kr",
    "gov.kr",
    "law.go.kr",
    "moleg",
    "kostat",
    "data.go.kr",
)


def _combined_candidate_text(candidate: models.ImageCandidate) -> str:
    return " ".join(
        [
            candidate.url or "",
            candidate.source_url or "",
            candidate.publisher or "",
            candidate.source_type or "",
        ],
    ).lower()


def _is_preferred_source(candidate: models.ImageCandidate) -> bool:
    source_type = (candidate.source_type or "").lower()
    if source_type in PREFERRED_SOURCE_TYPES:
        return True
    combined = _combined_candidate_text(candidate)
    return any(hint in combined for hint in PREFERRED_SOURCE_HINTS)


def _matches_issue(candidate: models.ImageCandidate, *, issue: models.Issue) -> bool:
    combined = _combined_candidate_text(candidate)
    issue_text = f"{issue.title or ''} {issue.topic or ''} {issue.summary or ''}".lower()
    for token in token_set(issue_text):
        if token in combined:
            return True
    return False


def score_image_candidate(candidate: models.ImageCandidate, *, issue: models.Issue) -> tuple[float, str]:
    url = (candidate.url or "").strip()
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return 0.0, "invalid_url"

    lowered_url = url.lower()
    if any(term in lowered_url for term in LOW_QUALITY_URL_TERMS):
        return 0.0, "low_quality_url"

    width = int(candidate.width or 0)
    height = int(candidate.height or 0)
    if width and height and (width < 300 or height < 160):
        return 0.0, "too_small"

    score = 0.2
    reasons = ["valid_url"]

    if _is_preferred_source(candidate):
        score += 0.4
        reasons.append("preferred_source")

    if width and height:
        if width >= 1200 and height >= 630:
            score += 0.25
            reasons.append("large_dimensions")
        elif width >= 600 and height >= 315:
            score += 0.18
            reasons.append("adequate_dimensions")
        else:
            score += 0.1
            reasons.append("minimum_dimensions")
    else:
        score += 0.05
        reasons.append("unknown_dimensions")

    if _matches_issue(candidate, issue=issue):
        score += 0.1
        reasons.append("issue_match")

    return min(score, 1.0), ",".join(reasons)


def _clear_representative_image(issue: models.Issue) -> None:
    issue.representative_image_url = ""
    issue.representative_image_source = ""
    issue.representative_image_source_url = ""
    issue.representative_image_confidence = 0.0
    issue.representative_image_updated_at = models.now_utc()
    issue.updated_at = models.now_utc()


def select_representative_image(db: Session, *, issue_id: str) -> models.ImageCandidate | None:
    issue = db.get(models.Issue, issue_id)
    if not issue:
        return None

    candidates = db.scalars(
        select(models.ImageCandidate)
        .where(models.ImageCandidate.issue_id == issue_id)
        .order_by(models.ImageCandidate.created_at.asc()),
    ).all()
    best: models.ImageCandidate | None = None
    best_score = 0.0

    for candidate in candidates:
        score, reason = score_image_candidate(candidate, issue=issue)
        candidate.confidence = score
        candidate.reason = reason
        candidate.updated_at = models.now_utc()
        if score == 0 and reason in {"low_quality_url", "too_small", "invalid_url"}:
            candidate.status = "rejected"
        else:
            candidate.status = "candidate"
        if score > best_score:
            best = candidate
            best_score = score

    if not best or best_score < 0.35:
        _clear_representative_image(issue)
        db.flush()
        return None

    best.status = "selected"
    issue.representative_image_url = best.url
    issue.representative_image_source = best.publisher
    issue.representative_image_source_url = best.source_url
    issue.representative_image_confidence = best_score
    issue.representative_image_updated_at = models.now_utc()
    issue.updated_at = models.now_utc()
    db.flush()
    return best
