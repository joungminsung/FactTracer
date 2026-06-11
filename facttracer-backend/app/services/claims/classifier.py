from __future__ import annotations

from app.services.claims.entity_extractor import extract_entities
from app.services.safety.label_filter import has_high_risk_label


def classify_claim(text: str) -> str:
    entities = extract_entities(text)
    if has_high_risk_label(text):
        return "낙인 표현"
    if entities["numbers"]:
        return "수치 주장"
    if any(keyword in text for keyword in ("법", "위법", "소송", "판결", "재판", "헌법")):
        return "법적 주장"
    if any(keyword in text for keyword in ("책임", "문책", "사과", "관리 부실", "감사")):
        return "책임 주장"
    if any(keyword in text for keyword in ("요구", "해야", "필요", "촉구", "개선")):
        return "요구 사항"
    if any(keyword in text for keyword in ("의혹", "고의", "조작", "개입", "침투")):
        return "의혹 주장"
    if any(keyword in text for keyword in ("때문", "원인", "실패", "부실")):
        return "원인 해석"
    if any(keyword in text for keyword in ("전략", "메시지", "프레임", "구호")):
        return "운동 전략"
    return "사실 주장"
