from __future__ import annotations

import re


BLOCKED_PUBLIC_LABELS = {
    "보수 의견",
    "진보 의견",
    "보수",
    "진보",
    "좌파",
    "우파",
    "빨갱이",
    "부정선거충",
}

REPLACEMENTS = {
    "쁘락지": "조직적 방해 의혹",
    "조작 세력": "조직적 개입 의혹",
    "선동꾼": "강한 주장 참여자",
    "빨갱이": "정치적 낙인 표현",
    "부정선거충": "정치적 낙인 표현",
}


def sanitize_public_label(value: str) -> str:
    text = value.strip()
    if text in BLOCKED_PUBLIC_LABELS:
        return "주장 중심 관점"
    for unsafe, replacement in REPLACEMENTS.items():
        text = re.sub(re.escape(unsafe), replacement, text, flags=re.IGNORECASE)
    text = re.sub(r"\b(보수|진보)\s*(의견|진영|측)\b", "해당 관점", text)
    return text.strip() or "주장 중심 관점"


def sanitize_claim_text(value: str) -> tuple[str, str]:
    sanitized = value
    reasons: list[str] = []
    for unsafe, replacement in REPLACEMENTS.items():
        if unsafe in sanitized:
            sanitized = sanitized.replace(unsafe, replacement)
            reasons.append(f"낙인 표현 정제: {unsafe}")
    return sanitized.strip(), "; ".join(reasons)


def has_high_risk_label(value: str) -> bool:
    return any(item in value for item in REPLACEMENTS) or any(item in value for item in BLOCKED_PUBLIC_LABELS)
