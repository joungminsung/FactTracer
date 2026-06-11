from __future__ import annotations

from app import models
from app.services.evidence.ranker import rank_evidence


def compare_entities(claim: models.Claim, evidences: list[models.Evidence]) -> dict:
    entities = claim.entities_json or {}
    evidence_text = " ".join(
        f"{evidence.title} {evidence.evidence_text} {evidence.source_domain}" for evidence in evidences
    )
    checks = {}
    for key in ("numbers", "dates", "organizations", "places"):
        values = entities.get(key) or []
        if not values:
            checks[key] = {"required": [], "matched": [], "missing": []}
            continue
        matched = [value for value in values if value in evidence_text]
        checks[key] = {
            "required": values,
            "matched": matched,
            "missing": [value for value in values if value not in matched],
        }
    return checks


def verdict_from_evidence(claim: models.Claim, evidences: list[models.Evidence]) -> tuple[str, float, str]:
    if claim.claim_type == "낙인 표현":
        return "근거 부족", 0.25, "낙인 표현은 공개 확산을 제한하고 근거 제시 여부를 별도 검토합니다."
    if claim.claim_type == "법적 주장":
        return "법적 판단 필요", 0.42, "법적 결론은 자동 단정하지 않고 전문 검토 대상으로 분리합니다."
    if not evidences:
        return "근거 부족", 0.18, "현재 연결 가능한 근거 자료가 없습니다."

    best = max(rank_evidence(evidence) for evidence in evidences)
    official = any(evidence.source_type in {"official", "public"} for evidence in evidences)
    entity_checks = compare_entities(claim, evidences)
    missing_critical = [
        key
        for key, result in entity_checks.items()
        if result["required"] and result["missing"] and key in {"numbers", "dates", "organizations"}
    ]
    if official and missing_critical:
        return "맥락 누락", max(best - 0.18, 0.35), f"근거 후보가 있으나 {', '.join(missing_critical)} 값이 직접 일치하지 않습니다."
    if official and best >= 0.72:
        return "대체로 사실", best, "공식 또는 공공 출처 근거 후보와 연결되었습니다."
    if best >= 0.6:
        return "초기 기준", best, "보도 또는 공개 출처 근거가 있으나 후속 확인이 필요합니다."
    return "업데이트 필요", best, "근거 관련도 또는 신뢰도가 충분하지 않아 추가 확인이 필요합니다."
