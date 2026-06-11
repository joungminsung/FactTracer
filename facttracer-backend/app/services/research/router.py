from __future__ import annotations

import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models


SOURCE_TYPE_ALIASES = {
    "company": {"company", "corporate"},
    "law": {"law", "public"},
    "news": {"media", "news_search", "rss", "search"},
    "official": {"government", "official", "public"},
    "public": {"government", "official", "public"},
    "statistics": {"public", "statistics"},
}


def _wanted_source_types(plan: dict[str, Any]) -> set[str]:
    wanted = {"news"}
    for route in plan.get("sourceRoutes") or []:
        if not isinstance(route, dict):
            continue
        source_type = str(route.get("sourceType") or "").strip()
        if source_type:
            wanted.add(source_type)
    return wanted


def _compact(value: Any) -> str:
    return re.sub(r"^www\.", "", str(value or "").strip().lower())


def _route_for_source(source: models.SourceDomain, *, reason: str, source_type: str | None = None) -> dict[str, Any]:
    return {
        "collectionUrl": source.collection_url,
        "credibility": source.credibility,
        "domain": source.domain,
        "name": source.name,
        "provider": "site_query",
        "reason": reason,
        "sourceId": source.id,
        "sourceType": source.source_type if not source_type else source.source_type or source_type,
    }


def _matches_source_type(source: models.SourceDomain, wanted: str) -> bool:
    aliases = SOURCE_TYPE_ALIASES.get(wanted, {wanted})
    source_type = str(source.source_type or "").strip().lower()
    return source_type in aliases


def _source_matches_hint(source: models.SourceDomain, hint: str) -> bool:
    compact_hint = _compact(hint)
    if not compact_hint:
        return False
    domain = _compact(source.domain)
    collection_url = _compact(source.collection_url)
    name = _compact(source.name)
    note = _compact(source.note)
    return (
        compact_hint == domain
        or compact_hint in domain
        or compact_hint in collection_url
        or compact_hint in name
        or compact_hint in note
    )


def _target_rows(plan: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for target in plan.get("officialTargets") or []:
        if isinstance(target, str):
            target = {"domain": target}
        if not isinstance(target, dict):
            continue
        rows.append(
            {
                "domain": str(target.get("domain") or "").strip(),
                "name": str(target.get("name") or "").strip(),
                "reason": str(target.get("reason") or "ai planner official target").strip(),
                "sourceType": str(target.get("sourceType") or "official").strip(),
            },
        )
    for route in plan.get("sourceRoutes") or []:
        if not isinstance(route, dict):
            continue
        hint = str(route.get("domainHint") or route.get("domain") or "").strip()
        if not hint:
            continue
        rows.append(
            {
                "domain": hint,
                "name": "",
                "reason": str(route.get("reason") or "ai planner route hint").strip(),
                "sourceType": str(route.get("sourceType") or "official").strip(),
            },
        )
    return rows


def _append_hinted_routes(
    routes: list[dict[str, Any]],
    *,
    plan: dict[str, Any],
    seen_source_ids: set[str],
    sources: list[models.SourceDomain],
) -> None:
    for target in _target_rows(plan):
        wanted = str(target.get("sourceType") or "official")
        hints = [target.get("domain"), target.get("name")]
        matches = [
            source
            for source in sources
            if _matches_source_type(source, wanted)
            and any(_source_matches_hint(source, hint) for hint in hints if hint)
        ]
        for source in matches:
            if source.id in seen_source_ids:
                continue
            routes.append(_route_for_source(source, reason=target["reason"], source_type=wanted))
            seen_source_ids.add(source.id)


def route_sources_for_plan(db: Session, *, limit_per_type: int = 4, plan: dict[str, Any]) -> list[dict[str, Any]]:
    routes: list[dict[str, Any]] = [
        {
            "domain": "",
            "provider": "google_news",
            "reason": "baseline news search",
            "sourceType": "news",
        },
    ]
    sources = db.scalars(
        select(models.SourceDomain)
        .where(models.SourceDomain.is_active.is_(True))
        .order_by(models.SourceDomain.credibility.desc(), models.SourceDomain.name.asc()),
    ).all()
    seen_source_ids: set[str] = set()
    _append_hinted_routes(routes, plan=plan, seen_source_ids=seen_source_ids, sources=sources)
    for wanted in sorted(_wanted_source_types(plan)):
        if wanted == "news":
            continue
        count = 0
        for source in sources:
            if not _matches_source_type(source, wanted):
                continue
            if source.id in seen_source_ids:
                continue
            routes.append(_route_for_source(source, reason=f"{wanted} route from source registry"))
            seen_source_ids.add(source.id)
            count += 1
            if count >= limit_per_type:
                break
    return routes[:20]
