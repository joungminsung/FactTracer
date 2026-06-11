from __future__ import annotations

from sqlalchemy.orm import Session

from app import models
from app.services.ai.deepseek_client import DeepSeekAnalysisService
from app.services.evidence.retriever import retrieve_evidence_for_claim
from app.services.verification.rules import verdict_from_evidence
from app.utils import new_id


ALLOWED_VERDICTS = {
    "사실",
    "대체로 사실",
    "일부 사실",
    "초기 기준",
    "업데이트 필요",
    "맥락 누락",
    "과장",
    "오해 소지",
    "사실 아님",
    "근거 부족",
    "법적 판단 필요",
    "단정 불가",
    "검증 불가",
}


def _evidence_payload(evidences: list[models.Evidence]) -> list[dict]:
    return [
        {
            "id": evidence.id,
            "title": evidence.title,
            "url": evidence.url,
            "source_domain": evidence.source_domain,
            "source_type": evidence.source_type,
            "credibility_score": evidence.credibility_score,
            "relevance_score": evidence.relevance_score,
            "evidence_text": evidence.evidence_text[:1200],
        }
        for evidence in evidences
    ]


def _ai_verdict(db: Session, *, claim: models.Claim, evidences: list[models.Evidence]) -> tuple[str, float, str] | None:
    result = DeepSeekAnalysisService(db).verify_claim_against_evidence(
        claim_text=claim.sanitized_text or claim.claim_text,
        claim_type=claim.claim_type,
        entities_json=claim.entities_json or {},
        evidences=_evidence_payload(evidences),
    )
    if not isinstance(result, dict):
        return None
    verdict = str(result.get("verdict") or "").strip()
    if verdict not in ALLOWED_VERDICTS:
        return None
    try:
        confidence = float(result.get("confidence") or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(confidence, 1.0))
    reason = str(result.get("reason") or result.get("missing_context") or "AI 판정 결과입니다.").strip()
    claim.ai_notes = {**(claim.ai_notes or {}), "verification": result}
    return verdict, confidence, reason


def verify_claim(db: Session, *, claim: models.Claim) -> models.Claim:
    previous = claim.verdict
    evidences = retrieve_evidence_for_claim(db, claim=claim)
    verdict, confidence, reason = _ai_verdict(db, claim=claim, evidences=evidences) or verdict_from_evidence(
        claim,
        evidences,
    )
    claim.verdict = verdict
    claim.confidence = confidence
    claim.status = (
        "verified"
        if verdict not in {"근거 부족", "검증 불가", "단정 불가"}
        else "needs_evidence"
    )
    claim.updated_at = models.now_utc()
    if previous != verdict:
        db.add(
            models.VerdictHistory(
                claim_id=claim.id,
                confidence=confidence,
                current_verdict=verdict,
                id=new_id("verdict"),
                previous_verdict=previous,
                reason=reason,
            ),
        )
    db.flush()
    return claim
