from __future__ import annotations

import os
import threading
import time
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app import models
from app.db.session import SessionLocal
from app.services.admin.settings import get_effective_setting
from app.services.jobs import (
    claim_due_jobs,
    execute_claimed_job_by_id,
    recover_stale_collector_runs,
    recover_stale_jobs,
    run_due_jobs,
    schedule_due_collector_jobs,
    schedule_due_discovery_jobs,
    schedule_due_issue_backfill_jobs,
    schedule_due_podcast_jobs,
    schedule_due_search_jobs,
)


HEARTBEAT_ID = "default"


def _aware(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=UTC)


def scheduler_status(db: Session) -> models.SchedulerHeartbeat:
    heartbeat = db.get(models.SchedulerHeartbeat, HEARTBEAT_ID)
    if heartbeat:
        return heartbeat
    heartbeat = models.SchedulerHeartbeat(id=HEARTBEAT_ID, status="idle")
    db.add(heartbeat)
    db.flush()
    return heartbeat


def tick_scheduler_once(db: Session, *, execute_jobs: bool = True, owner_id: str = "manual") -> dict:
    poll_seconds = int(get_effective_setting(db, "scheduler_poll_seconds"))
    heartbeat = scheduler_status(db)
    now = models.now_utc()
    locked_until = _aware(heartbeat.locked_until)
    if locked_until and locked_until > now and heartbeat.owner_id != owner_id:
        return {
            "status": "skipped_locked",
            "ownerId": heartbeat.owner_id,
            "lockedUntil": locked_until.isoformat(),
        }

    heartbeat.owner_id = owner_id
    heartbeat.status = "running"
    heartbeat.locked_until = now + timedelta(seconds=max(poll_seconds * 2, 30))
    heartbeat.last_heartbeat_at = now
    heartbeat.last_tick_started_at = now
    heartbeat.updated_at = now
    db.flush()

    try:
        scheduled_search = schedule_due_search_jobs(db)
        scheduled_discovery = schedule_due_discovery_jobs(db)
        scheduled_backfill = schedule_due_issue_backfill_jobs(db)
        scheduled_collectors = schedule_due_collector_jobs(db)
        scheduled_podcasts = schedule_due_podcast_jobs(db)
        executed = run_due_jobs(db) if execute_jobs else []
        result = {
            "status": "completed",
            "scheduledBackfills": len(scheduled_backfill),
            "scheduledCollectors": len(scheduled_collectors),
            "scheduledDiscoveries": len(scheduled_discovery),
            "scheduledPodcasts": len(scheduled_podcasts),
            "scheduledSearches": len(scheduled_search),
            "executed": len(executed),
        }
        heartbeat.status = "idle"
        heartbeat.error_message = ""
        heartbeat.last_tick_json = result
    except Exception as exc:
        result = {"status": "failed", "error": str(exc)}
        heartbeat.status = "failed"
        heartbeat.error_message = str(exc)
        heartbeat.last_tick_json = result

    heartbeat.tick_count += 1
    heartbeat.locked_until = None
    heartbeat.last_heartbeat_at = models.now_utc()
    heartbeat.last_tick_finished_at = models.now_utc()
    heartbeat.updated_at = models.now_utc()
    db.flush()
    return result


class EmbeddedScheduler:
    def __init__(self) -> None:
        self.owner_id = f"embedded:{os.getpid()}"
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        db = SessionLocal()
        try:
            if not get_effective_setting(db, "embedded_scheduler_enabled"):
                return
        finally:
            db.close()
        self._thread = threading.Thread(target=self._loop, name="facttracer-scheduler", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)

    def _loop(self) -> None:
        while not self._stop.is_set():
            db = SessionLocal()
            try:
                tick_scheduler_once(db, execute_jobs=False, owner_id=self.owner_id)
                db.commit()
                poll_seconds = int(get_effective_setting(db, "scheduler_poll_seconds"))
            except Exception:
                db.rollback()
                poll_seconds = 30
            finally:
                db.close()
            self._stop.wait(max(poll_seconds, 5))


class EmbeddedWorker:
    def __init__(self) -> None:
        self.owner_id = f"embedded-worker:{os.getpid()}"
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []

    def start(self) -> None:
        if any(thread.is_alive() for thread in self._threads):
            return
        self._stop.clear()
        concurrency = 1
        db = SessionLocal()
        try:
            if not get_effective_setting(db, "embedded_worker_enabled"):
                return
            if get_effective_setting(db, "worker_backend") == "inline":
                recover_stale_jobs(db, stale_after_minutes=0)
                recover_stale_collector_runs(db, stale_after_minutes=0)
                db.commit()
            concurrency = max(1, int(get_effective_setting(db, "embedded_worker_concurrency") or 1))
        finally:
            db.close()
        self._threads = [
            threading.Thread(target=self._loop, name=f"facttracer-worker-{index + 1}", daemon=True)
            for index in range(concurrency)
        ]
        for thread in self._threads:
            thread.start()

    def stop(self) -> None:
        self._stop.set()
        for thread in self._threads:
            if thread.is_alive():
                thread.join(timeout=3)

    def _loop(self) -> None:
        while not self._stop.is_set():
            claimed_job_ids: list[str] = []
            db = SessionLocal()
            try:
                poll_seconds = int(get_effective_setting(db, "embedded_worker_poll_seconds"))
                if get_effective_setting(db, "worker_backend") == "inline":
                    batch_size = int(get_effective_setting(db, "embedded_worker_batch_size") or 1)
                    concurrency = max(1, int(get_effective_setting(db, "embedded_worker_concurrency") or 1))
                    per_worker_limit = max(1, batch_size // concurrency)
                    claimed_job_ids = claim_due_jobs(db, limit=per_worker_limit)
                db.commit()
            except Exception:
                db.rollback()
                poll_seconds = 5
            finally:
                db.close()
            for job_id in claimed_job_ids:
                if self._stop.is_set():
                    break
                execute_claimed_job_by_id(job_id)
            self._stop.wait(max(poll_seconds, 1))


embedded_scheduler = EmbeddedScheduler()
embedded_worker = EmbeddedWorker()
