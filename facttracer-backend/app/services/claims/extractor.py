from __future__ import annotations

import re

from app.services.articles.normalizer import normalize_whitespace
from app.services.claims.classifier import classify_claim
from app.services.claims.entity_extractor import extract_entities
from app.services.safety.toxicity_filter import moderate_claim_text


VERIFY_HINTS = (
    "했다",
    "한다",
    "발생",
    "확인",
    "발표",
    "밝혔다",
    "설명",
    "전했다",
    "주장",
    "촉구",
    "접수",
    "신고",
    "확대",
    "늘었다",
    "줄었다",
    "부족",
    "증가",
    "감소",
    "요구",
    "필요",
    "의혹",
    "책임",
    "위법",
)


def split_sentences(text: str) -> list[str]:
    cleaned = normalize_whitespace(text)
    if not cleaned:
        return []
    pieces = re.split(r"(?<=[.!?。！？])\s+|(?<=[다요])\.\s*|\n+", cleaned)
    return [piece.strip(" .") for piece in pieces if len(piece.strip()) >= 8]


def extract_claim_candidates(text: str, *, limit: int = 12) -> list[dict]:
    claims: list[dict] = []
    for sentence in split_sentences(text):
        if not any(hint in sentence for hint in VERIFY_HINTS) and not re.search(r"\d", sentence):
            continue
        moderation = moderate_claim_text(sentence)
        claims.append(
            {
                "claim_text": sentence,
                "claim_type": classify_claim(sentence),
                "entities_json": extract_entities(sentence),
                "moderation": moderation,
            },
        )
        if len(claims) >= limit:
            break
    return claims
