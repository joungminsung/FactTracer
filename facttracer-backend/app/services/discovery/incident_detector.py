from __future__ import annotations

import re
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.collectors.base import CollectedArticle
from app.services.ai.deepseek_client import DeepSeekAnalysisService
from app.services.articles.normalizer import hash_text, normalize_whitespace, token_set
from app.services.issues.publisher import slugify
from app.services.issues.scoring import infer_topic
from app.services.search.keywords import is_search_query_usable
from app.services.topics import normalize_topic
from app.utils import new_id


STOPWORDS = {
    "뉴스",
    "단독",
    "관련",
    "종합",
    "속보",
    "오늘",
    "이번",
    "지난",
    "대한",
    "기자",
}


def _article_text(article: CollectedArticle) -> str:
    return normalize_whitespace(f"{article.title} {article.summary} {article.body_text[:500]}")


def _cluster_similarity(tokens: set[str], cluster_tokens: set[str]) -> float:
    if not tokens or not cluster_tokens:
        return 0.0
    shared = tokens & cluster_tokens
    jaccard = len(shared) / len(tokens | cluster_tokens)
    if len(shared) >= 2:
        return max(jaccard, 0.31)
    return jaccard


def cluster_collected_articles(
    articles: list[CollectedArticle],
    *,
    min_similarity: float = 0.26,
) -> list[list[CollectedArticle]]:
    clusters: list[list[CollectedArticle]] = []
    cluster_tokens: list[set[str]] = []
    seen_urls: set[str] = set()
    for article in articles:
        if not article.url or article.url in seen_urls:
            continue
        seen_urls.add(article.url)
        tokens = token_set(_article_text(article))
        best_index = -1
        best_score = 0.0
        for index, tokens_for_cluster in enumerate(cluster_tokens):
            score = _cluster_similarity(tokens, tokens_for_cluster)
            if score > best_score:
                best_index = index
                best_score = score
        if best_index >= 0 and best_score >= min_similarity:
            clusters[best_index].append(article)
            cluster_tokens[best_index] |= tokens
        else:
            clusters.append([article])
            cluster_tokens.append(set(tokens))
    return sorted(clusters, key=lambda cluster: len(cluster), reverse=True)


def _fallback_title(articles: list[CollectedArticle], *, topic_name: str) -> str:
    titles = [normalize_whitespace(article.title.split(" - ")[0]) for article in articles if article.title]
    text = " ".join(titles)
    counts = Counter(
        token
        for token in token_set(text)
        if token not in STOPWORDS and not re.fullmatch(r"\d+", token)
    )
    keywords = [token for token, _ in counts.most_common(5)]
    if keywords:
        return normalize_whitespace(" ".join(keywords))[:80]
    return (titles[0] if titles else topic_name)[:120]


def _signals(articles: list[CollectedArticle]) -> dict:
    text = " ".join(_article_text(article) for article in articles)
    publishers = sorted({article.publisher for article in articles if article.publisher})
    numbers = re.findall(r"\d+(?:,\d{3})*(?:\.\d+)?", text)
    official_mentions = len(re.findall(r"위원회|정부|부|청|공공|공식|발표|수사|조사", text))
    return {
        "article_count": len(articles),
        "publisher_count": len(publishers),
        "publishers": publishers[:10],
        "number_count": len(numbers),
        "numbers": numbers[:10],
        "official_mentions": official_mentions,
        "keywords": sorted(token_set(text))[:30],
    }


def _score(signals: dict) -> int:
    return min(
        100,
        20
        + min(int(signals.get("article_count") or 0) * 10, 30)
        + min(int(signals.get("publisher_count") or 0) * 8, 24)
        + min(int(signals.get("number_count") or 0) * 4, 16)
        + min(int(signals.get("official_mentions") or 0) * 4, 16),
    )


def _normalize_score(value: object, fallback: int) -> int:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return fallback
    if 0 < score <= 1:
        score *= 100
    return max(0, min(int(score), 100))


def _keyword_candidates(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [str(value.get("query") or value.get("keyword") or value.get("title") or "")]
    if isinstance(value, list):
        candidates: list[str] = []
        for item in value:
            candidates.extend(_keyword_candidates(item))
        return candidates
    return []


def _clean_incident_keywords(value: object, *, fallback: str) -> list[str]:
    keywords: list[str] = []
    seen: set[str] = set()
    for candidate in [*_keyword_candidates(value), fallback]:
        keyword = normalize_whitespace(str(candidate or ""))[:300]
        if not is_search_query_usable(keyword) or keyword in seen:
            continue
        keywords.append(keyword)
        seen.add(keyword)
    return keywords[:10]


def _taxonomy_name(row: dict, *keys: str) -> str:
    for key in keys:
        value = normalize_whitespace(str(row.get(key) or ""))
        if value:
            return value[:240]
    return ""


def define_incident(
    db: Session,
    *,
    articles: list[CollectedArticle],
    topic_name: str,
    topic: str,
) -> dict:
    topic = normalize_topic(topic)
    payload = [
        {
            "title": article.title,
            "publisher": article.publisher,
            "summary": article.summary or article.body_text[:300],
            "url": article.url,
        }
        for article in articles[:8]
    ]
    ai_result = DeepSeekAnalysisService(db).define_incident_candidate(
        articles=payload,
        topic_name=topic_name,
    )
    signals = _signals(articles)
    if isinstance(ai_result, dict) and ai_result.get("title"):
        title = normalize_whitespace(str(ai_result.get("title") or ""))[:180]
        keywords = _clean_incident_keywords(
            ai_result.get("search_keywords") or ai_result.get("keywords"),
            fallback=title,
        )
        return {
            "event_group_name": _taxonomy_name(ai_result, "event_group_name", "eventGroup", "event_group"),
            "keywords": keywords or [title],
            "major_topic_name": _taxonomy_name(ai_result, "major_topic_name", "majorTopic", "major_topic"),
            "score": _normalize_score(ai_result.get("score"), _score(signals)),
            "signals": signals,
            "summary": normalize_whitespace(str(ai_result.get("summary") or ""))[:1000],
            "title": title,
            "topic": normalize_topic(ai_result.get("topic"), default=topic or infer_topic(title)),
        }

    title = _fallback_title(articles, topic_name=topic_name)
    summary = articles[0].summary or articles[0].body_text[:300] if articles else ""
    return {
        "keywords": [title, *(article.title.split(" - ")[0] for article in articles[:3])],
        "score": _score(signals),
        "signals": signals,
        "summary": normalize_whitespace(summary)[:1000],
        "title": title,
        "topic": normalize_topic(topic or infer_topic(title)),
    }


def upsert_discovery_topic(
    db: Session,
    *,
    base_queries: list[str],
    interval_minutes: int = 60,
    max_results_per_query: int = 12,
    min_cluster_size: int = 2,
    name: str,
    priority: str = "normal",
    status: str = "active",
    topic: str = "사회",
) -> models.DiscoveryTopic:
    existing = db.scalar(select(models.DiscoveryTopic).where(models.DiscoveryTopic.name == name))
    cleaned_queries = [normalize_whitespace(query) for query in base_queries if normalize_whitespace(query)]
    topic = normalize_topic(topic)
    if existing:
        existing.base_queries_json = cleaned_queries or existing.base_queries_json
        existing.discovery_interval_minutes = interval_minutes
        existing.max_results_per_query = max_results_per_query
        existing.min_cluster_size = min_cluster_size
        existing.priority = priority
        existing.status = status
        existing.topic = topic
        existing.updated_at = models.now_utc()
        db.flush()
        return existing
    row = models.DiscoveryTopic(
        base_queries_json=cleaned_queries or [name],
        discovery_interval_minutes=interval_minutes,
        id=new_id("discovery"),
        max_results_per_query=max_results_per_query,
        min_cluster_size=min_cluster_size,
        name=name,
        priority=priority,
        status=status,
        topic=topic,
    )
    db.add(row)
    db.flush()
    return row


def upsert_discovered_incident(
    db: Session,
    *,
    article_ids: list[str],
    definition: dict,
    discovery_topic_id: str | None,
    issue_id: str | None,
    keyword_ids: list[str],
) -> models.DiscoveredIncident:
    title = normalize_whitespace(str(definition.get("title") or "새 사건 후보"))[:240]
    basis = "|".join(sorted(article_ids)) if article_ids else title
    incident_id = f"incident_{hash_text(basis)[:16]}"
    incident = db.get(models.DiscoveredIncident, incident_id)
    if not incident:
        incident = models.DiscoveredIncident(
            discovery_topic_id=discovery_topic_id,
            id=incident_id,
            title=title,
        )
        db.add(incident)
    incident.article_ids_json = article_ids
    incident.discovery_topic_id = discovery_topic_id
    incident.issue_id = issue_id
    incident.keyword_ids_json = keyword_ids
    incident.last_seen_at = models.now_utc()
    incident.score = int(definition.get("score") or 0)
    incident.signals_json = definition.get("signals") or {}
    incident.status = "promoted" if issue_id else "candidate"
    incident.summary = str(definition.get("summary") or "")[:1200]
    incident.topic = normalize_topic(definition.get("topic"))
    incident.updated_at = models.now_utc()
    db.flush()
    return incident
