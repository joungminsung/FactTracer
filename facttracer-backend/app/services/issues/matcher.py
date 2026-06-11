from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.services.articles.normalizer import jaccard_similarity, token_set
from app.services.topics import normalize_topic


INCIDENT_STOPWORDS = {
    "관련",
    "기사",
    "뉴스",
    "단독",
    "속보",
    "종합",
    "보도",
    "후속",
    "추가",
    "논란",
    "사태",
    "사안",
    "확인",
    "발표",
    "기자",
    "검증",
    "단위",
    "주장",
    "중",
}

INCIDENT_SUFFIXES = (
    "입니다",
    "였습니다",
    "합니다",
    "했습니다",
    "이었다",
    "였다",
    "한다",
    "했다",
    "에서",
    "으로",
    "부터",
    "까지",
    "에게",
    "보다",
    "처럼",
    "은",
    "는",
    "이",
    "가",
    "을",
    "를",
    "의",
    "와",
    "과",
    "도",
    "만",
    "에",
    "로",
)

INCIDENT_ALIASES = {
    "중앙선거관리위원회": "선관위",
    "중앙선관위": "선관위",
    "선거관리위원회": "선관위",
    "투표지": "투표용지",
    "투표용지": "투표용지",
    "사전투표": "사전투표",
    "본투표": "투표",
    "개표": "개표",
    "투표소": "투표소",
}

INCIDENT_PHRASES = (
    "투표용지 부족",
    "투표소 투표용지",
    "사전투표",
    "개표 논란",
    "선거 관리",
    "공식자료",
    "설명자료",
    "감사 착수",
    "고발",
)


def _normalize_incident_token(token: str) -> str:
    for suffix in INCIDENT_SUFFIXES:
        if token.endswith(suffix) and len(token) - len(suffix) >= 2:
            token = token[: -len(suffix)]
            break
    return INCIDENT_ALIASES.get(token, token)


def _incident_tokens(value: str) -> set[str]:
    tokens: set[str] = set()
    text = value.lower()
    compact_text = text.replace(" ", "")
    for phrase in INCIDENT_PHRASES:
        if phrase in text or phrase.replace(" ", "") in compact_text:
            tokens.add(phrase)
    for phrase, alias in INCIDENT_ALIASES.items():
        if phrase in text or phrase.replace(" ", "") in compact_text:
            tokens.add(alias)
    for raw_token in token_set(value):
        token = _normalize_incident_token(raw_token)
        if token in INCIDENT_STOPWORDS or any(char.isdigit() for char in token):
            continue
        tokens.add(token)
    return tokens


def incident_similarity(left: str, right: str) -> float:
    left_tokens = _incident_tokens(left)
    right_tokens = _incident_tokens(right)
    if not left_tokens or not right_tokens:
        return jaccard_similarity(left, right)

    shared = left_tokens & right_tokens
    if not shared:
        return 0.0

    jaccard = len(shared) / len(left_tokens | right_tokens)
    containment = len(shared) / min(len(left_tokens), len(right_tokens))
    score = max(jaccard, containment * 0.86)
    if len(shared) >= 3:
        score = max(score, containment * 0.96)
    return max(0.0, min(score, 1.0))


def issue_similarity(text: str, issue: models.Issue, *, topic: str | None = None) -> float:
    context = _issue_context_text(issue)
    score = max(
        jaccard_similarity(text, issue.title),
        jaccard_similarity(text, issue.summary),
        incident_similarity(text, context),
    )
    if topic and normalize_topic(topic) == normalize_topic(issue.topic):
        score = min(score + 0.03, 1.0)
    return score


def _issue_context_text(issue: models.Issue) -> str:
    parts = [issue.title, issue.summary]
    for row in issue.claim_clusters or []:
        if isinstance(row, dict):
            parts.extend(
                [
                    str(row.get("title") or ""),
                    str(row.get("question") or ""),
                    " ".join(str(claim) for claim in row.get("claims") or []),
                ],
            )
    for row in issue.articles or []:
        if isinstance(row, dict):
            parts.extend([str(row.get("title") or ""), str(row.get("note") or "")])
    for row in issue.source_documents or []:
        if isinstance(row, dict):
            parts.extend([str(row.get("title") or ""), str(row.get("publisher") or "")])
    return " ".join(part for part in parts if part)


def find_similar_issue(
    db: Session,
    *,
    summary: str = "",
    threshold: float = 0.58,
    title: str,
    topic: str | None = None,
) -> tuple[models.Issue | None, float]:
    text = f"{title} {summary}".strip()
    issues = db.scalars(
        select(models.Issue).where(models.Issue.status.notin_(["숨김", "병합됨"])),
    ).all()
    best: tuple[models.Issue | None, float] = (None, 0.0)
    for issue in issues:
        score = issue_similarity(text, issue, topic=topic)
        if score > best[1]:
            best = (issue, score)
    return best if best[1] >= threshold else (None, best[1])


def match_article_to_issue(db: Session, *, article: models.Article) -> tuple[models.Issue | None, float]:
    issues = db.scalars(
        select(models.Issue).where(models.Issue.status.notin_(["숨김", "병합됨"])),
    ).all()
    text = f"{article.title} {article.summary} {article.body_text[:1000]}"
    best: tuple[models.Issue | None, float] = (None, 0.0)
    for issue in issues:
        score = issue_similarity(text, issue)
        if score > best[1]:
            best = (issue, score)
    return best if best[1] >= 0.48 else (None, best[1])
