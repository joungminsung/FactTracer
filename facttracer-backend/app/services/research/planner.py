from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app import models
from app.services.ai.deepseek_client import DeepSeekAnalysisService
from app.services.search.keywords import fallback_keyword_variants
from app.services.topics import normalize_topic


MISSING_SIGNAL_PURPOSES: dict[str, tuple[str, ...]] = {
    "articleCoverage": ("core", "followup"),
    "publisherDiversity": ("core", "comparison"),
    "officialCoverage": ("official", "public"),
    "claimCoverage": ("claim", "controversy"),
    "evidenceCoverage": ("evidence", "official"),
    "confirmedFacts": ("factcheck", "official"),
    "perspectiveCoverage": ("opposition", "response"),
    "timelineCoverage": ("followup", "official"),
    "numberCoverage": ("numbers", "statistics"),
    "parseHealth": ("original", "official"),
}

PURPOSE_TERMS: dict[str, tuple[str, ...]] = {
    "claim": ("주장", "쟁점", "의혹"),
    "comparison": ("종합", "쟁점", "비교"),
    "controversy": ("논란", "반박", "반론"),
    "core": ("", "논란"),
    "evidence": ("근거", "자료", "팩트체크"),
    "factcheck": ("확인", "검증", "팩트체크"),
    "followup": ("후속", "고발", "감사", "수사", "집회", "기자회견"),
    "numbers": ("수치", "집계", "통계"),
    "official": ("공식자료", "해명", "설명자료", "브리핑"),
    "opposition": ("반론", "입장"),
    "original": ("원문", "전문"),
    "public": ("정부", "기관", "보도자료"),
    "response": ("대응", "입장문"),
    "statistics": ("통계", "현황", "집계"),
}

SOURCE_TYPES = {"news", "official", "public", "statistics", "law", "company"}


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _append_query(rows: list[dict[str, Any]], seen: set[str], *, purpose: str, query: str, reason: str) -> None:
    cleaned = _clean(query)[:300]
    if len(cleaned) < 2 or cleaned in seen:
        return
    rows.append(
        {
            "priority": "high" if purpose in {"core", "official"} else "normal",
            "purpose": purpose,
            "query": cleaned,
            "reason": reason,
        },
    )
    seen.add(cleaned)


def _base_terms(issue: models.Issue | None, seed_query: str = "") -> list[str]:
    values = [
        seed_query,
        issue.title if issue else "",
        issue.event_group_name if issue else "",
        issue.major_topic_name if issue else "",
        issue.summary[:120] if issue and issue.summary else "",
    ]
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = _clean(value)
        if len(cleaned) >= 2 and cleaned not in seen:
            result.append(cleaned)
            seen.add(cleaned)
    return result


def _purposes_for_missing_signals(missing_signals: list[str]) -> list[str]:
    purposes = ["core"]
    for signal in missing_signals:
        for purpose in MISSING_SIGNAL_PURPOSES.get(signal, ("core",)):
            if purpose not in purposes:
                purposes.append(purpose)
    return purposes


def _fallback_plan(
    *,
    issue: models.Issue | None,
    missing_signals: list[str],
    seed_query: str,
    topic: str,
) -> dict[str, Any]:
    base_terms = _base_terms(issue, seed_query)
    purposes = _purposes_for_missing_signals(missing_signals)
    queries: list[dict[str, Any]] = []
    seen: set[str] = set()
    reason_suffix = ", ".join(missing_signals) if missing_signals else "seed"

    for base in base_terms[:4]:
        for purpose in purposes[:8]:
            for term in PURPOSE_TERMS.get(purpose, ("",))[:4]:
                _append_query(
                    queries,
                    seen,
                    purpose=purpose,
                    query=f"{base} {term}",
                    reason=f"{purpose} query from {reason_suffix}",
                )
        for variant in fallback_keyword_variants(base)[:6]:
            _append_query(queries, seen, purpose="core", query=variant, reason="deterministic variant")

    source_routes = [{"reason": "baseline news coverage", "sourceType": "news"}]
    official_targets: list[dict[str, Any]] = []
    if any(signal in missing_signals for signal in ["officialCoverage", "evidenceCoverage", "confirmedFacts", "timelineCoverage"]):
        source_routes.append({"reason": "missing official/public confirmation", "sourceType": "official"})
    if "numberCoverage" in missing_signals:
        source_routes.append({"reason": "numeric claims need data source", "sourceType": "statistics"})
    if issue and issue.topic in {"경제", "보건", "사회", "재난", "정치", "IT"}:
        source_routes.append({"reason": "high-impact public issue", "sourceType": "public"})
    issue_text = " ".join(base_terms)
    if issue_text and any(term in issue_text for term in ["선관위", "중앙선거관리위원회", "선거", "투표"]):
        official_targets.append(
            {
                "domain": "nec.go.kr",
                "name": "중앙선거관리위원회",
                "reason": "election incident official source",
                "sourceType": "official",
            },
        )

    return {
        "eventGroup": issue.event_group_name if issue else "",
        "majorTopic": issue.major_topic_name if issue else "",
        "officialTargets": official_targets,
        "queries": queries[:24],
        "sourceRoutes": source_routes,
        "stopRules": {"maxQueries": 24, "maxRounds": 2, "minNewArticles": 1},
        "topic": normalize_topic(topic),
    }


def _normalize_ai_plan(payload: Any, fallback: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return fallback
    rows = payload.get("queries")
    if not isinstance(rows, list):
        return fallback

    cleaned_queries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        query = _clean(row.get("query"))
        if len(query) < 2 or query in seen:
            continue
        cleaned_queries.append(
            {
                "priority": _clean(row.get("priority")) or "normal",
                "purpose": _clean(row.get("purpose")) or "core",
                "query": query[:300],
                "reason": _clean(row.get("reason")) or "ai planner",
            },
        )
        seen.add(query)
    if not cleaned_queries:
        return fallback

    source_routes = _normalize_source_routes(payload.get("sourceRoutes"), fallback["sourceRoutes"])
    official_targets = _normalize_official_targets(payload.get("officialTargets"), fallback.get("officialTargets") or [])
    return fallback | {
        "officialTargets": official_targets[:12],
        "queries": cleaned_queries[:24],
        "sourceRoutes": source_routes[:12],
        "stopRules": payload.get("stopRules") if isinstance(payload.get("stopRules"), dict) else fallback.get("stopRules", {}),
    }


def _normalize_source_routes(value: Any, fallback: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return fallback
    routes: list[dict[str, Any]] = []
    for row in value:
        if not isinstance(row, dict):
            continue
        source_type = _clean(row.get("sourceType"))
        if source_type not in SOURCE_TYPES:
            continue
        routes.append(
            {
                "domainHint": _clean(row.get("domainHint") or row.get("domain") or row.get("site")),
                "reason": _clean(row.get("reason")) or "ai planner route",
                "sourceType": source_type,
            },
        )
    return routes or fallback


def _normalize_official_targets(value: Any, fallback: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return fallback
    targets: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in value:
        if isinstance(row, str):
            row = {"domain": row}
        if not isinstance(row, dict):
            continue
        domain = _clean(row.get("domain") or row.get("domainHint") or row.get("site"))
        name = _clean(row.get("name") or row.get("organization"))
        source_type = _clean(row.get("sourceType")) or "official"
        if source_type not in SOURCE_TYPES - {"news"}:
            source_type = "official"
        key = domain or name
        if not key or key in seen:
            continue
        targets.append(
            {
                "domain": domain,
                "name": name,
                "reason": _clean(row.get("reason")) or "ai planner official target",
                "sourceType": source_type,
            },
        )
        seen.add(key)
    return targets or fallback


def build_research_plan(
    db: Session,
    *,
    issue: models.Issue | None = None,
    missing_signals: list[str] | None = None,
    seed_query: str = "",
    topic: str = "사회",
    trigger_type: str = "manual",
) -> dict[str, Any]:
    normalized_topic = normalize_topic(issue.topic if issue else topic)
    gaps = [str(item) for item in (missing_signals or []) if str(item).strip()]
    fallback = _fallback_plan(
        issue=issue,
        missing_signals=gaps,
        seed_query=seed_query,
        topic=normalized_topic,
    )
    ai_plan = DeepSeekAnalysisService(db).build_research_plan(
        issue=(
            {
                "eventGroup": issue.event_group_name,
                "majorTopic": issue.major_topic_name,
                "summary": issue.summary,
                "title": issue.title,
                "topic": issue.topic,
            }
            if issue
            else {"title": seed_query, "topic": normalized_topic}
        ),
        missing_signals=gaps,
        trigger_type=trigger_type,
    )
    return _normalize_ai_plan(ai_plan, fallback)
