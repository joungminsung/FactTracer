from __future__ import annotations

from app.services.safety.label_filter import has_high_risk_label, sanitize_claim_text


def moderate_claim_text(value: str) -> dict:
    sanitized, reason = sanitize_claim_text(value)
    high_risk = has_high_risk_label(value)
    return {
        "moderation_status": "needs_review" if high_risk else "approved",
        "moderation_reason": reason or ("공개 가능" if not high_risk else "검토 필요"),
        "sanitized_text": sanitized,
    }
