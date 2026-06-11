from __future__ import annotations

import argparse
import io
import json
import wave
from typing import Any

from app.db.session import SessionLocal
from app import models
from app.services.files.storage import store_binary_file
from app.services.podcasts.generator import generate_podcast_episodes
from app.services.podcasts.tts import render_episode_audio, safe_tts_error_message


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed initial FactTracer podcast episodes.")
    parser.add_argument(
        "--feed",
        action="append",
        choices=["recommended", "daily", "featured", "urgent", "latest", "ranking", "category", "personalized"],
        help="Feed to generate. Repeatable. Defaults to recommended, daily, featured.",
    )
    parser.add_argument("--format", choices=["solo", "panel_2", "panel_3"], default=None)
    parser.add_argument("--force", action="store_true", help="Regenerate existing matching episodes.")
    parser.add_argument("--fixture-audio", action="store_true", help="Attach local silent WAV files for browser playback QA without calling OpenAI TTS.")
    parser.add_argument("--limit", type=int, default=6)
    parser.add_argument("--render-audio", action="store_true", help="Render OpenAI TTS audio after script generation.")
    parser.add_argument("--topic", default=None, help="Optional category/topic filter.")
    parser.add_argument("--variant", choices=["short", "standard", "deep"], default="standard")
    args = parser.parse_args()
    if args.fixture_audio and args.render_audio:
        parser.error("--fixture-audio and --render-audio are mutually exclusive")
    return args


def silent_wav_bytes(duration_seconds: int, *, frame_rate: int = 8000) -> bytes:
    frames = max(1, frame_rate * max(1, duration_seconds))
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(frame_rate)
        audio.writeframes(b"\x00\x00" * frames)
    return buffer.getvalue()


def attach_fixture_audio(episode: models.PodcastEpisode) -> models.PodcastEpisode:
    duration_seconds = max(1, int(episode.duration_seconds or 30))
    storage_url, byte_count = store_binary_file(
        data=silent_wav_bytes(duration_seconds),
        directory="podcasts",
        file_id=episode.id,
        suffix=".wav",
    )
    episode.audio_url = storage_url
    episode.generation_json = {
        **(episode.generation_json or {}),
        "audioBytes": byte_count,
        "audioMimeType": "audio/wav",
        "audioStoragePath": storage_url,
        "renderedAt": models.now_utc().isoformat(),
        "ttsModel": "fixture-silent-wav",
        "ttsProvider": "fixture",
        "ttsResponseFormat": "wav",
        "ttsStatus": "completed",
    }
    episode.updated_at = models.now_utc()
    return episode


def mark_seed_script_episode(
    episode: models.PodcastEpisode,
    *,
    feed: str,
    fixture_audio: bool,
    render_audio: bool,
) -> models.PodcastEpisode:
    episode.generation_json = {
        **(episode.generation_json or {}),
        "seedFeed": feed,
        "seedFixtureAudio": fixture_audio,
        "seedRenderAudio": render_audio,
        "seedScript": "scripts/seed_podcast_episodes.py",
        "seededAt": models.now_utc().isoformat(),
    }
    episode.updated_at = models.now_utc()
    return episode


def main() -> None:
    args = parse_args()
    feeds = args.feed or ["recommended", "daily", "featured"]
    db = SessionLocal()
    try:
        results: list[dict[str, Any]] = []
        render_errors: dict[str, str] = {}
        for feed in feeds:
            episodes = generate_podcast_episodes(
                db,
                episode_format=args.format,
                feed=feed,
                force=args.force,
                limit=args.limit,
                topic=args.topic,
                variant=args.variant,
            )
            if args.render_audio:
                rendered_episodes: list[models.PodcastEpisode] = []
                for episode in episodes:
                    try:
                        rendered_episodes.append(render_episode_audio(db, episode=episode, force=args.force))
                    except Exception as exc:
                        render_errors[episode.id] = safe_tts_error_message(exc)
                        rendered_episodes.append(episode)
                episodes = rendered_episodes
            if args.fixture_audio:
                episodes = [attach_fixture_audio(episode) for episode in episodes]
            episodes = [
                mark_seed_script_episode(
                    episode,
                    feed=feed,
                    fixture_audio=args.fixture_audio,
                    render_audio=args.render_audio,
                )
                for episode in episodes
            ]
            results.extend(
                {
                    "audioUrl": episode.audio_url,
                    "feed": feed,
                    "id": episode.id,
                    "renderError": render_errors.get(episode.id),
                    "seededAt": (episode.generation_json or {}).get("seededAt"),
                    "status": episode.status,
                    "title": episode.title,
                    "ttsAttemptCount": (episode.generation_json or {}).get("ttsAttemptCount"),
                    "ttsProvider": (episode.generation_json or {}).get("ttsProvider"),
                    "ttsStatus": (episode.generation_json or {}).get("ttsStatus"),
                    "variant": episode.variant,
                }
                for episode in episodes
            )
        db.commit()
        print(json.dumps({"episodes": results, "generatedCount": len(results)}, ensure_ascii=False, indent=2))
        if render_errors:
            raise SystemExit(1)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
