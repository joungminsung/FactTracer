from __future__ import annotations

import re

from app import models
from app.services.articles.normalizer import token_set
from app.services.issues.article_quality import is_generic_article_page
from app.services.topics import normalize_topic


TOPIC_KEYWORDS: dict[str, tuple[tuple[str, int], ...]] = {
    "재난": (
        ("재난", 5),
        ("화재", 6),
        ("폭발", 6),
        ("사고", 4),
        ("탈선", 5),
        ("유류누출", 5),
        ("인명피해", 5),
        ("중대재해", 5),
        ("사상", 4),
        ("피해", 3),
        ("안전사고", 4),
    ),
    "보건": (
        ("보건", 5),
        ("의료", 5),
        ("질병", 5),
        ("질병관리청", 5),
        ("감염", 5),
        ("백신", 5),
        ("식품", 4),
        ("의약품", 4),
        ("병원", 4),
        ("환자", 4),
        ("치료제", 4),
        ("에볼라", 5),
        ("rsv", 5),
        ("호흡기", 4),
    ),
    "경제": (
        ("경제", 5),
        ("한은", 6),
        ("한국은행", 6),
        ("이창용", 5),
        ("물가", 5),
        ("금리", 5),
        ("환율", 5),
        ("금융", 5),
        ("부동산", 5),
        ("고유가", 5),
        ("석유", 4),
        ("고용", 4),
        ("기업", 4),
        ("세금", 4),
        ("지원금", 3),
        ("통계", 3),
    ),
    "정치": (
        ("정치", 5),
        ("선거", 6),
        ("선관위", 6),
        ("국회", 5),
        ("정당", 5),
        ("대통령", 5),
        ("민주당", 5),
        ("국민의힘", 5),
        ("방첩사", 6),
        ("국방방첩본부", 6),
        ("국방", 4),
        ("법안", 4),
        ("의원", 4),
        ("대변인", 4),
        ("임명", 3),
        ("사퇴", 3),
        ("정부", 2),
        ("정책", 1),
    ),
    "국제": (
        ("국제", 3),
        ("외교", 5),
        ("해외", 4),
        ("분쟁", 5),
        ("전쟁", 5),
        ("제재", 5),
        ("협상", 5),
        ("안보", 4),
        ("이란", 5),
        ("미국", 4),
        ("중일", 5),
        ("센카쿠", 6),
        ("세계", 3),
        ("트럼프", 3),
    ),
    "IT": (
        ("IT", 5),
        ("AI", 4),
        ("ai", 4),
        ("인공지능", 5),
        ("반도체", 5),
        ("플랫폼", 4),
        ("통신", 4),
        ("보안", 4),
        ("과학", 3),
        ("기술", 3),
        ("마이데이터", 3),
    ),
    "사회": (
        ("사회", 4),
        ("양평", 4),
        ("공공", 3),
        ("교육", 4),
        ("교사", 5),
        ("특수교사", 6),
        ("복지", 4),
        ("수사", 4),
        ("조사", 3),
        ("범죄", 4),
        ("노동", 4),
        ("지역", 2),
    ),
}

TOPIC_TIEBREAK = ("재난", "보건", "경제", "정치", "국제", "IT", "사회")


def _compact_text(text: str) -> str:
    return re.sub(r"[^0-9a-zA-Z가-힣]+", "", text).lower()


def infer_topic(text: str) -> str:
    compact = _compact_text(str(text or ""))
    scores: dict[str, int] = {}
    for topic, keywords in TOPIC_KEYWORDS.items():
        score = 0
        for keyword, weight in keywords:
            hits = compact.count(_compact_text(keyword))
            if hits:
                score += min(hits, 3) * weight
        if score:
            scores[topic] = score
    if scores:
        best = max(scores.values())
        candidates = {topic for topic, score in scores.items() if score == best}
        for topic in TOPIC_TIEBREAK:
            if topic in candidates:
                return topic
    return normalize_topic(text)


def score_issue_candidate(articles: list[models.Article]) -> dict:
    usable_articles = [
        article
        for article in articles
        if not is_generic_article_page(
            publisher=article.publisher,
            title=article.title,
            url=article.url,
        )
    ]
    if not usable_articles:
        return {"score": 0, "topic": "사회", "signals": {}}
    text = " ".join(f"{article.title} {article.body_text[:500]}" for article in usable_articles)
    publishers = {article.publisher for article in usable_articles if article.publisher}
    numbers = re.findall(r"\d+(?:,\d{3})*(?:\.\d+)?", text)
    official_mentions = len(re.findall(r"위원회|정부|부|청|공공|공식|발표", text))
    topic = infer_topic(text)
    high_impact = topic in {"정치", "재난", "보건", "경제"}
    score = min(
        100,
        18
        + min(len(usable_articles) * 8, 28)
        + min(len(publishers) * 6, 18)
        + min(len(numbers) * 4, 16)
        + min(official_mentions * 5, 15)
        + (12 if high_impact else 0),
    )
    return {
        "score": int(score),
        "topic": topic,
        "signals": {
            "article_count": len(articles),
            "usable_article_count": len(usable_articles),
            "publisher_count": len(publishers),
            "number_count": len(numbers),
            "official_mentions": official_mentions,
            "keywords": sorted(token_set(text))[:20],
        },
    }
