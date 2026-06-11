from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app import models
from app.services.ai.deepseek_client import DeepSeekAnalysisService
from app.services.issues.quality import build_issue_quality_report


SUPPORTED_VERDICTS = {"사실", "대체로 사실", "일부 사실"}
SECTION_KEYS = {
    "article_comparison",
    "claim_verification",
    "issue_map",
    "number_changes",
    "perspectives",
    "source_gaps",
    "timeline",
}


def _count_from_payload(payload: dict[str, Any], quality: dict[str, Any]) -> int:
    direct_count = payload.get("article_count")
    if isinstance(direct_count, int):
        return direct_count

    signals = quality.get("signals") if isinstance(quality.get("signals"), dict) else {}
    for value in (quality.get("articleCount"), signals.get("articleCount")):
        if isinstance(value, int):
            return value
    return len(payload.get("articles") or [])


def _has_evidence(claim: dict[str, Any]) -> bool:
    evidences = claim.get("evidences")
    if isinstance(evidences, list) and len(evidences) > 0:
        return True
    return str(claim.get("evidence") or "").strip() not in {"", "근거 확인 중"}


def _supported_claim_refs(payload: dict[str, Any]) -> tuple[set[str], set[str]]:
    supported_ids: set[str] = set()
    supported_texts: set[str] = set()
    for claim in payload.get("claims") or []:
        if not isinstance(claim, dict):
            continue
        claim_id = str(claim.get("id") or "").strip()
        text = str(claim.get("text") or "").strip()
        if (
            claim.get("status") == "verified"
            and claim.get("verdict") in SUPPORTED_VERDICTS
            and _has_evidence(claim)
        ):
            if claim_id:
                supported_ids.add(claim_id)
            if text:
                supported_texts.add(text)
    return supported_ids, supported_texts


def _ground_confirmed_facts(payload: dict[str, Any]) -> list[dict[str, Any]]:
    supported_ids, supported_texts = _supported_claim_refs(payload)
    grounded: list[dict[str, Any]] = []
    for fact in payload.get("confirmed_facts") or []:
        if not isinstance(fact, dict):
            continue
        claim_id = str(fact.get("claimId") or fact.get("claim_id") or "").strip()
        text = str(fact.get("text") or "").strip()
        if claim_id and claim_id in supported_ids:
            grounded.append(fact)
        elif text and text in supported_texts:
            grounded.append(fact)
    return grounded


def _computed_summary(issue: models.Issue, payload: dict[str, Any], quality: dict[str, Any]) -> str:
    existing = str(payload.get("computed_summary") or "").strip()
    if issue.summary or existing:
        return existing

    article_count = _count_from_payload(payload, quality)
    claim_count = int(payload.get("verified_count") or 0) + int(payload.get("needs_review_count") or 0)
    if claim_count:
        return f"{article_count}개 기사에서 {claim_count}개 주장을 추출해 검증 중입니다."
    return f"{article_count}개 기사 기준으로 사실관계 신호를 수집 중입니다."


def _list_of_text(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _section_map(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    sections: dict[str, str] = {}
    for key in SECTION_KEYS:
        text = str(value.get(key) or "").strip()
        if text:
            sections[key] = text[:1200]
    return sections


def _merge_ai_detail(db: Session, *, issue: models.Issue, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        detail = DeepSeekAnalysisService(db).synthesize_issue_detail(issue_title=issue.title, records=payload)
    except Exception:
        return payload
    if not isinstance(detail, dict):
        return payload

    merged = dict(payload)
    summary = str(detail.get("summary") or "").strip()
    if summary and not issue.summary:
        merged["computed_summary"] = summary[:1200]

    confirmed_facts = detail.get("confirmed_facts")
    if isinstance(confirmed_facts, list):
        merged["confirmed_facts"] = [fact for fact in confirmed_facts if isinstance(fact, dict)]

    sections = _section_map(detail.get("section_map") or detail.get("sectionMap"))
    missing_context = _list_of_text(detail.get("missing_context") or detail.get("missingContext"))
    if sections or missing_context or summary:
        merged["ai_synthesis"] = {
            "missingContext": missing_context[:20],
            "sectionMap": sections,
            "summary": summary[:1200],
        }
    return merged


def _merge_existing_ai_detail(*, issue: models.Issue, payload: dict[str, Any]) -> dict[str, Any]:
    quality = issue.quality_report_json if isinstance(issue.quality_report_json, dict) else {}
    existing = quality.get("aiSynthesis")
    if not isinstance(existing, dict):
        return payload
    return payload | {"ai_synthesis": existing}


def synthesize_issue_cache(
    db: Session,
    *,
    issue: models.Issue,
    payload: dict[str, Any],
    use_ai: bool = True,
) -> dict[str, Any]:
    enriched = dict(payload)
    enriched = _merge_ai_detail(db, issue=issue, payload=enriched) if use_ai else _merge_existing_ai_detail(issue=issue, payload=enriched)
    quality = build_issue_quality_report(db, issue=issue)
    enriched["quality"] = quality
    enriched["computed_summary"] = _computed_summary(issue, enriched, quality)
    enriched["confirmed_facts"] = _ground_confirmed_facts(enriched)
    return enriched
