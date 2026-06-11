from __future__ import annotations

import re

CANONICAL_TOPICS = ("정치", "사회", "경제", "국제", "재난", "보건", "IT")
TOPIC_FILTERS = ("전체", *CANONICAL_TOPICS)

_TOPIC_ALIASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("국제", ("국제", "국게", "외교", "해외", "분쟁", "제재", "협상", "안보")),
    ("경제", ("경제", "물가", "금리", "환율", "금융", "부동산", "고용", "기업", "세금", "지원금")),
    ("재난", ("재난", "사고", "화재", "지진", "폭우", "태풍", "안전", "피해")),
    ("보건", ("보건", "의료", "질병", "감염", "백신", "식품", "의약품", "병원")),
    ("IT", ("it", "ai", "과학", "기술", "테크", "인공지능", "반도체", "플랫폼", "통신", "보안", "우주")),
    ("정치", ("정치", "선거", "국회", "정당", "대통령", "정부", "법안", "정책")),
    ("사회", ("사회", "공공", "교육", "복지", "수사", "조사", "범죄", "노동", "지역")),
)


def _compact_topic(value: str) -> str:
    return re.sub(r"[\s/_·|,.-]+", "", value.strip().lower())


def normalize_topic(value: object, *, default: str = "사회") -> str:
    raw = str(value or "").strip()
    if not raw:
        return default if default in CANONICAL_TOPICS else "사회"

    compact = _compact_topic(raw)
    for topic in CANONICAL_TOPICS:
        if compact == _compact_topic(topic):
            return topic

    for topic, aliases in _TOPIC_ALIASES:
        if any(_compact_topic(alias) in compact for alias in aliases):
            return topic

    return default if default in CANONICAL_TOPICS else "사회"


def normalize_topic_filter(value: object | None) -> str | None:
    raw = str(value or "").strip()
    if not raw or raw == "전체":
        return None
    return normalize_topic(raw)


def public_topic_filters(values: list[str]) -> list[str]:
    normalized = {normalize_topic(value) for value in values if str(value or "").strip()}
    ordered = [topic for topic in CANONICAL_TOPICS if topic in normalized]
    return ["전체", *(ordered or CANONICAL_TOPICS)]
