from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.services.ai.deepseek_client import DeepSeekAnalysisService
from app.services.articles.normalizer import jaccard_similarity, normalize_whitespace
from app.services.claims.classifier import classify_claim
from app.services.claims.clusterer import assign_cluster, find_similar_cluster
from app.services.claims.entity_extractor import extract_entities
from app.services.claims.extractor import extract_claim_candidates
from app.services.safety.toxicity_filter import moderate_claim_text
from app.services.vector.store import embed_claim_if_possible
from app.utils import new_id


def _dict_or_empty(value: object) -> dict:
    return value if isinstance(value, dict) else {}


def _optional_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def _claim_key(value: str) -> str:
    return normalize_whitespace(value).rstrip(" .。!！?？").lower()


def _claim_number_tokens(candidate: dict, text: str) -> set[str]:
    entities = _dict_or_empty(candidate.get("entities_json") or candidate.get("entities"))
    values = [str(value) for value in entities.get("numbers", []) if str(value).strip()]
    if not values:
        values = extract_entities(text).get("numbers", [])
    return set(re.findall(r"\d+(?:,\d{3})*(?:\.\d+)?", " ".join(values) or text))


def _is_duplicate_candidate(
    *,
    candidate: dict,
    seen: list[tuple[str, set[str]]],
    text: str,
) -> bool:
    candidate_key = _claim_key(text)
    candidate_numbers = _claim_number_tokens(candidate, text)
    for existing_text, existing_numbers in seen:
        if candidate_key == _claim_key(existing_text):
            return True
        similarity = jaccard_similarity(text, existing_text)
        if similarity >= 0.68:
            return True
        if candidate_numbers and candidate_numbers & existing_numbers and similarity >= 0.45:
            return True
    return False


def _merge_claim_candidates(
    ai_candidates: list[dict],
    rule_candidates: list[dict],
    *,
    limit: int,
) -> list[dict]:
    merged: list[dict] = []
    seen: list[tuple[str, set[str]]] = []
    for source, rows in (("deepseek", ai_candidates), ("rule_based", rule_candidates)):
        for row in rows:
            if not isinstance(row, dict):
                continue
            claim_text = _optional_text(row.get("claim_text"))
            if not claim_text:
                continue
            if _is_duplicate_candidate(candidate=row, seen=seen, text=claim_text):
                continue
            seen.append((claim_text, _claim_number_tokens(row, claim_text)))
            merged.append({**row, "claim_text": claim_text, "_source": source})
            if len(merged) >= limit:
                return merged
    return merged


def create_claim_from_text(
    db: Session,
    *,
    ai_notes: dict | None = None,
    article_id: str | None = None,
    canonical_question: str | None = None,
    claim_type: str | None = None,
    entities_json: dict | None = None,
    issue_id: str,
    source_kind: str,
    submitted_claim_id: str | None = None,
    text: str,
) -> models.Claim:
    existing = db.scalar(
        select(models.Claim).where(
            models.Claim.issue_id == issue_id,
            models.Claim.claim_text == text,
            models.Claim.article_id == article_id,
        ),
    )
    if existing:
        existing.spread_count += 1
        existing.updated_at = models.now_utc()
        db.flush()
        return existing

    moderation = moderate_claim_text(text)
    resolved_type = claim_type or classify_claim(text)
    resolved_entities = entities_json or extract_entities(text)
    claim = models.Claim(
        article_id=article_id,
        claim_text=text,
        ai_notes=ai_notes or {},
        claim_type=resolved_type,
        entities_json=resolved_entities,
        id=new_id("claim"),
        issue_id=issue_id,
        sanitized_text=moderation["sanitized_text"],
        source_kind=source_kind,
        status="needs_evidence" if moderation["moderation_status"] == "approved" else "needs_review",
        submitted_claim_id=submitted_claim_id,
    )
    embed_claim_if_possible(db, claim)
    db.add(claim)
    db.flush()
    cluster = assign_cluster(db, claim=claim)
    if canonical_question and cluster.canonical_question.startswith(claim.claim_type):
        cluster.canonical_question = canonical_question[:500]
        cluster.updated_at = models.now_utc()
    return claim


def extract_claims_for_article(db: Session, *, article: models.Article) -> list[models.Claim]:
    if not article.issue_id:
        return []
    text = article.body_text or article.summary or article.title
    limit = 18
    ai_candidates = DeepSeekAnalysisService(db).extract_claims_from_article(
        body_text=text,
        limit=limit,
        summary=article.summary,
        title=article.title,
    )
    rule_candidates = extract_claim_candidates(text, limit=limit)
    candidates = _merge_claim_candidates(ai_candidates, rule_candidates, limit=limit)
    claims: list[models.Claim] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        claim_text = _optional_text(candidate.get("claim_text"))
        if not claim_text:
            continue
        entities = _dict_or_empty(candidate.get("entities_json") or candidate.get("entities"))
        source = _optional_text(candidate.get("_source"))
        raw_candidate = {key: value for key, value in candidate.items() if key != "_source"}
        claims.append(
            create_claim_from_text(
                db,
                ai_notes={"source": source, "raw": raw_candidate} if source else {},
                article_id=article.id,
                canonical_question=_optional_text(candidate.get("canonical_question")),
                claim_type=_optional_text(candidate.get("claim_type")),
                entities_json=entities or None,
                issue_id=article.issue_id,
                source_kind="article",
                text=claim_text,
            ),
        )
    article.updated_at = models.now_utc()
    db.flush()
    return claims


def ingest_submitted_claim(db: Session, *, submitted_claim: models.SubmittedClaim) -> models.Claim:
    moderation = moderate_claim_text(submitted_claim.claim_text)
    submitted_claim.sanitized_text = moderation["sanitized_text"]
    submitted_claim.moderation_reason = moderation["moderation_reason"]
    submitted_claim.moderation_status = moderation["moderation_status"]
    similar, _ = find_similar_cluster(
        db,
        issue_id=submitted_claim.issue_id,
        text=submitted_claim.claim_text,
    )
    if similar:
        submitted_claim.duplicate_cluster_candidate = similar.id
        submitted_claim.cluster_id = similar.id
    claim = create_claim_from_text(
        db,
        ai_notes=submitted_claim.ai_notes or {},
        claim_type=_optional_text((submitted_claim.ai_notes or {}).get("claim_type")) or submitted_claim.claim_type,
        entities_json=_dict_or_empty((submitted_claim.ai_notes or {}).get("entities_json")) or None,
        issue_id=submitted_claim.issue_id,
        source_kind="user",
        submitted_claim_id=submitted_claim.id,
        text=submitted_claim.claim_text,
    )
    submitted_claim.cluster_id = claim.cluster_id
    submitted_claim.status = "needs_review" if submitted_claim.moderation_status == "needs_review" else "classified"
    db.flush()
    return claim
