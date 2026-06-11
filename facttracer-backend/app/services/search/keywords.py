from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.services.ai.deepseek_client import DeepSeekAnalysisService
from app.services.articles.normalizer import normalize_whitespace
from app.services.topics import normalize_topic
from app.utils import new_id


def _clean_query(query: str) -> str:
    return normalize_whitespace(query).strip(" \"'")


FOLLOWUP_TERMS = (
    "후속",
    "해명",
    "설명자료",
    "공식자료",
    "발표",
    "조사",
    "감사",
    "고발",
    "수사",
    "논란",
    "의혹",
)


def is_search_query_usable(query: object) -> bool:
    cleaned = _clean_query(str(query or ""))
    compact = re.sub(r"[\s\"'·,._:;|/\\-]+", "", cleaned)
    if len(compact) < 2:
        return False
    if not re.search(r"[0-9A-Za-z가-힣]", compact):
        return False
    return True


def _append_unique(values: list[str], *candidates: str) -> None:
    seen = {_clean_query(value) for value in values}
    for candidate in candidates:
        value = _clean_query(candidate)
        if is_search_query_usable(value) and value not in seen:
            values.append(value)
            seen.add(value)


def _head_terms(tokens: list[str]) -> list[str]:
    anchors = [token for token in tokens if len(token) >= 2 and not re.fullmatch(r"\d+", token)]
    if not anchors:
        return []
    if len(anchors) == 1:
        return anchors
    return [
        " ".join(anchors[:2]),
        anchors[0],
        anchors[-1],
    ]


def fallback_keyword_variants(query: str) -> list[str]:
    query = _clean_query(query)
    tokens = [token for token in re.split(r"\s+", query) if token]
    variants = [query]
    if len(tokens) >= 2:
        _append_unique(
            variants,
            " ".join(tokens[:3]),
            " ".join(tokens[-3:]),
            f"{tokens[0]} {tokens[-1]}",
        )
    if "사태" in query:
        _append_unique(variants, query.replace("사태", "").strip())

    for anchor in _head_terms(tokens)[:2]:
        for followup in FOLLOWUP_TERMS[:5]:
            _append_unique(variants, f"{anchor} {followup}")
    for followup in FOLLOWUP_TERMS[:6]:
        _append_unique(variants, f"{query} {followup}")

    seen: set[str] = set()
    cleaned: list[str] = []
    for variant in variants:
        value = _clean_query(variant)
        if not is_search_query_usable(value) or value in seen:
            continue
        seen.add(value)
        cleaned.append(value[:300])
    return cleaned[:36]


def generate_search_keywords(
    db: Session,
    *,
    query: str,
    topic: str = "사회",
    limit: int = 10,
) -> list[dict]:
    topic = normalize_topic(topic)
    rows = DeepSeekAnalysisService(db).generate_search_keywords(
        query=query,
        topic=topic,
        limit=limit,
    )
    if rows:
        return rows[:limit]
    return [
        {
            "query": keyword,
            "topic": topic,
            "priority": "high" if index == 0 else "normal",
            "reason": "fallback keyword variant",
        }
        for index, keyword in enumerate(fallback_keyword_variants(query)[:limit])
    ]


def upsert_search_keyword(
    db: Session,
    *,
    interval_minutes: int = 30,
    issue_id: str | None = None,
    priority: str = "normal",
    query: str,
    seed_query: str = "",
    source: str = "manual",
    status: str = "active",
    topic: str = "사회",
    metadata: dict | None = None,
) -> models.SearchKeyword:
    cleaned = _clean_query(query)
    topic = normalize_topic(topic)
    existing = db.scalar(select(models.SearchKeyword).where(models.SearchKeyword.query == cleaned))
    if existing:
        existing.priority = priority or existing.priority
        existing.search_interval_minutes = interval_minutes or existing.search_interval_minutes
        existing.seed_query = seed_query or existing.seed_query
        existing.source = source or existing.source
        existing.status = status or existing.status
        existing.topic = topic or existing.topic
        if issue_id:
            existing.issue_id = issue_id
        if metadata:
            existing.metadata_json = {**(existing.metadata_json or {}), **metadata}
        existing.updated_at = models.now_utc()
        db.flush()
        return existing

    keyword = models.SearchKeyword(
        id=new_id("keyword"),
        issue_id=issue_id,
        metadata_json=metadata or {},
        priority=priority,
        query=cleaned,
        search_interval_minutes=interval_minutes,
        seed_query=seed_query or cleaned,
        source=source,
        status=status,
        topic=topic,
    )
    db.add(keyword)
    db.flush()
    return keyword


def seed_search_keywords(
    db: Session,
    *,
    generate_variants: bool = True,
    interval_minutes: int = 30,
    priority: str = "high",
    query: str,
    source: str = "manual",
    topic: str = "사회",
) -> list[models.SearchKeyword]:
    topic = normalize_topic(topic)
    keyword_rows = (
        generate_search_keywords(db, query=query, topic=topic)
        if generate_variants
        else [{"query": query, "topic": topic, "priority": priority}]
    )
    rows: list[models.SearchKeyword] = []
    for index, row in enumerate(keyword_rows):
        if not isinstance(row, dict):
            continue
        keyword_query = _clean_query(str(row.get("query") or ""))
        if not is_search_query_usable(keyword_query):
            continue
        rows.append(
            upsert_search_keyword(
                db,
                interval_minutes=interval_minutes,
                priority=str(row.get("priority") or (priority if index == 0 else "normal")),
                query=keyword_query,
                seed_query=query,
                source=source,
                topic=normalize_topic(row.get("topic"), default=topic),
                metadata={"reason": row.get("reason"), "generated": generate_variants},
            ),
        )
    db.flush()
    return rows
