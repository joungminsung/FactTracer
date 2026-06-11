# Agentic News Collection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current shallow RSS/search-keyword collection flow with an agentic research loop that plans searches, routes official/news sources, collects evidence in bursts, detects gaps, re-searches, and leaves auditable collection traces.

**Architecture:** Keep the existing `Issue`, `DiscoveryTopic`, `SearchKeyword`, `SourceDomain`, `CollectorRun`, and quality pipeline. Add a `ResearchRun` trace model, a structured `ResearchPlan`, provider-based search execution, optional OpenAI `web_search` fallback, and a new `research_issue` job that can run immediately after discovery or quality failure.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy, Alembic, pytest, OpenAI-compatible chat via DeepSeek, optional OpenAI Responses API `web_search`, Google News RSS, existing collector/parser pipeline.

---

## Current State

- Broad discovery topics are now correct: `정치`, `사회`, `경제`, `국제`, `재난`, `보건` plus disaster/safety style coverage.
- `MajorTopic`, `EventGroup`, representative image fields, issue quality fields, and ranking metadata already exist.
- Current collection still depends heavily on `collect_google_news_search()` through `issue_jobs._collect_search_results()`.
- `SourceDomain` exists, but a fresh DB has no broad official/source registry.
- `fallback_keyword_variants()` contains election-specific rules. That helped one case, but this logic should move into an agentic planner so default topics remain broad.
- `assess_issue_quality()` already detects missing signals and creates `quality_retry` keywords, but its query generation is deterministic and source routing is weak.
- Embedded worker currently runs `run_due_jobs(db, limit=1)`, so discovery/search/parse/enrichment are serialized and breaking-news first runs can publish thin issues with no articles or weak detail sections.

## Target Collection Loop

```text
seed topic / issue / keyword
-> ResearchPlanner builds purpose-based queries
-> SourceRouter selects news, official, public, stats, law, company routes
-> SearchExecutor runs providers and deduplicates URLs
-> articles are upserted and linked to the issue
-> parser / claim / evidence / page jobs run
-> quality scorer detects gaps
-> research_issue runs another bounded round when evidence is thin
-> ResearchRun stores all queries, routes, chosen URLs, rejected URLs, and gap reasons
```

## File Structure

Create:

- `facttracer-backend/app/services/research/__init__.py` - package marker.
- `facttracer-backend/app/services/research/planner.py` - builds `ResearchPlan` from topic, issue, quality gaps, and known articles.
- `facttracer-backend/app/services/research/providers.py` - provider interface plus Google News, official site-query, and optional OpenAI web search providers.
- `facttracer-backend/app/services/research/router.py` - maps topic/issue/gaps to source routes and official domain candidates.
- `facttracer-backend/app/services/research/executor.py` - executes a plan, upserts articles, enqueues parsing, and writes `ResearchRun`.
- `facttracer-backend/app/services/bootstrap/sources.py` - seeds broad official/public source domains.
- `facttracer-backend/app/db/migrations/versions/0004_agentic_research_runs.py` - additive research trace schema and optional job priority index.

Modify:

- `facttracer-backend/app/models.py` - add `ResearchRun`.
- `facttracer-backend/app/core/config.py` - add research loop, OpenAI web search, worker batch settings.
- `facttracer-backend/app/services/admin/settings.py` - expose runtime settings for research depth, source caps, provider selection, and worker batch size.
- `facttracer-backend/app/services/bootstrap/defaults.py` - call source-domain seeding and keep default topics broad.
- `facttracer-backend/app/services/search/keywords.py` - remove election-specific hardcoding from generic fallback and delegate richer expansion to planner.
- `facttracer-backend/app/services/ai/deepseek_client.py` - add structured research-planning method.
- `facttracer-backend/app/services/ai/openai_web_search.py` - optional OpenAI Responses API provider wrapper.
- `facttracer-backend/app/services/jobs.py` - register `research_issue`, adjust collection job priority, and support batch execution.
- `facttracer-backend/app/services/scheduler/runtime.py` - use configurable worker batch size.
- `facttracer-backend/app/workers/issue_jobs.py` - integrate `research_issue` into discovery, keyword search, backfill, and quality loops.
- `facttracer-backend/app/api/routes/admin.py` - expose recent research traces for an issue.
- `facttracer-backend/tests/test_api.py` - add planner/router/executor/job/trace tests.
- `docker-compose.yml` - set faster worker poll and batch size for local development.

## OpenAI API Position

Use OpenAI `web_search` as an optional provider, not the primary crawler.

- Default mode: local planner + Google News RSS + site-restricted official/public searches + direct source fetch.
- OpenAI fallback mode: enabled only when `openai_web_search_enabled=true`, API key exists, and the issue is high impact or quality retries are exhausted.
- Cost control: cap OpenAI web search calls by issue, day, and research round.
- Audit: all OpenAI-derived URLs must be written into `ResearchRun.result_urls_json` with provider `openai_web_search`.

Reference docs:

- `https://developers.openai.com/api/docs/guides/tools-web-search`
- `https://developers.openai.com/api/docs/guides/tools`

---

### Task 1: Research Trace Schema

**Files:**
- Modify: `facttracer-backend/app/models.py`
- Create: `facttracer-backend/app/db/migrations/versions/0004_agentic_research_runs.py`
- Test: `facttracer-backend/tests/test_api.py`

- [ ] **Step 1: Write failing model/migration test**

Append this test to `facttracer-backend/tests/test_api.py`:

```python
def test_research_run_persists_collection_evidence() -> None:
    db = SessionLocal()
    try:
        issue = models.Issue(
            id="issue_research_trace",
            title="선거 투표용지 부족 논란",
            topic="정치",
            status="검증 진행",
            is_public=True,
        )
        run = models.ResearchRun(
            id="research_trace_1",
            issue_id=issue.id,
            trigger_type="quality_gap",
            seed_query="선거 투표용지 부족 논란",
            status="completed",
            round_index=1,
            plan_json={"queries": [{"query": "선관위 투표용지 부족", "purpose": "core"}]},
            source_routes_json=[{"sourceType": "official", "domain": "nec.go.kr"}],
            executed_queries_json=[{"provider": "google_news", "query": "선관위 투표용지 부족"}],
            result_urls_json=[{"url": "https://example.com/a", "selected": True, "reason": "new article"}],
            selected_article_ids_json=["article_1"],
            missing_signals_json=["officialCoverage"],
        )
        db.add(issue)
        db.add(run)
        db.commit()

        saved = db.get(models.ResearchRun, "research_trace_1")
        assert saved is not None
        assert saved.issue_id == "issue_research_trace"
        assert saved.source_routes_json[0]["domain"] == "nec.go.kr"
        assert saved.result_urls_json[0]["selected"] is True
    finally:
        db.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd facttracer-backend
pytest tests/test_api.py::test_research_run_persists_collection_evidence -q
```

Expected: FAIL with `AttributeError: module 'app.models' has no attribute 'ResearchRun'`.

- [ ] **Step 3: Add model**

Add this class after `CollectorRun` in `facttracer-backend/app/models.py`:

```python
class ResearchRun(Base):
    __tablename__ = "research_runs"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    issue_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    discovery_topic_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    keyword_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    trigger_type: Mapped[str] = mapped_column(String(80), default="manual", index=True)
    seed_query: Mapped[str] = mapped_column(String(300), default="")
    status: Mapped[str] = mapped_column(String(80), default="running", index=True)
    round_index: Mapped[int] = mapped_column(Integer, default=1)
    plan_json: Mapped[dict] = mapped_column(JSON, default=dict)
    source_routes_json: Mapped[list] = mapped_column(JSON, default=list)
    executed_queries_json: Mapped[list] = mapped_column(JSON, default=list)
    result_urls_json: Mapped[list] = mapped_column(JSON, default=list)
    selected_article_ids_json: Mapped[list] = mapped_column(JSON, default=list)
    missing_signals_json: Mapped[list] = mapped_column(JSON, default=list)
    error_message: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
```

- [ ] **Step 4: Add migration**

Create `facttracer-backend/app/db/migrations/versions/0004_agentic_research_runs.py`:

```python
"""add agentic research runs

Revision ID: 0004_agentic_research_runs
Revises: 0003_podcast_episodes
Create Date: 2026-06-10
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0004_agentic_research_runs"
down_revision = "0003_podcast_episodes"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    return set(inspect(op.get_bind()).get_table_names())


def _index_names(table_name: str) -> set[str]:
    if table_name not in _tables():
        return set()
    return {index["name"] for index in inspect(op.get_bind()).get_indexes(table_name)}


def _create_index_if_missing(index_name: str, table_name: str, columns: list[str]) -> None:
    if table_name in _tables() and index_name not in _index_names(table_name):
        op.create_index(index_name, table_name, columns)


def _drop_index_if_exists(index_name: str, table_name: str) -> None:
    if table_name in _tables() and index_name in _index_names(table_name):
        op.drop_index(index_name, table_name=table_name)


def upgrade() -> None:
    if "research_runs" not in _tables():
        op.create_table(
            "research_runs",
            sa.Column("id", sa.String(length=80), primary_key=True),
            sa.Column("issue_id", sa.String(length=80), nullable=True),
            sa.Column("discovery_topic_id", sa.String(length=80), nullable=True),
            sa.Column("keyword_id", sa.String(length=80), nullable=True),
            sa.Column("trigger_type", sa.String(length=80), nullable=False, server_default="manual"),
            sa.Column("seed_query", sa.String(length=300), nullable=False, server_default=""),
            sa.Column("status", sa.String(length=80), nullable=False, server_default="running"),
            sa.Column("round_index", sa.Integer(), nullable=False, server_default=sa.text("1")),
            sa.Column("plan_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column("source_routes_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
            sa.Column("executed_queries_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
            sa.Column("result_urls_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
            sa.Column("selected_article_ids_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
            sa.Column("missing_signals_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
            sa.Column("error_message", sa.Text(), nullable=False, server_default=""),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("duration_ms", sa.Integer(), nullable=False, server_default=sa.text("0")),
        )

    _create_index_if_missing("ix_research_runs_issue_id", "research_runs", ["issue_id"])
    _create_index_if_missing("ix_research_runs_discovery_topic_id", "research_runs", ["discovery_topic_id"])
    _create_index_if_missing("ix_research_runs_keyword_id", "research_runs", ["keyword_id"])
    _create_index_if_missing("ix_research_runs_trigger_type", "research_runs", ["trigger_type"])
    _create_index_if_missing("ix_research_runs_status", "research_runs", ["status"])


def downgrade() -> None:
    for index_name in [
        "ix_research_runs_status",
        "ix_research_runs_trigger_type",
        "ix_research_runs_keyword_id",
        "ix_research_runs_discovery_topic_id",
        "ix_research_runs_issue_id",
    ]:
        _drop_index_if_exists(index_name, "research_runs")
    if "research_runs" in _tables():
        op.drop_table("research_runs")
```

- [ ] **Step 5: Verify schema test passes**

Run:

```bash
cd facttracer-backend
pytest tests/test_api.py::test_research_run_persists_collection_evidence -q
```

Expected: PASS.

---

### Task 2: Research Planner Contract

**Files:**
- Create: `facttracer-backend/app/services/research/__init__.py`
- Create: `facttracer-backend/app/services/research/planner.py`
- Modify: `facttracer-backend/app/services/ai/deepseek_client.py`
- Test: `facttracer-backend/tests/test_api.py`

- [ ] **Step 1: Write failing planner test**

Append:

```python
def test_research_planner_builds_purpose_based_queries_without_narrow_default_topic() -> None:
    from app.services.research.planner import build_research_plan

    db = SessionLocal()
    try:
        issue = models.Issue(
            id="issue_research_plan",
            title="선관위 투표용지 부족 사태",
            topic="정치",
            major_topic_name="2026 지방선거",
            event_group_name="선관위 투표용지 부족 사태",
            quality_report_json={"missingSignals": ["officialCoverage", "timelineCoverage"]},
        )
        db.add(issue)
        db.commit()

        plan = build_research_plan(
            db,
            issue=issue,
            trigger_type="quality_gap",
            missing_signals=["officialCoverage", "timelineCoverage"],
        )

        purposes = {query["purpose"] for query in plan["queries"]}
        assert {"core", "official", "followup"}.issubset(purposes)
        assert any("중앙선관위" in query["query"] or "선관위" in query["query"] for query in plan["queries"])
        assert any(route["sourceType"] == "official" for route in plan["sourceRoutes"])
        assert plan["topic"] == "정치"
        assert plan["majorTopic"] == "2026 지방선거"
    finally:
        db.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd facttracer-backend
pytest tests/test_api.py::test_research_planner_builds_purpose_based_queries_without_narrow_default_topic -q
```

Expected: FAIL because `app.services.research.planner` does not exist.

- [ ] **Step 3: Add planner implementation**

Create `facttracer-backend/app/services/research/__init__.py` as an empty file.

Create `facttracer-backend/app/services/research/planner.py`:

```python
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
    "core": ("", "논란"),
    "official": ("공식자료", "해명", "설명자료", "브리핑"),
    "public": ("정부", "기관", "보도자료"),
    "followup": ("후속", "고발", "감사", "수사", "집회", "기자회견"),
    "comparison": ("종합", "쟁점", "비교"),
    "claim": ("주장", "쟁점", "의혹"),
    "controversy": ("논란", "반박", "반론"),
    "evidence": ("근거", "자료", "팩트체크"),
    "factcheck": ("확인", "검증", "팩트체크"),
    "opposition": ("반론", "입장"),
    "response": ("대응", "입장문"),
    "numbers": ("수치", "집계", "통계"),
    "statistics": ("통계", "현황", "집계"),
    "original": ("원문", "전문"),
}


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _append_query(rows: list[dict[str, Any]], seen: set[str], *, purpose: str, query: str, reason: str) -> None:
    cleaned = _clean(query)[:300]
    if len(cleaned) < 2 or cleaned in seen:
        return
    rows.append({"query": cleaned, "purpose": purpose, "priority": "high" if purpose in {"core", "official"} else "normal", "reason": reason})
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


def _fallback_plan(
    *,
    issue: models.Issue | None,
    missing_signals: list[str],
    seed_query: str,
    topic: str,
) -> dict[str, Any]:
    base_terms = _base_terms(issue, seed_query)
    purposes = ["core"]
    for signal in missing_signals:
        for purpose in MISSING_SIGNAL_PURPOSES.get(signal, ("core",)):
            if purpose not in purposes:
                purposes.append(purpose)

    queries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for base in base_terms[:4]:
        for purpose in purposes[:8]:
            for term in PURPOSE_TERMS.get(purpose, ("",))[:4]:
                _append_query(
                    queries,
                    seen,
                    purpose=purpose,
                    query=f"{base} {term}",
                    reason=f"{purpose} query from {signal if missing_signals else 'seed'}",
                )
        for variant in fallback_keyword_variants(base)[:6]:
            _append_query(queries, seen, purpose="core", query=variant, reason="deterministic variant")

    source_routes = [{"sourceType": "news", "reason": "baseline news coverage"}]
    if any(signal in missing_signals for signal in ["officialCoverage", "evidenceCoverage", "confirmedFacts", "timelineCoverage"]):
        source_routes.append({"sourceType": "official", "reason": "missing official/public confirmation"})
    if any(signal in missing_signals for signal in ["numberCoverage"]):
        source_routes.append({"sourceType": "statistics", "reason": "numeric claims need data source"})
    if issue and issue.topic in {"정치", "사회", "경제", "보건", "재난"}:
        source_routes.append({"sourceType": "public", "reason": "high-impact public issue"})

    return {
        "topic": normalize_topic(topic),
        "majorTopic": issue.major_topic_name if issue else "",
        "eventGroup": issue.event_group_name if issue else "",
        "queries": queries[:24],
        "sourceRoutes": source_routes,
        "stopRules": {"maxRounds": 2, "minNewArticles": 1, "maxQueries": 24},
    }


def _normalize_ai_plan(payload: Any, fallback: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return fallback
    queries = payload.get("queries")
    if not isinstance(queries, list):
        return fallback
    cleaned_queries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in queries:
        if not isinstance(row, dict):
            continue
        query = _clean(row.get("query"))
        if len(query) < 2 or query in seen:
            continue
        cleaned_queries.append(
            {
                "query": query[:300],
                "purpose": _clean(row.get("purpose")) or "core",
                "priority": _clean(row.get("priority")) or "normal",
                "reason": _clean(row.get("reason")) or "ai planner",
            },
        )
        seen.add(query)
    if not cleaned_queries:
        return fallback
    source_routes = payload.get("sourceRoutes") if isinstance(payload.get("sourceRoutes"), list) else fallback["sourceRoutes"]
    return fallback | {"queries": cleaned_queries[:24], "sourceRoutes": source_routes[:12]}


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
    fallback = _fallback_plan(issue=issue, missing_signals=gaps, seed_query=seed_query, topic=normalized_topic)
    ai_plan = DeepSeekAnalysisService(db).build_research_plan(
        issue={
            "title": issue.title,
            "summary": issue.summary,
            "topic": issue.topic,
            "majorTopic": issue.major_topic_name,
            "eventGroup": issue.event_group_name,
        }
        if issue
        else {"title": seed_query, "topic": normalized_topic},
        missing_signals=gaps,
        trigger_type=trigger_type,
    )
    return _normalize_ai_plan(ai_plan, fallback)
```

- [ ] **Step 4: Add DeepSeek structured method**

Add this method to `DeepSeekAnalysisService` in `facttracer-backend/app/services/ai/deepseek_client.py`:

```python
    def build_research_plan(
        self,
        *,
        issue: dict,
        missing_signals: list[str],
        trigger_type: str,
    ) -> dict | None:
        if not self.enabled:
            return None
        return self._chat_json(
            fallback=None,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are FactTracer's Korean news research planner. Return strict JSON with keys "
                        "queries and sourceRoutes. queries must be compact Korean search phrases with "
                        "{query, purpose, priority, reason}. sourceRoutes must include {sourceType, reason, domainHint}. "
                        "sourceType must be one of news, official, public, statistics, law, company. "
                        "Plan searches for the same incident first, then official confirmation, then follow-up actions. "
                        "Do not turn narrow incidents into default topics."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "issue": issue,
                            "missingSignals": missing_signals,
                            "triggerType": trigger_type,
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            model=self.flash_model,
        )
```

- [ ] **Step 5: Verify planner test passes**

Run:

```bash
cd facttracer-backend
pytest tests/test_api.py::test_research_planner_builds_purpose_based_queries_without_narrow_default_topic -q
```

Expected: PASS.

---

### Task 3: Source Router And Broad Official Registry

**Files:**
- Create: `facttracer-backend/app/services/research/router.py`
- Create: `facttracer-backend/app/services/bootstrap/sources.py`
- Modify: `facttracer-backend/app/services/bootstrap/defaults.py`
- Test: `facttracer-backend/tests/test_api.py`

- [ ] **Step 1: Write failing router/bootstrap tests**

Append:

```python
def test_source_router_adds_official_domains_for_public_issue() -> None:
    from app.services.research.router import route_sources_for_plan

    db = SessionLocal()
    try:
        db.add(
            models.SourceDomain(
                id="source_nec",
                domain="nec.go.kr",
                name="중앙선거관리위원회",
                source_type="official",
                credibility=0.95,
                status="watch",
                collection_url="https://www.nec.go.kr",
                is_active=True,
                note="선거 공식자료",
            ),
        )
        db.commit()
        plan = {
            "topic": "정치",
            "queries": [{"query": "선관위 투표용지 부족", "purpose": "official"}],
            "sourceRoutes": [{"sourceType": "official", "reason": "official gap"}],
        }
        routes = route_sources_for_plan(db, plan=plan)
        assert any(route["provider"] == "site_query" for route in routes)
        assert any(route["domain"] == "nec.go.kr" for route in routes)
    finally:
        db.close()


def test_seed_default_source_domains_are_broad_categories() -> None:
    from app.services.bootstrap.sources import seed_default_source_domains

    db = SessionLocal()
    try:
        seed_default_source_domains(db)
        db.commit()
        domains = {row.domain for row in db.query(models.SourceDomain).all()}
        assert "korea.kr" in domains
        assert "law.go.kr" in domains
        assert "nec.go.kr" in domains
        assert "mohw.go.kr" in domains
        assert db.query(models.SourceDomain).count() >= 10
    finally:
        db.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd facttracer-backend
pytest \
  tests/test_api.py::test_source_router_adds_official_domains_for_public_issue \
  tests/test_api.py::test_seed_default_source_domains_are_broad_categories -q
```

Expected: FAIL because router and source bootstrap files do not exist.

- [ ] **Step 3: Add source router**

Create `facttracer-backend/app/services/research/router.py`:

```python
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models


SOURCE_TYPE_ALIASES = {
    "official": {"official", "public", "government"},
    "public": {"official", "public", "government"},
    "statistics": {"statistics", "public"},
    "law": {"law", "public"},
    "company": {"company", "corporate"},
    "news": {"rss", "search", "news_search", "media"},
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


def _matches_source_type(source: models.SourceDomain, wanted: str) -> bool:
    aliases = SOURCE_TYPE_ALIASES.get(wanted, {wanted})
    source_type = str(source.source_type or "").strip().lower()
    return source_type in aliases


def route_sources_for_plan(db: Session, *, plan: dict[str, Any], limit_per_type: int = 4) -> list[dict[str, Any]]:
    routes: list[dict[str, Any]] = [{"provider": "google_news", "sourceType": "news", "domain": "", "reason": "baseline news search"}]
    sources = db.scalars(
        select(models.SourceDomain)
        .where(models.SourceDomain.is_active.is_(True))
        .order_by(models.SourceDomain.credibility.desc(), models.SourceDomain.name.asc()),
    ).all()
    for wanted in _wanted_source_types(plan):
        if wanted == "news":
            continue
        count = 0
        for source in sources:
            if not _matches_source_type(source, wanted):
                continue
            routes.append(
                {
                    "provider": "site_query",
                    "sourceId": source.id,
                    "sourceType": source.source_type,
                    "domain": source.domain,
                    "name": source.name,
                    "collectionUrl": source.collection_url,
                    "credibility": source.credibility,
                    "reason": f"{wanted} route from source registry",
                },
            )
            count += 1
            if count >= limit_per_type:
                break
    return routes[:20]
```

- [ ] **Step 4: Seed broad source registry**

Create `facttracer-backend/app/services/bootstrap/sources.py`:

```python
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models


DEFAULT_SOURCE_DOMAINS: tuple[dict, ...] = (
    {"domain": "korea.kr", "name": "대한민국 정책브리핑", "source_type": "public", "collection_url": "https://www.korea.kr", "credibility": 0.9, "note": "정부 공식 정책자료"},
    {"domain": "law.go.kr", "name": "국가법령정보센터", "source_type": "law", "collection_url": "https://www.law.go.kr", "credibility": 0.95, "note": "법령 및 행정규칙"},
    {"domain": "data.go.kr", "name": "공공데이터포털", "source_type": "public", "collection_url": "https://www.data.go.kr", "credibility": 0.88, "note": "공공 데이터"},
    {"domain": "kostat.go.kr", "name": "통계청", "source_type": "statistics", "collection_url": "https://kostat.go.kr", "credibility": 0.95, "note": "국가 통계"},
    {"domain": "nec.go.kr", "name": "중앙선거관리위원회", "source_type": "official", "collection_url": "https://www.nec.go.kr", "credibility": 0.95, "note": "선거 공식자료"},
    {"domain": "mohw.go.kr", "name": "보건복지부", "source_type": "official", "collection_url": "https://www.mohw.go.kr", "credibility": 0.93, "note": "보건복지 공식자료"},
    {"domain": "kdca.go.kr", "name": "질병관리청", "source_type": "official", "collection_url": "https://www.kdca.go.kr", "credibility": 0.93, "note": "감염병 및 보건 통계"},
    {"domain": "moef.go.kr", "name": "기획재정부", "source_type": "official", "collection_url": "https://www.moef.go.kr", "credibility": 0.92, "note": "경제정책 공식자료"},
    {"domain": "bok.or.kr", "name": "한국은행", "source_type": "statistics", "collection_url": "https://www.bok.or.kr", "credibility": 0.94, "note": "경제 통계 및 금융 자료"},
    {"domain": "molit.go.kr", "name": "국토교통부", "source_type": "official", "collection_url": "https://www.molit.go.kr", "credibility": 0.92, "note": "부동산·교통 공식자료"},
    {"domain": "mofa.go.kr", "name": "외교부", "source_type": "official", "collection_url": "https://www.mofa.go.kr", "credibility": 0.92, "note": "외교 공식자료"},
    {"domain": "police.go.kr", "name": "경찰청", "source_type": "official", "collection_url": "https://www.police.go.kr", "credibility": 0.9, "note": "수사·치안 공식자료"},
    {"domain": "nfa.go.kr", "name": "소방청", "source_type": "official", "collection_url": "https://www.nfa.go.kr", "credibility": 0.9, "note": "재난·소방 공식자료"},
    {"domain": "fsc.go.kr", "name": "금융위원회", "source_type": "official", "collection_url": "https://www.fsc.go.kr", "credibility": 0.91, "note": "금융정책 공식자료"},
    {"domain": "ftc.go.kr", "name": "공정거래위원회", "source_type": "official", "collection_url": "https://www.ftc.go.kr", "credibility": 0.91, "note": "시장·기업 공정거래 공식자료"},
)


def seed_default_source_domains(db: Session) -> int:
    created = 0
    for row in DEFAULT_SOURCE_DOMAINS:
        existing = db.scalar(select(models.SourceDomain).where(models.SourceDomain.domain == row["domain"]))
        if existing:
            existing.name = row["name"]
            existing.source_type = row["source_type"]
            existing.collection_url = row["collection_url"]
            existing.credibility = row["credibility"]
            existing.note = row["note"]
            existing.is_active = True
            existing.status = "watch"
            existing.last_reviewed_at = models.now_utc()
            continue
        db.add(
            models.SourceDomain(
                id=f"source_{row['domain'].replace('.', '_')}",
                domain=row["domain"],
                name=row["name"],
                source_type=row["source_type"],
                collection_url=row["collection_url"],
                credibility=row["credibility"],
                note=row["note"],
                is_active=True,
                status="watch",
            ),
        )
        created += 1
    db.flush()
    return created
```

- [ ] **Step 5: Call source seeding from defaults bootstrap**

In `facttracer-backend/app/services/bootstrap/defaults.py`, import and call source seeding inside the existing bootstrap function:

```python
from app.services.bootstrap.sources import seed_default_source_domains
```

Then, after default discovery topics are seeded:

```python
    seed_default_source_domains(db)
```

- [ ] **Step 6: Verify router/bootstrap tests pass**

Run:

```bash
cd facttracer-backend
pytest \
  tests/test_api.py::test_source_router_adds_official_domains_for_public_issue \
  tests/test_api.py::test_seed_default_source_domains_are_broad_categories -q
```

Expected: PASS.

---

### Task 4: Search Providers And Optional OpenAI Web Search

**Files:**
- Create: `facttracer-backend/app/services/research/providers.py`
- Create: `facttracer-backend/app/services/ai/openai_web_search.py`
- Modify: `facttracer-backend/app/core/config.py`
- Modify: `facttracer-backend/app/services/admin/settings.py`
- Test: `facttracer-backend/tests/test_api.py`

- [ ] **Step 1: Write failing provider tests**

Append:

```python
def test_site_query_provider_builds_site_restricted_google_news_query(monkeypatch) -> None:
    from app.collectors.base import CollectedArticle
    from app.services.research.providers import SiteQueryProvider

    captured: list[str] = []

    def fake_collect(query: str, *, max_items: int = 30, publisher: str = "Google News", **kwargs):
        captured.append(query)
        return [CollectedArticle(title="선관위 설명자료", url="https://www.nec.go.kr/notice", publisher="중앙선거관리위원회")]

    monkeypatch.setattr("app.services.research.providers.collect_google_news_search", fake_collect)
    provider = SiteQueryProvider()
    results = provider.search(
        query="선관위 투표용지 부족",
        route={"domain": "nec.go.kr", "name": "중앙선거관리위원회", "sourceType": "official"},
        max_items=3,
    )
    assert captured == ["site:nec.go.kr 선관위 투표용지 부족"]
    assert results[0].source_type == "official"
    assert results[0].publisher == "중앙선거관리위원회"


def test_openai_web_search_provider_disabled_without_setting() -> None:
    from app.services.ai.openai_web_search import OpenAIWebSearchProvider

    db = SessionLocal()
    try:
        provider = OpenAIWebSearchProvider(db)
        assert provider.enabled is False
        assert provider.search_sources("선관위 투표용지 부족", max_items=3) == []
    finally:
        db.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd facttracer-backend
pytest \
  tests/test_api.py::test_site_query_provider_builds_site_restricted_google_news_query \
  tests/test_api.py::test_openai_web_search_provider_disabled_without_setting -q
```

Expected: FAIL because provider modules do not exist.

- [ ] **Step 3: Add provider classes**

Create `facttracer-backend/app/services/research/providers.py`:

```python
from __future__ import annotations

from typing import Any, Protocol

from app.collectors.base import CollectedArticle
from app.collectors.news_search import collect_google_news_search


class SearchProvider(Protocol):
    name: str

    def search(self, *, query: str, route: dict[str, Any], max_items: int) -> list[CollectedArticle]:
        ...


class GoogleNewsProvider:
    name = "google_news"

    def search(self, *, query: str, route: dict[str, Any] | None = None, max_items: int = 10) -> list[CollectedArticle]:
        return collect_google_news_search(query, max_items=max_items)


class SiteQueryProvider:
    name = "site_query"

    def search(self, *, query: str, route: dict[str, Any], max_items: int = 10) -> list[CollectedArticle]:
        domain = str(route.get("domain") or "").strip()
        if not domain:
            return []
        site_query = f"site:{domain} {query}".strip()
        source_type = str(route.get("sourceType") or "official")
        publisher = str(route.get("name") or domain)
        rows = collect_google_news_search(site_query, max_items=max_items, publisher=publisher)
        for row in rows:
            row.source_type = source_type
            row.publisher = row.publisher or publisher
        return rows


def provider_for_route(route: dict[str, Any]) -> SearchProvider:
    provider = str(route.get("provider") or "google_news")
    if provider == "site_query":
        return SiteQueryProvider()
    return GoogleNewsProvider()
```

- [ ] **Step 4: Add OpenAI web search wrapper**

Create `facttracer-backend/app/services/ai/openai_web_search.py`:

```python
from __future__ import annotations

from typing import Any

from openai import OpenAI
from sqlalchemy.orm import Session

from app.collectors.base import CollectedArticle
from app.services.admin.settings import get_effective_setting


class OpenAIWebSearchProvider:
    name = "openai_web_search"

    def __init__(self, db: Session | None = None) -> None:
        self.api_key = get_effective_setting(db, "openai_api_key")
        self.enabled_setting = bool(get_effective_setting(db, "openai_web_search_enabled", False))
        self.model = str(get_effective_setting(db, "openai_web_search_model", "gpt-5.5"))
        self._client: OpenAI | None = None

    @property
    def enabled(self) -> bool:
        return bool(self.enabled_setting and self.api_key)

    @property
    def client(self) -> OpenAI:
        if not self.api_key:
            raise RuntimeError("OpenAI API key is not configured")
        if self._client is None:
            self._client = OpenAI(api_key=self.api_key, timeout=30)
        return self._client

    def search_sources(self, query: str, *, max_items: int = 5) -> list[dict[str, Any]]:
        if not self.enabled:
            return []
        response = self.client.responses.create(
            model=self.model,
            tools=[{"type": "web_search"}],
            include=["web_search_call.action.sources"],
            input=(
                "Find current Korean news and official/public sources for this FactTracer research query. "
                "Return concise source candidates with title, url, publisher, and why relevant.\n"
                f"Query: {query}"
            ),
        )
        sources: list[dict[str, Any]] = []
        for item in getattr(response, "output", []) or []:
            action = getattr(item, "action", None)
            for source in getattr(action, "sources", []) or []:
                url = getattr(source, "url", "") or (source.get("url") if isinstance(source, dict) else "")
                title = getattr(source, "title", "") or (source.get("title") if isinstance(source, dict) else "")
                if url:
                    sources.append({"url": url, "title": title or url, "publisher": "", "reason": "openai web search"})
                if len(sources) >= max_items:
                    return sources
        return sources[:max_items]

    def search(self, *, query: str, route: dict[str, Any] | None = None, max_items: int = 5) -> list[CollectedArticle]:
        rows = []
        for source in self.search_sources(query, max_items=max_items):
            rows.append(
                CollectedArticle(
                    title=str(source.get("title") or source.get("url") or ""),
                    url=str(source.get("url") or ""),
                    publisher=str(source.get("publisher") or "OpenAI Web Search"),
                    source_type=str((route or {}).get("sourceType") or "web_search"),
                    summary=str(source.get("reason") or ""),
                ),
            )
        return rows
```

- [ ] **Step 5: Add settings**

Add to `Settings` in `facttracer-backend/app/core/config.py`:

```python
    research_max_rounds: int = 2
    research_max_queries_per_round: int = 16
    research_max_results_per_query: int = 8
    research_openai_fallback_after_round: int = 2
    openai_web_search_enabled: bool = False
    openai_web_search_model: str = Field(default="gpt-5.5", validation_alias="OPENAI_WEB_SEARCH_MODEL")
```

Add to `DEFINITIONS` in `facttracer-backend/app/services/admin/settings.py`:

```python
    SettingDefinition("research_max_rounds", "automation", "리서치 최대 라운드", "이슈 하나당 자동 재탐색 라운드 상한", "integer", min_value=1, max_value=5),
    SettingDefinition("research_max_queries_per_round", "automation", "라운드당 검색어 수", "리서치 라운드 하나에서 실행할 검색어 상한", "integer", min_value=1, max_value=50),
    SettingDefinition("research_max_results_per_query", "automation", "검색어당 결과 수", "리서치 검색어 하나에서 가져올 결과 상한", "integer", min_value=1, max_value=30),
    SettingDefinition("research_openai_fallback_after_round", "automation", "OpenAI 검색 전환 라운드", "해당 라운드 이후에도 근거가 부족하면 OpenAI web_search를 사용할 수 있습니다", "integer", min_value=1, max_value=5),
    SettingDefinition("openai_web_search_enabled", "ai", "OpenAI Web Search", "OpenAI Responses API web_search 보조 사용 여부", "boolean"),
    SettingDefinition("openai_web_search_model", "ai", "OpenAI Web Search 모델", "web_search 도구 호출에 사용할 모델", "string"),
```

- [ ] **Step 6: Verify provider tests pass**

Run:

```bash
cd facttracer-backend
pytest \
  tests/test_api.py::test_site_query_provider_builds_site_restricted_google_news_query \
  tests/test_api.py::test_openai_web_search_provider_disabled_without_setting -q
```

Expected: PASS.

---

### Task 5: Research Executor And `research_issue` Job

**Files:**
- Create: `facttracer-backend/app/services/research/executor.py`
- Modify: `facttracer-backend/app/workers/issue_jobs.py`
- Modify: `facttracer-backend/app/services/jobs.py`
- Test: `facttracer-backend/tests/test_api.py`

- [ ] **Step 1: Write failing executor/job test**

Append:

```python
def test_research_issue_collects_articles_and_writes_trace(monkeypatch) -> None:
    from app.collectors.base import CollectedArticle
    from app.workers.issue_jobs import research_issue

    def fake_execute_provider_query(*, db, provider, query, route, max_items):
        return [
            CollectedArticle(
                title="선관위 투표용지 부족 후속 보도",
                url="https://example.com/research-article",
                publisher="예시뉴스",
                source_type="news_search",
                summary="후속 보도 요약",
            ),
        ]

    monkeypatch.setattr("app.services.research.executor._execute_provider_query", fake_execute_provider_query)

    db = SessionLocal()
    try:
        issue = models.Issue(
            id="issue_research_job",
            title="선관위 투표용지 부족 사태",
            topic="정치",
            is_public=True,
            quality_report_json={"missingSignals": ["officialCoverage"]},
        )
        db.add(issue)
        db.commit()
    finally:
        db.close()

    result = research_issue(issue_id="issue_research_job", trigger_type="quality_gap")
    assert result["status"] == "completed"
    assert result["created"] == 1
    assert result["research_run_id"]

    db = SessionLocal()
    try:
        trace = db.get(models.ResearchRun, result["research_run_id"])
        assert trace is not None
        assert trace.issue_id == "issue_research_job"
        assert trace.selected_article_ids_json
        article = db.query(models.Article).filter(models.Article.url == "https://example.com/research-article").one()
        assert article.issue_id == "issue_research_job"
    finally:
        db.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd facttracer-backend
pytest tests/test_api.py::test_research_issue_collects_articles_and_writes_trace -q
```

Expected: FAIL because `research_issue` and executor do not exist.

- [ ] **Step 3: Add executor**

Create `facttracer-backend/app/services/research/executor.py`:

```python
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app import models
from app.collectors.base import CollectedArticle
from app.services.admin.settings import get_effective_setting
from app.services.articles.normalizer import normalize_url
from app.services.research.planner import build_research_plan
from app.services.research.providers import provider_for_route
from app.services.research.router import route_sources_for_plan
from app.utils import new_id


def _duration_ms(started_at: datetime) -> int:
    return int((datetime.now(UTC) - started_at).total_seconds() * 1000)


def _execute_provider_query(
    *,
    db: Session,
    provider: Any,
    query: str,
    route: dict[str, Any],
    max_items: int,
) -> list[CollectedArticle]:
    return provider.search(query=query, route=route, max_items=max_items)


def _dedupe_collected(rows: list[CollectedArticle]) -> list[CollectedArticle]:
    seen: set[str] = set()
    deduped: list[CollectedArticle] = []
    for row in rows:
        key = normalize_url(row.url) or row.url
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


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
    routes = route_sources_for_plan(db, plan=plan)
    run = models.ResearchRun(
        id=new_id("research"),
        discovery_topic_id=discovery_topic_id,
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
    max_items = int(get_effective_setting(db, "research_max_results_per_query") or 8)
    collected: list[CollectedArticle] = []
    executed_queries: list[dict[str, Any]] = []
    result_urls: list[dict[str, Any]] = []

    try:
        for route in routes:
            provider = provider_for_route(route)
            for query_row in (plan.get("queries") or [])[:max_queries]:
                query = str(query_row.get("query") or "").strip()
                if not query:
                    continue
                provider_rows = _execute_provider_query(
                    db=db,
                    provider=provider,
                    query=query,
                    route=route,
                    max_items=max_items,
                )
                executed_queries.append(
                    {
                        "provider": getattr(provider, "name", "unknown"),
                        "query": query,
                        "route": route,
                        "resultCount": len(provider_rows),
                    },
                )
                collected.extend(provider_rows)

        created = 0
        parse_jobs = 0
        selected_article_ids: list[str] = []
        for row in _dedupe_collected(collected):
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
            result_urls.append(
                {
                    "url": row.url,
                    "title": row.title,
                    "publisher": row.publisher,
                    "sourceType": row.source_type,
                    "selected": True,
                    "articleId": article.id,
                    "created": was_created,
                    "reason": "deduped and linked",
                },
            )

        run.status = "completed"
        run.executed_queries_json = executed_queries
        run.result_urls_json = result_urls
        run.selected_article_ids_json = selected_article_ids
        run.finished_at = models.now_utc()
        run.duration_ms = _duration_ms(started_at)
        db.flush()
        return {
            "status": "completed",
            "research_run_id": run.id,
            "collected": len(collected),
            "created": created,
            "linked": len(selected_article_ids),
            "parse_jobs": parse_jobs,
            "executed_queries": len(executed_queries),
        }
    except Exception as exc:
        run.status = "failed"
        run.error_message = str(exc)
        run.executed_queries_json = executed_queries
        run.result_urls_json = result_urls
        run.finished_at = models.now_utc()
        run.duration_ms = _duration_ms(started_at)
        db.flush()
        return {"status": "failed", "research_run_id": run.id, "error": str(exc)}
```

- [ ] **Step 4: Add worker job**

In `facttracer-backend/app/workers/issue_jobs.py`, add:

```python
def research_issue(
    issue_id: str | None = None,
    *,
    keyword_id: str | None = None,
    missing_signals: list[str] | None = None,
    round_index: int = 1,
    seed_query: str = "",
    trigger_type: str = "manual",
) -> dict:
    from app.services.research.executor import execute_research_plan

    db = SessionLocal()
    try:
        issue = db.get(models.Issue, issue_id) if issue_id else None
        if issue_id and not issue:
            return {"status": "not_found", "created": 0}
        if issue and not missing_signals:
            missing_signals = list((issue.quality_report_json or {}).get("missingSignals") or [])
        result = execute_research_plan(
            db,
            issue=issue,
            keyword_id=keyword_id,
            missing_signals=missing_signals or [],
            round_index=round_index,
            seed_query=seed_query,
            trigger_type=trigger_type,
        )
        if issue:
            refresh_issue_cache(db, issue_id=issue.id)
            _enqueue_issue_enrichment_jobs(db, issue_id=issue.id)
        db.commit()
        return result
    except Exception as exc:
        db.rollback()
        return {"status": "failed", "created": 0, "error": str(exc)}
    finally:
        db.close()
```

- [ ] **Step 5: Register job handler**

In `_handlers()` in `facttracer-backend/app/services/jobs.py`, add:

```python
        "research_issue": issue_jobs.research_issue,
```

- [ ] **Step 6: Verify executor/job test passes**

Run:

```bash
cd facttracer-backend
pytest tests/test_api.py::test_research_issue_collects_articles_and_writes_trace -q
```

Expected: PASS.

---

### Task 6: Integrate Research Burst Into Discovery, Keyword Search, And Quality

**Files:**
- Modify: `facttracer-backend/app/workers/issue_jobs.py`
- Modify: `facttracer-backend/app/services/issues/quality.py`
- Test: `facttracer-backend/tests/test_api.py`

- [ ] **Step 1: Write failing integration test**

Append:

```python
def test_discovery_promoted_issue_queues_research_before_parse(monkeypatch) -> None:
    db = SessionLocal()
    try:
        issue = models.Issue(
            id="issue_research_queue",
            title="큰 사건",
            topic="사회",
            is_public=True,
        )
        db.add(issue)
        db.commit()
    finally:
        db.close()

    from app.workers.issue_jobs import _enqueue_research_issue_job

    db = SessionLocal()
    try:
        queued = _enqueue_research_issue_job(db, issue_id="issue_research_queue", trigger_type="discovery_burst")
        db.commit()
        assert queued is True
        jobs = db.query(models.JobAttempt).filter(models.JobAttempt.target_id == "issue_research_queue").all()
        assert [job.job_type for job in jobs] == ["research_issue"]
        assert jobs[0].input_json["trigger_type"] == "discovery_burst"
    finally:
        db.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd facttracer-backend
pytest tests/test_api.py::test_discovery_promoted_issue_queues_research_before_parse -q
```

Expected: FAIL because `_enqueue_research_issue_job` does not exist.

- [ ] **Step 3: Add singleton enqueue helper**

In `facttracer-backend/app/workers/issue_jobs.py`, add near `_enqueue_singleton_job`:

```python
def _enqueue_research_issue_job(
    db: Session,
    *,
    issue_id: str,
    missing_signals: list[str] | None = None,
    round_index: int = 1,
    seed_query: str = "",
    trigger_type: str,
) -> bool:
    existing = db.scalar(
        select(models.JobAttempt.id).where(
            models.JobAttempt.job_type == "research_issue",
            models.JobAttempt.target_id == issue_id,
            models.JobAttempt.status.in_(["queued", "running"]),
        ),
    )
    if existing:
        return False
    from app.services.jobs import enqueue_job

    enqueue_job(
        db,
        input_json={
            "issue_id": issue_id,
            "missing_signals": missing_signals or [],
            "round_index": round_index,
            "seed_query": seed_query,
            "trigger_type": trigger_type,
        },
        job_type="research_issue",
        run_immediately=False,
        target_id=issue_id,
    )
    return True
```

- [ ] **Step 4: Use research burst after discovery promotion**

Inside `discover_topic()`, after `issue = _ensure_discovery_issue(...)` and before parse jobs are enqueued, add:

```python
                research_job_queued = _enqueue_research_issue_job(
                    db,
                    issue_id=issue.id,
                    seed_query=str(definition.get("title") or issue.title),
                    trigger_type="discovery_burst",
                )
```

Add this field to the `promoted.append(...)` payload:

```python
                        "research_job": research_job_queued,
```

- [ ] **Step 5: Use research burst for quality retry**

In `assess_issue_quality()` in `facttracer-backend/app/services/issues/quality.py`, keep existing keyword creation and add a metadata signal:

```python
    report["researchTrigger"] = {
        "issueId": issue.id,
        "missingSignals": missing_signals,
        "reason": "quality_gap",
    }
```

In `assess_issue_quality_job()` in `issue_jobs.py`, after calling `assess_issue_quality`, enqueue research when status is `needs_retry`:

```python
        if result.get("status") == "needs_retry":
            _enqueue_research_issue_job(
                db,
                issue_id=issue_id,
                missing_signals=list(result.get("missingSignals") or []),
                round_index=int(issue.quality_attempts or 1) if issue else 1,
                seed_query=issue.title if issue else "",
                trigger_type="quality_gap",
            )
```

- [ ] **Step 6: Verify integration test passes**

Run:

```bash
cd facttracer-backend
pytest tests/test_api.py::test_discovery_promoted_issue_queues_research_before_parse -q
```

Expected: PASS.

---

### Task 7: Worker Throughput And Job Priority

**Files:**
- Modify: `facttracer-backend/app/core/config.py`
- Modify: `facttracer-backend/app/services/admin/settings.py`
- Modify: `facttracer-backend/app/services/scheduler/runtime.py`
- Modify: `facttracer-backend/app/services/jobs.py`
- Modify: `docker-compose.yml`
- Test: `facttracer-backend/tests/test_api.py`

- [ ] **Step 1: Write failing priority/batch tests**

Append:

```python
def test_collection_jobs_have_priority_over_parse_backlog() -> None:
    from app.services.jobs import run_due_jobs

    executed: list[str] = []

    db = SessionLocal()
    try:
        db.add_all(
            [
                models.JobAttempt(id="job_parse_backlog", job_type="parse_article", target_id="article_1", status="queued"),
                models.JobAttempt(id="job_research", job_type="research_issue", target_id="issue_1", status="queued"),
            ],
        )
        db.commit()

        import app.services.jobs as jobs_module

        original_execute_job = jobs_module.execute_job

        def fake_execute_job(db, *, job):
            executed.append(job.job_type)
            job.status = "completed"
            return job

        jobs_module.execute_job = fake_execute_job
        try:
            run_due_jobs(db, limit=1)
        finally:
            jobs_module.execute_job = original_execute_job

        assert executed == ["research_issue"]
    finally:
        db.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd facttracer-backend
pytest tests/test_api.py::test_collection_jobs_have_priority_over_parse_backlog -q
```

Expected: FAIL because current `run_due_jobs()` prioritizes parse/enrichment before collection/research.

- [ ] **Step 3: Add worker batch setting**

Add to `Settings`:

```python
    embedded_worker_batch_size: int = 5
```

Add to `DEFINITIONS`:

```python
    SettingDefinition(
        "embedded_worker_batch_size",
        "automation",
        "워커 배치 크기",
        "내장 워커가 한 번에 처리할 작업 수",
        "integer",
        min_value=1,
        max_value=50,
        is_runtime_mutable=False,
    ),
```

- [ ] **Step 4: Use batch size in embedded worker**

In `EmbeddedWorker._loop()` in `facttracer-backend/app/services/scheduler/runtime.py`, replace:

```python
                    run_due_jobs(db, limit=1)
```

with:

```python
                    batch_size = int(get_effective_setting(db, "embedded_worker_batch_size") or 1)
                    run_due_jobs(db, limit=max(1, batch_size))
```

- [ ] **Step 5: Adjust job priority**

In `run_due_jobs()` in `facttracer-backend/app/services/jobs.py`, replace `job_priority = case(...)` with:

```python
    job_priority = case(
        (
            models.JobAttempt.job_type.in_(
                [
                    "research_issue",
                    "search_news",
                    "collect_source",
                    "collect_sources",
                    "backfill_issue_sources",
                    "discover_topic",
                ],
            ),
            0,
        ),
        (
            models.JobAttempt.job_type.in_(
                [
                    "parse_article",
                    "extract_claims",
                    "cluster_claim",
                    "retrieve_evidence",
                    "verify_claim",
                    "update_issue_page",
                    "assess_issue_quality",
                    "select_representative_image",
                ],
            ),
            5,
        ),
        (
            models.JobAttempt.job_type.in_(["generate_podcasts", "render_podcast_audio"]),
            8,
        ),
        else_=10,
    )
```

- [ ] **Step 6: Update local compose speed**

In `docker-compose.yml`, set API environment:

```yaml
      FACTTRACER_EMBEDDED_WORKER_POLL_SECONDS: "1"
      FACTTRACER_EMBEDDED_WORKER_BATCH_SIZE: "5"
```

- [ ] **Step 7: Verify priority test passes**

Run:

```bash
cd facttracer-backend
pytest tests/test_api.py::test_collection_jobs_have_priority_over_parse_backlog -q
```

Expected: PASS.

---

### Task 8: Generic Keyword Fallback Cleanup

**Files:**
- Modify: `facttracer-backend/app/services/search/keywords.py`
- Test: `facttracer-backend/tests/test_api.py`

- [ ] **Step 1: Write failing cleanup test**

Append:

```python
def test_generic_keyword_fallback_does_not_inject_election_terms_for_unrelated_queries() -> None:
    from app.services.search.keywords import fallback_keyword_variants

    variants = fallback_keyword_variants("병원 진료 대기 논란")
    joined = " ".join(variants)
    assert "선관위" not in joined
    assert "투표용지" not in joined
    assert any("후속" in value or "해명" in value for value in variants)
```

- [ ] **Step 2: Run test**

Run:

```bash
cd facttracer-backend
pytest tests/test_api.py::test_generic_keyword_fallback_does_not_inject_election_terms_for_unrelated_queries -q
```

Expected: PASS today for unrelated queries. Keep it as a regression guard.

- [ ] **Step 3: Reduce hard-coded election expansion**

In `facttracer-backend/app/services/search/keywords.py`, keep only generic follow-up expansion in `fallback_keyword_variants()`. Remove the broad election-specific cross-product block:

```python
    if has_election_entity or has_election_issue:
        for entity in ELECTION_ENTITY_VARIANTS[:3]:
            for term in ELECTION_ISSUE_TERMS[:5]:
                if entity in query or term in query:
                    _append_unique(variants, f"{entity} {term}")
        for followup in FOLLOWUP_TERMS[:8]:
            _append_unique(variants, f"{query} {followup}")
```

Replace it with:

```python
    for anchor in _head_terms(tokens)[:2]:
        for followup in FOLLOWUP_TERMS[:5]:
            _append_unique(variants, f"{anchor} {followup}")
    for followup in FOLLOWUP_TERMS[:6]:
        _append_unique(variants, f"{query} {followup}")
```

The richer domain-specific expansion now belongs to `build_research_plan()`.

- [ ] **Step 4: Verify keyword tests**

Run:

```bash
cd facttracer-backend
pytest tests/test_api.py::test_generic_keyword_fallback_does_not_inject_election_terms_for_unrelated_queries -q
```

Expected: PASS.

---

### Task 9: Admin Research Trace API

**Files:**
- Modify: `facttracer-backend/app/api/routes/admin.py`
- Modify: `facttracer-backend/app/schemas.py`
- Test: `facttracer-backend/tests/test_api.py`

- [ ] **Step 1: Write failing API test**

Append:

```python
def test_admin_can_read_issue_research_runs() -> None:
    from app.core.security import create_access_token, hash_password

    db = SessionLocal()
    try:
        admin = models.User(
            id="admin_research_runs",
            email="admin-research@example.com",
            password_hash=hash_password("password123"),
            name="Admin",
            role="admin",
        )
        issue = models.Issue(id="issue_admin_research", title="수집 근거 테스트", topic="사회", is_public=True)
        run = models.ResearchRun(
            id="research_admin_1",
            issue_id=issue.id,
            trigger_type="manual",
            seed_query="수집 근거 테스트",
            status="completed",
            plan_json={"queries": [{"query": "수집 근거 테스트", "purpose": "core"}]},
            executed_queries_json=[{"provider": "google_news", "query": "수집 근거 테스트"}],
            result_urls_json=[{"url": "https://example.com", "selected": True}],
        )
        db.add_all([admin, issue, run])
        db.commit()
    finally:
        db.close()

        token, _ = create_access_token("admin_research_runs", "admin")
    with TestClient(app) as client:
        response = client.get(
            "/v1/admin/issues/issue_admin_research/research-runs",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["items"][0]["id"] == "research_admin_1"
        assert payload["items"][0]["executedQueries"][0]["provider"] == "google_news"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd facttracer-backend
pytest tests/test_api.py::test_admin_can_read_issue_research_runs -q
```

Expected: FAIL with 404.

- [ ] **Step 3: Add schemas**

In `facttracer-backend/app/schemas.py`, add:

```python
class ResearchRunItem(BaseModel):
    id: str
    issueId: str | None = None
    triggerType: str
    seedQuery: str
    status: str
    roundIndex: int
    plan: dict = Field(default_factory=dict)
    sourceRoutes: list = Field(default_factory=list)
    executedQueries: list = Field(default_factory=list)
    resultUrls: list = Field(default_factory=list)
    selectedArticleIds: list = Field(default_factory=list)
    missingSignals: list = Field(default_factory=list)
    errorMessage: str = ""
    startedAt: str | None = None
    finishedAt: str | None = None
    durationMs: int = 0


class ResearchRunListResponse(BaseModel):
    items: list[ResearchRunItem]
```

- [ ] **Step 4: Add admin route**

In `facttracer-backend/app/api/routes/admin.py`, first add these names to the existing `from app.schemas import (...)` block:

```python
    ResearchRunItem,
    ResearchRunListResponse,
```

Then add the route:

```python
@router.get("/issues/{issue_id}/research-runs", response_model=ResearchRunListResponse)
def list_issue_research_runs(
    issue_id: str,
    _: Annotated[models.User, Depends(reviewer_user)],
    db: Session = Depends(get_db),
) -> ResearchRunListResponse:
    rows = db.scalars(
        select(models.ResearchRun)
        .where(models.ResearchRun.issue_id == issue_id)
        .order_by(models.ResearchRun.started_at.desc())
        .limit(20),
    ).all()
    return ResearchRunListResponse(
        items=[
            ResearchRunItem(
                id=row.id,
                issueId=row.issue_id,
                triggerType=row.trigger_type,
                seedQuery=row.seed_query,
                status=row.status,
                roundIndex=row.round_index,
                plan=row.plan_json or {},
                sourceRoutes=row.source_routes_json or [],
                executedQueries=row.executed_queries_json or [],
                resultUrls=row.result_urls_json or [],
                selectedArticleIds=row.selected_article_ids_json or [],
                missingSignals=row.missing_signals_json or [],
                errorMessage=row.error_message,
                startedAt=to_iso(row.started_at),
                finishedAt=to_iso(row.finished_at),
                durationMs=row.duration_ms,
            )
            for row in rows
        ],
    )
```

Ensure `select` and `to_iso` are imported if missing:

```python
from sqlalchemy import select
from app.utils import to_iso
```

- [ ] **Step 5: Verify API test passes**

Run:

```bash
cd facttracer-backend
pytest tests/test_api.py::test_admin_can_read_issue_research_runs -q
```

Expected: PASS.

---

### Task 10: End-To-End Verification

**Files:**
- `facttracer-backend/tests/test_api.py`
- `docker-compose.yml`

- [ ] **Step 1: Run focused backend tests**

Run:

```bash
cd facttracer-backend
pytest \
  tests/test_api.py::test_research_run_persists_collection_evidence \
  tests/test_api.py::test_research_planner_builds_purpose_based_queries_without_narrow_default_topic \
  tests/test_api.py::test_source_router_adds_official_domains_for_public_issue \
  tests/test_api.py::test_seed_default_source_domains_are_broad_categories \
  tests/test_api.py::test_site_query_provider_builds_site_restricted_google_news_query \
  tests/test_api.py::test_openai_web_search_provider_disabled_without_setting \
  tests/test_api.py::test_research_issue_collects_articles_and_writes_trace \
  tests/test_api.py::test_discovery_promoted_issue_queues_research_before_parse \
  tests/test_api.py::test_collection_jobs_have_priority_over_parse_backlog \
  tests/test_api.py::test_generic_keyword_fallback_does_not_inject_election_terms_for_unrelated_queries \
  tests/test_api.py::test_admin_can_read_issue_research_runs -q
```

Expected: all listed tests PASS.

- [ ] **Step 2: Run full backend tests**

Run:

```bash
cd facttracer-backend
pytest -q
```

Expected: all backend tests PASS.

- [ ] **Step 3: Run migration check from clean DB**

Run:

```bash
cd facttracer-backend
rm -f /tmp/facttracer-agentic-plan.db
DATABASE_URL=sqlite:////tmp/facttracer-agentic-plan.db alembic upgrade head
DATABASE_URL=sqlite:////tmp/facttracer-agentic-plan.db python - <<'PY'
from sqlalchemy import create_engine, inspect
engine = create_engine("sqlite:////tmp/facttracer-agentic-plan.db")
tables = set(inspect(engine).get_table_names())
assert "research_runs" in tables
print("research_runs ok")
PY
```

Expected output:

```text
research_runs ok
```

- [ ] **Step 4: Rebuild and run local services**

Run:

```bash
docker compose up -d --build api web
docker compose ps
```

Expected: `api` is healthy and `web` is running.

- [ ] **Step 5: Verify first collection wave produces traces**

Run:

```bash
docker compose exec -T api python - <<'PY'
from sqlalchemy import select
from app.db.session import SessionLocal
from app import models

db = SessionLocal()
try:
    print("topics", db.query(models.DiscoveryTopic).filter(models.DiscoveryTopic.status == "active").count())
    print("sources", db.query(models.SourceDomain).filter(models.SourceDomain.is_active.is_(True)).count())
    print("research_runs", db.query(models.ResearchRun).count())
    jobs = db.scalars(select(models.JobAttempt).order_by(models.JobAttempt.created_at.desc()).limit(10)).all()
    print([(job.job_type, job.status) for job in jobs])
finally:
    db.close()
PY
```

Expected after the scheduler/worker has run: active broad topics exist, source domains are seeded, and `research_issue` jobs or `ResearchRun` rows appear after a discovery promotion or quality gap.

## Acceptance Criteria

- Default discovery topics remain broad categories, not narrow issues such as “선거 관리 감시”.
- A promoted issue can immediately queue `research_issue` so first-run/breaking-news pages are less likely to have zero articles.
- Research traces show seed query, generated queries, source routes, executed provider calls, selected URLs, and missing signals.
- Official/public source routing can produce `site:<domain> <query>` searches from seeded `SourceDomain` rows.
- Quality gaps trigger bounded research rounds, not only static keyword retries.
- Worker processes a configurable batch size and prioritizes collection/research before parse backlog.
- OpenAI `web_search` is optional, disabled by default, and auditable when enabled.
- Full backend test suite passes.

## Execution Notes

- Implement this after the existing `0002_collection_classification_ranking` and `0003_podcast_episodes` migrations are stable.
- Keep OpenAI web search behind settings until cost and result quality are measured.
- Do not add narrow issue names to default discovery topics. Narrow terms belong in planner output, `SearchKeyword`, `ResearchRun`, or issue-specific metadata.
- For the current Docker environment, use embedded scheduler/worker with `FACTTRACER_EMBEDDED_WORKER_BATCH_SIZE=5` during local validation.
