from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Callable

from sqlalchemy import case, or_, select, update
from sqlalchemy.orm import Session

from app import models
from app.db.session import SessionLocal
from app.services.admin.settings import get_effective_setting
from app.services.podcasts.tts import safe_tts_error_message
from app.services.search.keywords import is_search_query_usable
from app.utils import new_id


JobHandler = Callable[..., dict]


def _age_seconds(value: datetime | None, now: datetime) -> float | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    return (now - value).total_seconds()


def _is_future(value: datetime | None, now: datetime) -> bool:
    if value is None:
        return False
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    return value > now


def _quality_retry_keyword_due(db: Session, keyword: models.SearchKeyword, now: datetime) -> bool:
    if keyword.source != "quality_retry":
        return True
    if not keyword.issue_id:
        keyword.status = "inactive"
        keyword.updated_at = now
        return False
    issue = db.get(models.Issue, keyword.issue_id)
    if not issue or issue.quality_status != "needs_retry":
        keyword.status = "inactive"
        keyword.updated_at = now
        return False
    return not _is_future(issue.next_quality_retry_at, now)


def _deactivate_low_quality_keyword(keyword: models.SearchKeyword, now: datetime) -> None:
    keyword.status = "inactive"
    keyword.metadata_json = {
        **(keyword.metadata_json or {}),
        "deactivated_at": now.isoformat(),
        "deactivated_reason": "low_quality_query",
    }
    keyword.updated_at = now


def _handlers() -> dict[str, JobHandler]:
    from app.workers import issue_jobs
    from app.workers import podcast_jobs

    return {
        "collect_source": issue_jobs.collect_source,
        "collect_sources": issue_jobs.collect_sources,
        "backfill_issue_sources": issue_jobs.backfill_issue_sources,
        "parse_article": issue_jobs.parse_article,
        "deduplicate_article": issue_jobs.deduplicate_article,
        "discover_topic": issue_jobs.discover_topic,
        "detect_issue": issue_jobs.detect_issue,
        "match_issue": issue_jobs.match_issue,
        "research_issue": issue_jobs.research_issue,
        "extract_claims": issue_jobs.extract_claims,
        "cluster_claim": issue_jobs.cluster_claim,
        "retrieve_evidence": issue_jobs.retrieve_evidence,
        "verify_claim": issue_jobs.verify_claim,
        "update_issue_page": issue_jobs.update_issue_page,
        "assess_issue_quality": issue_jobs.assess_issue_quality_job,
        "select_representative_image": issue_jobs.select_representative_image_job,
        "send_issue_notifications": issue_jobs.send_issue_notifications,
        "search_news": issue_jobs.search_news,
        "generate_podcasts": podcast_jobs.generate_podcasts,
        "render_podcast_audio": podcast_jobs.render_podcast_audio,
    }


def _rq_enqueue(db: Session, job_id: str) -> bool:
    redis_url = get_effective_setting(db, "redis_url")
    try:
        from redis import Redis
        from rq import Queue

        redis = Redis.from_url(redis_url)
        queue = Queue("facttracer", connection=redis)
        queue.enqueue("app.services.jobs.execute_job_by_id", job_id)
        return True
    except Exception:
        return False


def enqueue_job(
    db: Session,
    *,
    input_json: dict | None = None,
    job_type: str,
    max_attempts: int = 3,
    run_immediately: bool | None = None,
    target_id: str,
) -> models.JobAttempt:
    worker_backend = get_effective_setting(db, "worker_backend")
    job = models.JobAttempt(
        id=new_id("job"),
        input_json=input_json or {},
        job_type=job_type,
        max_attempts=max_attempts,
        status="queued",
        target_id=target_id,
    )
    db.add(job)
    db.flush()

    should_run_now = bool(run_immediately)
    if worker_backend == "rq" and _rq_enqueue(db, job.id):
        job.status = "queued"
    elif should_run_now:
        execute_job(db, job=job)
    db.flush()
    return job


def execute_job(db: Session, *, job: models.JobAttempt) -> models.JobAttempt:
    job.status = "running"
    job.attempts += 1
    job.updated_at = models.now_utc()
    db.flush()
    db.commit()
    db.refresh(job)
    return _execute_running_job(db, job=job)


def _execute_running_job(db: Session, *, job: models.JobAttempt) -> models.JobAttempt:
    handlers = _handlers()
    handler = handlers.get(job.job_type)
    if not handler:
        job.status = "dead_letter"
        job.last_error = f"Unknown job type: {job.job_type}"
        job.updated_at = models.now_utc()
        db.flush()
        return job

    try:
        result = _call_handler(handler, job)
        job.output_json = result or {}
        job.status = result.get("status", "completed") if isinstance(result, dict) else "completed"
        if job.status == "failed":
            error = ""
            if isinstance(result, dict):
                error = str(result.get("error") or result.get("message") or result.get("reason") or "")
            job.last_error = error or "Handler returned failed status"
            if job.attempts >= job.max_attempts:
                job.status = "dead_letter"
                job.next_run_at = None
            else:
                job.next_run_at = models.now_utc() + timedelta(minutes=min(job.attempts * 5, 30))
        elif job.status not in {"dead_letter"}:
            job.last_error = ""
            job.next_run_at = None
    except Exception as exc:
        job.last_error = (
            safe_tts_error_message(exc)
            if job.job_type in {"generate_podcasts", "render_podcast_audio"}
            else str(exc)
        )
        job.status = "dead_letter" if job.attempts >= job.max_attempts else "failed"
        if job.status == "failed":
            job.next_run_at = models.now_utc() + timedelta(minutes=min(job.attempts * 5, 30))
    job.updated_at = models.now_utc()
    db.flush()
    return job


def _call_handler(handler: JobHandler, job: models.JobAttempt) -> dict:
    payload: dict[str, Any] = job.input_json or {}
    if job.job_type == "collect_sources":
        return handler(payload.get("source_ids"))
    if job.job_type == "detect_issue":
        return handler(payload.get("article_ids", [job.target_id]))
    if job.job_type == "send_issue_notifications":
        return handler(payload.get("issue_id"), payload.get("update_log_id", job.target_id))
    if payload:
        try:
            return handler(**payload)
        except TypeError:
            pass
    return handler(job.target_id)


def execute_job_by_id(job_id: str) -> dict:
    db = SessionLocal()
    try:
        job = db.get(models.JobAttempt, job_id)
        if not job:
            return {"status": "not_found"}
        execute_job(db, job=job)
        db.commit()
        return {"status": job.status, "output": job.output_json}
    finally:
        db.close()


def execute_claimed_job_by_id(job_id: str) -> dict:
    db = SessionLocal()
    try:
        job = db.get(models.JobAttempt, job_id)
        if not job:
            return {"status": "not_found"}
        if job.status != "running":
            return {"reason": f"job_status:{job.status}", "status": "skipped"}
        _execute_running_job(db, job=job)
        db.commit()
        return {"status": job.status, "output": job.output_json}
    finally:
        db.close()


def recover_stale_jobs(db: Session, *, stale_after_minutes: int | None = None) -> list[models.JobAttempt]:
    minutes = int(get_effective_setting(db, "job_stale_after_minutes") if stale_after_minutes is None else stale_after_minutes)
    now = models.now_utc()
    rows = db.scalars(select(models.JobAttempt).where(models.JobAttempt.status == "running")).all()
    recovered: list[models.JobAttempt] = []
    for job in rows:
        age = _age_seconds(job.updated_at, now)
        if age is None or age < minutes * 60:
            continue
        job.status = "failed" if job.attempts < job.max_attempts else "dead_letter"
        job.next_run_at = now if job.status == "failed" else None
        job.last_error = f"실행 중단 감지: {minutes}분 이상 상태 갱신 없음"
        job.updated_at = now
        recovered.append(job)
    if recovered:
        db.flush()
    return recovered


def recover_stale_collector_runs(db: Session, *, stale_after_minutes: int | None = None) -> list[models.CollectorRun]:
    minutes = int(get_effective_setting(db, "job_stale_after_minutes") if stale_after_minutes is None else stale_after_minutes)
    now = models.now_utc()
    rows = db.scalars(select(models.CollectorRun).where(models.CollectorRun.status == "running")).all()
    recovered: list[models.CollectorRun] = []
    for run in rows:
        age = _age_seconds(run.started_at, now)
        if age is None or age < minutes * 60:
            continue
        run.status = "failed"
        run.finished_at = now
        run.error_message = f"실행 중단 감지: {minutes}분 이상 완료되지 않음"
        recovered.append(run)
    if recovered:
        db.flush()
    return recovered


def _job_priority_expression():
    return case(
        (
            models.JobAttempt.job_type == "verify_claim",
            0,
        ),
        (
            models.JobAttempt.job_type == "retrieve_evidence",
            1,
        ),
        (
            models.JobAttempt.job_type.in_(
                [
                    "extract_claims",
                    "cluster_claim",
                ],
            ),
            2,
        ),
        (
            models.JobAttempt.job_type == "parse_article",
            3,
        ),
        (
            models.JobAttempt.job_type.in_(
                [
                    "update_issue_page",
                    "assess_issue_quality",
                    "select_representative_image",
                ],
            ),
            4,
        ),
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
            5,
        ),
        (
            models.JobAttempt.job_type.in_(["generate_podcasts", "render_podcast_audio"]),
            8,
        ),
        else_=10,
    )


def claim_due_jobs(db: Session, *, limit: int = 20) -> list[str]:
    recover_stale_jobs(db)
    recover_stale_collector_runs(db)
    due_now = models.now_utc()
    candidate_ids = db.scalars(
        select(models.JobAttempt.id)
        .where(
            models.JobAttempt.status.in_(["queued", "failed"]),
            (models.JobAttempt.next_run_at.is_(None)) | (models.JobAttempt.next_run_at <= due_now),
        )
        .order_by(_job_priority_expression().asc(), models.JobAttempt.created_at.asc())
        .limit(limit),
    ).all()
    now = models.now_utc()
    claimed: list[str] = []
    for job_id in candidate_ids:
        result = db.execute(
            update(models.JobAttempt)
            .where(
                models.JobAttempt.id == job_id,
                models.JobAttempt.status.in_(["queued", "failed"]),
                (models.JobAttempt.next_run_at.is_(None)) | (models.JobAttempt.next_run_at <= now),
            )
            .values(
                attempts=models.JobAttempt.attempts + 1,
                status="running",
                updated_at=now,
            )
            .execution_options(synchronize_session=False),
        )
        if result.rowcount:
            claimed.append(str(job_id))
    if claimed:
        db.flush()
    return claimed


def run_due_jobs(db: Session, *, limit: int = 20) -> list[models.JobAttempt]:
    recover_stale_jobs(db)
    recover_stale_collector_runs(db)
    rows = db.scalars(
        select(models.JobAttempt)
        .where(
            models.JobAttempt.status.in_(["queued", "failed"]),
            (models.JobAttempt.next_run_at.is_(None)) | (models.JobAttempt.next_run_at <= models.now_utc()),
        )
        .order_by(_job_priority_expression().asc(), models.JobAttempt.created_at.asc())
        .limit(limit),
    ).all()
    for job in rows:
        execute_job(db, job=job)
    db.flush()
    return rows


def schedule_due_collector_jobs(db: Session) -> list[models.JobAttempt]:
    jobs: list[models.JobAttempt] = []
    sources = db.scalars(select(models.SourceDomain).where(models.SourceDomain.is_active.is_(True))).all()
    now = models.now_utc()
    for source in sources:
        if not source.collection_url:
            continue
        age = _age_seconds(source.last_collected_at, now)
        due = age is None or age >= source.collection_interval_minutes * 60
        if not due:
            continue
        existing = db.scalar(
            select(models.JobAttempt).where(
                models.JobAttempt.job_type == "collect_source",
                models.JobAttempt.target_id == source.id,
                models.JobAttempt.status.in_(["queued", "running"]),
            ),
        )
        if existing:
            continue
        jobs.append(
            enqueue_job(
                db,
                input_json={"source_id": source.id},
                job_type="collect_source",
                run_immediately=False,
                target_id=source.id,
            ),
        )
    db.flush()
    return jobs


def schedule_due_search_jobs(db: Session) -> list[models.JobAttempt]:
    jobs: list[models.JobAttempt] = []
    keywords = db.scalars(
        select(models.SearchKeyword).where(models.SearchKeyword.status == "active"),
    ).all()
    now = models.now_utc()
    for keyword in keywords:
        if not is_search_query_usable(keyword.query):
            _deactivate_low_quality_keyword(keyword, now)
            continue
        if not _quality_retry_keyword_due(db, keyword, now):
            continue
        age = _age_seconds(keyword.last_searched_at, now)
        due = age is None or age >= keyword.search_interval_minutes * 60
        if not due:
            continue
        existing = db.scalar(
            select(models.JobAttempt).where(
                models.JobAttempt.job_type == "search_news",
                models.JobAttempt.target_id == keyword.id,
                models.JobAttempt.status.in_(["queued", "running"]),
            ),
        )
        if existing:
            continue
        jobs.append(
            enqueue_job(
                db,
                input_json={"keyword_id": keyword.id},
                job_type="search_news",
                run_immediately=False,
                target_id=keyword.id,
            ),
        )
    db.flush()
    return jobs


def schedule_due_discovery_jobs(db: Session) -> list[models.JobAttempt]:
    jobs: list[models.JobAttempt] = []
    topics = db.scalars(
        select(models.DiscoveryTopic).where(models.DiscoveryTopic.status == "active"),
    ).all()
    now = models.now_utc()
    for topic in topics:
        age = _age_seconds(topic.last_discovered_at, now)
        due = age is None or age >= topic.discovery_interval_minutes * 60
        if not due:
            continue
        existing = db.scalar(
            select(models.JobAttempt).where(
                models.JobAttempt.job_type == "discover_topic",
                models.JobAttempt.target_id == topic.id,
                models.JobAttempt.status.in_(["queued", "running"]),
            ),
        )
        if existing:
            continue
        jobs.append(
            enqueue_job(
                db,
                input_json={"topic_id": topic.id},
                job_type="discover_topic",
                run_immediately=False,
                target_id=topic.id,
            ),
        )
    db.flush()
    return jobs


def schedule_due_issue_backfill_jobs(db: Session) -> list[models.JobAttempt]:
    min_sources = int(get_effective_setting(db, "issue_min_sources_for_public") or 1)
    limit = int(get_effective_setting(db, "issue_source_backfill_limit") or 8)
    followup_limit = int(get_effective_setting(db, "issue_followup_limit") or 12)
    followup_interval_minutes = int(get_effective_setting(db, "issue_followup_interval_minutes") or 180)
    followup_window_days = int(get_effective_setting(db, "issue_followup_window_days") or 7)
    now = models.now_utc()
    issues = db.scalars(
        select(models.Issue)
        .where(
            models.Issue.status != "숨김",
            models.Issue.article_count < min_sources,
        )
        .order_by(models.Issue.updated_at.asc())
        .limit(limit),
    ).all()
    jobs: list[models.JobAttempt] = []
    for issue in issues:
        existing = db.scalar(
            select(models.JobAttempt).where(
                models.JobAttempt.job_type == "backfill_issue_sources",
                models.JobAttempt.target_id == issue.id,
                models.JobAttempt.status.in_(["queued", "running"]),
            ),
        )
        if existing:
            continue
        jobs.append(
            enqueue_job(
                db,
                input_json={"issue_id": issue.id, "limit": 1},
                job_type="backfill_issue_sources",
                run_immediately=False,
                target_id=issue.id,
            ),
        )
    db.flush()
    recent_cutoff = now - timedelta(days=max(1, followup_window_days))
    due_cutoff = now - timedelta(minutes=max(5, followup_interval_minutes))
    followup_issues = db.scalars(
        select(models.Issue)
        .where(
            models.Issue.status.notin_(["숨김", "병합됨"]),
            models.Issue.is_public.is_(True),
            models.Issue.article_count >= min_sources,
            or_(
                models.Issue.created_at >= recent_cutoff,
                models.Issue.last_updated_at >= recent_cutoff,
            ),
            models.Issue.updated_at <= due_cutoff,
        )
        .order_by(models.Issue.issue_score.desc(), models.Issue.updated_at.asc())
        .limit(followup_limit),
    ).all()
    for issue in followup_issues:
        existing = db.scalar(
            select(models.JobAttempt).where(
                models.JobAttempt.job_type == "backfill_issue_sources",
                models.JobAttempt.target_id == issue.id,
                models.JobAttempt.status.in_(["queued", "running"]),
            ),
        )
        if existing:
            continue
        jobs.append(
            enqueue_job(
                db,
                input_json={"force": True, "issue_id": issue.id, "limit": 1},
                job_type="backfill_issue_sources",
                run_immediately=False,
                target_id=issue.id,
            ),
        )
    db.flush()
    return jobs


def schedule_due_podcast_jobs(db: Session) -> list[models.JobAttempt]:
    if not get_effective_setting(db, "podcast_generation_enabled", True):
        return []
    interval_minutes = int(get_effective_setting(db, "podcast_generation_interval_minutes", 60) or 60)
    limit = int(get_effective_setting(db, "podcast_generation_limit", 6) or 6)
    now = models.now_utc()

    has_public_issue = db.scalar(
        select(models.Issue.id)
        .where(
            models.Issue.is_public.is_(True),
            models.Issue.status.notin_(["숨김", "병합됨"]),
        )
        .limit(1),
    )
    if not has_public_issue:
        return []

    jobs: list[models.JobAttempt] = []
    for target_id, feed, job_limit in [
        ("podcast:auto", "recommended", max(1, min(limit, 30))),
        ("podcast:daily", "daily", max(2, min(limit, 8))),
    ]:
        existing = db.scalar(
            select(models.JobAttempt).where(
                models.JobAttempt.job_type == "generate_podcasts",
                models.JobAttempt.target_id == target_id,
                models.JobAttempt.status.in_(["queued", "running"]),
            ),
        )
        if existing:
            continue

        last_completed = db.scalar(
            select(models.JobAttempt)
            .where(
                models.JobAttempt.job_type == "generate_podcasts",
                models.JobAttempt.target_id == target_id,
                models.JobAttempt.status == "completed",
            )
            .order_by(models.JobAttempt.updated_at.desc())
            .limit(1),
        )
        age = _age_seconds(last_completed.updated_at if last_completed else None, now)
        if age is not None and age < interval_minutes * 60:
            continue

        jobs.append(
            enqueue_job(
                db,
                input_json={
                    "feed": feed,
                    "limit": job_limit,
                    "render_audio": bool(get_effective_setting(db, "podcast_tts_render_on_generate", True)),
                },
                job_type="generate_podcasts",
                run_immediately=False,
                target_id=target_id,
            ),
        )
    db.flush()
    return jobs
