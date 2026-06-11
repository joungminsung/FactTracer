# Backend Collection Classification Ranking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add automatic major-topic/event-group classification, representative images, quality-driven re-search, issue synthesis, and ranking/personalization for FactTracer.

**Architecture:** Add additive DB fields and focused backend services around the existing `Issue`, discovery, search, worker, and cache-refresh pipeline. Keep existing API fields backward-compatible while adding taxonomy, image, quality, and rank metadata. Integrate frontend rendering only after backend contract tests pass.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy, SQLite/PostgreSQL-ready models, pytest, Next.js/TypeScript.

---

## File Structure

Create:

- `facttracer-backend/app/services/classification/__init__.py` - classification package marker.
- `facttracer-backend/app/services/classification/taxonomy.py` - deterministic major-topic/event-group matching and creation.
- `facttracer-backend/app/services/images/__init__.py` - image service package marker.
- `facttracer-backend/app/services/images/candidates.py` - image URL extraction and candidate persistence.
- `facttracer-backend/app/services/images/selector.py` - candidate scoring and representative image selection.
- `facttracer-backend/app/services/issues/quality.py` - issue quality report and bounded re-search triggers.
- `facttracer-backend/app/services/issues/ranking.py` - issue ranking and personalization.
- `facttracer-backend/app/services/issues/synthesis.py` - DB-grounded issue detail synthesis before cache refresh.
- `facttracer-backend/scripts/backfill_issue_taxonomy.py` - local backfill entrypoint for existing issues.

Modify:

- `facttracer-backend/app/models.py` - add `MajorTopic`, `EventGroup`, `ImageCandidate`, `UserInterestProfile`; extend `Issue` and `CollectedArticle` flow support.
- `facttracer-backend/app/schemas.py` - add public API fields and sort query response metadata.
- `facttracer-backend/app/serializers.py` - serialize taxonomy, image, rank metadata.
- `facttracer-backend/app/collectors/base.py` - carry collected image candidates.
- `facttracer-backend/app/collectors/news_search.py` - extract RSS image candidates when present.
- `facttracer-backend/app/services/articles/parser.py` - extract HTML image candidates from submitted/fetched URLs.
- `facttracer-backend/app/services/discovery/incident_detector.py` - include taxonomy signals in incident definitions.
- `facttracer-backend/app/workers/issue_jobs.py` - call classification, image, quality, synthesis jobs in collection flows.
- `facttracer-backend/app/services/jobs.py` - register and prioritize new jobs.
- `facttracer-backend/app/services/admin/settings.py` - add runtime settings for quality and ranking thresholds.
- `facttracer-backend/app/core/config.py` - add matching env-backed defaults.
- `facttracer-backend/app/services/issues/page_builder.py` - call synthesis and include quality metadata.
- `facttracer-backend/app/services/ai/deepseek_client.py` - add optional structured methods for classification and synthesis.
- `facttracer-backend/app/api/routes/issues.py` - support `sort`, `majorTopic`, `eventGroup`, and optional user ranking.
- `facttracer-backend/tests/test_api.py` - add contract/unit coverage for the new behavior.
- `facttracer-next/src/lib/api/types.ts` - add new issue fields and sort types.
- `facttracer-next/src/lib/api/facttracer.ts` - pass sort and taxonomy filters.
- `facttracer-next/src/app/page.tsx` - use representative images and stop client-side resorting over backend-ranked results.

Current workspace note: `/Users/joungminsung/Desktop/01_프로젝트-개발/AI/facknews` is not a Git repository. Commit steps below should be run only after this work is moved into or initialized as a Git repository.

---

### Task 1: Public Contract And Additive Schema

**Files:**
- Modify: `facttracer-backend/app/models.py`
- Modify: `facttracer-backend/app/schemas.py`
- Modify: `facttracer-backend/app/serializers.py`
- Modify: `facttracer-backend/tests/test_api.py`
- Modify: `facttracer-next/src/lib/api/types.ts`

- [ ] **Step 1: Write failing backend contract test**

Append this test to `facttracer-backend/tests/test_api.py`:

```python
def test_public_issue_contract_includes_taxonomy_image_and_rank_metadata() -> None:
    db = SessionLocal()
    try:
        major = models.MajorTopic(
            id="major_2026_local_election",
            name="2026 지방선거",
            slug="2026-local-election",
            topic="정치",
            summary="2026 지방선거 관련 사건을 묶습니다.",
            keywords_json=["선거", "투표", "선관위"],
            aliases_json=["지방선거"],
            signal_json={"reason": "election terms"},
        )
        event = models.EventGroup(
            id="event_ballot_shortage",
            major_topic_id=major.id,
            name="선관위 투표용지 부족 사태",
            slug="ballot-shortage",
            topic="정치",
            summary="투표용지 부족 관련 후속 보도를 묶습니다.",
            keywords_json=["선관위", "투표용지", "부족"],
            aliases_json=["투표지 부족"],
            signal_json={"reason": "same incident"},
        )
        issue = models.Issue(
            id="issue_contract_taxonomy",
            is_public=True,
            title="선관위 투표용지 부족 사태",
            topic="정치",
            major_topic_id=major.id,
            major_topic_name=major.name,
            event_group_id=event.id,
            event_group_name=event.name,
            representative_image_url="https://example.com/ballot.jpg",
            representative_image_source="예시뉴스",
            representative_image_source_url="https://example.com/article",
            representative_image_confidence=0.87,
            quality_score=82,
            quality_status="sufficient",
            quality_report_json={"missingSignals": []},
            ranking_json={"rankScore": 91.2, "rankReason": "후속 기사 증가"},
            summary="투표용지 부족 논란과 후속 조치를 검증 중입니다.",
        )
        db.add_all([major, event, issue])
        db.commit()
    finally:
        db.close()

    with TestClient(app) as client:
        response = client.get("/v1/issues/home")
        assert response.status_code == 200
        issue_payload = response.json()["issues"][0]
        assert issue_payload["majorTopic"] == "2026 지방선거"
        assert issue_payload["majorTopicId"] == "major_2026_local_election"
        assert issue_payload["eventGroup"] == "선관위 투표용지 부족 사태"
        assert issue_payload["eventGroupId"] == "event_ballot_shortage"
        assert issue_payload["representativeImageUrl"] == "https://example.com/ballot.jpg"
        assert issue_payload["rankScore"] == 91.2
        assert issue_payload["rankReason"] == "후속 기사 증가"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd facttracer-backend
pytest tests/test_api.py::test_public_issue_contract_includes_taxonomy_image_and_rank_metadata -q
```

Expected: FAIL because `models.MajorTopic` and the new `Issue` fields do not exist.

- [ ] **Step 3: Add additive models**

In `facttracer-backend/app/models.py`, add classes after `Topic`:

```python
class MajorTopic(Base):
    __tablename__ = "major_topics"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    slug: Mapped[str] = mapped_column(String(240), unique=True, index=True)
    topic: Mapped[str] = mapped_column(String(80), default="사회", index=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(60), default="active", index=True)
    keywords_json: Mapped[list] = mapped_column(JSON, default=list)
    aliases_json: Mapped[list] = mapped_column(JSON, default=list)
    signal_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class EventGroup(Base):
    __tablename__ = "event_groups"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    major_topic_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    topic: Mapped[str] = mapped_column(String(80), default="사회", index=True)
    name: Mapped[str] = mapped_column(String(240), index=True)
    slug: Mapped[str] = mapped_column(String(280), default="", index=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(60), default="active", index=True)
    keywords_json: Mapped[list] = mapped_column(JSON, default=list)
    aliases_json: Mapped[list] = mapped_column(JSON, default=list)
    signal_json: Mapped[dict] = mapped_column(JSON, default=dict)
    article_count: Mapped[int] = mapped_column(Integer, default=0)
    issue_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
```

Extend `Issue` with:

```python
    major_topic_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    event_group_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    major_topic_name: Mapped[str] = mapped_column(String(200), default="", index=True)
    event_group_name: Mapped[str] = mapped_column(String(240), default="", index=True)
    representative_image_url: Mapped[str] = mapped_column(Text, default="")
    representative_image_source: Mapped[str] = mapped_column(String(200), default="")
    representative_image_source_url: Mapped[str] = mapped_column(Text, default="")
    representative_image_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    representative_image_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    quality_score: Mapped[int] = mapped_column(Integer, default=0)
    quality_status: Mapped[str] = mapped_column(String(60), default="unchecked", index=True)
    quality_report_json: Mapped[dict] = mapped_column(JSON, default=dict)
    quality_attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_quality_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_quality_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ranking_json: Mapped[dict] = mapped_column(JSON, default=dict)
```

Add after `Article`:

```python
class ImageCandidate(Base):
    __tablename__ = "image_candidates"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    issue_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    article_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    url: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(Text, default="")
    publisher: Mapped[str] = mapped_column(String(200), default="")
    source_type: Mapped[str] = mapped_column(String(80), default="news")
    width: Mapped[int] = mapped_column(Integer, default=0)
    height: Mapped[int] = mapped_column(Integer, default=0)
    mime_type: Mapped[str] = mapped_column(String(120), default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(60), default="candidate", index=True)
    reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class UserInterestProfile(Base):
    __tablename__ = "user_interest_profiles"

    user_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    topic_weights_json: Mapped[dict] = mapped_column(JSON, default=dict)
    major_topic_weights_json: Mapped[dict] = mapped_column(JSON, default=dict)
    event_group_weights_json: Mapped[dict] = mapped_column(JSON, default=dict)
    publisher_weights_json: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
```

- [ ] **Step 4: Add public schema fields**

In `facttracer-backend/app/schemas.py`, extend `Issue`:

```python
    majorTopic: str | None = None
    majorTopicId: str | None = None
    eventGroup: str | None = None
    eventGroupId: str | None = None
    representativeImageUrl: str | None = None
    representativeImageSource: str | None = None
    rankScore: float | None = None
    rankReason: str | None = None
```

In `facttracer-next/src/lib/api/types.ts`, extend `Issue`:

```ts
  majorTopic?: string | null;
  majorTopicId?: string | null;
  eventGroup?: string | null;
  eventGroupId?: string | null;
  representativeImageUrl?: string | null;
  representativeImageSource?: string | null;
  rankScore?: number | null;
  rankReason?: string | null;
```

- [ ] **Step 5: Serialize fields**

In `facttracer-backend/app/serializers.py`, update `issue_summary`:

```python
    ranking = issue.ranking_json or {}
    return Issue(
        articleCount=cache.get("article_count", issue.article_count),
        changedClaims=cache.get("changed_claims", issue.changed_claims),
        clusterCount=cache.get("cluster_count", issue.cluster_count),
        eventGroup=issue.event_group_name or None,
        eventGroupId=issue.event_group_id,
        id=issue.id,
        issueScore=issue.issue_score,
        majorTopic=issue.major_topic_name or None,
        majorTopicId=issue.major_topic_id,
        needsReviewCount=cache.get("needs_review_count", issue.needs_review_count),
        rankReason=str(ranking.get("rankReason") or "") or None,
        rankScore=float(ranking["rankScore"]) if ranking.get("rankScore") is not None else None,
        representativeImageSource=issue.representative_image_source or None,
        representativeImageUrl=issue.representative_image_url or None,
        risk=issue.risk,
        status=issue.status,
        summary=issue.summary or cache.get("computed_summary", ""),
        title=issue.title,
        topic=normalize_topic(issue.topic),
        updatedAt=to_iso(issue.updated_at),
        verifiedCount=cache.get("verified_count", issue.verified_count),
    )
```

- [ ] **Step 6: Run contract test**

Run:

```bash
cd facttracer-backend
pytest tests/test_api.py::test_public_issue_contract_includes_taxonomy_image_and_rank_metadata -q
```

Expected: PASS.

- [ ] **Step 7: Run current backend suite**

Run:

```bash
cd facttracer-backend
pytest -q
```

Expected: PASS.

- [ ] **Step 8: Commit if repository exists**

Run only in a Git repository:

```bash
git add facttracer-backend/app/models.py facttracer-backend/app/schemas.py facttracer-backend/app/serializers.py facttracer-backend/tests/test_api.py facttracer-next/src/lib/api/types.ts
git commit -m "feat: add issue taxonomy image ranking contract"
```

---

### Task 2: Automatic Major Topic And Event Group Classification

**Files:**
- Create: `facttracer-backend/app/services/classification/__init__.py`
- Create: `facttracer-backend/app/services/classification/taxonomy.py`
- Modify: `facttracer-backend/app/workers/issue_jobs.py`
- Modify: `facttracer-backend/app/services/discovery/incident_detector.py`
- Create: `facttracer-backend/scripts/backfill_issue_taxonomy.py`
- Modify: `facttracer-backend/tests/test_api.py`

- [ ] **Step 1: Write failing classification tests**

Append:

```python
def test_election_incidents_share_major_topic_but_not_event_group() -> None:
    from app.services.classification.taxonomy import classify_issue_taxonomy

    db = SessionLocal()
    try:
        first = models.Issue(
            id="issue_ballot_shortage",
            title="선관위 투표용지 부족 사태",
            topic="정치",
            summary="투표용지 부족 투표소가 늘었다는 논란입니다.",
        )
        second = models.Issue(
            id="issue_incheon_equal_votes",
            title="인천 사전투표 동일 득표 논란",
            topic="정치",
            summary="사전투표 득표 수치가 동일하다는 별도 논란입니다.",
        )
        db.add_all([first, second])
        db.flush()

        classify_issue_taxonomy(db, issue=first)
        classify_issue_taxonomy(db, issue=second)
        db.commit()

        assert first.major_topic_name == "2026 지방선거"
        assert second.major_topic_name == "2026 지방선거"
        assert first.event_group_id != second.event_group_id
        assert first.event_group_name == "선관위 투표용지 부족 사태"
        assert second.event_group_name == "인천 사전투표 동일 득표 논란"
    finally:
        db.close()


def test_same_incident_followup_reuses_event_group() -> None:
    from app.services.classification.taxonomy import classify_issue_taxonomy

    db = SessionLocal()
    try:
        first = models.Issue(
            id="issue_ballot_shortage_initial",
            title="선관위 투표용지 부족 사태",
            topic="정치",
            summary="투표용지 부족 사태 초기 보도입니다.",
        )
        second = models.Issue(
            id="issue_ballot_shortage_followup",
            title="선관위 투표용지 부족 후속 감사 착수",
            topic="정치",
            summary="투표용지 부족 사태와 관련해 감사가 착수됐습니다.",
        )
        db.add_all([first, second])
        db.flush()

        classify_issue_taxonomy(db, issue=first)
        classify_issue_taxonomy(db, issue=second)
        db.commit()

        assert first.event_group_id == second.event_group_id
        assert second.event_group_name == "선관위 투표용지 부족 사태"
    finally:
        db.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd facttracer-backend
pytest tests/test_api.py::test_election_incidents_share_major_topic_but_not_event_group tests/test_api.py::test_same_incident_followup_reuses_event_group -q
```

Expected: FAIL because `app.services.classification.taxonomy` does not exist.

- [ ] **Step 3: Create classification service**

Create `facttracer-backend/app/services/classification/__init__.py` as an empty package file.

Create `facttracer-backend/app/services/classification/taxonomy.py`:

```python
from __future__ import annotations

import re
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models
from app.services.articles.normalizer import normalize_whitespace, token_set
from app.services.issues.matcher import incident_similarity
from app.services.issues.publisher import slugify
from app.services.topics import normalize_topic
from app.utils import new_id


ELECTION_TERMS = ("선거", "선관위", "중앙선관위", "중앙선거관리위원회", "투표", "사전투표", "개표", "득표")
BALLOT_SHORTAGE_TERMS = ("투표용지", "투표지", "부족")
EQUAL_VOTE_TERMS = ("동일 득표", "득표 논란", "사전투표 동일")
FOLLOWUP_TERMS = ("후속", "감사", "고발", "수사", "집회", "기자회견", "해명", "설명자료")


def _context(issue: models.Issue, *, title: str = "", summary: str = "") -> str:
    return normalize_whitespace(" ".join([title or issue.title, summary or issue.summary, issue.topic]))


def infer_major_topic_name(text: str, *, now: datetime | None = None) -> str:
    if any(term in text for term in ELECTION_TERMS):
        current = now or datetime.now(UTC)
        year = 2026 if current.year <= 2026 else current.year
        return f"{year} 지방선거"
    if "의료" in text or "병원" in text:
        return "의료 현안"
    if "부동산" in text or "주택" in text or "공급" in text:
        return "부동산 공급정책"
    return f"{normalize_topic(text)} 주요 이슈"


def infer_event_group_name(text: str) -> str:
    if "선관위" in text and all(term in text for term in BALLOT_SHORTAGE_TERMS):
        return "선관위 투표용지 부족 사태"
    if "인천" in text and any(term in text for term in EQUAL_VOTE_TERMS):
        return "인천 사전투표 동일 득표 논란"
    cleaned = re.sub(r"\s+", " ", text).strip()
    cleaned = re.sub("|".join(FOLLOWUP_TERMS), "", cleaned).strip()
    tokens = [token for token in token_set(cleaned) if len(token) >= 2 and not token.isdigit()]
    return normalize_whitespace(" ".join(tokens[:6]))[:120] or cleaned[:120]


def _upsert_major_topic(db: Session, *, name: str, topic: str, signal: dict) -> models.MajorTopic:
    existing = db.scalar(select(models.MajorTopic).where(models.MajorTopic.name == name))
    if existing:
        existing.last_seen_at = models.now_utc()
        existing.updated_at = models.now_utc()
        existing.signal_json = {**(existing.signal_json or {}), **signal}
        db.flush()
        return existing
    row = models.MajorTopic(
        id=new_id("major"),
        name=name,
        slug=slugify(name),
        topic=normalize_topic(topic),
        summary=f"{name} 관련 사건을 자동으로 묶은 주제입니다.",
        keywords_json=sorted(token_set(name)),
        signal_json=signal,
    )
    db.add(row)
    db.flush()
    return row


def _find_event_group(db: Session, *, name: str, major_topic_id: str, text: str) -> models.EventGroup | None:
    rows = db.scalars(
        select(models.EventGroup).where(
            models.EventGroup.major_topic_id == major_topic_id,
            models.EventGroup.status != "hidden",
        ),
    ).all()
    best: tuple[models.EventGroup | None, float] = (None, 0.0)
    for row in rows:
        score = max(
            incident_similarity(name, row.name),
            incident_similarity(text, f"{row.name} {row.summary}"),
        )
        if score > best[1]:
            best = (row, score)
    return best[0] if best[1] >= 0.62 else None


def _upsert_event_group(
    db: Session,
    *,
    major_topic: models.MajorTopic,
    name: str,
    topic: str,
    text: str,
    signal: dict,
) -> models.EventGroup:
    existing = _find_event_group(db, name=name, major_topic_id=major_topic.id, text=text)
    if existing:
        existing.article_count += 0
        existing.last_seen_at = models.now_utc()
        existing.updated_at = models.now_utc()
        existing.signal_json = {**(existing.signal_json or {}), **signal}
        db.flush()
        return existing
    row = models.EventGroup(
        id=new_id("event"),
        major_topic_id=major_topic.id,
        name=name,
        slug=slugify(name),
        topic=normalize_topic(topic),
        summary=f"{name} 관련 보도와 후속 조치를 묶은 사건 그룹입니다.",
        keywords_json=sorted(token_set(text))[:30],
        signal_json=signal,
    )
    db.add(row)
    db.flush()
    return row


def refresh_group_counts(db: Session, *, event_group: models.EventGroup) -> None:
    event_group.issue_count = int(
        db.scalar(select(func.count(models.Issue.id)).where(models.Issue.event_group_id == event_group.id)) or 0
    )
    event_group.article_count = int(
        db.scalar(
            select(func.count(models.Article.id)).where(
                models.Article.issue_id.in_(
                    select(models.Issue.id).where(models.Issue.event_group_id == event_group.id)
                )
            )
        )
        or 0
    )
    event_group.updated_at = models.now_utc()


def classify_issue_taxonomy(
    db: Session,
    *,
    issue: models.Issue,
    title: str = "",
    summary: str = "",
) -> tuple[models.MajorTopic, models.EventGroup]:
    text = _context(issue, title=title, summary=summary)
    major_name = infer_major_topic_name(text)
    event_name = infer_event_group_name(text)
    signal = {"text": text[:500], "source": "deterministic"}
    major = _upsert_major_topic(db, name=major_name, topic=issue.topic, signal=signal)
    event = _upsert_event_group(db, major_topic=major, name=event_name, topic=issue.topic, text=text, signal=signal)
    issue.major_topic_id = major.id
    issue.major_topic_name = major.name
    issue.event_group_id = event.id
    issue.event_group_name = event.name
    issue.updated_at = models.now_utc()
    refresh_group_counts(db, event_group=event)
    db.flush()
    return major, event
```

- [ ] **Step 4: Integrate classification into issue creation**

In `facttracer-backend/app/workers/issue_jobs.py`, import:

```python
from app.services.classification.taxonomy import classify_issue_taxonomy
```

Call after any `Issue` is created or matched in `_ensure_search_issue` and `_ensure_discovery_issue`:

```python
    classify_issue_taxonomy(db, issue=issue)
```

Call in `process_article` after `article.issue_id = issue.id`:

```python
    classify_issue_taxonomy(db, issue=issue, title=article.title, summary=article.summary)
```

- [ ] **Step 5: Add taxonomy backfill script**

Create `facttracer-backend/scripts/backfill_issue_taxonomy.py`:

```python
from sqlalchemy import select

from app import models
from app.db.session import SessionLocal
from app.services.classification.taxonomy import classify_issue_taxonomy


def main() -> None:
    db = SessionLocal()
    try:
        issues = db.scalars(select(models.Issue).where(models.Issue.status.notin_(["숨김", "병합됨"]))).all()
        for issue in issues:
            classify_issue_taxonomy(db, issue=issue)
        db.commit()
        print(f"Backfilled taxonomy for {len(issues)} issues")
    finally:
        db.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Run classification tests**

Run:

```bash
cd facttracer-backend
pytest tests/test_api.py::test_election_incidents_share_major_topic_but_not_event_group tests/test_api.py::test_same_incident_followup_reuses_event_group -q
```

Expected: PASS.

- [ ] **Step 7: Run current related tests**

Run:

```bash
cd facttracer-backend
pytest tests/test_api.py::test_same_incident_reuses_existing_issue_for_search_and_discovery tests/test_api.py::test_active_issue_followup_runs_even_with_enough_sources -q
```

Expected: PASS.

- [ ] **Step 8: Commit if repository exists**

Run only in a Git repository:

```bash
git add facttracer-backend/app/services/classification facttracer-backend/app/workers/issue_jobs.py facttracer-backend/app/services/discovery/incident_detector.py facttracer-backend/scripts/backfill_issue_taxonomy.py facttracer-backend/tests/test_api.py
git commit -m "feat: classify issues into major topics and event groups"
```

---

### Task 3: Representative Image Candidate Extraction And Selection

**Files:**
- Modify: `facttracer-backend/app/collectors/base.py`
- Modify: `facttracer-backend/app/collectors/news_search.py`
- Modify: `facttracer-backend/app/services/articles/parser.py`
- Create: `facttracer-backend/app/services/images/__init__.py`
- Create: `facttracer-backend/app/services/images/candidates.py`
- Create: `facttracer-backend/app/services/images/selector.py`
- Modify: `facttracer-backend/app/workers/issue_jobs.py`
- Modify: `facttracer-backend/app/services/jobs.py`
- Modify: `facttracer-backend/tests/test_api.py`

- [ ] **Step 1: Write failing image tests**

Append:

```python
def test_representative_image_selector_prefers_relevant_official_image(monkeypatch) -> None:
    from app.services.images.selector import select_representative_image

    db = SessionLocal()
    try:
        issue = models.Issue(
            id="issue_image_selection",
            title="선관위 투표용지 부족 사태",
            topic="정치",
            summary="공식자료와 보도 이미지를 비교합니다.",
        )
        official = models.ImageCandidate(
            id="image_official",
            issue_id=issue.id,
            url="https://nec.go.kr/briefing.jpg",
            source_url="https://nec.go.kr/briefing",
            publisher="중앙선관위",
            source_type="official",
            width=1200,
            height=630,
            status="candidate",
        )
        logo = models.ImageCandidate(
            id="image_logo",
            issue_id=issue.id,
            url="https://example.com/logo.png",
            source_url="https://example.com/article",
            publisher="예시뉴스",
            source_type="news",
            width=120,
            height=60,
            status="candidate",
        )
        db.add_all([issue, official, logo])
        db.commit()

        selected = select_representative_image(db, issue_id=issue.id)
        db.commit()

        assert selected is not None
        assert selected.id == "image_official"
        assert issue.representative_image_url == "https://nec.go.kr/briefing.jpg"
        assert issue.representative_image_source == "중앙선관위"
        assert issue.representative_image_confidence > 0.7
    finally:
        db.close()


def test_html_parser_extracts_open_graph_images() -> None:
    from app.services.images.candidates import extract_image_urls_from_html

    html = '''
    <html><head>
      <meta property="og:image" content="https://example.com/og.jpg">
      <meta name="twitter:image" content="https://example.com/twitter.jpg">
    </head></html>
    '''
    assert extract_image_urls_from_html(html) == [
        "https://example.com/og.jpg",
        "https://example.com/twitter.jpg",
    ]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd facttracer-backend
pytest tests/test_api.py::test_representative_image_selector_prefers_relevant_official_image tests/test_api.py::test_html_parser_extracts_open_graph_images -q
```

Expected: FAIL because image services do not exist.

- [ ] **Step 3: Extend collected article shape**

In `facttracer-backend/app/collectors/base.py`:

```python
from dataclasses import dataclass, field
```

Add fields:

```python
    image_url: str = ""
    image_candidates: list[str] = field(default_factory=list)
```

- [ ] **Step 4: Create image candidate utilities**

Create `facttracer-backend/app/services/images/candidates.py`:

```python
from __future__ import annotations

import html
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.utils import new_id


IMAGE_META_PATTERNS = (
    r"<meta[^>]+property=[\"']og:image[\"'][^>]+content=[\"']([^\"']+)[\"']",
    r"<meta[^>]+name=[\"']twitter:image[\"'][^>]+content=[\"']([^\"']+)[\"']",
    r"<meta[^>]+property=[\"']twitter:image[\"'][^>]+content=[\"']([^\"']+)[\"']",
)


def extract_image_urls_from_html(raw_html: str) -> list[str]:
    seen: set[str] = set()
    urls: list[str] = []
    for pattern in IMAGE_META_PATTERNS:
        for match in re.finditer(pattern, raw_html, re.IGNORECASE | re.DOTALL):
            url = html.unescape(match.group(1)).strip()
            if url.startswith("http") and url not in seen:
                urls.append(url)
                seen.add(url)
    return urls


def upsert_image_candidate(
    db: Session,
    *,
    article_id: str | None,
    issue_id: str | None,
    publisher: str,
    source_type: str,
    source_url: str,
    url: str,
) -> models.ImageCandidate | None:
    clean = str(url or "").strip()
    if not clean.startswith(("http://", "https://")):
        return None
    existing = db.scalar(select(models.ImageCandidate).where(models.ImageCandidate.url == clean))
    if existing:
        if issue_id and not existing.issue_id:
            existing.issue_id = issue_id
        if article_id and not existing.article_id:
            existing.article_id = article_id
        existing.updated_at = models.now_utc()
        db.flush()
        return existing
    row = models.ImageCandidate(
        article_id=article_id,
        id=new_id("image"),
        issue_id=issue_id,
        publisher=publisher,
        source_type=source_type or "news",
        source_url=source_url,
        url=clean,
    )
    db.add(row)
    db.flush()
    return row
```

- [ ] **Step 5: Create selector**

Create `facttracer-backend/app/services/images/selector.py`:

```python
from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models


LOW_QUALITY_IMAGE_TERMS = re.compile(r"(favicon|logo|sprite|profile|avatar|icon|blank|spacer)", re.IGNORECASE)


def score_image_candidate(candidate: models.ImageCandidate, *, issue: models.Issue) -> tuple[float, str]:
    if LOW_QUALITY_IMAGE_TERMS.search(candidate.url):
        return 0.0, "로고 또는 아이콘 이미지 후보 제외"
    if candidate.width and candidate.width < 300:
        return 0.0, "이미지 너비가 너무 작음"
    if candidate.height and candidate.height < 160:
        return 0.0, "이미지 높이가 너무 작음"
    score = 0.35
    reasons = ["기본 이미지 후보"]
    if candidate.source_type in {"official", "public", "statistics", "law"}:
        score += 0.35
        reasons.append("공식/공공 출처")
    if candidate.publisher and candidate.publisher in {issue.representative_image_source, "중앙선관위"}:
        score += 0.08
        reasons.append("관련 출처")
    if candidate.width >= 900 and candidate.height >= 450:
        score += 0.12
        reasons.append("카드 표시 적합 해상도")
    if any(term in candidate.url for term in ("briefing", "news", "photo", "image")):
        score += 0.08
        reasons.append("이미지 URL 패턴")
    return min(score, 1.0), ", ".join(reasons)


def select_representative_image(db: Session, *, issue_id: str) -> models.ImageCandidate | None:
    issue = db.get(models.Issue, issue_id)
    if not issue:
        return None
    candidates = db.scalars(
        select(models.ImageCandidate).where(
            models.ImageCandidate.issue_id == issue_id,
            models.ImageCandidate.status.in_(["candidate", "selected"]),
        )
    ).all()
    best: tuple[models.ImageCandidate | None, float, str] = (None, 0.0, "")
    for candidate in candidates:
        score, reason = score_image_candidate(candidate, issue=issue)
        candidate.confidence = score
        candidate.reason = reason
        candidate.status = "rejected" if score <= 0 else "candidate"
        if score > best[1]:
            best = (candidate, score, reason)
    selected, score, reason = best
    if not selected or score < 0.35:
        db.flush()
        return None
    selected.status = "selected"
    selected.reason = reason
    issue.representative_image_url = selected.url
    issue.representative_image_source = selected.publisher
    issue.representative_image_source_url = selected.source_url
    issue.representative_image_confidence = score
    issue.representative_image_updated_at = models.now_utc()
    issue.updated_at = models.now_utc()
    db.flush()
    return selected
```

- [ ] **Step 6: Extract RSS and HTML image candidates**

In `facttracer-backend/app/collectors/news_search.py`, inside `collect_google_news_search`, read namespaced media thumbnail/content:

```python
        image_candidates: list[str] = []
        for child in item:
            if child.tag.endswith("thumbnail") or child.tag.endswith("content"):
                candidate_url = child.attrib.get("url") or ""
                if candidate_url.startswith("http"):
                    image_candidates.append(candidate_url)
```

Pass to `CollectedArticle`:

```python
                image_url=image_candidates[0] if image_candidates else "",
                image_candidates=image_candidates,
```

In `facttracer-backend/app/services/articles/parser.py`, import `extract_image_urls_from_html` and extend `ParsedArticle` with:

```python
    image_candidates: list[str]
```

Return `image_candidates=[]` in `parse_article_content`, and pass extracted candidates from `fetch_and_parse_url`:

```python
image_candidates=extract_image_urls_from_html(raw_html)
```

- [ ] **Step 7: Persist image candidates from collected articles**

In `facttracer-backend/app/workers/issue_jobs.py`, import:

```python
from app.services.images.candidates import upsert_image_candidate
from app.services.images.selector import select_representative_image
```

Add helper:

```python
def _persist_collected_image_candidates(
    db: Session,
    *,
    article: models.Article,
    collected: CollectedArticle,
    issue_id: str | None,
) -> None:
    urls = [collected.image_url, *(collected.image_candidates or [])]
    for url in urls:
        upsert_image_candidate(
            db,
            article_id=article.id,
            issue_id=issue_id or article.issue_id,
            publisher=article.publisher,
            source_type=article.source_type,
            source_url=article.url,
            url=url,
        )
```

Call the helper in `ingest_collected_article` and `upsert_collected_article_record` after `upsert_article`. If `article.issue_id` exists, call:

```python
select_representative_image(db, issue_id=article.issue_id)
```

- [ ] **Step 8: Register image selection job**

In `facttracer-backend/app/services/jobs.py`, add handler:

```python
"select_representative_image": issue_jobs.select_representative_image_job,
```

In `facttracer-backend/app/workers/issue_jobs.py`, add:

```python
def select_representative_image_job(issue_id: str) -> dict:
    db = SessionLocal()
    try:
        selected = select_representative_image(db, issue_id=issue_id)
        db.commit()
        return {
            "status": "completed" if selected else "needs_candidate",
            "image_id": selected.id if selected else None,
        }
    finally:
        db.close()
```

- [ ] **Step 9: Run image tests**

Run:

```bash
cd facttracer-backend
pytest tests/test_api.py::test_representative_image_selector_prefers_relevant_official_image tests/test_api.py::test_html_parser_extracts_open_graph_images -q
```

Expected: PASS.

- [ ] **Step 10: Run full backend suite**

Run:

```bash
cd facttracer-backend
pytest -q
```

Expected: PASS.

- [ ] **Step 11: Commit if repository exists**

Run only in a Git repository:

```bash
git add facttracer-backend/app/collectors facttracer-backend/app/services/articles/parser.py facttracer-backend/app/services/images facttracer-backend/app/workers/issue_jobs.py facttracer-backend/app/services/jobs.py facttracer-backend/tests/test_api.py
git commit -m "feat: select representative images automatically"
```

---

### Task 4: Issue Quality Scoring And Bounded Re-Search

**Files:**
- Create: `facttracer-backend/app/services/issues/quality.py`
- Modify: `facttracer-backend/app/core/config.py`
- Modify: `facttracer-backend/app/services/admin/settings.py`
- Modify: `facttracer-backend/app/workers/issue_jobs.py`
- Modify: `facttracer-backend/app/services/jobs.py`
- Modify: `facttracer-backend/tests/test_api.py`

- [ ] **Step 1: Write failing quality tests**

Append:

```python
def test_issue_quality_detects_missing_signals_and_creates_retry_keywords() -> None:
    from app.services.issues.quality import assess_issue_quality

    db = SessionLocal()
    try:
        issue = models.Issue(
            id="issue_quality_missing",
            title="선관위 투표용지 부족 사태",
            topic="정치",
            summary="기사와 공식자료가 부족한 상태입니다.",
            article_count=1,
            quality_attempts=0,
        )
        db.add(issue)
        db.add(
            models.Article(
                id="article_quality_1",
                issue_id=issue.id,
                title="투표용지 부족 논란",
                publisher="테스트뉴스",
                url="https://example.com/quality-1",
                dedup_hash="quality-1",
                body_text="투표용지 부족 주장이 제기됐다.",
                summary="투표용지 부족 주장",
                source_type="news",
            )
        )
        db.commit()

        report = assess_issue_quality(db, issue_id=issue.id)
        db.commit()

        assert report["status"] == "needs_retry"
        assert "officialCoverage" in report["missingSignals"]
        assert "claimCoverage" in report["missingSignals"]
        keywords = db.scalars(
            select(models.SearchKeyword).where(models.SearchKeyword.issue_id == issue.id)
        ).all()
        assert any(keyword.source == "quality_retry" for keyword in keywords)
        assert issue.quality_attempts == 1
        assert issue.next_quality_retry_at is not None
    finally:
        db.close()


def test_issue_quality_retry_budget_prevents_infinite_research() -> None:
    from app.services.issues.quality import assess_issue_quality

    db = SessionLocal()
    try:
        issue = models.Issue(
            id="issue_quality_budget",
            title="선관위 투표용지 부족 사태",
            topic="정치",
            summary="반복 재검색 예산을 확인합니다.",
            quality_attempts=5,
        )
        db.add(issue)
        db.commit()

        report = assess_issue_quality(db, issue_id=issue.id)
        db.commit()

        assert report["status"] == "exhausted"
        assert issue.quality_status == "exhausted"
        assert not db.scalars(
            select(models.SearchKeyword).where(models.SearchKeyword.issue_id == issue.id)
        ).all()
    finally:
        db.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd facttracer-backend
pytest tests/test_api.py::test_issue_quality_detects_missing_signals_and_creates_retry_keywords tests/test_api.py::test_issue_quality_retry_budget_prevents_infinite_research -q
```

Expected: FAIL because `app.services.issues.quality` does not exist.

- [ ] **Step 3: Add config defaults and settings**

In `facttracer-backend/app/core/config.py`, add:

```python
    issue_quality_max_attempts: int = 3
    issue_quality_high_impact_max_attempts: int = 5
    issue_quality_retry_cooldown_minutes: int = 30
    issue_quality_min_articles: int = 4
    issue_quality_min_publishers: int = 2
```

In `facttracer-backend/app/services/admin/settings.py`, add `SettingDefinition` rows in the automation/review groups:

```python
    SettingDefinition(
        "issue_quality_max_attempts",
        "automation",
        "품질 재검색 최대 횟수",
        "일반 이슈가 상세 품질 부족으로 재검색할 수 있는 최대 횟수",
        "integer",
        min_value=0,
        max_value=10,
        unit="회",
    ),
    SettingDefinition(
        "issue_quality_high_impact_max_attempts",
        "automation",
        "고영향 품질 재검색 최대 횟수",
        "선거·재난·경제 등 고영향 이슈 재검색 최대 횟수",
        "integer",
        min_value=0,
        max_value=10,
        unit="회",
    ),
    SettingDefinition(
        "issue_quality_retry_cooldown_minutes",
        "automation",
        "품질 재검색 대기 시간",
        "같은 이슈에 추가 품질 재검색을 예약하기 전 대기 시간",
        "integer",
        min_value=5,
        max_value=1440,
        unit="분",
    ),
```

- [ ] **Step 4: Create quality service**

Create `facttracer-backend/app/services/issues/quality.py`:

```python
from __future__ import annotations

from datetime import timedelta
from urllib.parse import quote

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models
from app.services.admin.settings import get_effective_setting
from app.services.search.keywords import upsert_search_keyword


HIGH_IMPACT_TOPICS = {"정치", "재난", "보건", "경제"}


def _max_attempts(db: Session, issue: models.Issue) -> int:
    key = "issue_quality_high_impact_max_attempts" if issue.topic in HIGH_IMPACT_TOPICS else "issue_quality_max_attempts"
    return int(get_effective_setting(db, key) or (5 if issue.topic in HIGH_IMPACT_TOPICS else 3))


def _quality_queries(issue: models.Issue, missing: list[str]) -> list[str]:
    base = issue.event_group_name or issue.title
    queries = [base]
    if "officialCoverage" in missing:
        queries.extend([f"{base} 공식자료", f"{base} 해명", f"{base} 설명자료"])
    if "claimCoverage" in missing:
        queries.extend([f"{base} 쟁점", f"{base} 주장", f"{base} 논란"])
    if "timelineCoverage" in missing:
        queries.extend([f"{base} 후속", f"{base} 감사", f"{base} 고발", f"{base} 집회"])
    if "numberCoverage" in missing:
        queries.extend([f"{base} 수치", f"{base} 91곳", f"{base} 50곳"])
    seen: set[str] = set()
    result: list[str] = []
    for query in queries:
        clean = query.strip()
        if len(clean) >= 2 and clean not in seen:
            result.append(clean[:300])
            seen.add(clean)
    return result


def build_issue_quality_report(db: Session, *, issue: models.Issue) -> dict:
    articles = db.scalars(select(models.Article).where(models.Article.issue_id == issue.id)).all()
    claims = db.scalars(select(models.Claim).where(models.Claim.issue_id == issue.id)).all()
    claim_ids = [claim.id for claim in claims]
    evidence_count = (
        int(db.scalar(select(func.count(models.Evidence.id)).where(models.Evidence.claim_id.in_(claim_ids))) or 0)
        if claim_ids
        else 0
    )
    publishers = {article.publisher for article in articles if article.publisher}
    official_sources = [
        article for article in articles if article.source_type in {"official", "public", "statistics", "law"}
    ]
    missing: list[str] = []
    min_articles = int(get_effective_setting(db, "issue_quality_min_articles", 4) or 4)
    min_publishers = int(get_effective_setting(db, "issue_quality_min_publishers", 2) or 2)
    if len(articles) < min_articles:
        missing.append("articleCoverage")
    if len(publishers) < min_publishers:
        missing.append("sourceDiversity")
    if issue.topic in HIGH_IMPACT_TOPICS and not official_sources:
        missing.append("officialCoverage")
    if len(claims) < max(2, len(articles) // 2):
        missing.append("claimCoverage")
    if not issue.confirmed_facts:
        missing.append("factCoverage")
    if claims and evidence_count / max(len(claims), 1) < 0.5:
        missing.append("evidenceCoverage")
    if len(issue.perspectives or []) < 2 and len(claims) >= 2:
        missing.append("perspectiveCoverage")
    if len(issue.timeline or []) < 2:
        missing.append("timelineCoverage")
    if any(claim.claim_type == "수치 주장" for claim in claims) and not issue.number_changes:
        missing.append("numberCoverage")
    title_only_count = len([article for article in articles if article.parse_status == "title_only"])
    if articles and title_only_count / len(articles) > 0.4:
        missing.append("parseHealth")
    score = max(0, 100 - len(set(missing)) * 10)
    return {
        "articleCount": len(articles),
        "distinctPublisherCount": len(publishers),
        "evidenceCount": evidence_count,
        "missingSignals": sorted(set(missing)),
        "score": score,
    }


def assess_issue_quality(db: Session, *, issue_id: str) -> dict:
    issue = db.get(models.Issue, issue_id)
    if not issue:
        return {"status": "not_found", "missingSignals": [], "score": 0}
    report = build_issue_quality_report(db, issue=issue)
    missing = report["missingSignals"]
    issue.quality_score = int(report["score"])
    issue.quality_report_json = report
    issue.last_quality_checked_at = models.now_utc()
    max_attempts = _max_attempts(db, issue)
    if not missing:
        issue.quality_status = "sufficient"
        issue.next_quality_retry_at = None
        db.flush()
        return report | {"status": "sufficient"}
    if issue.quality_attempts >= max_attempts:
        issue.quality_status = "exhausted"
        issue.next_quality_retry_at = None
        db.flush()
        return report | {"status": "exhausted"}
    issue.quality_attempts += 1
    issue.quality_status = "needs_retry"
    cooldown = int(get_effective_setting(db, "issue_quality_retry_cooldown_minutes") or 30)
    issue.next_quality_retry_at = models.now_utc() + timedelta(minutes=cooldown)
    for query in _quality_queries(issue, missing):
        upsert_search_keyword(
            db,
            interval_minutes=max(15, cooldown),
            issue_id=issue.id,
            priority="high" if issue.topic in HIGH_IMPACT_TOPICS else "normal",
            query=query,
            seed_query=issue.title,
            source="quality_retry",
            topic=issue.topic,
            metadata={"missingSignals": missing, "qualityIssueId": issue.id},
        )
    db.flush()
    return report | {"status": "needs_retry"}
```

- [ ] **Step 5: Register quality job**

In `facttracer-backend/app/services/jobs.py`, add handler:

```python
"assess_issue_quality": issue_jobs.assess_issue_quality_job,
```

Give it priority near `update_issue_page`:

```python
"assess_issue_quality",
```

In `facttracer-backend/app/workers/issue_jobs.py`, add:

```python
def assess_issue_quality_job(issue_id: str) -> dict:
    from app.services.issues.quality import assess_issue_quality

    db = SessionLocal()
    try:
        report = assess_issue_quality(db, issue_id=issue_id)
        db.commit()
        return report
    finally:
        db.close()
```

- [ ] **Step 6: Enqueue quality assessment after cache refresh**

In `issue_jobs.py`, add helper:

```python
def _enqueue_quality_job(db: Session, *, issue_id: str) -> bool:
    existing = db.scalar(
        select(models.JobAttempt.id).where(
            models.JobAttempt.job_type == "assess_issue_quality",
            models.JobAttempt.target_id == issue_id,
            models.JobAttempt.status.in_(["queued", "running"]),
        )
    )
    if existing:
        return False
    from app.services.jobs import enqueue_job

    enqueue_job(
        db,
        input_json={"issue_id": issue_id},
        job_type="assess_issue_quality",
        run_immediately=False,
        target_id=issue_id,
    )
    return True
```

Call `_enqueue_quality_job(db, issue_id=issue.id)` after `refresh_issue_cache` in `process_article`, `search_news`, `backfill_issue_sources`, and `discover_topic`.

- [ ] **Step 7: Run quality tests**

Run:

```bash
cd facttracer-backend
pytest tests/test_api.py::test_issue_quality_detects_missing_signals_and_creates_retry_keywords tests/test_api.py::test_issue_quality_retry_budget_prevents_infinite_research -q
```

Expected: PASS.

- [ ] **Step 8: Run scheduler-related tests**

Run:

```bash
cd facttracer-backend
pytest tests/test_api.py::test_active_issue_followup_runs_even_with_enough_sources -q
```

Expected: PASS.

- [ ] **Step 9: Commit if repository exists**

Run only in a Git repository:

```bash
git add facttracer-backend/app/services/issues/quality.py facttracer-backend/app/core/config.py facttracer-backend/app/services/admin/settings.py facttracer-backend/app/workers/issue_jobs.py facttracer-backend/app/services/jobs.py facttracer-backend/tests/test_api.py
git commit -m "feat: add quality driven issue re-search"
```

---

### Task 5: DB-Grounded Issue Detail Synthesis

**Files:**
- Create: `facttracer-backend/app/services/issues/synthesis.py`
- Modify: `facttracer-backend/app/services/issues/page_builder.py`
- Modify: `facttracer-backend/app/services/ai/deepseek_client.py`
- Modify: `facttracer-backend/tests/test_api.py`

- [ ] **Step 1: Write failing synthesis tests**

Append:

```python
def test_issue_synthesis_enriches_summary_and_missing_signals_without_inventing_facts() -> None:
    from app.services.issues.synthesis import synthesize_issue_cache

    db = SessionLocal()
    try:
        issue = models.Issue(
            id="issue_synthesis",
            title="선관위 투표용지 부족 사태",
            topic="정치",
            summary="",
        )
        article = models.Article(
            id="article_synthesis",
            issue_id=issue.id,
            title="투표용지 부족 후속 보도",
            publisher="테스트뉴스",
            url="https://example.com/synthesis",
            dedup_hash="synthesis",
            body_text="선관위 투표용지 부족 문제와 후속 감사 가능성이 보도됐다.",
            summary="후속 감사 가능성 보도",
        )
        claim = models.Claim(
            id="claim_synthesis",
            issue_id=issue.id,
            article_id=article.id,
            claim_text="투표용지 부족 문제가 일부 투표소에서 발생했다.",
            sanitized_text="투표용지 부족 문제가 일부 투표소에서 발생했다.",
            claim_type="사실 주장",
            verdict="근거 부족",
            status="needs_evidence",
        )
        db.add_all([issue, article, claim])
        db.commit()

        _, cache = build_issue_cache_payload(db, issue_id=issue.id)
        enriched = synthesize_issue_cache(db, issue=issue, payload=cache)

        assert "1개 기사" in enriched["computed_summary"]
        assert "officialCoverage" in enriched["quality"]["missingSignals"]
        assert enriched["confirmed_facts"] == []
    finally:
        db.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd facttracer-backend
pytest tests/test_api.py::test_issue_synthesis_enriches_summary_and_missing_signals_without_inventing_facts -q
```

Expected: FAIL because `app.services.issues.synthesis` does not exist.

- [ ] **Step 3: Create synthesis service**

Create `facttracer-backend/app/services/issues/synthesis.py`:

```python
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app import models
from app.services.issues.quality import build_issue_quality_report


def synthesize_issue_cache(db: Session, *, issue: models.Issue, payload: dict[str, Any]) -> dict[str, Any]:
    quality = build_issue_quality_report(db, issue=issue)
    enriched = dict(payload)
    enriched["quality"] = quality
    if not issue.summary and not enriched.get("computed_summary"):
        enriched["computed_summary"] = (
            f"{quality['articleCount']}개 기사에서 쟁점과 근거를 정리 중입니다."
        )
    confirmed = enriched.get("confirmed_facts") or []
    evidences = enriched.get("evidences") or []
    evidence_labels = {str(evidence.get("label") or evidence.get("title") or "") for evidence in evidences if isinstance(evidence, dict)}
    safe_confirmed = []
    for fact in confirmed:
        if not isinstance(fact, dict):
            continue
        text = str(fact.get("text") or "")
        if text and (fact.get("verdict") in {"사실", "대체로 사실", "일부 사실"} or evidence_labels):
            safe_confirmed.append(fact)
    enriched["confirmed_facts"] = safe_confirmed
    return enriched
```

- [ ] **Step 4: Wire synthesis into page builder**

In `facttracer-backend/app/services/issues/page_builder.py`, import:

```python
from app.services.issues.synthesis import synthesize_issue_cache
```

Before returning payload in `build_issue_cache_payload`, assign the dict to a local variable:

```python
    payload = {
        "article_count": len(articles),
        ...
        "computed_summary": computed_summary,
    }
    return issue, synthesize_issue_cache(db, issue=issue, payload=payload)
```

In `refresh_issue_cache`, after assigning `issue.confirmed_facts`, add:

```python
    if payload.get("quality"):
        issue.quality_report_json = payload["quality"]
        issue.quality_score = int(payload["quality"].get("score") or issue.quality_score)
```

- [ ] **Step 5: Add optional DeepSeek method for synthesis**

In `facttracer-backend/app/services/ai/deepseek_client.py`, add method but keep deterministic synthesis working when AI is disabled:

```python
    def synthesize_issue_detail(
        self,
        *,
        issue_title: str,
        articles: list[dict],
        claims: list[dict],
        evidences: list[dict],
    ) -> dict | None:
        if not self.enabled:
            return None
        return self._chat_json(
            fallback=None,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Synthesize a Korean fact-check issue page using only supplied records. "
                        "Return JSON keys: summary, confirmed_facts, timeline_notes, missing_signals. "
                        "Do not invent facts, dates, URLs, numbers, or official statements."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "issue_title": issue_title,
                            "articles": articles[:40],
                            "claims": claims[:80],
                            "evidences": evidences[:80],
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            model=self.pro_model,
        )
```

- [ ] **Step 6: Run synthesis test**

Run:

```bash
cd facttracer-backend
pytest tests/test_api.py::test_issue_synthesis_enriches_summary_and_missing_signals_without_inventing_facts -q
```

Expected: PASS.

- [ ] **Step 7: Run page-builder tests**

Run:

```bash
cd facttracer-backend
pytest tests/test_api.py::test_issue_timeline_lists_articles_and_update_logs_in_order tests/test_api.py::test_claims_cluster_by_prd_issue_bucket_not_each_sentence -q
```

Expected: PASS.

- [ ] **Step 8: Commit if repository exists**

Run only in a Git repository:

```bash
git add facttracer-backend/app/services/issues/synthesis.py facttracer-backend/app/services/issues/page_builder.py facttracer-backend/app/services/ai/deepseek_client.py facttracer-backend/tests/test_api.py
git commit -m "feat: synthesize grounded issue detail cache"
```

---

### Task 6: Issue Ranking, Sort Modes, And Personalization

**Files:**
- Create: `facttracer-backend/app/services/issues/ranking.py`
- Modify: `facttracer-backend/app/api/routes/issues.py`
- Modify: `facttracer-backend/app/schemas.py`
- Modify: `facttracer-backend/app/serializers.py`
- Modify: `facttracer-backend/tests/test_api.py`

- [ ] **Step 1: Write failing ranking tests**

Append:

```python
def test_home_sort_controversial_prioritizes_high_conflict_issue() -> None:
    db = SessionLocal()
    try:
        db.add_all(
            [
                models.Issue(
                    id="issue_latest_low_conflict",
                    is_public=True,
                    title="최근 단순 업데이트",
                    topic="사회",
                    summary="최근 업데이트됐지만 논란도는 낮습니다.",
                    article_count=2,
                    needs_review_count=0,
                    issue_score=40,
                    updated_at=datetime.now(UTC),
                ),
                models.Issue(
                    id="issue_controversial_election",
                    is_public=True,
                    title="선관위 투표용지 부족 사태",
                    topic="정치",
                    major_topic_name="2026 지방선거",
                    event_group_name="선관위 투표용지 부족 사태",
                    summary="기사와 주장 충돌이 큰 사건입니다.",
                    article_count=30,
                    needs_review_count=8,
                    changed_claims=4,
                    issue_score=91,
                    updated_at=datetime.now(UTC) - timedelta(hours=2),
                ),
            ]
        )
        db.commit()
    finally:
        db.close()

    with TestClient(app) as client:
        response = client.get("/v1/issues/home?sort=controversial")
        assert response.status_code == 200
        assert response.json()["issues"][0]["id"] == "issue_controversial_election"
        assert response.json()["issues"][0]["rankReason"]


def test_home_major_topic_filter_uses_major_topic_name() -> None:
    db = SessionLocal()
    try:
        db.add_all(
            [
                models.Issue(
                    id="issue_major_election",
                    is_public=True,
                    title="선관위 투표용지 부족 사태",
                    topic="정치",
                    major_topic_name="2026 지방선거",
                    summary="선거 관련 이슈입니다.",
                ),
                models.Issue(
                    id="issue_major_economy",
                    is_public=True,
                    title="부동산 공급 대책",
                    topic="경제",
                    major_topic_name="부동산 공급정책",
                    summary="경제 관련 이슈입니다.",
                ),
            ]
        )
        db.commit()
    finally:
        db.close()

    with TestClient(app) as client:
        response = client.get("/v1/issues/home?majorTopic=2026%20지방선거")
        assert response.status_code == 200
        assert [issue["id"] for issue in response.json()["issues"]] == ["issue_major_election"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd facttracer-backend
pytest tests/test_api.py::test_home_sort_controversial_prioritizes_high_conflict_issue tests/test_api.py::test_home_major_topic_filter_uses_major_topic_name -q
```

Expected: FAIL because `majorTopic` filter and `sort` are not implemented.

- [ ] **Step 3: Create ranking service**

Create `facttracer-backend/app/services/issues/ranking.py`:

```python
from __future__ import annotations

from datetime import UTC, datetime

from app import models


SORT_MODES = {
    "recommended",
    "latest",
    "controversial",
    "highImpact",
    "needsReview",
    "officialUpdated",
    "personalized",
}


def _age_hours(issue: models.Issue) -> float:
    now = datetime.now(UTC)
    updated = issue.updated_at
    if updated.tzinfo is None:
        updated = updated.replace(tzinfo=UTC)
    return max((now - updated).total_seconds() / 3600, 0.0)


def _freshness(issue: models.Issue) -> float:
    return max(0.0, 100.0 - _age_hours(issue) * 2.5)


def _controversy(issue: models.Issue) -> float:
    return min(100.0, issue.article_count * 2.2 + issue.needs_review_count * 7 + issue.changed_claims * 8)


def _impact(issue: models.Issue) -> float:
    topic_bonus = 30 if issue.topic in {"정치", "재난", "보건", "경제"} else 10
    election_bonus = 25 if "선거" in f"{issue.major_topic_name} {issue.title}" else 0
    return min(100.0, issue.issue_score * 0.55 + topic_bonus + election_bonus)


def _verification(issue: models.Issue) -> float:
    official = any(
        str(source.get("sourceType", "")).lower() in {"official", "public", "statistics", "law"}
        for source in (issue.source_documents or [])
        if isinstance(source, dict)
    )
    return min(100.0, issue.verified_count * 8 + len(issue.confirmed_facts or []) * 10 + (25 if official else 0))


def _momentum(issue: models.Issue) -> float:
    ranking = issue.ranking_json or {}
    return min(100.0, float(ranking.get("recentArticleGrowth") or 0) * 12 + issue.changed_claims * 6)


def _personal(issue: models.Issue, user: models.User | None) -> float:
    if not user:
        return 0.0
    preferences = user.preferences or {}
    preferred = str(preferences.get("preferredPerspective") or "")
    score = 0.0
    if issue.topic and issue.topic in preferred:
        score += 18
    if issue.major_topic_name and issue.major_topic_name in preferred:
        score += 24
    return min(score, 40.0)


def score_issue(issue: models.Issue, *, sort: str, user: models.User | None = None) -> tuple[float, str]:
    freshness = _freshness(issue)
    controversy = _controversy(issue)
    impact = _impact(issue)
    verification = _verification(issue)
    momentum = _momentum(issue)
    personal = _personal(issue, user)
    mode = sort if sort in SORT_MODES else "recommended"
    if mode == "latest":
        score = freshness
        reason = "최근 업데이트"
    elif mode == "controversial":
        score = controversy * 0.65 + impact * 0.25 + freshness * 0.10
        reason = "기사량·검토 필요·판정 변경 기준 논란도"
    elif mode == "highImpact":
        score = impact * 0.70 + controversy * 0.20 + freshness * 0.10
        reason = "공익 영향도"
    elif mode == "needsReview":
        score = issue.needs_review_count * 12 + (100 - issue.quality_score) * 0.35
        reason = "근거 부족 또는 검토 필요"
    elif mode == "officialUpdated":
        score = verification * 0.55 + issue.changed_claims * 10 + freshness * 0.20
        reason = "공식자료·수치·판정 변경"
    elif mode == "personalized":
        score = impact * 0.22 + controversy * 0.20 + freshness * 0.18 + momentum * 0.12 + verification * 0.08 + personal * 0.20
        reason = "관심 분야와 공익성 혼합"
    else:
        score = impact * 0.25 + controversy * 0.22 + freshness * 0.20 + momentum * 0.15 + verification * 0.10 + personal * 0.08
        reason = "공익성·논란도·최신성 추천"
    return round(score, 2), reason


def rank_issues(issues: list[models.Issue], *, sort: str = "recommended", user: models.User | None = None) -> list[models.Issue]:
    ranked: list[tuple[models.Issue, float, str]] = []
    for issue in issues:
        score, reason = score_issue(issue, sort=sort, user=user)
        issue.ranking_json = {**(issue.ranking_json or {}), "rankScore": score, "rankReason": reason}
        ranked.append((issue, score, reason))
    ranked.sort(key=lambda row: (row[1], row[0].updated_at), reverse=True)
    return [issue for issue, _, _ in ranked]
```

- [ ] **Step 4: Add query params to home route**

In `facttracer-backend/app/api/routes/issues.py`, import:

```python
from app.services.issues.ranking import rank_issues
```

Update `home` signature:

```python
    user: Annotated[models.User | None, Depends(optional_current_user)] = None,
    event_group: Annotated[str | None, Query(alias="eventGroup")] = None,
    major_topic: Annotated[str | None, Query(alias="majorTopic")] = None,
    sort: str = "recommended",
```

Filter and rank:

```python
    issues = [
        issue
        for issue in db.scalars(query).all()
        if (not requested_topic or normalize_topic(issue.topic) == requested_topic)
        and (not major_topic or issue.major_topic_name == major_topic or issue.major_topic_id == major_topic)
        and (not event_group or issue.event_group_name == event_group or issue.event_group_id == event_group)
    ]
    issues = rank_issues(issues, sort=sort, user=user)
    db.flush()
```

Remove `query.order_by(models.Issue.updated_at.desc())` or keep it only as a DB-level stable pre-order before ranking.

- [ ] **Step 5: Run ranking tests**

Run:

```bash
cd facttracer-backend
pytest tests/test_api.py::test_home_sort_controversial_prioritizes_high_conflict_issue tests/test_api.py::test_home_major_topic_filter_uses_major_topic_name -q
```

Expected: PASS.

- [ ] **Step 6: Run public API contract test**

Run:

```bash
cd facttracer-backend
pytest tests/test_api.py::test_api_spec_contract_all_declared_endpoints -q
```

Expected: PASS.

- [ ] **Step 7: Commit if repository exists**

Run only in a Git repository:

```bash
git add facttracer-backend/app/services/issues/ranking.py facttracer-backend/app/api/routes/issues.py facttracer-backend/app/schemas.py facttracer-backend/app/serializers.py facttracer-backend/tests/test_api.py
git commit -m "feat: rank issues by context and personalization"
```

---

### Task 7: Worker And Scheduler Integration

**Files:**
- Modify: `facttracer-backend/app/workers/issue_jobs.py`
- Modify: `facttracer-backend/app/services/jobs.py`
- Modify: `facttracer-backend/tests/test_api.py`

- [ ] **Step 1: Write failing worker integration test**

Append:

```python
def test_parse_article_refreshes_taxonomy_image_quality_jobs() -> None:
    db = SessionLocal()
    try:
        issue = models.Issue(
            id="issue_worker_integration",
            title="선관위 투표용지 부족 사태",
            topic="정치",
            summary="작업 연결 테스트입니다.",
        )
        article = models.Article(
            id="article_worker_integration",
            issue_id=issue.id,
            title="선관위 투표용지 부족 후속 보도",
            publisher="테스트뉴스",
            url="https://example.com/worker",
            dedup_hash="worker",
            body_text="선관위 투표용지 부족 후속 보도입니다.",
            summary="후속 보도",
        )
        db.add_all([issue, article])
        db.commit()
    finally:
        db.close()

    result = issue_jobs.parse_article("article_worker_integration")
    assert result["status"] == "completed"

    db = SessionLocal()
    try:
        issue = db.get(models.Issue, "issue_worker_integration")
        assert issue.major_topic_name == "2026 지방선거"
        assert issue.event_group_name == "선관위 투표용지 부족 사태"
        job_types = {
            row.job_type
            for row in db.scalars(select(models.JobAttempt).where(models.JobAttempt.target_id == issue.id)).all()
        }
        assert "assess_issue_quality" in job_types
        assert "select_representative_image" in job_types
    finally:
        db.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd facttracer-backend
pytest tests/test_api.py::test_parse_article_refreshes_taxonomy_image_quality_jobs -q
```

Expected: FAIL until parse pipeline enqueues the new jobs.

- [ ] **Step 3: Add shared enqueue helpers**

In `facttracer-backend/app/workers/issue_jobs.py`, add:

```python
def _enqueue_singleton_job(db: Session, *, issue_id: str, job_type: str) -> bool:
    existing = db.scalar(
        select(models.JobAttempt.id).where(
            models.JobAttempt.job_type == job_type,
            models.JobAttempt.target_id == issue_id,
            models.JobAttempt.status.in_(["queued", "running"]),
        )
    )
    if existing:
        return False
    from app.services.jobs import enqueue_job

    enqueue_job(
        db,
        input_json={"issue_id": issue_id},
        job_type=job_type,
        run_immediately=False,
        target_id=issue_id,
    )
    return True


def _enqueue_issue_enrichment_jobs(db: Session, *, issue_id: str) -> dict:
    return {
        "quality": _enqueue_singleton_job(db, issue_id=issue_id, job_type="assess_issue_quality"),
        "image": _enqueue_singleton_job(db, issue_id=issue_id, job_type="select_representative_image"),
        "page": _enqueue_singleton_job(db, issue_id=issue_id, job_type="update_issue_page"),
    }
```

Call this helper after `refresh_issue_cache` in:

- `process_article`
- `search_news`
- `backfill_issue_sources`
- `discover_topic`
- `verify_claim`

- [ ] **Step 4: Register job priority**

In `facttracer-backend/app/services/jobs.py`, include new jobs in the high-priority list:

```python
"select_representative_image",
"assess_issue_quality",
```

- [ ] **Step 5: Run worker integration test**

Run:

```bash
cd facttracer-backend
pytest tests/test_api.py::test_parse_article_refreshes_taxonomy_image_quality_jobs -q
```

Expected: PASS.

- [ ] **Step 6: Run scheduler suite subset**

Run:

```bash
cd facttracer-backend
pytest tests/test_api.py::test_active_issue_followup_runs_even_with_enough_sources tests/test_api.py::test_api_spec_contract_all_declared_endpoints -q
```

Expected: PASS.

- [ ] **Step 7: Commit if repository exists**

Run only in a Git repository:

```bash
git add facttracer-backend/app/workers/issue_jobs.py facttracer-backend/app/services/jobs.py facttracer-backend/tests/test_api.py
git commit -m "feat: enqueue issue enrichment jobs"
```

---

### Task 8: Frontend API And Image Fallback Compatibility

**Files:**
- Modify: `facttracer-next/src/lib/api/types.ts`
- Modify: `facttracer-next/src/lib/api/facttracer.ts`
- Modify: `facttracer-next/src/app/page.tsx`

- [ ] **Step 1: Update API types**

In `facttracer-next/src/lib/api/types.ts`, add:

```ts
export type IssueSortMode =
  | "recommended"
  | "latest"
  | "controversial"
  | "highImpact"
  | "needsReview"
  | "officialUpdated"
  | "personalized";
```

Ensure `Issue` includes:

```ts
  majorTopic?: string | null;
  majorTopicId?: string | null;
  eventGroup?: string | null;
  eventGroupId?: string | null;
  representativeImageUrl?: string | null;
  representativeImageSource?: string | null;
  rankScore?: number | null;
  rankReason?: string | null;
```

- [ ] **Step 2: Update API client params**

In `facttracer-next/src/lib/api/facttracer.ts`, import `IssueSortMode` and update `getPublicHome`:

```ts
export async function getPublicHome({
  eventGroup,
  issueId,
  majorTopic,
  query,
  sort,
  topic,
}: {
  eventGroup?: string;
  issueId?: string;
  majorTopic?: string;
  query?: string;
  sort?: IssueSortMode;
  topic?: string;
} = {}): Promise<PublicHomeResponse> {
  if (!isApiConfigured()) return emptyPublicHome;

  return apiFetch<PublicHomeResponse>("/v1/issues/home", {
    cache: "no-store",
    searchParams: { eventGroup, issueId, majorTopic, q: query, sort, topic },
  });
}
```

- [ ] **Step 3: Update home page search params and image component**

In `facttracer-next/src/app/page.tsx`, update `searchParams` type:

```ts
  searchParams?: Promise<{
    eventGroup?: string;
    majorTopic?: string;
    q?: string;
    sort?: IssueSortMode;
    topic?: string;
  }>;
```

Pass params:

```ts
    home = await getPublicHome({
      eventGroup: params.eventGroup,
      majorTopic: params.majorTopic,
      query: params.q,
      sort: params.sort ?? "recommended",
      topic: normalizeTopicParam(params.topic),
    });
```

Stop overriding backend ranking:

```ts
  const issues = home.issues;
```

Update `NewsImage` props:

```ts
function NewsImage({
  className,
  imageIndex,
  issue,
  sizes,
}: {
  className: string;
  imageIndex: number;
  issue?: Issue;
  sizes: string;
}) {
  const source =
    issue?.representativeImageUrl ||
    newsImageSources[imageIndex % newsImageSources.length] ||
    newsImageSources[0];
```

Pass `issue={issue}` to every `NewsImage` call.

- [ ] **Step 4: Keep Next image remote compatibility**

If Next rejects remote image domains at runtime, use `unoptimized` for representative images:

```tsx
      <Image
        alt=""
        className="object-cover"
        fill
        sizes={sizes}
        src={source}
        unoptimized={Boolean(issue?.representativeImageUrl)}
      />
```

- [ ] **Step 5: Run frontend checks**

Run:

```bash
cd facttracer-next
npm run lint
```

Expected: PASS.

- [ ] **Step 6: Run backend API contract after frontend type update**

Run:

```bash
cd facttracer-backend
pytest tests/test_api.py::test_api_spec_contract_all_declared_endpoints -q
```

Expected: PASS.

- [ ] **Step 7: Commit if repository exists**

Run only in a Git repository:

```bash
git add facttracer-next/src/lib/api/types.ts facttracer-next/src/lib/api/facttracer.ts facttracer-next/src/app/page.tsx
git commit -m "feat: render backend ranked issues and representative images"
```

---

### Task 9: Full Verification And Backfill Dry Run

**Files:**
- Modify after failures only: files touched in Tasks 1-8.

- [ ] **Step 1: Run full backend suite**

Run:

```bash
cd facttracer-backend
pytest -q
```

Expected: PASS.

- [ ] **Step 2: Run API spec audit**

Run:

```bash
cd facttracer-backend
python scripts/audit_api_spec.py
```

Expected: `API spec audit passed`.

- [ ] **Step 3: Run frontend lint**

Run:

```bash
cd facttracer-next
npm run lint
```

Expected: PASS.

- [ ] **Step 4: Run taxonomy backfill against local DB**

Run:

```bash
cd facttracer-backend
python scripts/backfill_issue_taxonomy.py
```

Expected: prints `Backfilled taxonomy for 0 issues` on an empty DB, or the exact number of existing issues on a populated DB.

- [ ] **Step 5: Start app locally for smoke test**

Run:

```bash
docker compose up --build
```

Expected:

- Web available at `http://localhost:3000`
- API available at `http://localhost:8000`
- Home endpoint returns additive fields:

```bash
curl -s "http://localhost:8000/v1/issues/home?sort=recommended" | python -m json.tool
```

- [ ] **Step 6: Confirm key runtime behavior**

Check response JSON contains these fields on issue rows when data exists:

```json
{
  "majorTopic": "2026 지방선거",
  "eventGroup": "선관위 투표용지 부족 사태",
  "representativeImageUrl": "https://...",
  "rankScore": 91.2,
  "rankReason": "공익성·논란도·최신성 추천"
}
```

- [ ] **Step 7: Stop local services**

Run:

```bash
docker compose down
```

Expected: containers stop cleanly.

- [ ] **Step 8: Final commit if repository exists**

Run only in a Git repository:

```bash
git status --short
git add facttracer-backend facttracer-next docs/superpowers
git commit -m "feat: improve backend collection classification ranking"
```

If previous task commits were made, this final commit should have no changes and can be skipped.

---

## Plan Self-Review

Spec coverage:

- `topic -> majorTopic -> eventGroup -> issue`: Task 1 and Task 2.
- Representative image extraction and automatic selection: Task 3.
- Quality-driven re-search: Task 4.
- Grounded detail synthesis: Task 5.
- Ranking, category sorting, and personalization hooks: Task 6.
- Worker/scheduler integration: Task 7.
- Frontend contract and image fallback: Task 8.
- Verification and backfill: Task 9.

Type consistency:

- Backend public fields use camelCase in schemas and serializers.
- DB fields use snake_case.
- Frontend `Issue` type mirrors backend response names.
- Job names are `select_representative_image` and `assess_issue_quality` across handlers and enqueues.

Execution note:

- This plan intentionally keeps all API changes additive.
- Current workspace root is not a Git repository, so commit steps are documented but not executable here until a repository exists.
