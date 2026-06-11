from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.services.admin.settings import get_effective_setting


PODCAST_CORRECTION_UPDATE_TYPES = {
    "correction",
    "number_changed",
    "official_source",
    "verdict_changed",
}


def _append_unique(values: list[str], value: str) -> list[str]:
    return values if value in values else [*values, value]


def apply_podcast_correction_policy(
    db: Session,
    *,
    description: str = "",
    issue_id: str,
    title: str = "",
    update_log_id: str | None = None,
    update_type: str,
) -> dict[str, Any]:
    if update_type not in PODCAST_CORRECTION_UPDATE_TYPES:
        return {"heldCount": 0, "queuedFollowUp": False, "status": "ignored"}

    now = models.now_utc()
    episodes = db.scalars(
        select(models.PodcastEpisode).where(
            models.PodcastEpisode.issue_id == issue_id,
            models.PodcastEpisode.status == "published",
        ),
    ).all()

    for episode in episodes:
        generation = dict(episode.generation_json or {})
        gate = dict(generation.get("publicationGate") or {})
        missing_signals = [
            signal
            for signal in gate.get("missingSignals") or []
            if isinstance(signal, str)
        ]
        gate.update(
            {
                "blockedByUpdateLogId": update_log_id,
                "blockedByUpdateType": update_type,
                "checkedAt": now.isoformat(),
                "missingSignals": _append_unique(missing_signals, "correctionReview"),
                "status": "blocked",
            },
        )
        generation["publicationGate"] = gate
        generation["correctionPolicy"] = {
            "action": "hold_for_follow_up",
            "description": description,
            "heldAt": now.isoformat(),
            "reason": update_type,
            "requiresUpdateEpisode": True,
            "title": title,
            "updateLogId": update_log_id,
        }
        episode.generation_json = generation
        episode.status = "draft"
        episode.auto_published = False
        episode.updated_at = now

    target_id = f"podcast:correction:{issue_id}"
    existing_job = db.scalar(
        select(models.JobAttempt).where(
            models.JobAttempt.job_type == "generate_podcasts",
            models.JobAttempt.target_id == target_id,
            models.JobAttempt.status.in_(["queued", "running"]),
        ),
    )
    queued_follow_up = False
    if not existing_job:
        from app.services.jobs import enqueue_job

        enqueue_job(
            db,
            input_json={
                "feed": "urgent",
                "force": True,
                "issue_id": issue_id,
                "limit": 1,
                "render_audio": bool(get_effective_setting(db, "podcast_tts_render_on_generate", True)),
                "variant": "standard",
            },
            job_type="generate_podcasts",
            run_immediately=False,
            target_id=target_id,
        )
        queued_follow_up = True

    db.flush()
    return {
        "heldCount": len(episodes),
        "queuedFollowUp": queued_follow_up,
        "status": "updated",
    }
