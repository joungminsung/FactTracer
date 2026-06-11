from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app import models
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.admin.settings import get_effective_setting
from app.services.jobs import schedule_due_podcast_jobs


REQUIRED_ENV_KEYS = [
    "FACTTRACER_PODCAST_GENERATION_ENABLED",
    "FACTTRACER_PODCAST_GENERATION_INTERVAL_MINUTES",
    "FACTTRACER_PODCAST_GENERATION_LIMIT",
    "FACTTRACER_PODCAST_TTS_ENABLED",
    "FACTTRACER_PODCAST_TTS_RENDER_ON_GENERATE",
    "FACTTRACER_PODCAST_MIN_SOURCES_FOR_PUBLISH",
    "FACTTRACER_PODCAST_MIN_PUBLISH_QUALITY_SCORE",
    "FACTTRACER_PODCAST_SENSITIVE_TOPICS_REQUIRE_OFFICIAL_SOURCE",
    "FACTTRACER_PODCAST_RECOMMENDATION_IMPACT_WEIGHT",
    "FACTTRACER_PODCAST_RECOMMENDATION_VERIFICATION_WEIGHT",
    "FACTTRACER_PODCAST_RECOMMENDATION_FRESHNESS_WEIGHT",
    "FACTTRACER_PODCAST_RECOMMENDATION_CONTROVERSY_WEIGHT",
    "FACTTRACER_PODCAST_RECOMMENDATION_MOMENTUM_WEIGHT",
    "FACTTRACER_PODCAST_PERSONALIZATION_INTEREST_WEIGHT",
    "FACTTRACER_PODCAST_TTS_PRONUNCIATION_LEXICON",
]

REQUIRED_EVENT_TYPES = [
    "podcast_home_impression",
    "podcast_play_start",
    "podcast_progress",
    "podcast_complete",
    "podcast_skip",
    "podcast_source_click",
]

SETTING_KEYS = [
    "podcast_generation_enabled",
    "podcast_generation_interval_minutes",
    "podcast_generation_limit",
    "podcast_tts_enabled",
    "podcast_tts_render_on_generate",
    "podcast_min_sources_for_publish",
    "podcast_min_publish_quality_score",
    "podcast_sensitive_topics_require_official_source",
    "podcast_recommendation_impact_weight",
    "podcast_recommendation_verification_weight",
    "podcast_recommendation_freshness_weight",
    "podcast_recommendation_controversy_weight",
    "podcast_recommendation_momentum_weight",
    "podcast_personalization_interest_weight",
    "podcast_tts_pronunciation_lexicon",
]

BROWSER_AUDIO_USER_AGENTS = {
    "chrome": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "safari": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit FactTracer podcast operational readiness.")
    parser.add_argument("--api-base-url", default="", help="Public API base URL, for example https://api.example.com")
    parser.add_argument("--enqueue-scheduler-check", action="store_true", help="Mutate the DB by scheduling due podcast jobs.")
    parser.add_argument("--json", action="store_true", help="Emit JSON only.")
    parser.add_argument("--require-audio-stream", action="store_true", help="Fail if the public API has no streamable podcast audio.")
    parser.add_argument("--require-env-vars", action="store_true", help="Fail when required deployment env vars are absent.")
    parser.add_argument("--require-events", action="store_true", help="Fail unless all podcast analytics event types have stored rows.")
    parser.add_argument("--require-failed-job", action="store_true", help="Fail unless at least one failed/dead-letter podcast job exists for admin verification.")
    parser.add_argument("--require-live-tts", action="store_true", help="Fail unless an OpenAI-rendered podcast audio episode exists.")
    parser.add_argument("--require-seed-script", action="store_true", help="Fail unless seed_podcast_episodes.py execution metadata exists.")
    parser.add_argument("--require-tts-retry-evidence", action="store_true", help="Fail unless TTS attempt logs or job retry attempts exist.")
    parser.add_argument("--timeout", type=int, default=12)
    return parser.parse_args()


def check(name: str, status: str, message: str, **details: Any) -> dict[str, Any]:
    return {"details": details, "message": message, "name": name, "status": status}


def http_json(url: str, *, timeout: int) -> tuple[int, Any]:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
            return response.status, json.loads(body.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, {"error": exc.read().decode("utf-8", "replace")}
    except Exception as exc:
        return 0, {"error": str(exc)}


def http_bytes(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: int,
    limit: int = 256_000,
) -> tuple[int, str, bytes]:
    request_headers = {"Accept": "audio/*", **(headers or {})}
    request = urllib.request.Request(url, headers=request_headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.headers.get("content-type", ""), response.read(limit)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.headers.get("content-type", ""), exc.read(limit)
    except Exception as exc:
        return 0, "", str(exc).encode("utf-8", "replace")


def joined_url(base_url: str, path: str) -> str:
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def generation(episode: models.PodcastEpisode) -> dict[str, Any]:
    return episode.generation_json if isinstance(episode.generation_json, dict) else {}


def is_openai_completed_audio(episode: models.PodcastEpisode) -> bool:
    return (
        generation(episode).get("ttsProvider") == "openai"
        and generation(episode).get("ttsStatus") == "completed"
        and bool(episode.audio_url)
    )


def public_audio_url_for_episode(episode: models.PodcastEpisode) -> str:
    return f"/v1/podcasts/{episode.id}/audio"


def tts_attempt_indicates_retry(attempt: Any) -> bool:
    if not isinstance(attempt, dict):
        return False
    try:
        attempt_number = int(attempt.get("attempt") or 0)
    except (TypeError, ValueError):
        attempt_number = 0
    return attempt_number > 1 or attempt.get("status") == "failed"


def local_audio_exists(audio_url: str) -> bool:
    if not audio_url or audio_url.startswith("http://") or audio_url.startswith("https://"):
        return False
    return Path(audio_url).exists()


def audit_settings(db) -> list[dict[str, Any]]:
    settings = get_settings()
    env_status = {
        key: {"configured": key in os.environ, "valuePreview": "<set>" if key in os.environ else ""}
        for key in REQUIRED_ENV_KEYS
    }
    env_status["OPENAI_API_KEY"] = {
        "configured": bool(settings.openai_api_key),
        "valuePreview": "<set>" if settings.openai_api_key else "",
    }
    effective = {key: get_effective_setting(db, key) for key in SETTING_KEYS}
    missing_env = [key for key, item in env_status.items() if not item["configured"]]
    return [
        check(
            "podcast_effective_settings",
            "pass",
            "팟캐스트 운영 설정을 읽었습니다.",
            settings=effective,
        ),
        check(
            "podcast_required_env_vars",
            "pass" if not missing_env else "warn",
            "필수 환경변수 설정 상태를 확인했습니다." if not missing_env else "일부 환경변수가 프로세스 환경에 직접 설정되어 있지 않습니다.",
            env=env_status,
            missing=missing_env,
        ),
    ]


def audit_database(
    db,
    *,
    enqueue_scheduler_check: bool,
    require_failed_job: bool,
    require_live_tts: bool,
    require_events: bool,
    require_tts_retry_evidence: bool = False,
    require_seed_script: bool = False,
) -> list[dict[str, Any]]:
    rows = db.scalars(select(models.PodcastEpisode).order_by(models.PodcastEpisode.created_at.desc())).all()
    openai_audio = [episode for episode in rows if is_openai_completed_audio(episode)]
    seeded_by_script = [
        episode
        for episode in rows
        if generation(episode).get("seedScript") == "scripts/seed_podcast_episodes.py"
    ]
    local_audio = [episode for episode in rows if local_audio_exists(episode.audio_url)]
    podcast_jobs = db.scalars(
        select(models.JobAttempt)
        .where(models.JobAttempt.job_type.in_(["generate_podcasts", "render_podcast_audio"]))
        .order_by(models.JobAttempt.created_at.desc()),
    ).all()
    failed_jobs = [job for job in podcast_jobs if job.status in {"failed", "dead_letter"}]
    failed_jobs_with_errors = [job for job in failed_jobs if job.last_error]
    retry_jobs = [job for job in podcast_jobs if job.attempts > 1]
    scheduler_targets = {job.target_id: job.status for job in podcast_jobs if job.target_id in {"podcast:auto", "podcast:daily"}}
    tts_attempt_episodes = [
        episode
        for episode in rows
        if isinstance(generation(episode).get("ttsAttempts"), list)
        and generation(episode).get("ttsAttempts")
    ]
    tts_retry_episodes = [
        episode
        for episode in tts_attempt_episodes
        if any(tts_attempt_indicates_retry(attempt) for attempt in generation(episode).get("ttsAttempts", []))
    ]
    event_counts = {
        event_type: len(
            db.scalars(
                select(models.ProductMetricEvent).where(models.ProductMetricEvent.event_type == event_type),
            ).all(),
        )
        for event_type in REQUIRED_EVENT_TYPES
    }
    profiles_with_podcast_weights = [
        profile.user_id
        for profile in db.scalars(select(models.UserInterestProfile)).all()
        if profile.topic_weights_json or any(str(key).startswith("podcast_format:") for key in (profile.event_group_weights_json or {}))
    ]
    scheduled = []
    if enqueue_scheduler_check:
        scheduled = schedule_due_podcast_jobs(db)
        db.commit()

    checks = [
        check(
            "podcast_episode_seed",
            "pass" if rows else "warn",
            "팟캐스트 회차가 DB에 존재합니다." if rows else "팟캐스트 회차가 아직 DB에 없습니다.",
            count=len(rows),
        ),
        check(
            "podcast_seed_script_run",
            "pass" if seeded_by_script else ("fail" if require_seed_script else "warn"),
            "seed_podcast_episodes.py 실행 흔적을 확인했습니다." if seeded_by_script else "seed_podcast_episodes.py 실행 흔적을 찾지 못했습니다.",
            episodes=[
                {
                    "episodeId": episode.id,
                    "seedFeed": generation(episode).get("seedFeed"),
                    "seededAt": generation(episode).get("seededAt"),
                }
                for episode in seeded_by_script[:10]
            ],
        ),
        check(
            "podcast_live_tts_audio",
            "pass" if openai_audio else ("fail" if require_live_tts else "warn"),
            "OpenAI TTS로 완료된 오디오 회차가 있습니다." if openai_audio else "OpenAI TTS 완료 회차를 찾지 못했습니다.",
            episodeIds=[episode.id for episode in openai_audio[:5]],
        ),
        check(
            "podcast_audio_storage_path",
            "pass" if local_audio else "warn",
            "로컬 저장 경로에 존재하는 팟캐스트 오디오 파일을 확인했습니다." if local_audio else "존재하는 로컬 오디오 저장 경로를 찾지 못했습니다.",
            episodeIds=[episode.id for episode in local_audio[:5]],
        ),
        check(
            "podcast_scheduler_jobs",
            "pass" if {"podcast:auto", "podcast:daily"}.issubset(scheduler_targets) or scheduled else "warn",
            "팟캐스트 스케줄러 작업을 확인했습니다." if scheduler_targets or scheduled else "팟캐스트 스케줄러 작업 이력이 없습니다.",
            scheduledNow=[job.id for job in scheduled],
            targets=scheduler_targets,
        ),
        check(
            "podcast_failed_jobs",
            "pass" if failed_jobs_with_errors else ("fail" if require_failed_job else "warn"),
            "실패한 팟캐스트 작업 이력과 오류 로그를 확인했습니다." if failed_jobs_with_errors else "오류 로그가 있는 실패 팟캐스트 작업 이력이 없습니다.",
            jobs=[
                {
                    "attempts": job.attempts,
                    "id": job.id,
                    "jobType": job.job_type,
                    "lastError": job.last_error,
                    "status": job.status,
                    "targetId": job.target_id,
                }
                for job in failed_jobs[:10]
            ],
        ),
        check(
            "podcast_tts_retry_evidence",
            "pass" if tts_retry_episodes or retry_jobs else ("fail" if require_tts_retry_evidence else "warn"),
            "TTS 재시도 증거를 확인했습니다." if tts_retry_episodes or retry_jobs else "TTS 재시도 증거가 없습니다.",
            episodeAttempts=[
                {
                    "episodeId": episode.id,
                    "ttsAttempts": generation(episode).get("ttsAttempts", [])[:5],
                    "ttsStatus": generation(episode).get("ttsStatus"),
                }
                for episode in tts_retry_episodes[:5]
            ],
            retryJobs=[
                {
                    "attempts": job.attempts,
                    "id": job.id,
                    "jobType": job.job_type,
                    "lastError": job.last_error,
                    "status": job.status,
                    "targetId": job.target_id,
                }
                for job in retry_jobs[:10]
            ],
        ),
        check(
            "podcast_metric_events",
            "pass" if all(event_counts.values()) else ("fail" if require_events else "warn"),
            "팟캐스트 이벤트 로그를 확인했습니다." if all(event_counts.values()) else ("일부 팟캐스트 이벤트 로그만 확인했습니다." if any(event_counts.values()) else "팟캐스트 이벤트 로그가 없습니다."),
            eventCounts=event_counts,
        ),
        check(
            "podcast_interest_profiles",
            "pass" if profiles_with_podcast_weights else ("fail" if require_events else "warn"),
            "팟캐스트 이벤트가 사용자 관심 프로필에 누적된 흔적을 확인했습니다." if profiles_with_podcast_weights else "팟캐스트 관심 프로필 누적 흔적이 없습니다.",
            userIds=profiles_with_podcast_weights[:10],
        ),
    ]
    return checks


def podcast_episode_items(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    episodes: list[dict[str, Any]] = []
    episode = payload.get("episode")
    if isinstance(episode, dict):
        episodes.append(episode)
    if isinstance(payload.get("episodes"), list):
        episodes.extend(item for item in payload["episodes"] if isinstance(item, dict))
    for section in payload.get("sections") or []:
        if isinstance(section, dict) and isinstance(section.get("episodes"), list):
            episodes.extend(item for item in section["episodes"] if isinstance(item, dict))
    now_playing = payload.get("nowPlaying")
    if isinstance(now_playing, dict):
        episodes.insert(0, now_playing)
    return episodes


def find_audio_url(payload: Any) -> str:
    for episode in podcast_episode_items(payload):
        if episode.get("audioUrl"):
            return str(episode["audioUrl"])
    return ""


def find_episode_id(payload: Any) -> str:
    for episode in podcast_episode_items(payload):
        if episode.get("id"):
            return str(episode["id"])
    return ""


def find_episode_ids(payload: Any) -> list[str]:
    episode_ids = []
    seen = set()
    for episode in podcast_episode_items(payload):
        episode_id = str(episode.get("id") or "")
        if episode_id and episode_id not in seen:
            seen.add(episode_id)
            episode_ids.append(episode_id)
    return episode_ids


def resolve_audio_url_from_detail(base_url: str, payloads: list[Any], *, timeout: int) -> tuple[str, dict[str, Any]]:
    for payload in payloads:
        for episode_id in find_episode_ids(payload):
            detail_status, detail_payload = http_json(joined_url(base_url, f"/v1/podcasts/{episode_id}"), timeout=timeout)
            audio_url = find_audio_url(detail_payload)
            if audio_url:
                return audio_url, {
                    "detailHttpStatus": detail_status,
                    "episodeId": episode_id,
                }
    return "", {}


def browser_audio_stream_results(url: str, *, timeout: int) -> list[dict[str, Any]]:
    results = []
    for browser, user_agent in BROWSER_AUDIO_USER_AGENTS.items():
        status, content_type, body = http_bytes(
            url,
            headers={"User-Agent": user_agent},
            timeout=timeout,
        )
        results.append(
            {
                "browser": browser,
                "bytesRead": len(body),
                "contentType": content_type,
                "httpStatus": status,
                "streamable": status == 200 and content_type.startswith("audio/") and len(body) > 0,
            },
        )
    return results


def audit_live_tts_delivery(db, base_url: str, *, require_live_tts: bool, timeout: int) -> list[dict[str, Any]]:
    episodes = db.scalars(select(models.PodcastEpisode).order_by(models.PodcastEpisode.created_at.desc())).all()
    openai_audio = [episode for episode in episodes if is_openai_completed_audio(episode)]
    if not openai_audio:
        return [
            check(
                "podcast_live_tts_delivery",
                "fail" if require_live_tts else "warn",
                "OpenAI TTS 완료 회차의 저장 경로와 공개 URL을 함께 확인할 수 없습니다.",
                episodeIds=[],
            ),
        ]

    results = []
    for episode in openai_audio[:10]:
        generation_json = generation(episode)
        storage_path = str(generation_json.get("audioStoragePath") or episode.audio_url or "")
        expected_audio_url = public_audio_url_for_episode(episode)
        local_storage_ok = local_audio_exists(storage_path)
        detail_status, detail_payload = http_json(joined_url(base_url, f"/v1/podcasts/{episode.id}"), timeout=timeout)
        detail_audio_url = find_audio_url(detail_payload)
        public_url_matches = detail_audio_url == expected_audio_url or detail_audio_url.endswith(expected_audio_url)
        audio_status = 0
        bytes_read = 0
        content_type = ""
        if detail_audio_url:
            audio_status, content_type, body = http_bytes(joined_url(base_url, detail_audio_url), timeout=timeout)
            bytes_read = len(body)
        streamable = audio_status == 200 and content_type.startswith("audio/") and bytes_read > 0
        result = {
            "audioStoragePath": storage_path,
            "bytesRead": bytes_read,
            "contentType": content_type,
            "detailAudioUrl": detail_audio_url,
            "detailHttpStatus": detail_status,
            "episodeId": episode.id,
            "expectedAudioUrl": expected_audio_url,
            "localStorageOk": local_storage_ok,
            "publicUrlMatches": public_url_matches,
            "streamable": streamable,
            "ttsProvider": generation_json.get("ttsProvider"),
            "ttsStatus": generation_json.get("ttsStatus"),
        }
        results.append(result)
        if local_storage_ok and public_url_matches and streamable:
            return [
                check(
                    "podcast_live_tts_delivery",
                    "pass",
                    "OpenAI TTS 완료 회차의 저장 경로와 공개 오디오 URL을 같은 회차 기준으로 확인했습니다.",
                    deliveries=[result],
                ),
            ]

    return [
        check(
            "podcast_live_tts_delivery",
            "fail" if require_live_tts else "warn",
            "OpenAI TTS 완료 회차의 저장 경로와 공개 URL이 같은 회차 기준으로 연결되지 않았습니다.",
            deliveries=results,
        ),
    ]


def audit_public_api(base_url: str, *, require_audio_stream: bool, timeout: int) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    health_status, health_payload = http_json(joined_url(base_url, "/health"), timeout=timeout)
    checks.append(
        check(
            "podcast_api_health",
            "pass" if health_status == 200 else "fail",
            "API health 응답을 확인했습니다." if health_status == 200 else "API health 응답에 실패했습니다.",
            httpStatus=health_status,
            response=health_payload,
        ),
    )
    metrics_status, _, metrics_body = http_bytes(joined_url(base_url, "/metrics"), timeout=timeout)
    metrics_text = metrics_body.decode("utf-8", "replace")
    metric_names = [
        "facttracer_podcast_draft_episodes",
        "facttracer_podcast_jobs_failed",
        "facttracer_podcast_tts_pending",
    ]
    checks.append(
        check(
            "podcast_api_metrics",
            "pass" if metrics_status == 200 and all(name in metrics_text for name in metric_names) else "fail",
            "팟캐스트 운영 메트릭을 확인했습니다." if metrics_status == 200 else "메트릭 응답에 실패했습니다.",
            httpStatus=metrics_status,
            required=metric_names,
        ),
    )
    home_status, home_payload = http_json(joined_url(base_url, "/v1/podcasts/home"), timeout=timeout)
    checks.append(
        check(
            "podcast_api_home",
            "pass" if home_status == 200 else "fail",
            "공개 팟캐스트 홈 응답을 확인했습니다." if home_status == 200 else "공개 팟캐스트 홈 응답에 실패했습니다.",
            httpStatus=home_status,
        ),
    )
    feed_status, feed_payload = http_json(joined_url(base_url, "/v1/podcasts?feed=latest&limit=20"), timeout=timeout)
    checks.append(
        check(
            "podcast_api_feed",
            "pass" if feed_status == 200 else "fail",
            "공개 팟캐스트 피드 응답을 확인했습니다." if feed_status == 200 else "공개 팟캐스트 피드 응답에 실패했습니다.",
            httpStatus=feed_status,
        ),
    )
    audio_url = find_audio_url(feed_payload) or find_audio_url(home_payload)
    audio_detail = {}
    if not audio_url:
        audio_url, audio_detail = resolve_audio_url_from_detail(base_url, [feed_payload, home_payload], timeout=timeout)
    if not audio_url:
        checks.append(
            check(
                "podcast_api_audio_stream",
                "fail" if require_audio_stream else "warn",
                "공개 피드와 회차 상세에서 오디오 URL이 있는 회차를 찾지 못했습니다.",
            ),
        )
        checks.append(
            check(
                "podcast_api_browser_audio_streams",
                "fail" if require_audio_stream else "warn",
                "Chrome/Safari 스트리밍을 확인할 오디오 URL이 없습니다.",
            ),
        )
        return checks
    full_audio_url = joined_url(base_url, audio_url)
    audio_status, content_type, body = http_bytes(full_audio_url, timeout=timeout)
    checks.append(
        check(
            "podcast_api_audio_stream",
            "pass" if audio_status == 200 and content_type.startswith("audio/") and len(body) > 0 else "fail",
            "공개 오디오 스트리밍 응답을 확인했습니다." if audio_status == 200 else "공개 오디오 스트리밍 응답에 실패했습니다.",
            audioUrl=audio_url,
            bytesRead=len(body),
            contentType=content_type,
            httpStatus=audio_status,
            **audio_detail,
        ),
    )
    browser_results = browser_audio_stream_results(full_audio_url, timeout=timeout)
    browser_streams_ok = all(item["streamable"] for item in browser_results)
    checks.append(
        check(
            "podcast_api_browser_audio_streams",
            "pass" if browser_streams_ok else ("fail" if require_audio_stream else "warn"),
            "Chrome/Safari User-Agent 오디오 스트리밍 응답을 확인했습니다." if browser_streams_ok else "Chrome/Safari User-Agent 오디오 스트리밍 확인에 실패했습니다.",
            audioUrl=audio_url,
            results=browser_results,
        ),
    )
    return checks


def apply_requirements(checks: list[dict[str, Any]], args: argparse.Namespace) -> list[dict[str, Any]]:
    if args.require_env_vars:
        for item in checks:
            if item["name"] == "podcast_required_env_vars" and item["status"] == "warn":
                item["status"] = "fail"
    return checks


def build_audit_payload(checks: list[dict[str, Any]]) -> dict[str, Any]:
    failed_checks = [item["name"] for item in checks if item["status"] == "fail"]
    warning_checks = [item["name"] for item in checks if item["status"] == "warn"]
    status = "failed" if failed_checks else "passed"
    return {
        "checks": checks,
        "failedChecks": failed_checks,
        "passed": status == "passed",
        "status": status,
        "summary": {
            "failed": len(failed_checks),
            "passed": sum(1 for item in checks if item["status"] == "pass"),
            "total": len(checks),
            "warnings": len(warning_checks),
        },
        "warningChecks": warning_checks,
    }


def main() -> int:
    args = parse_args()
    db = SessionLocal()
    try:
        checks = [
            *audit_settings(db),
            *audit_database(
                db,
                enqueue_scheduler_check=args.enqueue_scheduler_check,
                require_events=args.require_events,
                require_failed_job=args.require_failed_job,
                require_live_tts=args.require_live_tts,
                require_seed_script=args.require_seed_script,
                require_tts_retry_evidence=args.require_tts_retry_evidence,
            ),
        ]
    finally:
        db.close()

    if args.api_base_url:
        db = SessionLocal()
        try:
            checks.extend(
                audit_live_tts_delivery(
                    db,
                    args.api_base_url,
                    require_live_tts=args.require_live_tts,
                    timeout=args.timeout,
                ),
            )
        finally:
            db.close()
        checks.extend(
            audit_public_api(
                args.api_base_url,
                require_audio_stream=args.require_audio_stream,
                timeout=args.timeout,
            ),
        )
    checks = apply_requirements(checks, args)
    payload = build_audit_payload(checks)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for item in checks:
            print(f"[{item['status']}] {item['name']}: {item['message']}")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 1 if payload["status"] == "failed" else 0


if __name__ == "__main__":
    sys.exit(main())
