from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from typing import Any

from sqlalchemy import select

from app import models
from app.db.session import SessionLocal
from app.services.jobs import execute_job, schedule_due_podcast_jobs
from app.services.podcasts.generator import generate_podcast_episodes
from app.services.podcasts.tts import render_episode_audio, safe_tts_error_message
from app.utils import new_id
from scripts.audit_podcast_operations import REQUIRED_EVENT_TYPES, http_bytes, joined_url
from scripts.seed_podcast_episodes import attach_fixture_audio


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a staging podcast smoke flow and emit operational evidence JSON.",
    )
    parser.add_argument("--admin-email", default="", help="Existing admin/reviewer email for admin failed job verification.")
    parser.add_argument("--admin-password", default="", help="Existing admin/reviewer password for admin failed job verification.")
    parser.add_argument("--api-base-url", default="", help="Public API base URL, for example https://api.example.com")
    parser.add_argument("--check-admin-failed-jobs", action="store_true", help="Verify failed podcast jobs through /v1/admin/jobs.")
    parser.add_argument("--check-audio-stream", action="store_true", help="Fetch the selected episode audio URL through the public API.")
    parser.add_argument("--create-admin-failed-job", action="store_true", help="Create a deterministic failed render_podcast_audio job for admin verification.")
    parser.add_argument("--email", default="podcast-smoke@example.com", help="Smoke user email for authenticated analytics events.")
    parser.add_argument("--enqueue-scheduler-check", action="store_true", help="Schedule due podcast jobs in the current DB.")
    parser.add_argument(
        "--feed",
        action="append",
        choices=["recommended", "daily", "featured", "urgent", "latest", "ranking", "category", "personalized"],
        help="Feed to generate. Repeatable. Defaults to recommended.",
    )
    parser.add_argument("--fixture-audio", action="store_true", help="Attach local silent WAV audio instead of calling OpenAI TTS.")
    parser.add_argument("--force", action="store_true", help="Regenerate or rerender matching episodes.")
    parser.add_argument("--format", choices=["solo", "panel_2", "panel_3"], default=None)
    parser.add_argument("--limit", type=int, default=1)
    parser.add_argument("--password", default="password123", help="Smoke user password.")
    parser.add_argument("--record-events", action="store_true", help="Post all required podcast analytics events through the public API.")
    parser.add_argument("--render-audio", action="store_true", help="Render OpenAI TTS audio. This can incur API cost.")
    parser.add_argument("--timeout", type=int, default=12)
    parser.add_argument("--topic", default=None)
    parser.add_argument("--variant", choices=["short", "standard", "deep"], default="short")
    args = parser.parse_args()
    if args.fixture_audio and args.render_audio:
        parser.error("--fixture-audio and --render-audio are mutually exclusive")
    if (args.record_events or args.check_audio_stream or args.check_admin_failed_jobs) and not args.api_base_url:
        parser.error("--api-base-url is required with --record-events, --check-audio-stream, or --check-admin-failed-jobs")
    if args.check_admin_failed_jobs and (not args.admin_email or not args.admin_password):
        parser.error("--admin-email and --admin-password are required with --check-admin-failed-jobs")
    return args


def http_json(
    method: str,
    url: str,
    *,
    payload: dict[str, Any] | None = None,
    timeout: int,
    token: str | None = None,
) -> tuple[int, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
            if not body:
                return response.status, None
            return response.status, json.loads(body.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        try:
            parsed: Any = json.loads(body)
        except json.JSONDecodeError:
            parsed = {"error": body}
        return exc.code, parsed
    except Exception as exc:
        return 0, {"error": str(exc)}


def sign_in_smoke_user(base_url: str, *, email: str, password: str, timeout: int) -> dict[str, Any]:
    signup_payload = {"email": email, "name": "Podcast Smoke", "password": password}
    signup_status, signup_body = http_json(
        "POST",
        joined_url(base_url, "/v1/auth/signup"),
        payload=signup_payload,
        timeout=timeout,
    )
    if signup_status == 201 and isinstance(signup_body, dict):
        return {"action": "signup", "session": signup_body, "status": signup_status}
    if signup_status != 409:
        return {"action": "signup", "error": signup_body, "session": None, "status": signup_status}

    login_status, login_body = http_json(
        "POST",
        joined_url(base_url, "/v1/auth/login"),
        payload={"email": email, "password": password},
        timeout=timeout,
    )
    return {
        "action": "login",
        "error": None if login_status == 200 else login_body,
        "session": login_body if login_status == 200 and isinstance(login_body, dict) else None,
        "status": login_status,
    }


def login_user(base_url: str, *, email: str, password: str, timeout: int) -> dict[str, Any]:
    status, body = http_json(
        "POST",
        joined_url(base_url, "/v1/auth/login"),
        payload={"email": email, "password": password},
        timeout=timeout,
    )
    return {
        "error": None if status == 200 else body,
        "session": body if status == 200 and isinstance(body, dict) else None,
        "status": status,
    }


def first_episode_from_home(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    now_playing = payload.get("nowPlaying")
    if isinstance(now_playing, dict):
        return now_playing
    for section in payload.get("sections") or []:
        if not isinstance(section, dict):
            continue
        for episode in section.get("episodes") or []:
            if isinstance(episode, dict):
                return episode
    return None


def first_generated_episode(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    for row in rows:
        if isinstance(row, dict) and row.get("id"):
            return row
    return None


def podcast_event_payloads(episode: dict[str, Any], detail: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    detail = detail or {}
    issue_id = episode.get("issueId") or detail.get("issueId")
    episode_id = episode.get("id") or detail.get("id")
    category = episode.get("category") or detail.get("category")
    podcast_format = episode.get("format") or detail.get("format")
    base_metadata = {
        "episodeId": episode_id,
        "podcastCategory": category,
        "podcastFormat": podcast_format,
        "surface": "podcast_operational_smoke",
    }
    payloads = [
        {
            "eventType": event_type,
            "issueId": issue_id,
            "metadata": {
                **base_metadata,
                "completionRate": 1 if event_type == "podcast_complete" else 0.5,
            },
        }
        for event_type in REQUIRED_EVENT_TYPES
        if event_type != "podcast_source_click"
    ]
    sources = detail.get("sources") if isinstance(detail.get("sources"), list) else []
    source = sources[0] if sources and isinstance(sources[0], dict) else {}
    payloads.append(
        {
            "eventType": "podcast_source_click",
            "issueId": issue_id,
            "metadata": {
                **base_metadata,
                "sourceId": source.get("id"),
                "sourceType": source.get("sourceType"),
            },
        },
    )
    return payloads


def failed_podcast_jobs_from_admin_payload(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    jobs = payload.get("jobs")
    if not isinstance(jobs, list):
        return []
    return [
        job
        for job in jobs
        if isinstance(job, dict)
        and job.get("jobType") in {"generate_podcasts", "render_podcast_audio"}
        and job.get("status") in {"dead_letter", "failed"}
    ]


def smoke_event_persistence_evidence(email: str) -> dict[str, Any]:
    db = SessionLocal()
    try:
        user = db.scalar(select(models.User).where(models.User.email == email))
        if not user:
            return {
                "email": email,
                "error": "smoke user not found",
                "eventCounts": {},
                "missingEventTypes": REQUIRED_EVENT_TYPES,
                "profile": None,
            }
        events = db.scalars(
            select(models.ProductMetricEvent)
            .where(models.ProductMetricEvent.user_id == user.id)
            .order_by(models.ProductMetricEvent.created_at.desc()),
        ).all()
        smoke_events = [
            event
            for event in events
            if isinstance(event.metadata_json, dict)
            and event.metadata_json.get("surface") == "podcast_operational_smoke"
        ]
        event_counts = {
            event_type: sum(1 for event in smoke_events if event.event_type == event_type)
            for event_type in REQUIRED_EVENT_TYPES
        }
        profile = db.get(models.UserInterestProfile, user.id)
        format_weights = {
            key: value
            for key, value in ((profile.event_group_weights_json or {}) if profile else {}).items()
            if str(key).startswith("podcast_format:")
        }
        return {
            "email": email,
            "eventCounts": event_counts,
            "missingEventTypes": [
                event_type
                for event_type, count in event_counts.items()
                if count <= 0
            ],
            "profile": {
                "eventGroupWeights": format_weights,
                "topicWeights": profile.topic_weights_json or {},
                "updatedAt": profile.updated_at.isoformat() if profile else None,
                "userId": user.id,
            } if profile else None,
        }
    finally:
        db.close()


def create_failed_podcast_job_evidence(db) -> models.JobAttempt:
    target_id = f"podcast_smoke_missing_{new_id('episode')}"
    job = models.JobAttempt(
        id=new_id("job"),
        input_json={"episode_id": target_id, "force": True},
        job_type="render_podcast_audio",
        max_attempts=1,
        status="queued",
        target_id=target_id,
    )
    db.add(job)
    db.flush()
    execute_job(db, job=job)
    db.flush()
    return job


def generate_smoke_episodes(args: argparse.Namespace) -> list[dict[str, Any]]:
    feeds = args.feed or ["recommended"]
    db = SessionLocal()
    try:
        results: list[dict[str, Any]] = []
        scheduled_jobs = []
        if args.enqueue_scheduler_check:
            scheduled_jobs = schedule_due_podcast_jobs(db)
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
            for episode in episodes:
                render_error = None
                if args.fixture_audio:
                    attach_fixture_audio(episode)
                if args.render_audio:
                    try:
                        render_episode_audio(db, episode=episode, force=args.force)
                    except Exception as exc:
                        render_error = safe_tts_error_message(exc)
                generation = episode.generation_json if isinstance(episode.generation_json, dict) else {}
                results.append(
                    {
                        "audioUrl": episode.audio_url,
                        "feed": feed,
                        "id": episode.id,
                        "renderError": render_error,
                        "status": episode.status,
                        "title": episode.title,
                        "ttsAttemptCount": generation.get("ttsAttemptCount"),
                        "ttsProvider": generation.get("ttsProvider"),
                        "ttsStatus": generation.get("ttsStatus"),
                        "variant": episode.variant,
                    },
                )
        db.commit()
        if scheduled_jobs:
            results.append(
                {
                    "scheduledJobIds": [job.id for job in scheduled_jobs],
                    "scheduledTargets": [job.target_id for job in scheduled_jobs],
                    "type": "scheduler",
                },
            )
        if getattr(args, "create_admin_failed_job", False):
            failed_job = create_failed_podcast_job_evidence(db)
            db.commit()
            results.append(
                {
                    "attempts": failed_job.attempts,
                    "id": failed_job.id,
                    "jobType": failed_job.job_type,
                    "lastError": failed_job.last_error,
                    "status": failed_job.status,
                    "targetId": failed_job.target_id,
                    "type": "admin_failed_job",
                },
            )
        return results
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def exercise_public_api(args: argparse.Namespace, generated_rows: list[dict[str, Any]]) -> dict[str, Any]:
    status, home_payload = http_json("GET", joined_url(args.api_base_url, "/v1/podcasts/home"), timeout=args.timeout)
    result: dict[str, Any] = {
        "homeStatus": status,
    }
    generated_episode = first_generated_episode(generated_rows)
    episode = generated_episode or first_episode_from_home(home_payload)
    if not episode:
        result["error"] = "no public podcast episode found"
        return result
    result["episodeId"] = episode.get("id")
    result["episodeSource"] = "generated" if generated_episode else "home"

    detail_status, detail_payload = http_json(
        "GET",
        joined_url(args.api_base_url, f"/v1/podcasts/{episode['id']}"),
        timeout=args.timeout,
    )
    detail = detail_payload.get("episode") if detail_status == 200 and isinstance(detail_payload, dict) else {}
    result["detailStatus"] = detail_status
    if generated_episode and detail_status != 200:
        result["error"] = "generated episode is not visible through the public API; check DB/API target mismatch or publication status"
        return result
    result["audioUrl"] = detail.get("audioUrl") if isinstance(detail, dict) else None

    if args.check_audio_stream and result["audioUrl"]:
        audio_status, content_type, body = http_bytes(
            joined_url(args.api_base_url, str(result["audioUrl"])),
            timeout=args.timeout,
        )
        result["audioStream"] = {
            "bytesRead": len(body),
            "contentType": content_type,
            "status": audio_status,
        }

    if args.record_events:
        session_result = sign_in_smoke_user(
            args.api_base_url,
            email=args.email,
            password=args.password,
            timeout=args.timeout,
        )
        result["auth"] = {
            "action": session_result["action"],
            "status": session_result["status"],
        }
        token = (session_result.get("session") or {}).get("accessToken")
        if not token:
            result["eventResults"] = [{"error": session_result.get("error"), "status": "auth_failed"}]
            return result
        event_results = []
        for payload in podcast_event_payloads(episode, detail if isinstance(detail, dict) else {}):
            event_status, event_body = http_json(
                "POST",
                joined_url(args.api_base_url, "/v1/analytics/events"),
                payload=payload,
                timeout=args.timeout,
                token=token,
            )
            event_results.append(
                {
                    "eventType": payload["eventType"],
                    "id": event_body.get("id") if isinstance(event_body, dict) else None,
                    "status": event_status,
                },
            )
        result["eventResults"] = event_results
        result["eventPersistence"] = smoke_event_persistence_evidence(args.email)
    if args.check_admin_failed_jobs:
        admin_result = login_user(
            args.api_base_url,
            email=args.admin_email,
            password=args.admin_password,
            timeout=args.timeout,
        )
        result["adminAuth"] = {"status": admin_result["status"]}
        admin_token = (admin_result.get("session") or {}).get("accessToken")
        if not admin_token:
            result["adminFailedJobs"] = {
                "error": admin_result.get("error"),
                "status": "auth_failed",
            }
        else:
            jobs_status, jobs_body = http_json(
                "GET",
                joined_url(args.api_base_url, "/v1/admin/jobs"),
                timeout=args.timeout,
                token=admin_token,
            )
            failed_podcast_jobs = failed_podcast_jobs_from_admin_payload(jobs_body) if jobs_status == 200 else []
            result["adminFailedJobs"] = {
                "count": len(failed_podcast_jobs),
                "jobs": [
                    {
                        "attempts": job.get("attempts"),
                        "id": job.get("id"),
                        "jobType": job.get("jobType"),
                        "lastError": job.get("lastError"),
                        "status": job.get("status"),
                        "targetId": job.get("targetId"),
                        "userMessage": job.get("userMessage"),
                    }
                    for job in failed_podcast_jobs[:10]
                ],
                "status": jobs_status,
            }
    return result


def public_api_has_failure(result: dict[str, Any], args: argparse.Namespace) -> bool:
    if result.get("error"):
        return True
    if args.check_audio_stream:
        stream = result.get("audioStream")
        if not isinstance(stream, dict):
            return True
        if stream.get("status") != 200 or not str(stream.get("contentType") or "").startswith("audio/"):
            return True
        if int(stream.get("bytesRead") or 0) <= 0:
            return True
    if args.record_events:
        event_results = result.get("eventResults")
        if not isinstance(event_results, list) or not event_results:
            return True
        if any(item.get("status") != 201 for item in event_results if isinstance(item, dict)):
            return True
        persistence = result.get("eventPersistence")
        if not isinstance(persistence, dict):
            return True
        if persistence.get("missingEventTypes") or not persistence.get("profile"):
            return True
    if args.check_admin_failed_jobs:
        admin_failed_jobs = result.get("adminFailedJobs")
        if not isinstance(admin_failed_jobs, dict):
            return True
        if admin_failed_jobs.get("status") != 200 or int(admin_failed_jobs.get("count") or 0) <= 0:
            return True
    return False


def main() -> int:
    args = parse_args()
    database_results = generate_smoke_episodes(args)
    payload: dict[str, Any] = {
        "database": database_results,
    }
    if args.api_base_url:
        payload["publicApi"] = exercise_public_api(args, database_results)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    has_render_error = any(item.get("renderError") for item in payload["database"] if isinstance(item, dict))
    api_error = isinstance(payload.get("publicApi"), dict) and public_api_has_failure(payload["publicApi"], args)
    return 1 if has_render_error or api_error else 0


if __name__ == "__main__":
    sys.exit(main())
