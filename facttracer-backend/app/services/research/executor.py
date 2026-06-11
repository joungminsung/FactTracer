from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.collectors.base import CollectedArticle
from app.services.admin.settings import get_effective_setting
from app.services.articles.normalizer import normalize_url
from app.services.research.planner import build_research_plan
from app.services.research.providers import provider_for_route
from app.services.research.router import route_sources_for_plan
from app.utils import new_id


@dataclass
class _CollectedResult:
    article: CollectedArticle
    provider: str
    query: str
    route: dict[str, Any]


@dataclass
class _DedupedCollectedResult:
    article: CollectedArticle
    sources: list[dict[str, Any]]


def _duration_ms(started_at: datetime) -> int:
    return int((datetime.now(UTC) - started_at).total_seconds() * 1000)


def _execute_provider_query(
    *,
    db: Session,
    max_items: int,
    provider: Any,
    query: str,
    route: dict[str, Any],
) -> list[CollectedArticle]:
    return provider.search(max_items=max_items, query=query, route=route)


def _dedupe_collected(rows: list[_CollectedResult]) -> list[_DedupedCollectedResult]:
    seen: set[str] = set()
    by_key: dict[str, _DedupedCollectedResult] = {}
    deduped: list[_DedupedCollectedResult] = []
    for row in rows:
        key = normalize_url(row.article.url) or row.article.url
        if not key:
            continue
        source = {
            "provider": row.provider,
            "query": row.query,
            "route": row.route,
        }
        if key in seen:
            by_key[key].sources.append(source)
            continue
        seen.add(key)
        result = _DedupedCollectedResult(article=row.article, sources=[source])
        by_key[key] = result
        deduped.append(result)
    return deduped


def _openai_runs_today(db: Session, *, issue_id: str | None) -> int:
    if not issue_id:
        return 0
    since = models.now_utc() - timedelta(days=1)
    rows = db.scalars(
        select(models.ResearchRun).where(
            models.ResearchRun.issue_id == issue_id,
            models.ResearchRun.started_at >= since,
        ),
    ).all()
    return sum(
        1
        for row in rows
        if any(route.get("provider") == "openai_web_search" for route in (row.source_routes_json or []))
    )


def _maybe_append_openai_route(
    db: Session,
    *,
    issue: models.Issue | None,
    round_index: int,
    routes: list[dict[str, Any]],
    trigger_type: str,
) -> list[dict[str, Any]]:
    if not bool(get_effective_setting(db, "openai_web_search_enabled", False)):
        return routes
    if not get_effective_setting(db, "openai_api_key"):
        return routes
    daily_limit = int(get_effective_setting(db, "openai_web_search_daily_issue_limit") or 0)
    if daily_limit <= 0 or (issue and _openai_runs_today(db, issue_id=issue.id) >= daily_limit):
        return routes
    fallback_after = int(get_effective_setting(db, "research_openai_fallback_after_round") or 2)
    high_impact = bool(issue and issue.topic in {"경제", "보건", "재난", "정치"})
    retry_exhausted = trigger_type == "quality_gap" and round_index >= fallback_after
    if not high_impact and not retry_exhausted:
        return routes
    if round_index < fallback_after and not high_impact:
        return routes
    if any(route.get("provider") == "openai_web_search" for route in routes):
        return routes
    return [
        *routes,
        {
            "domain": "",
            "provider": "openai_web_search",
            "reason": "enabled fallback for high-impact or repeated quality gap",
            "sourceType": "web_search",
        },
    ]


def execute_research_plan(
    db: Session,
    *,
    discovery_topic_id: str | None = None,
    issue: models.Issue | None,
    keyword_id: str | None = None,
    missing_signals: list[str] | None = None,
    round_index: int = 1,
    seed_query: str = "",
    trigger_type: str = "manual",
) -> dict[str, Any]:
    max_rounds = max(round_index, int(get_effective_setting(db, "research_max_rounds") or round_index))
    current_missing = list(missing_signals or [])
    aggregate: dict[str, Any] = {
        "article_count": 0,
        "collected": 0,
        "created": 0,
        "executed_queries": 0,
        "linked": 0,
        "parse_jobs": 0,
        "research_run_ids": [],
        "rounds": 0,
        "status": "completed",
    }
    last_result: dict[str, Any] = {}

    for current_round in range(round_index, max_rounds + 1):
        result = _execute_research_plan_round(
            db,
            discovery_topic_id=discovery_topic_id,
            issue=issue,
            keyword_id=keyword_id,
            missing_signals=current_missing,
            round_index=current_round,
            seed_query=seed_query,
            trigger_type=trigger_type,
        )
        last_result = result
        aggregate["rounds"] += 1
        aggregate["article_count"] += int(result.get("article_count") or 0)
        aggregate["collected"] += int(result.get("collected") or 0)
        aggregate["created"] += int(result.get("created") or 0)
        aggregate["executed_queries"] += int(result.get("executed_queries") or 0)
        aggregate["linked"] += int(result.get("linked") or 0)
        aggregate["parse_jobs"] += int(result.get("parse_jobs") or 0)
        if result.get("research_run_id"):
            aggregate["research_run_ids"].append(result["research_run_id"])
        if result.get("status") == "failed":
            break
        if int(result.get("linked") or 0) > 0 or int(result.get("collected") or 0) > 0:
            break
        if "articleCoverage" not in current_missing:
            current_missing.append("articleCoverage")

    aggregate["status"] = last_result.get("status", "completed")
    aggregate["research_run_id"] = last_result.get("research_run_id")
    if last_result.get("error"):
        aggregate["error"] = last_result["error"]
    return aggregate


def _execute_research_plan_round(
    db: Session,
    *,
    discovery_topic_id: str | None = None,
    issue: models.Issue | None,
    keyword_id: str | None = None,
    missing_signals: list[str] | None = None,
    round_index: int = 1,
    seed_query: str = "",
    trigger_type: str = "manual",
) -> dict[str, Any]:
    from app.workers.issue_jobs import (
        _enqueue_parse_article_job,
        _link_and_select_article_image_candidates,
        upsert_collected_article_record,
    )

    started_at = datetime.now(UTC)
    plan = build_research_plan(
        db,
        issue=issue,
        missing_signals=missing_signals or [],
        seed_query=seed_query,
        topic=issue.topic if issue else "사회",
        trigger_type=trigger_type,
    )
    routes = _maybe_append_openai_route(
        db,
        issue=issue,
        round_index=round_index,
        routes=route_sources_for_plan(db, plan=plan),
        trigger_type=trigger_type,
    )
    run = models.ResearchRun(
        discovery_topic_id=discovery_topic_id,
        id=new_id("research"),
        issue_id=issue.id if issue else None,
        keyword_id=keyword_id,
        missing_signals_json=missing_signals or [],
        plan_json=plan,
        round_index=round_index,
        seed_query=seed_query or (issue.title if issue else ""),
        source_routes_json=routes,
        status="running",
        trigger_type=trigger_type,
    )
    db.add(run)
    db.flush()

    max_queries = int(get_effective_setting(db, "research_max_queries_per_round") or 16)
    openai_max_queries = int(get_effective_setting(db, "openai_web_search_max_queries_per_round") or 2)
    max_items = int(get_effective_setting(db, "research_max_results_per_query") or 8)
    collected: list[_CollectedResult] = []
    executed_queries: list[dict[str, Any]] = []
    result_urls: list[dict[str, Any]] = []

    try:
        for route in routes:
            provider = provider_for_route(route, db=db)
            provider_name = getattr(provider, "name", "unknown")
            route_query_limit = max(1, min(max_queries, openai_max_queries)) if provider_name == "openai_web_search" else max_queries
            for query_row in (plan.get("queries") or [])[:route_query_limit]:
                if not isinstance(query_row, dict):
                    continue
                query = str(query_row.get("query") or "").strip()
                if not query:
                    continue
                try:
                    provider_rows = _execute_provider_query(
                        db=db,
                        max_items=max_items,
                        provider=provider,
                        query=query,
                        route=route,
                    )
                except Exception as exc:
                    executed_queries.append(
                        {
                            "error": str(exc),
                            "provider": provider_name,
                            "query": query,
                            "resultCount": 0,
                            "route": route,
                            "status": "failed",
                        },
                    )
                    continue
                executed_queries.append(
                    {
                        "provider": provider_name,
                        "query": query,
                        "resultCount": len(provider_rows),
                        "route": route,
                        "status": "completed",
                    },
                )
                collected.extend(
                    _CollectedResult(
                        article=row,
                        provider=provider_name,
                        query=query,
                        route=dict(route),
                    )
                    for row in provider_rows
                )

        created = 0
        parse_jobs = 0
        selected_article_ids: list[str] = []
        for collected_result in _dedupe_collected(collected):
            row = collected_result.article
            article, was_created = upsert_collected_article_record(
                db,
                collected=row,
                issue_id=issue.id if issue else None,
            )
            if issue and article.issue_id != issue.id:
                article.issue_id = issue.id
                _link_and_select_article_image_candidates(db, article=article, issue_id=issue.id)
            selected_article_ids.append(article.id)
            created += int(was_created)
            if _enqueue_parse_article_job(db, article_id=article.id):
                parse_jobs += 1
            primary_source = collected_result.sources[0]
            result_urls.append(
                {
                    "articleId": article.id,
                    "collectionSources": collected_result.sources,
                    "created": was_created,
                    "provider": primary_source["provider"],
                    "publisher": row.publisher,
                    "query": primary_source["query"],
                    "reason": "deduped and linked",
                    "route": primary_source["route"],
                    "selected": True,
                    "sourceType": row.source_type,
                    "title": row.title,
                    "url": row.url,
                },
            )

        run.duration_ms = _duration_ms(started_at)
        run.executed_queries_json = executed_queries
        run.finished_at = models.now_utc()
        run.result_urls_json = result_urls
        run.selected_article_ids_json = selected_article_ids
        run.status = "completed"
        db.flush()
        return {
            "article_count": created,
            "collected": len(collected),
            "created": created,
            "executed_queries": len(executed_queries),
            "linked": len(selected_article_ids),
            "parse_jobs": parse_jobs,
            "research_run_id": run.id,
            "status": "completed",
        }
    except Exception as exc:
        run.duration_ms = _duration_ms(started_at)
        run.error_message = str(exc)
        run.executed_queries_json = executed_queries
        run.finished_at = models.now_utc()
        run.result_urls_json = result_urls
        run.status = "failed"
        db.flush()
        return {"article_count": 0, "error": str(exc), "research_run_id": run.id, "status": "failed"}
