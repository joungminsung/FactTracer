from __future__ import annotations

import argparse
import json
import subprocess
import sys
from typing import Any


SENSITIVE_FLAGS = {"--admin-password", "--password"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the staging checks needed to close docs/PODCAST_REMAINING_WORK.md.",
    )
    parser.add_argument("--admin-email", required=True, help="Admin/reviewer email used to verify failed podcast jobs.")
    parser.add_argument("--admin-password", required=True, help="Admin/reviewer password. Redacted from output.")
    parser.add_argument("--api-base-url", required=True, help="Public API base URL, for example https://api.example.com")
    parser.add_argument("--email", default="podcast-smoke@example.com", help="Smoke user email for analytics event checks.")
    parser.add_argument(
        "--feed",
        action="append",
        choices=["recommended", "daily", "featured", "urgent", "latest", "ranking", "category", "personalized"],
        help="Feed to generate. Repeatable. Defaults to recommended.",
    )
    parser.add_argument("--force", action="store_true", help="Force rerender/regeneration in smoke.")
    parser.add_argument("--format", choices=["solo", "panel_2", "panel_3"], default=None)
    parser.add_argument(
        "--fixture-audio",
        action="store_true",
        help="Use fixture audio for a dry run. This intentionally cannot pass live TTS requirements.",
    )
    parser.add_argument("--limit", type=int, default=1)
    parser.add_argument("--password", default="password123", help="Smoke user password. Redacted from output.")
    parser.add_argument("--timeout", type=int, default=12)
    parser.add_argument("--topic", default=None)
    parser.add_argument("--variant", choices=["short", "standard", "deep"], default="short")
    return parser.parse_args()


def redact_command(command: list[str]) -> list[str]:
    redacted = []
    skip_next = False
    for index, part in enumerate(command):
        if skip_next:
            skip_next = False
            continue
        redacted.append(part)
        if part in SENSITIVE_FLAGS and index + 1 < len(command):
            redacted.append("<redacted>")
            skip_next = True
    return redacted


def run_json_command(command: list[str]) -> dict[str, Any]:
    completed = subprocess.run(command, capture_output=True, check=False, text=True)
    parsed: Any = None
    parse_error = ""
    if completed.stdout.strip():
        try:
            parsed = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            parse_error = str(exc)
    return {
        "command": redact_command(command),
        "exitCode": completed.returncode,
        "json": parsed,
        "parseError": parse_error,
        "stderr": completed.stderr.strip()[:4000],
    }


def audit_check(audit_payload: Any, name: str) -> dict[str, Any]:
    if not isinstance(audit_payload, dict):
        return {}
    checks = audit_payload.get("checks")
    if not isinstance(checks, list):
        return {}
    for item in checks:
        if isinstance(item, dict) and item.get("name") == name:
            return item
    return {}


def payload_section(payload: Any, key: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    section = payload.get(key)
    return section if isinstance(section, dict) else {}


def check_status(audit_payload: Any, name: str) -> str:
    return str(audit_check(audit_payload, name).get("status") or "")


def smoke_generated_openai_episode(smoke_payload: Any) -> bool:
    if not isinstance(smoke_payload, dict):
        return False
    rows = smoke_payload.get("database")
    if not isinstance(rows, list):
        return False
    return any(
        isinstance(row, dict)
        and row.get("ttsProvider") == "openai"
        and row.get("ttsStatus") == "completed"
        and bool(row.get("audioUrl"))
        for row in rows
    )


def smoke_events_profile_pass(smoke_payload: Any) -> bool:
    persistence = payload_section(smoke_payload, "publicApi").get("eventPersistence")
    if not isinstance(persistence, dict):
        return False
    if persistence.get("missingEventTypes"):
        return False
    profile = persistence.get("profile")
    if not isinstance(profile, dict):
        return False
    return bool(profile.get("topicWeights") or profile.get("eventGroupWeights"))


def smoke_admin_jobs_pass(smoke_payload: Any) -> bool:
    admin_jobs = payload_section(smoke_payload, "publicApi").get("adminFailedJobs")
    if not isinstance(admin_jobs, dict):
        return False
    if admin_jobs.get("status") != 200 or int(admin_jobs.get("count") or 0) <= 0:
        return False
    jobs = admin_jobs.get("jobs")
    if not isinstance(jobs, list):
        return False
    return any(
        isinstance(job, dict)
        and job.get("jobType") == "render_podcast_audio"
        and job.get("status") in {"dead_letter", "failed"}
        and bool(job.get("userMessage"))
        for job in jobs
    )


def build_smoke_command(args: argparse.Namespace) -> list[str]:
    command = [
        sys.executable,
        "scripts/run_podcast_operational_smoke.py",
        "--api-base-url",
        args.api_base_url,
        "--limit",
        str(args.limit),
        "--variant",
        args.variant,
        "--create-admin-failed-job",
        "--record-events",
        "--check-audio-stream",
        "--check-admin-failed-jobs",
        "--admin-email",
        args.admin_email,
        "--admin-password",
        args.admin_password,
        "--email",
        args.email,
        "--password",
        args.password,
        "--timeout",
        str(args.timeout),
        "--enqueue-scheduler-check",
    ]
    if args.fixture_audio:
        command.append("--fixture-audio")
    else:
        command.append("--render-audio")
    if args.force:
        command.append("--force")
    if args.format:
        command.extend(["--format", args.format])
    if args.topic:
        command.extend(["--topic", args.topic])
    for feed in args.feed or ["recommended"]:
        command.extend(["--feed", feed])
    return command


def build_audit_command(args: argparse.Namespace) -> list[str]:
    return [
        sys.executable,
        "scripts/audit_podcast_operations.py",
        "--api-base-url",
        args.api_base_url,
        "--require-env-vars",
        "--require-live-tts",
        "--require-audio-stream",
        "--require-events",
        "--require-failed-job",
        "--require-seed-script",
        "--require-tts-retry-evidence",
        "--timeout",
        str(args.timeout),
        "--json",
    ]


def build_remaining_work_report(
    *,
    smoke_result: dict[str, Any],
    audit_result: dict[str, Any],
) -> dict[str, Any]:
    smoke_payload = smoke_result.get("json")
    audit_payload = audit_result.get("json")
    live_tts_audio_pass = (
        check_status(audit_payload, "podcast_live_tts_audio") == "pass"
        and smoke_generated_openai_episode(smoke_payload)
    )
    smoke_and_audit_pass = (
        smoke_result.get("exitCode") == 0
        and audit_result.get("exitCode") == 0
        and isinstance(audit_payload, dict)
        and audit_payload.get("status") == "passed"
        and audit_payload.get("passed") is True
        and audit_payload.get("failedChecks") == []
    )
    live_tts_delivery_pass = check_status(audit_payload, "podcast_live_tts_delivery") == "pass"
    recommendation_events_pass = (
        smoke_events_profile_pass(smoke_payload)
        and check_status(audit_payload, "podcast_metric_events") == "pass"
        and check_status(audit_payload, "podcast_interest_profiles") == "pass"
    )
    admin_operational_pass = (
        smoke_admin_jobs_pass(smoke_payload)
        and check_status(audit_payload, "podcast_failed_jobs") == "pass"
    )
    items = [
        {
            "id": "live_tts_audio",
            "passed": live_tts_audio_pass,
            "requirement": "OpenAI TTS 완료 회차 1개 이상 생성 및 podcast_live_tts_audio=pass",
            "evidence": {
                "auditCheck": audit_check(audit_payload, "podcast_live_tts_audio"),
                "smokeGeneratedOpenAiEpisode": smoke_generated_openai_episode(smoke_payload),
            },
        },
        {
            "id": "staging_smoke_and_audit",
            "passed": smoke_and_audit_pass,
            "requirement": "스테이징 smoke/audit 전체 요구 조건 status=passed, passed=true, failedChecks=[]",
            "evidence": {
                "auditFailedChecks": audit_payload.get("failedChecks") if isinstance(audit_payload, dict) else None,
                "auditPassed": audit_payload.get("passed") if isinstance(audit_payload, dict) else None,
                "auditStatus": audit_payload.get("status") if isinstance(audit_payload, dict) else None,
                "smokeExitCode": smoke_result.get("exitCode"),
                "auditExitCode": audit_result.get("exitCode"),
            },
        },
        {
            "id": "live_tts_delivery",
            "passed": live_tts_delivery_pass,
            "requirement": "OpenAI TTS 오디오 저장 경로와 배포 접근 URL이 같은 회차 기준으로 연결",
            "evidence": {
                "auditCheck": audit_check(audit_payload, "podcast_live_tts_delivery"),
            },
        },
        {
            "id": "recommendation_events_profile",
            "passed": recommendation_events_pass,
            "requirement": "행동 이벤트 6종과 UserInterestProfile 토픽/포맷 가중치 누적 확인",
            "evidence": {
                "auditInterestProfiles": audit_check(audit_payload, "podcast_interest_profiles"),
                "auditMetricEvents": audit_check(audit_payload, "podcast_metric_events"),
                "smokeEventPersistence": payload_section(smoke_payload, "publicApi").get("eventPersistence"),
            },
        },
        {
            "id": "admin_failed_job_display_data",
            "passed": admin_operational_pass,
            "requirement": "/admin/podcasts 실패 render_podcast_audio 작업 이력과 운영자 userMessage 표시 데이터 확인",
            "evidence": {
                "adminUrl": "/admin/podcasts",
                "auditFailedJobs": audit_check(audit_payload, "podcast_failed_jobs"),
                "smokeAdminFailedJobs": payload_section(smoke_payload, "publicApi").get("adminFailedJobs"),
            },
        },
    ]
    return {
        "audit": audit_result,
        "items": items,
        "passed": all(item["passed"] for item in items),
        "smoke": smoke_result,
        "summary": {
            "failed": sum(1 for item in items if not item["passed"]),
            "passed": sum(1 for item in items if item["passed"]),
            "total": len(items),
        },
    }


def main() -> int:
    args = parse_args()
    smoke_result = run_json_command(build_smoke_command(args))
    audit_result = run_json_command(build_audit_command(args))
    report = build_remaining_work_report(smoke_result=smoke_result, audit_result=audit_result)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
