# DB Quality Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent new low-relevance/generic articles from being attached to issues, make quality/ranking scores reflect usable evidence, and provide a repair path for the contaminated live DB identified in `docs/DB_INFORMATION_QUALITY_AUDIT_2026-06-11.md`.

**Architecture:** Add a focused issue/article quality module that centralizes relevance, generic-page, duplicate-content, and score-signal logic. Wire that module into collection workers, quality scoring, ranking/scoring, and a DB repair script so new ingestion and existing data use the same gates.

**Tech Stack:** Python, FastAPI backend, SQLAlchemy ORM, SQLite, pytest.

---

### Task 1: Article-Issue Quality Gate

**Files:**
- Create: `facttracer-backend/app/services/issues/article_quality.py`
- Modify: `facttracer-backend/app/workers/issue_jobs.py`
- Test: `facttracer-backend/tests/test_api.py`

- [ ] **Step 1: Write failing tests**

```python
def test_issue_article_quality_rejects_generic_public_pages() -> None:
    from app.services.issues.article_quality import is_generic_article_page
    assert is_generic_article_page(title="- 공공데이터포털", publisher="공공데이터포털", url="https://data.go.kr/data/1")
    assert is_generic_article_page(title="문서뷰어 - 대한민국 정책브리핑", publisher="대한민국 정책브리핑", url="https://korea.kr/viewer")
    assert is_generic_article_page(title="Untitled - 중앙선거관리위원회", publisher="중앙선거관리위원회", url="https://nec.go.kr/doc")


def test_issue_article_quality_requires_issue_relevance() -> None:
    from app.services.issues.article_quality import article_matches_issue
    issue = models.Issue(id="issue_fire", title="대전 한화에어로 공장 화재 사고", topic="재난", status="검증 진행", risk="고영향")
    relevant = CollectedArticle(title="'7명 사상' 한화에어로스페이스 폭발 화재", publisher="연합뉴스", url="https://example.com/a")
    irrelevant = CollectedArticle(title="전세사기피해지원위원회 피해자 825건 결정", publisher="국토교통부", url="https://example.com/b")
    assert article_matches_issue(issue, relevant)
    assert not article_matches_issue(issue, irrelevant)
```

- [ ] **Step 2: Run tests to verify RED**

Run: `cd facttracer-backend && pytest tests/test_api.py::test_issue_article_quality_rejects_generic_public_pages tests/test_api.py::test_issue_article_quality_requires_issue_relevance -q`

Expected: fail because `app.services.issues.article_quality` does not exist.

- [ ] **Step 3: Implement the module and wire workers**

Create `article_quality.py` with:
- `is_generic_article_page(...)`
- `article_matches_issue(...)`
- `should_attach_article_to_issue(...)`
- `relevant_issue_articles(...)`
- `cleanup_redundant_parse_jobs(...)`

Update workers so `search_news`, `backfill_issue_sources`, and discovery linking only attach collected articles that pass `should_attach_article_to_issue`.

- [ ] **Step 4: Run targeted tests**

Run: `cd facttracer-backend && pytest tests/test_api.py::test_issue_article_quality_rejects_generic_public_pages tests/test_api.py::test_issue_article_quality_requires_issue_relevance -q`

Expected: pass.

### Task 2: Quality And Ranking Corrections

**Files:**
- Modify: `facttracer-backend/app/services/issues/quality.py`
- Modify: `facttracer-backend/app/services/issues/scoring.py`
- Modify: `facttracer-backend/app/services/issues/ranking.py`
- Test: `facttracer-backend/tests/test_api.py`

- [ ] **Step 1: Write failing tests**

```python
def test_quality_report_penalizes_low_relevance_articles_and_zero_claims() -> None:
    db = SessionLocal()
    try:
        issue = models.Issue(id="issue_low", title="RSV 전국 유행 주의보", topic="보건", status="검증 진행", risk="고영향", issue_score=90)
        db.add(issue)
        db.add(models.Article(id="article_generic", issue_id=issue.id, title="이달의 건강정보 - 국가건강정보포털", publisher="국가건강정보포털", url="https://health.example/generic", normalized_url="https://health.example/generic", dedup_hash="dh1", content_hash="ch1", parse_status="parsed"))
        db.commit()
        report = build_issue_quality_report(db, issue=issue)
        assert "relevanceCoverage" in report["missingSignals"]
        assert "claimCoverage" in report["missingSignals"]
        assert report["score"] <= 60
    finally:
        db.close()
```

- [ ] **Step 2: Run test to verify RED**

Run: `cd facttracer-backend && pytest tests/test_api.py::test_quality_report_penalizes_low_relevance_articles_and_zero_claims -q`

Expected: fail because relevance is not part of the score.

- [ ] **Step 3: Implement score fixes**

Use `relevant_issue_articles()` in quality/scoring/ranking. Cap `needs_retry` scores, penalize zero-claim high-article issues, and base article/publisher signals on relevant non-generic articles.

- [ ] **Step 4: Run targeted tests**

Run: `cd facttracer-backend && pytest tests/test_api.py::test_quality_report_penalizes_low_relevance_articles_and_zero_claims -q`

Expected: pass.

### Task 3: Live DB Repair Script

**Files:**
- Create: `facttracer-backend/scripts/repair_db_quality.py`
- Test: `facttracer-backend/tests/test_api.py`

- [ ] **Step 1: Write failing tests**

```python
def test_cleanup_redundant_parse_jobs_marks_parsed_article_jobs_completed() -> None:
    db = SessionLocal()
    try:
        article = models.Article(id="article_done", title="완료 기사", publisher="연합뉴스", url="https://example.com/done", normalized_url="https://example.com/done", dedup_hash="done", content_hash="done", parse_status="parsed")
        db.add(article)
        db.add(models.JobAttempt(id="job_parse_done", job_type="parse_article", target_id=article.id, status="queued", input_json={"article_id": article.id}))
        db.commit()
        from app.services.issues.article_quality import cleanup_redundant_parse_jobs
        result = cleanup_redundant_parse_jobs(db)
        db.commit()
        assert result["completed"] == 1
        assert db.get(models.JobAttempt, "job_parse_done").status == "completed"
    finally:
        db.close()
```

- [ ] **Step 2: Run test to verify RED**

Run: `cd facttracer-backend && pytest tests/test_api.py::test_cleanup_redundant_parse_jobs_marks_parsed_article_jobs_completed -q`

Expected: fail until cleanup helper exists.

- [ ] **Step 3: Implement repair script**

The script must:
- detach generic/low-relevance issue articles
- complete redundant queued parse jobs
- deactivate stale/broad quality retry keywords that use generic event group text
- rebuild issue caches and quality reports
- support `--dry-run` and default to dry run unless `--apply` is passed

- [ ] **Step 4: Run dry-run and tests**

Run: `cd facttracer-backend && pytest tests/test_api.py::test_cleanup_redundant_parse_jobs_marks_parsed_article_jobs_completed -q`

Run: `docker exec -i facttracer-api-1 python /app/scripts/repair_db_quality.py --dry-run`

Expected: test pass and dry-run reports candidate repairs without mutating DB.

### Task 4: Verification And Re-Audit

**Files:**
- Modify: `docs/DB_INFORMATION_QUALITY_AUDIT_2026-06-11.md` only if results need a remediation appendix.

- [ ] **Step 1: Run full backend tests**

Run: `cd facttracer-backend && pytest -q`

Expected: all tests pass.

- [ ] **Step 2: Apply repair to live DB**

Run: `docker compose build api && docker compose up -d api`

Run: `docker exec -i facttracer-api-1 python /app/scripts/repair_db_quality.py --apply`

Expected: repair script reports detached/cleaned counts and exits 0.

- [ ] **Step 3: Re-audit live DB**

Run live DB aggregate checks for:
- low-relevance high-article issues
- zero-claim public high-article issues
- cross-issue `content_hash` duplicate groups
- redundant queued `parse_article` jobs
- quality `needs_retry` score contradictions

Expected: all audit categories have either zero violations or documented remaining exceptions with reasons.
