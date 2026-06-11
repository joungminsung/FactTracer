from __future__ import annotations

from app import models
from app.db.session import SessionLocal
from app.services.admin.settings import get_effective_setting
from app.services.podcasts.generator import generate_podcast_episodes
from app.services.podcasts.tts import render_episode_audio


def generate_podcasts(
    *,
    episode_format: str | None = None,
    feed: str = "recommended",
    force: bool = False,
    issue_id: str | None = None,
    limit: int = 6,
    render_audio: bool | None = None,
    topic: str | None = None,
    user_id: str | None = None,
    variant: str | None = None,
) -> dict:
    db = SessionLocal()
    try:
        user = db.get(models.User, user_id) if user_id else None
        episodes = generate_podcast_episodes(
            db,
            episode_format=episode_format,
            feed=feed,
            force=force,
            issue_id=issue_id,
            limit=limit,
            topic=topic,
            user=user,
            variant=variant,
        )
        should_render_audio = (
            bool(get_effective_setting(db, "podcast_tts_render_on_generate", True))
            if render_audio is None
            else bool(render_audio)
        )
        rendered_audio_count = 0
        if should_render_audio:
            for episode in episodes:
                render_episode_audio(db, episode=episode, force=force)
                if episode.audio_url:
                    rendered_audio_count += 1
        db.commit()
        return {
            "episode_count": len(episodes),
            "episode_ids": [episode.id for episode in episodes],
            "feed": feed,
            "rendered_audio_count": rendered_audio_count,
            "status": "completed",
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def render_podcast_audio(*, episode_id: str, force: bool = False) -> dict:
    db = SessionLocal()
    try:
        episode = db.get(models.PodcastEpisode, episode_id)
        if not episode:
            return {
                "episode_id": episode_id,
                "error": "podcast episode not found",
                "status": "failed",
            }
        render_episode_audio(db, episode=episode, force=force)
        db.commit()
        return {
            "audio_url": episode.audio_url,
            "episode_id": episode.id,
            "status": "completed" if episode.audio_url else "skipped",
            "tts_status": (episode.generation_json or {}).get("ttsStatus"),
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
