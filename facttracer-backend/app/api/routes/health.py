from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models
from app.db.session import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/metrics", response_class=PlainTextResponse)
def metrics(db: Annotated[Session, Depends(get_db)]) -> str:
    counters = {
        "facttracer_issues_total": models.Issue,
        "facttracer_articles_total": models.Article,
        "facttracer_claims_total": models.Claim,
        "facttracer_evidences_total": models.Evidence,
        "facttracer_jobs_total": models.JobAttempt,
        "facttracer_notifications_total": models.Notification,
    }
    lines = []
    for name, model in counters.items():
        value = db.scalar(select(func.count()).select_from(model)) or 0
        lines.append(f"# TYPE {name} gauge")
        lines.append(f"{name} {value}")
    podcast_failed_jobs = (
        db.scalar(
            select(func.count())
            .select_from(models.JobAttempt)
            .where(
                models.JobAttempt.job_type.in_(["generate_podcasts", "render_podcast_audio"]),
                models.JobAttempt.status.in_(["failed", "dead_letter"]),
            ),
        )
        or 0
    )
    podcast_draft_episodes = (
        db.scalar(
            select(func.count())
            .select_from(models.PodcastEpisode)
            .where(models.PodcastEpisode.status == "draft"),
        )
        or 0
    )
    podcast_tts_pending = (
        db.scalar(
            select(func.count())
            .select_from(models.PodcastEpisode)
            .where(
                models.PodcastEpisode.status != "archived",
                models.PodcastEpisode.audio_url == "",
            ),
        )
        or 0
    )
    podcast_metrics = {
        "facttracer_podcast_draft_episodes": podcast_draft_episodes,
        "facttracer_podcast_jobs_failed": podcast_failed_jobs,
        "facttracer_podcast_tts_pending": podcast_tts_pending,
    }
    for name, value in podcast_metrics.items():
        lines.append(f"# TYPE {name} gauge")
        lines.append(f"{name} {value}")
    return "\n".join(lines) + "\n"
