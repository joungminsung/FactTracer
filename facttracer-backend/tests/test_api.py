import base64
import io
import importlib
import math
import os
import shutil
import time
import wave
from pathlib import Path
from datetime import UTC, datetime, timedelta

os.environ["FACTTRACER_DATABASE_URL"] = "sqlite:///./test_facttracer.db"
os.environ["FACTTRACER_JWT_SECRET"] = "test-secret-with-at-least-thirty-two-bytes"
os.environ["FACTTRACER_AI_PROCESSING_ENABLED"] = "false"
os.environ["FACTTRACER_BOOTSTRAP_DEFAULT_DISCOVERY_ENABLED"] = "false"
os.environ["FACTTRACER_EMBEDDED_SCHEDULER_ENABLED"] = "false"
os.environ["FACTTRACER_EMBEDDED_WORKER_ENABLED"] = "false"
os.environ["FACTTRACER_OBJECT_STORAGE_PATH"] = "./test_storage"

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, event, select, text  # noqa: E402

from app import models, schemas  # noqa: E402
from app.collectors.base import CollectedArticle  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.schema import ensure_database_schema  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.services.ai.deepseek_client import DeepSeekAnalysisService  # noqa: E402
from app.services.claims.workflow import create_claim_from_text  # noqa: E402
from app.services.discovery.incident_detector import upsert_discovery_topic  # noqa: E402
from app.services.issues.page_builder import build_issue_cache_payload  # noqa: E402
from app.services.jobs import run_due_jobs, schedule_due_issue_backfill_jobs  # noqa: E402
from app.services.scheduler.runtime import tick_scheduler_once  # noqa: E402
from app.services.search.keywords import fallback_keyword_variants, seed_search_keywords  # noqa: E402
from app.services.topics import normalize_topic  # noqa: E402
from app.workers import issue_jobs  # noqa: E402
from app.workers.issue_jobs import process_article  # noqa: E402


def setup_function() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def teardown_module() -> None:
    Base.metadata.drop_all(bind=engine)
    db_path = Path("test_facttracer.db")
    if db_path.exists():
        db_path.unlink()
    storage_path = Path("test_storage")
    if storage_path.exists():
        shutil.rmtree(storage_path)


def signup(client: TestClient, email: str = "admin@example.com") -> dict:
    response = client.post(
        "/v1/auth/signup",
        json={"email": email, "name": "관리자", "password": "password123"},
    )
    assert response.status_code == 201
    return response.json()


def wait_for_check_result(client: TestClient, check_id: str) -> dict:
    deadline = time.monotonic() + 5
    latest: dict = {}
    while time.monotonic() < deadline:
        response = client.get(f"/v1/checks/{check_id}")
        assert response.status_code == 200
        latest = response.json()
        if latest["status"] in {"completed", "needs_review"}:
            return latest
        time.sleep(0.05)
    raise AssertionError(f"manual check did not finish: {latest}")


def seed_contract_records(user_id: str | None = None) -> None:
    db = SessionLocal()
    try:
        issue = models.Issue(
            id="issue_001",
            title="고영향 공공 이슈 A",
            topic="정치",
            status="검증 진행",
            risk="고영향",
            summary="주요 수치와 근거가 서로 다른 주장으로 확산되고 있습니다.",
            issue_score=91,
            article_count=126,
            cluster_count=18,
            verified_count=11,
            needs_review_count=7,
            changed_claims=3,
            confirmed_facts=[
                {
                    "label": "확인",
                    "text": "일부 현장에서 절차 지연 또는 수치 차이가 발생했습니다.",
                    "verdict": "공식자료 확인",
                    "tone": "positive",
                },
            ],
            claim_clusters=[
                {
                    "title": "발생 범위",
                    "question": "문제 발생 범위는 어느 기준으로 봐야 하는가?",
                    "claims": ["14곳 초기 파악", "전국 50곳 후속 주장"],
                    "conflict": "집계 기준과 발표 시점이 다릅니다.",
                    "commonGround": "일부 현장 문제 발생 자체는 확인 가능합니다.",
                    "verdict": "수치 충돌",
                    "tone": "warning",
                },
            ],
            claims=[
                {
                    "id": "claim_public_001",
                    "text": "전국적으로 동일 문제가 대규모로 발생했다.",
                    "type": "수치 주장",
                    "verdict": "일부 사실",
                    "tone": "warning",
                    "confidence": 0.62,
                    "evidence": "복수 언론 보도",
                    "status": "후속 수치 확인 필요",
                },
            ],
            evidences=[
                {
                    "id": "evidence_001",
                    "label": "최신 공식 기준",
                    "source": "관계 기관 설명자료",
                    "date": "2026-06-08",
                    "summary": "지역별 집계 기준과 후속 설명을 포함합니다.",
                    "credibility": 0.94,
                },
            ],
            perspectives=[
                {
                    "name": "관리 책임 강조",
                    "core": "기관의 현장 관리 실패와 재발 방지 대책을 핵심 문제로 봅니다.",
                    "uses": "현장 지연 보도, 기관 사과",
                    "challengedBy": "고의성 여부는 단정하기 어렵습니다.",
                    "commonGround": "절차 지연 발생 자체는 확인 가능한 사안입니다.",
                },
            ],
            articles=[
                {
                    "id": "article-001",
                    "title": "일부 현장 절차 지연으로 혼선",
                    "outlet": "연합뉴스",
                    "publishedAt": "06-08 08:21",
                    "url": "https://example.com/news/article-001",
                    "claimCount": 5,
                    "outdatedClaims": 1,
                    "officialSourceCount": 2,
                    "verdict": "초기 기준",
                    "tone": "warning",
                    "note": "초기 발생 범위가 후속 공식자료와 다릅니다.",
                },
            ],
            timeline=[
                {
                    "id": "timeline-001",
                    "occurredAt": "06-08 07:58",
                    "type": "현장 제보",
                    "title": "일부 현장 절차 지연 제보 확산",
                    "description": "현장 영상과 SNS 게시물이 먼저 확산됐습니다.",
                },
            ],
            source_documents=[
                {
                    "id": "source-001",
                    "title": "현장 집계 기준 설명자료",
                    "publisher": "관계 기관",
                    "publishedAt": "2026-06-08T10:05:00+09:00",
                    "url": "https://example.com/source/briefing",
                    "sourceType": "official",
                    "credibility": 0.94,
                },
            ],
            number_changes=[
                {
                    "id": "num-001",
                    "label": "현장 수",
                    "previousValue": "14곳",
                    "currentValue": "50곳",
                    "changedAt": "06-08 10:05",
                    "source": "공식 설명자료",
                    "note": "초기 보도 기준과 후속 집계 기준이 다릅니다.",
                    "tone": "warning",
                },
            ],
        )
        db.add(issue)
        db.add(
            models.AdminQueueItem(
                article_count=126,
                id="issue_001",
                priority="높음",
                reason="고영향 이슈, 낙인 표현 신고 증가, 공식자료 갱신",
                status="검토 대기",
                title="고영향 공공 이슈 A",
                topic="공공",
            ),
        )
        db.add(
            models.ModerationReport(
                excerpt="특정 세력이 의도적으로 문제를 만들었다.",
                id="report-001",
                issue_id="issue_001",
                issue_title="고영향 공공 이슈 A",
                priority="높음",
                reason="근거 없는 고의성 단정",
                status="open",
                target_type="claim",
            ),
        )
        db.add(
            models.SourceDomain(
                credibility=0.94,
                domain="example.com",
                id="domain-001",
                name="예시 출처",
                note="공식자료 1순위 출처",
                source_type="official",
                status="trusted",
            ),
        )
        db.add(
            models.AgentRun(
                agent="News Watcher",
                id="run-001",
                status="completed",
                target="새 기사 4건 감지",
            ),
        )
        if user_id:
            db.add(models.SavedIssue(issue_id="issue_001", user_id=user_id))
            db.add(
                models.SubmittedClaim(
                    claim_text="일부 현장에서 절차가 지연되었다.",
                    claim_type="수치",
                    id="claim_001",
                    issue_id="issue_001",
                    reason="후속 기사 기준이 기존 발표와 다릅니다.",
                    refutable_point="현장별 처리 시각이 확인되면 판정이 바뀔 수 있습니다.",
                    status="received",
                    user_id=user_id,
                ),
            )
            db.add(
                models.VerificationRequest(
                    article_url="https://example.com/news/001",
                    id="vr_001",
                    issue_id="issue_001",
                    matched_issue_id="issue_001",
                    status="queued",
                    user_id=user_id,
                ),
            )
        db.commit()
    finally:
        db.close()


def seed_podcast_issue(
    *,
    article_count: int = 18,
    changed_claims: int = 0,
    issue_id: str,
    issue_score: int = 70,
    needs_review_count: int = 2,
    summary: str = "핵심 주장과 공식자료를 함께 확인해야 하는 이슈입니다.",
    title: str,
    topic: str,
) -> None:
    db = SessionLocal()
    try:
        db.add(
            models.Issue(
                id=issue_id,
                title=title,
                topic=topic,
                status="검증 진행",
                risk="고영향" if issue_score >= 80 else "일반",
                summary=summary,
                issue_score=issue_score,
                article_count=article_count,
                cluster_count=4,
                verified_count=2,
                needs_review_count=needs_review_count,
                changed_claims=changed_claims,
                representative_image_url=f"https://example.com/images/{issue_id}.jpg",
                confirmed_facts=[
                    {
                        "label": "확인",
                        "text": "공식자료와 복수 보도를 기준으로 핵심 사실을 확인 중입니다.",
                        "verdict": "대체로 사실",
                        "tone": "positive",
                    },
                ],
                claim_clusters=[
                    {
                        "title": "핵심 쟁점",
                        "question": "무엇을 기준으로 사실관계를 봐야 하는가?",
                        "claims": ["초기 보도 기준", "공식자료 후속 기준"],
                        "conflict": "발표 시점과 집계 기준이 다릅니다.",
                        "commonGround": "공식자료의 기준을 우선 확인합니다.",
                        "verdict": "근거 확인 중",
                        "tone": "warning",
                    },
                ],
                evidences=[
                    {
                        "id": f"evidence_{issue_id}",
                        "label": "공식 설명자료",
                        "source": "관계 기관",
                        "date": "2026-06-10",
                        "summary": "기준 변경과 후속 설명을 포함합니다.",
                        "credibility": 0.91,
                        "url": f"https://example.com/sources/{issue_id}",
                        "sourceType": "official",
                    },
                ],
                articles=[
                    {
                        "id": f"article_{issue_id}",
                        "title": f"{title} 후속 보도",
                        "outlet": "연합뉴스",
                        "publishedAt": "2026-06-10T09:00:00+09:00",
                        "url": f"https://example.com/news/{issue_id}",
                        "claimCount": 3,
                        "outdatedClaims": 0,
                        "officialSourceCount": 1,
                        "verdict": "검증 중",
                        "tone": "warning",
                        "note": "후속 공식자료와 대조 중입니다.",
                    },
                ],
                source_documents=[
                    {
                        "id": f"source_{issue_id}",
                        "title": "공식 설명자료",
                        "publisher": "관계 기관",
                        "publishedAt": "2026-06-10T08:30:00+09:00",
                        "url": f"https://example.com/source/{issue_id}",
                        "sourceType": "official",
                        "credibility": 0.91,
                    },
                ],
            ),
        )
        db.commit()
    finally:
        db.close()


def silent_wav_bytes(duration_ms: int = 40, *, frame_rate: int = 8000) -> bytes:
    frames = int(frame_rate * duration_ms / 1000)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(frame_rate)
        audio.writeframes(b"\x00\x00" * frames)
    return buffer.getvalue()


def wav_bytes_with_declared_frame_count(
    *,
    declared_frames: int,
    actual_frames: int,
    frame_rate: int = 8000,
) -> bytes:
    channels = 1
    sample_width = 2
    block_align = channels * sample_width
    declared_data_size = declared_frames * block_align
    actual_data = b"\x00\x00" * actual_frames
    return (
        b"RIFF"
        + (36 + declared_data_size).to_bytes(4, "little")
        + b"WAVE"
        + b"fmt "
        + (16).to_bytes(4, "little")
        + (1).to_bytes(2, "little")
        + channels.to_bytes(2, "little")
        + frame_rate.to_bytes(4, "little")
        + (frame_rate * block_align).to_bytes(4, "little")
        + block_align.to_bytes(2, "little")
        + (sample_width * 8).to_bytes(2, "little")
        + b"data"
        + declared_data_size.to_bytes(4, "little")
        + actual_data
    )


def enable_test_openai_tts(db) -> None:
    db.merge(
        models.SystemSetting(
            description="test AI processing",
            group="automation",
            is_secret=False,
            key="ai_processing_enabled",
            label="자동 처리",
            value=True,
            value_type="boolean",
        ),
    )
    db.merge(
        models.SystemSetting(
            description="test OpenAI key",
            group="ai",
            is_secret=True,
            key="openai_api_key",
            label="OpenAI API Key",
            value="test-openai-key",
            value_type="string",
        ),
    )
    db.flush()


def test_health_and_empty_home() -> None:
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}
        metrics = client.get("/metrics")
        assert metrics.status_code == 200
        assert "facttracer_issues_total" in metrics.text
        assert "facttracer_podcast_jobs_failed" in metrics.text
        assert "facttracer_podcast_draft_episodes" in metrics.text
        assert "facttracer_podcast_tts_pending" in metrics.text
        response = client.get("/v1/issues/home")
        assert response.status_code == 200
        payload = response.json()
        assert payload["issues"] == []
        assert payload["selectedIssue"] is None
        assert "전체" in payload["topics"]


def test_default_cors_origins_cover_dev_frontend_ports() -> None:
    from app.core.config import get_settings

    origins = set(get_settings().cors_origins)

    assert "http://localhost:3002" in origins
    assert "http://127.0.0.1:3002" in origins
    assert "http://localhost:3003" in origins
    assert "http://127.0.0.1:3003" in origins


def test_generate_podcast_episodes_uses_personalized_issue_ranking() -> None:
    with TestClient(app) as client:
        session = signup(client, email="podcast-user@example.com")
    user_id = session["user"]["id"]
    token = session["accessToken"]
    seed_podcast_issue(
        issue_id="issue_podcast_politics",
        issue_score=90,
        title="선거 관리 쟁점",
        topic="정치",
    )
    seed_podcast_issue(
        issue_id="issue_podcast_economy",
        issue_score=55,
        title="물가 지원금 기준 논란",
        topic="경제",
    )

    db = SessionLocal()
    try:
        user = db.get(models.User, user_id)
        assert user is not None
        db.add(
            models.UserInterestProfile(
                user_id=user_id,
                topic_weights_json={"경제": 6},
            ),
        )
        db.commit()

        from app.services.podcasts.generator import generate_podcast_episodes

        episodes = generate_podcast_episodes(db, user=user, feed="personalized", limit=2)
        db.commit()

        assert [episode.issue_id for episode in episodes] == [
            "issue_podcast_economy",
            "issue_podcast_politics",
        ]
        assert episodes[0].rank_json["rankMode"] == "personalized"
        assert episodes[0].script_json[0]["speakerName"]
    finally:
        db.close()

    with TestClient(app) as client:
        response = client.get("/v1/podcasts/home", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    sections = {section["id"]: section for section in response.json()["sections"]}
    assert sections["personalized"]["episodes"][0]["issueId"] == "issue_podcast_economy"
    assert sections["personalized"]["episodes"][0]["rankReason"]


def test_podcast_recommendation_weights_are_operational_settings() -> None:
    seed_podcast_issue(
        issue_id="issue_podcast_high_impact_old",
        issue_score=96,
        title="고영향 오래된 이슈",
        topic="사회",
    )
    seed_podcast_issue(
        issue_id="issue_podcast_fresh_low",
        issue_score=45,
        title="최신성 우선 이슈",
        topic="사회",
    )

    db = SessionLocal()
    try:
        old_issue = db.get(models.Issue, "issue_podcast_high_impact_old")
        fresh_issue = db.get(models.Issue, "issue_podcast_fresh_low")
        assert old_issue is not None
        assert fresh_issue is not None
        old_issue.updated_at = datetime.now(UTC) - timedelta(days=4)
        fresh_issue.updated_at = datetime.now(UTC)
        for key, value in {
            "podcast_recommendation_controversy_weight": 0,
            "podcast_recommendation_freshness_weight": 1,
            "podcast_recommendation_impact_weight": 0,
            "podcast_recommendation_momentum_weight": 0,
            "podcast_recommendation_verification_weight": 0,
        }.items():
            db.merge(
                models.SystemSetting(
                    description="test podcast recommendation weight",
                    group="automation",
                    is_secret=False,
                    key=key,
                    label=key,
                    value=value,
                    value_type="float",
                ),
            )
        db.commit()

        from app.services.podcasts.generator import generate_podcast_episodes

        episodes = generate_podcast_episodes(db, feed="recommended", limit=2)
        db.commit()

        assert episodes[0].issue_id == "issue_podcast_fresh_low"
        assert episodes[0].rank_json["rankReason"] == "사회적 영향도, 검증 필요도, 최신성 우선"
        assert episodes[0].rank_json["weights"]["freshness"] == 1
    finally:
        db.close()


def test_podcast_detail_returns_transcript_sources_and_next_queue() -> None:
    seed_podcast_issue(issue_id="issue_podcast_detail_a", title="재난 문자 기준 변경", topic="재난", issue_score=84)
    seed_podcast_issue(issue_id="issue_podcast_detail_b", title="보건 정책 발표 검증", topic="보건", issue_score=78)

    db = SessionLocal()
    try:
        from app.services.podcasts.generator import generate_podcast_episodes

        episodes = generate_podcast_episodes(db, feed="latest", limit=2)
        db.commit()
        episode_id = episodes[0].id
    finally:
        db.close()

    with TestClient(app) as client:
        response = client.get(f"/v1/podcasts/{episode_id}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["episode"]["id"] == episode_id
    assert payload["episode"]["script"][0]["text"]
    assert payload["episode"]["sources"][0]["url"]
    assert payload["nextQueue"][0]["id"] != episode_id


def test_podcast_script_segments_include_sentence_source_references() -> None:
    seed_podcast_issue(
        issue_id="issue_podcast_source_refs",
        title="출처 매핑 팟캐스트",
        topic="정치",
        issue_score=82,
    )

    db = SessionLocal()
    try:
        from app.services.podcasts.generator import generate_podcast_episodes

        episodes = generate_podcast_episodes(
            db,
            feed="recommended",
            issue_id="issue_podcast_source_refs",
            limit=1,
        )
        db.commit()
        episode_id = episodes[0].id
    finally:
        db.close()

    with TestClient(app) as client:
        response = client.get(f"/v1/podcasts/{episode_id}")

    assert response.status_code == 200
    episode = response.json()["episode"]
    source_ids = {source["id"] for source in episode["sources"]}
    assert source_ids
    assert all("sourceRefs" in segment for segment in episode["script"])
    referenced_ids = {
        ref["sourceId"]
        for segment in episode["script"]
        for ref in segment["sourceRefs"]
    }
    assert referenced_ids
    assert referenced_ids.issubset(source_ids)


def test_podcast_expression_review_flags_pattern_based_risky_language() -> None:
    seed_podcast_issue(
        issue_id="issue_podcast_expression_review",
        title="표현 검수 팟캐스트",
        topic="정치",
        issue_score=82,
        summary="이 사안은 100% 조작이 분명하다는 주장이 확산됐지만 확인이 필요합니다.",
    )

    db = SessionLocal()
    try:
        from app.services.podcasts.generator import generate_podcast_episodes

        episodes = generate_podcast_episodes(
            db,
            feed="recommended",
            issue_id="issue_podcast_expression_review",
            limit=1,
        )
        db.commit()
        episode = episodes[0]
        joined_script = " ".join(segment["text"] for segment in episode.script_json)
        risky_segments = [
            segment
            for segment in episode.script_json
            if (segment.get("expressionReview") or {}).get("findings")
        ]

        assert risky_segments
        assert "100%" not in joined_script
        assert "조작이 분명" not in joined_script
        gate = episode.generation_json["publicationGate"]
        assert "riskyExpression" in gate["warnings"]
        assert gate["expressionFindings"]
    finally:
        db.close()


def test_admin_can_inspect_and_archive_podcast_episode() -> None:
    seed_podcast_issue(issue_id="issue_podcast_admin", title="관리자 팟캐스트 점검", topic="정치", issue_score=86)

    db = SessionLocal()
    try:
        from app.services.podcasts.generator import generate_podcast_episodes

        episodes = generate_podcast_episodes(db, feed="latest", limit=1)
        db.commit()
        episode_id = episodes[0].id
    finally:
        db.close()

    with TestClient(app) as client:
        session = signup(client, email="podcast-admin@example.com")
        headers = {"Authorization": f"Bearer {session['accessToken']}"}

        list_response = client.get("/v1/admin/podcasts", headers=headers)
        assert list_response.status_code == 200
        assert list_response.json()["episodes"][0]["id"] == episode_id

        detail_response = client.get(f"/v1/admin/podcasts/{episode_id}", headers=headers)
        assert detail_response.status_code == 200
        detail_episode = detail_response.json()["episode"]
        assert detail_episode["script"][0]["text"]
        assert detail_episode["publicationGate"]["status"] == "publishable"
        assert detail_episode["notationReview"]["terms"]
        assert detail_episode["correctionPolicy"]["action"] == "monitor"
        assert detail_episode["variant"] == "standard"

        status_response = client.patch(
            f"/v1/admin/podcasts/{episode_id}/status",
            headers=headers,
            json={"status": "archived"},
        )
        assert status_response.status_code == 200
        assert status_response.json()["status"] == "archived"

        public_detail_response = client.get(f"/v1/podcasts/{episode_id}")
        assert public_detail_response.status_code == 404

        admin_archived_response = client.get(
            "/v1/admin/podcasts?status=archived",
            headers=headers,
        )
        assert admin_archived_response.status_code == 200
        assert admin_archived_response.json()["episodes"][0]["status"] == "archived"


def test_admin_podcast_generation_targets_single_issue_and_can_render_later(monkeypatch) -> None:
    seed_podcast_issue(issue_id="issue_podcast_admin_target", title="선택 생성 대상 이슈", topic="경제", issue_score=82)
    seed_podcast_issue(issue_id="issue_podcast_admin_other", title="선택 생성 제외 이슈", topic="정치", issue_score=95)

    def fake_speech_bytes(self, *, input_text: str, instructions: str, voice: str) -> bytes:
        return silent_wav_bytes()

    with TestClient(app) as client:
        session = signup(client, email="podcast-admin-target@example.com")
        headers = {"Authorization": f"Bearer {session['accessToken']}"}
        generate_response = client.post(
            "/v1/podcasts/generate?issueId=issue_podcast_admin_target&limit=1&renderAudio=false",
            headers=headers,
        )
        assert generate_response.status_code == 200
        generated = generate_response.json()["episodes"]
        assert len(generated) == 1
        assert generated[0]["issueId"] == "issue_podcast_admin_target"
        assert generated[0]["ttsStatus"] == "script_ready"
        episode_id = generated[0]["id"]
        detail_before_render = client.get(f"/v1/admin/podcasts/{episode_id}", headers=headers)
        assert detail_before_render.status_code == 200
        assert detail_before_render.json()["episode"]["audioUrl"] is None

        db = SessionLocal()
        try:
            from app.services.podcasts.tts import OpenAITTSEpisodeRenderer

            monkeypatch.setattr(OpenAITTSEpisodeRenderer, "_speech_bytes", fake_speech_bytes)
            enable_test_openai_tts(db)
            db.commit()
        finally:
            db.close()

        render_response = client.post(
            f"/v1/podcasts/{episode_id}/render-audio?force=true",
            headers=headers,
        )
        assert render_response.status_code == 200
        episode = render_response.json()["episode"]
        assert episode["ttsStatus"] == "completed"
        assert episode["audioUrl"] == f"/v1/podcasts/{episode_id}/audio"


def test_admin_podcast_status_changes_reflect_public_feed_immediately() -> None:
    seed_podcast_issue(issue_id="issue_podcast_status_feed", title="상태 반영 팟캐스트", topic="사회", issue_score=82)

    db = SessionLocal()
    try:
        from app.services.podcasts.generator import generate_podcast_episodes

        episode = generate_podcast_episodes(
            db,
            feed="latest",
            issue_id="issue_podcast_status_feed",
            limit=1,
        )[0]
        db.commit()
        episode_id = episode.id
    finally:
        db.close()

    with TestClient(app) as client:
        session = signup(client, email="podcast-admin-status@example.com")
        headers = {"Authorization": f"Bearer {session['accessToken']}"}

        public_feed = client.get("/v1/podcasts?feed=latest")
        assert public_feed.status_code == 200
        assert any(row["id"] == episode_id for row in public_feed.json()["episodes"])

        draft_response = client.patch(
            f"/v1/admin/podcasts/{episode_id}/status",
            headers=headers,
            json={"status": "draft"},
        )
        assert draft_response.status_code == 200
        assert client.get(f"/v1/podcasts/{episode_id}").status_code == 404
        draft_feed = client.get("/v1/podcasts?feed=latest")
        assert not any(row["id"] == episode_id for row in draft_feed.json()["episodes"])

        published_response = client.patch(
            f"/v1/admin/podcasts/{episode_id}/status",
            headers=headers,
            json={"status": "published"},
        )
        assert published_response.status_code == 200
        republished_feed = client.get("/v1/podcasts?feed=latest")
        assert any(row["id"] == episode_id for row in republished_feed.json()["episodes"])

        archived_response = client.patch(
            f"/v1/admin/podcasts/{episode_id}/status",
            headers=headers,
            json={"status": "archived"},
        )
        assert archived_response.status_code == 200
        archived_feed = client.get("/v1/podcasts?feed=latest")
        assert not any(row["id"] == episode_id for row in archived_feed.json()["episodes"])


def test_admin_podcast_failed_jobs_include_operator_message() -> None:
    db = SessionLocal()
    try:
        db.add(
            models.JobAttempt(
                attempts=1,
                id="job_podcast_tts_failed_message",
                job_type="render_podcast_audio",
                last_error="invalid_api_key: Incorrect API key provided",
                max_attempts=3,
                status="failed",
                target_id="podcast_failed_message",
            ),
        )
        db.commit()
    finally:
        db.close()

    with TestClient(app) as client:
        session = signup(client, email="podcast-admin-job-message@example.com")
        response = client.get(
            "/v1/admin/jobs",
            headers={"Authorization": f"Bearer {session['accessToken']}"},
        )

    assert response.status_code == 200
    job = next(row for row in response.json()["jobs"] if row["id"] == "job_podcast_tts_failed_message")
    assert job["userMessage"] == "OpenAI TTS 연결 키 또는 모델 설정을 확인해야 합니다."


def test_podcast_analytics_updates_user_interest_profile() -> None:
    seed_podcast_issue(
        issue_id="issue_podcast_interest",
        title="경제 팟캐스트 개인화",
        topic="경제",
    )

    with TestClient(app) as client:
        session = signup(client, email="podcast-interest@example.com")
        headers = {"Authorization": f"Bearer {session['accessToken']}"}
        response = client.post(
            "/v1/analytics/events",
            headers=headers,
            json={
                "eventType": "podcast_play_start",
                "issueId": "issue_podcast_interest",
                "metadata": {
                    "episodeId": "podcast_interest_001",
                    "podcastCategory": "경제",
                    "podcastFormat": "panel_2",
                },
            },
        )
        assert response.status_code == 201

    db = SessionLocal()
    try:
        profile = db.get(models.UserInterestProfile, session["user"]["id"])
        assert profile is not None
        assert profile.topic_weights_json["경제"] == 1.2
        assert profile.event_group_weights_json["podcast_format:panel_2"] == 1.2
    finally:
        db.close()


def test_podcast_personalized_order_changes_after_user_behavior() -> None:
    seed_podcast_issue(
        issue_id="issue_podcast_behavior_politics",
        issue_score=76,
        title="정치 팟캐스트 기본 추천",
        topic="정치",
    )
    seed_podcast_issue(
        issue_id="issue_podcast_behavior_economy",
        issue_score=70,
        title="경제 팟캐스트 행동 추천",
        topic="경제",
    )

    db = SessionLocal()
    try:
        from app.services.podcasts.generator import generate_podcast_episodes

        generate_podcast_episodes(db, feed="recommended", limit=2)
        db.commit()
    finally:
        db.close()

    with TestClient(app) as client:
        session = signup(client, email="podcast-behavior@example.com")
        headers = {"Authorization": f"Bearer {session['accessToken']}"}

        before = client.get("/v1/podcasts/home", headers=headers)
        assert before.status_code == 200
        before_sections = {section["id"]: section for section in before.json()["sections"]}
        assert before_sections["personalized"]["episodes"][0]["issueId"] == "issue_podcast_behavior_politics"

        event = client.post(
            "/v1/analytics/events",
            headers=headers,
            json={
                "eventType": "podcast_complete",
                "issueId": "issue_podcast_behavior_economy",
                "metadata": {
                    "episodeId": before_sections["personalized"]["episodes"][1]["id"],
                    "podcastCategory": "경제",
                    "podcastFormat": "panel_2",
                },
            },
        )
        assert event.status_code == 201

        after = client.get("/v1/podcasts/home", headers=headers)
        assert after.status_code == 200
        after_sections = {section["id"]: section for section in after.json()["sections"]}
        assert after_sections["personalized"]["episodes"][0]["issueId"] == "issue_podcast_behavior_economy"


def test_daily_podcast_groups_multiple_issues_and_deduplicates_by_day() -> None:
    seed_podcast_issue(issue_id="issue_podcast_daily_a", title="데일리 첫 번째 이슈", topic="정치", issue_score=88)
    seed_podcast_issue(issue_id="issue_podcast_daily_b", title="데일리 두 번째 이슈", topic="경제", issue_score=82)

    db = SessionLocal()
    try:
        from app.services.podcasts.generator import generate_podcast_episodes, list_podcast_episodes

        first = generate_podcast_episodes(db, feed="daily", limit=2)
        db.commit()
        assert len(first) == 1
        assert first[0].episode_type == "daily"
        assert first[0].issue_id is None
        assert set(first[0].generation_json["issueIds"]) == {
            "issue_podcast_daily_a",
            "issue_podcast_daily_b",
        }
        assert "종합 팟캐스트" in first[0].title
        assert first[0].generation_json["podcastKind"] == "comprehensive"
        assert len({segment["speakerId"] for segment in first[0].script_json}) >= 2
        joined_script = " ".join(segment["text"] for segment in first[0].script_json)
        assert "에 따르면" in joined_script
        assert "어떤 내용인가요" in joined_script
        assert "나눠보겠습니다" in joined_script
        assert "진행됐다" not in joined_script
        assert "제기됨" not in joined_script
        first_episode_id = first[0].id

        second = generate_podcast_episodes(db, feed="daily", limit=2)
        db.commit()
        assert second[0].id == first_episode_id
        assert list_podcast_episodes(db, feed="daily", limit=5)[0].id == first_episode_id
    finally:
        db.close()

    with TestClient(app) as client:
        response = client.get("/v1/podcasts/home")

    assert response.status_code == 200
    section_episode_ids = [
        episode["id"]
        for section in response.json()["sections"]
        for episode in section["episodes"]
    ]
    assert section_episode_ids.count(first_episode_id) == 1


def test_daily_podcast_uses_openai_script_generation_when_available(monkeypatch) -> None:
    seed_podcast_issue(issue_id="issue_podcast_ai_daily_a", title="AI 종합 첫 이슈", topic="정치", issue_score=88)
    seed_podcast_issue(issue_id="issue_podcast_ai_daily_b", title="AI 종합 둘째 이슈", topic="경제", issue_score=82)

    from app.services.podcasts.script_ai import OpenAIPodcastScriptGenerator

    def fake_generate_daily_script(self, *, hosts, issue_payloads, sources, validation_feedback=None, variant):
        assert hosts[0]["id"] == "anchor"
        assert len(issue_payloads) == 2
        assert sources
        assert validation_feedback is None
        source_id = sources[0]["id"]
        first_issue_id = issue_payloads[0][0].id
        second_issue_id = issue_payloads[1][0].id
        return {
            "summary": "AI가 오늘 핵심 사건 두 가지를 대화형으로 정리했습니다.",
            "script": [
                {
                    "issueId": first_issue_id,
                    "speakerId": "anchor",
                    "sourceIds": [source_id],
                    "text": "국민의 알 권리를 위해 오늘 핵심 사건을 같이 짚어보겠습니다. 관계 기관에 따르면 첫 이슈는 확인된 자료를 중심으로 봐야 합니다.",
                },
                {
                    "issueId": second_issue_id,
                    "speakerId": "analyst",
                    "sourceIds": [source_id],
                    "text": "네, 관계 기관에 따르면 둘째 이슈도 공식자료와 보도 기준을 함께 확인해야 합니다.",
                },
            ],
        }

    monkeypatch.setattr(OpenAIPodcastScriptGenerator, "generate_daily_script", fake_generate_daily_script)

    db = SessionLocal()
    try:
        enable_test_openai_tts(db)
        db.merge(
            models.SystemSetting(
                description="test podcast script model",
                group="ai",
                is_secret=False,
                key="openai_podcast_script_model",
                label="OpenAI 팟캐스트 대본 모델",
                value="test-script-model",
                value_type="string",
            ),
        )
        db.flush()
        from app.services.podcasts.generator import generate_podcast_episodes

        episode = generate_podcast_episodes(db, feed="daily", limit=2, force=True)[0]
        db.commit()

        assert episode.generation_json["scriptProvider"] == "openai"
        assert episode.generation_json["scriptModel"] == "test-script-model"
        assert episode.generation_json["scriptVersion"].startswith("openai-ai-v1")
        assert episode.summary == "AI가 오늘 핵심 사건 두 가지를 대화형으로 정리했습니다."
        joined_script = " ".join(segment["text"] for segment in episode.script_json)
        assert "관계 기관에 따르면" in joined_script
        assert "오늘은 핵심 사건을 한 번에 듣는 종합 팟캐스트" not in joined_script
    finally:
        db.close()


def test_podcast_home_includes_it_category_section() -> None:
    seed_podcast_issue(
        issue_id="issue_podcast_it",
        title="AI 보안 정책 발표",
        topic="과학기술",
        issue_score=79,
    )

    db = SessionLocal()
    try:
        from app.services.podcasts.generator import generate_podcast_episodes

        generate_podcast_episodes(
            db,
            feed="category",
            issue_id="issue_podcast_it",
            limit=1,
            topic="IT",
        )
        db.commit()
    finally:
        db.close()

    with TestClient(app) as client:
        response = client.get("/v1/podcasts/home")
    assert response.status_code == 200
    sections = {section["id"]: section for section in response.json()["sections"]}
    assert sections["technology"]["episodes"][0]["category"] == "IT"


def test_podcast_variants_can_create_standard_short_and_deep_versions_for_same_issue() -> None:
    seed_podcast_issue(issue_id="issue_podcast_variants", title="변형 회차 생성", topic="사회", issue_score=76)

    db = SessionLocal()
    try:
        from app.services.podcasts.generator import generate_podcast_episodes

        standard = generate_podcast_episodes(
            db,
            episode_format="panel_2",
            feed="recommended",
            issue_id="issue_podcast_variants",
            limit=1,
            variant="standard",
        )
        short = generate_podcast_episodes(
            db,
            episode_format="panel_2",
            feed="recommended",
            issue_id="issue_podcast_variants",
            limit=1,
            variant="short",
        )
        deep = generate_podcast_episodes(
            db,
            episode_format="panel_2",
            feed="recommended",
            issue_id="issue_podcast_variants",
            limit=1,
            variant="deep",
        )
        db.commit()

        assert standard[0].issue_id == short[0].issue_id == deep[0].issue_id == "issue_podcast_variants"
        assert len({standard[0].id, short[0].id, deep[0].id}) == 3
        assert standard[0].episode_format == short[0].episode_format == deep[0].episode_format == "panel_2"
        assert standard[0].variant == "standard"
        assert short[0].variant == "short"
        assert deep[0].variant == "deep"
        assert standard[0].generation_json["variant"] == "standard"
        assert short[0].generation_json["variant"] == "short"
        assert deep[0].generation_json["variant"] == "deep"
        assert short[0].generation_json["notationReview"]["terms"]
        assert short[0].generation_json["correctionPolicy"]["action"] == "monitor"

        duplicate_short = generate_podcast_episodes(
            db,
            episode_format="panel_2",
            feed="recommended",
            issue_id="issue_podcast_variants",
            limit=1,
            variant="short",
        )
        assert duplicate_short[0].id == short[0].id
    finally:
        db.close()


def test_podcast_quality_gate_keeps_source_poor_episode_as_draft() -> None:
    db = SessionLocal()
    try:
        db.add(
            models.Issue(
                id="issue_podcast_no_sources",
                title="출처 부족 팟캐스트",
                topic="정치",
                status="검증 진행",
                risk="일반",
                summary="출처가 없어 공개하면 안 되는 이슈입니다.",
                issue_score=70,
                article_count=0,
                cluster_count=1,
                verified_count=0,
                needs_review_count=1,
                changed_claims=0,
            ),
        )
        db.commit()

        from app.services.podcasts.generator import generate_podcast_episodes

        episodes = generate_podcast_episodes(db, feed="recommended", issue_id="issue_podcast_no_sources", limit=1)
        db.commit()

        assert episodes[0].status == "draft"
        assert episodes[0].auto_published is False
        assert episodes[0].generation_json["publicationGate"]["status"] == "blocked"
        assert "sourceCount" in episodes[0].generation_json["publicationGate"]["missingSignals"]
        episode_id = episodes[0].id
    finally:
        db.close()

    with TestClient(app) as client:
        session = signup(client, email="podcast-draft-admin@example.com")
        response = client.get(
            "/v1/admin/podcasts?status=draft",
            headers={"Authorization": f"Bearer {session['accessToken']}"},
        )

    assert response.status_code == 200
    draft_cards = response.json()["episodes"]
    draft_card = next(card for card in draft_cards if card["id"] == episode_id)
    assert draft_card["status"] == "draft"
    assert draft_card["publicationGateStatus"] == "blocked"
    assert "sourceCount" in draft_card["publicationGateMissingSignals"]
    assert draft_card["publicationGateQualityScore"] < 70
    assert draft_card["ttsStatus"] == "script_ready"


def test_podcast_quality_gate_requires_official_source_for_sensitive_topics() -> None:
    db = SessionLocal()
    try:
        db.add(
            models.Issue(
                id="issue_podcast_sensitive_media_only",
                title="선거 관련 민감 이슈",
                topic="정치",
                status="검증 진행",
                risk="고영향",
                summary="보도 자료만 연결된 민감 이슈입니다.",
                issue_score=86,
                article_count=1,
                cluster_count=2,
                verified_count=1,
                needs_review_count=2,
                changed_claims=0,
                source_documents=[
                    {
                        "id": "media_source_only",
                        "title": "언론 보도",
                        "publisher": "뉴스사",
                        "publishedAt": "2026-06-10T08:30:00+09:00",
                        "url": "https://example.com/media-only",
                        "sourceType": "media",
                        "credibility": 0.72,
                    },
                ],
            ),
        )
        db.commit()

        from app.services.podcasts.generator import generate_podcast_episodes

        episodes = generate_podcast_episodes(
            db,
            feed="recommended",
            issue_id="issue_podcast_sensitive_media_only",
            limit=1,
        )
        db.commit()

        gate = episodes[0].generation_json["publicationGate"]
        assert episodes[0].status == "draft"
        assert gate["sensitiveTopicsRequireOfficialSource"] is True
        assert "officialSource" in gate["missingSignals"]
    finally:
        db.close()


def test_podcast_quality_gate_uses_configured_min_publish_quality_score() -> None:
    seed_podcast_issue(
        issue_id="issue_podcast_quality_threshold",
        issue_score=88,
        title="자료 조작이 분명하다는 주장",
        topic="사회",
    )

    db = SessionLocal()
    try:
        db.merge(
            models.SystemSetting(
                description="test podcast quality threshold",
                group="automation",
                is_secret=False,
                key="podcast_min_publish_quality_score",
                label="팟캐스트 자동발행 최소 품질 점수",
                value=95,
                value_type="integer",
            ),
        )
        db.commit()

        from app.services.podcasts.generator import generate_podcast_episodes

        episodes = generate_podcast_episodes(
            db,
            feed="recommended",
            issue_id="issue_podcast_quality_threshold",
            limit=1,
        )
        db.commit()

        gate = episodes[0].generation_json["publicationGate"]
        assert episodes[0].status == "draft"
        assert gate["minPublishQualityScore"] == 95
        assert gate["qualityScore"] < 95
        assert gate["warnings"] == ["riskyExpression"]
        assert gate["missingSignals"] == []
    finally:
        db.close()


def test_podcast_correction_update_holds_episode_and_queues_follow_up() -> None:
    seed_podcast_issue(
        issue_id="issue_podcast_correction",
        title="공식자료 정정 팟캐스트",
        topic="정치",
        issue_score=88,
    )

    db = SessionLocal()
    try:
        from app.services.podcasts.generator import generate_podcast_episodes

        episodes = generate_podcast_episodes(
            db,
            feed="recommended",
            issue_id="issue_podcast_correction",
            limit=1,
        )
        db.commit()
        episode_id = episodes[0].id
        assert episodes[0].status == "published"

        update_log = issue_jobs.create_update_log(
            db,
            description="공식자료 변경으로 기존 대본의 후속 검토가 필요합니다.",
            issue_id="issue_podcast_correction",
            title="공식자료 정정",
            update_type="official_source",
        )
        db.commit()

        episode = db.get(models.PodcastEpisode, episode_id)
        assert episode is not None
        assert episode.status == "draft"
        assert episode.auto_published is False
        assert episode.generation_json["correctionPolicy"]["action"] == "hold_for_follow_up"
        assert episode.generation_json["correctionPolicy"]["updateLogId"] == update_log.id
        assert episode.generation_json["publicationGate"]["status"] == "blocked"
        assert "correctionReview" in episode.generation_json["publicationGate"]["missingSignals"]

        follow_up_job = db.scalar(
            select(models.JobAttempt).where(
                models.JobAttempt.job_type == "generate_podcasts",
                models.JobAttempt.target_id == "podcast:correction:issue_podcast_correction",
            ),
        )
        assert follow_up_job is not None
        assert follow_up_job.input_json["feed"] == "urgent"
        assert follow_up_job.input_json["issue_id"] == "issue_podcast_correction"
    finally:
        db.close()


def test_generate_podcasts_job_auto_publishes_without_duplicates() -> None:
    seed_podcast_issue(issue_id="issue_podcast_job", title="공공 데이터 정정", topic="사회", issue_score=82)

    db = SessionLocal()
    try:
        from app.services.jobs import enqueue_job, run_due_jobs

        job = enqueue_job(
            db,
            input_json={"feed": "latest", "limit": 1},
            job_type="generate_podcasts",
            run_immediately=False,
            target_id="podcast:auto",
        )
        db.commit()

        run_due_jobs(db)
        db.commit()
        db.refresh(job)

        assert job.status == "completed"
        first_count = len(db.scalars(select(models.PodcastEpisode)).all())

        duplicate_job = enqueue_job(
            db,
            input_json={"feed": "latest", "limit": 1},
            job_type="generate_podcasts",
            run_immediately=False,
            target_id="podcast:auto",
        )
        db.commit()
        run_due_jobs(db)
        db.commit()
        db.refresh(duplicate_job)

        assert duplicate_job.status == "completed"
        assert len(db.scalars(select(models.PodcastEpisode)).all()) == first_count
    finally:
        db.close()


def test_combine_wav_uses_actual_frame_bytes_for_duration() -> None:
    from app.services.podcasts.tts import OpenAITTSEpisodeRenderer

    renderer = OpenAITTSEpisodeRenderer()
    audio_bytes, duration = renderer._combine_wav(
        [
            wav_bytes_with_declared_frame_count(
                declared_frames=1_000_000,
                actual_frames=8_000,
                frame_rate=8_000,
            ),
        ],
    )

    assert duration == 1
    with wave.open(io.BytesIO(audio_bytes), "rb") as audio:
        assert audio.getframerate() == 8_000
        assert audio.getnframes() == 8_000


def test_render_podcast_audio_uses_openai_tts_segments_and_serves_file(monkeypatch) -> None:
    seed_podcast_issue(issue_id="issue_podcast_tts", title="선거 팟캐스트 TTS", topic="정치", issue_score=84)
    calls: list[dict] = []

    def fake_speech_bytes(self, *, input_text: str, instructions: str, voice: str) -> bytes:
        calls.append({"instructions": instructions, "input_text": input_text, "voice": voice})
        return silent_wav_bytes()

    db = SessionLocal()
    try:
        from app.services.podcasts.generator import generate_podcast_episodes
        from app.services.podcasts.tts import OpenAITTSEpisodeRenderer, render_episode_audio

        monkeypatch.setattr(OpenAITTSEpisodeRenderer, "_speech_bytes", fake_speech_bytes)
        enable_test_openai_tts(db)
        episodes = generate_podcast_episodes(db, episode_format="panel_2", feed="recommended", limit=1)
        episode = render_episode_audio(db, episode=episodes[0], force=True)
        db.commit()

        assert len(calls) == len(episode.script_json)
        assert len({call["voice"] for call in calls}) >= 2
        assert calls[0]["input_text"] == episode.script_json[0]["text"]
        assert episode.audio_url.endswith(".wav")
        assert Path(episode.audio_url).exists()
        assert episode.generation_json["ttsStatus"] == "completed"
        assert episode.generation_json["ttsProvider"] == "openai"
        episode_id = episode.id
    finally:
        db.close()

    with TestClient(app) as client:
        response = client.get(f"/v1/podcasts/{episode_id}/audio")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("audio/wav")
    assert response.content.startswith(b"RIFF")


def test_render_podcast_audio_retries_and_records_attempts(monkeypatch) -> None:
    seed_podcast_issue(issue_id="issue_podcast_tts_retry", title="선거 팟캐스트 TTS 재시도", topic="정치", issue_score=84)
    calls = 0

    def flaky_speech_bytes(self, *, input_text: str, instructions: str, voice: str) -> bytes:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("temporary OpenAI TTS outage")
        return silent_wav_bytes()

    db = SessionLocal()
    try:
        from app.services.podcasts.generator import generate_podcast_episodes
        from app.services.podcasts.tts import OpenAITTSEpisodeRenderer, render_episode_audio

        monkeypatch.setattr(OpenAITTSEpisodeRenderer, "_speech_bytes", flaky_speech_bytes)
        enable_test_openai_tts(db)
        episode = generate_podcast_episodes(db, episode_format="panel_2", feed="recommended", limit=1)[0]
        episode = render_episode_audio(db, episode=episode, force=True)
        db.commit()

        attempts = episode.generation_json["ttsAttempts"]
        assert episode.generation_json["ttsStatus"] == "completed"
        assert episode.generation_json["ttsAttemptCount"] == len(attempts)
        assert attempts[0]["status"] == "failed"
        assert attempts[0]["attempt"] == 1
        assert attempts[1]["status"] == "completed"
        assert attempts[1]["attempt"] == 2
    finally:
        db.close()


def test_render_podcast_audio_records_failed_attempts_before_raising(monkeypatch) -> None:
    seed_podcast_issue(issue_id="issue_podcast_tts_failed_attempts", title="선거 팟캐스트 TTS 실패", topic="정치", issue_score=84)

    def failing_speech_bytes(self, *, input_text: str, instructions: str, voice: str) -> bytes:
        raise RuntimeError("invalid_api_key")

    db = SessionLocal()
    try:
        from app.services.podcasts.generator import generate_podcast_episodes
        from app.services.podcasts.tts import OpenAITTSEpisodeRenderer, render_episode_audio

        monkeypatch.setattr(OpenAITTSEpisodeRenderer, "_speech_bytes", failing_speech_bytes)
        enable_test_openai_tts(db)
        episode = generate_podcast_episodes(db, episode_format="panel_2", feed="recommended", limit=1)[0]
        try:
            render_episode_audio(db, episode=episode, force=True)
            raise AssertionError("render_episode_audio should raise after retry exhaustion")
        except RuntimeError as exc:
            assert "invalid_api_key" in str(exc)

        attempts = episode.generation_json["ttsAttempts"]
        assert episode.generation_json["ttsStatus"] == "failed"
        assert "invalid_api_key" in episode.generation_json["ttsError"]
        assert episode.generation_json["ttsAttemptCount"] == 2
        assert [attempt["status"] for attempt in attempts] == ["failed", "failed"]
    finally:
        db.close()


def test_render_podcast_audio_sanitizes_sensitive_tts_errors(monkeypatch) -> None:
    seed_podcast_issue(issue_id="issue_podcast_tts_sanitized", title="TTS 오류 정제", topic="정치", issue_score=84)

    def failing_speech_bytes(self, *, input_text: str, instructions: str, voice: str) -> bytes:
        raise RuntimeError("Incorrect API key provided: sk-proj-secret123456789 invalid_api_key")

    db = SessionLocal()
    try:
        from app.services.podcasts.generator import generate_podcast_episodes
        from app.services.podcasts.tts import OpenAITTSEpisodeRenderer, render_episode_audio

        monkeypatch.setattr(OpenAITTSEpisodeRenderer, "_speech_bytes", failing_speech_bytes)
        enable_test_openai_tts(db)
        episode = generate_podcast_episodes(db, episode_format="panel_2", feed="recommended", limit=1)[0]
        try:
            render_episode_audio(db, episode=episode, force=True)
            raise AssertionError("render_episode_audio should raise after retry exhaustion")
        except RuntimeError:
            pass

        attempts = episode.generation_json["ttsAttempts"]
        assert episode.generation_json["ttsStatus"] == "failed"
        assert "invalid_api_key" in episode.generation_json["ttsError"]
        assert "sk-" not in episode.generation_json["ttsError"]
        assert all("sk-" not in attempt["error"] for attempt in attempts)
    finally:
        db.close()


def test_render_podcast_audio_job_sanitizes_failure_error(monkeypatch) -> None:
    seed_podcast_issue(issue_id="issue_podcast_tts_job_sanitized", title="TTS 작업 오류 정제", topic="정치", issue_score=84)

    def failing_speech_bytes(self, *, input_text: str, instructions: str, voice: str) -> bytes:
        raise RuntimeError("Incorrect API key provided: sk-proj-secret123456789 invalid_api_key")

    db = SessionLocal()
    try:
        from app.services.jobs import enqueue_job
        from app.services.podcasts.generator import generate_podcast_episodes
        from app.services.podcasts.tts import OpenAITTSEpisodeRenderer

        monkeypatch.setattr(OpenAITTSEpisodeRenderer, "_speech_bytes", failing_speech_bytes)
        enable_test_openai_tts(db)
        episode = generate_podcast_episodes(db, episode_format="panel_2", feed="recommended", limit=1)[0]
        job = enqueue_job(
            db,
            input_json={"episode_id": episode.id, "force": True},
            job_type="render_podcast_audio",
            max_attempts=1,
            run_immediately=True,
            target_id=episode.id,
        )
        db.commit()

        assert job.status == "dead_letter"
        assert "invalid_api_key" in job.last_error
        assert "sk-" not in job.last_error
    finally:
        db.close()


def test_seed_script_can_attach_fixture_audio_for_browser_playback() -> None:
    seed_podcast_issue(issue_id="issue_podcast_fixture_audio", title="오디오 재생 QA", topic="사회", issue_score=83)

    db = SessionLocal()
    try:
        from app.services.podcasts.generator import generate_podcast_episodes
        from scripts.seed_podcast_episodes import attach_fixture_audio, mark_seed_script_episode

        episodes = generate_podcast_episodes(
            db,
            feed="recommended",
            issue_id="issue_podcast_fixture_audio",
            limit=1,
        )
        episode = attach_fixture_audio(episodes[0])
        episode = mark_seed_script_episode(
            episode,
            feed="recommended",
            fixture_audio=True,
            render_audio=False,
        )
        db.commit()

        assert episode.audio_url.endswith(".wav")
        assert Path(episode.audio_url).exists()
        assert episode.generation_json["ttsProvider"] == "fixture"
        assert episode.generation_json["ttsStatus"] == "completed"
        assert episode.generation_json["seedScript"] == "scripts/seed_podcast_episodes.py"
        assert episode.generation_json["seedFeed"] == "recommended"
        assert episode.generation_json["seedFixtureAudio"] is True
        episode_id = episode.id
    finally:
        db.close()

    with TestClient(app) as client:
        detail_response = client.get(f"/v1/podcasts/{episode_id}")
        audio_response = client.get(f"/v1/podcasts/{episode_id}/audio")

    assert detail_response.status_code == 200
    assert detail_response.json()["episode"]["audioUrl"] == f"/v1/podcasts/{episode_id}/audio"
    assert audio_response.status_code == 200
    assert audio_response.headers["content-type"].startswith("audio/wav")
    assert audio_response.content.startswith(b"RIFF")


def test_seed_script_commits_tts_failure_evidence(monkeypatch, capsys) -> None:
    import sys

    seed_podcast_issue(issue_id="issue_podcast_seed_tts_failure", title="시드 TTS 실패 증거", topic="경제", issue_score=83)

    def failing_speech_bytes(self, *, input_text: str, instructions: str, voice: str) -> bytes:
        raise RuntimeError("Incorrect API key provided: sk-proj-secret123456789 invalid_api_key")

    db = SessionLocal()
    try:
        enable_test_openai_tts(db)
        db.commit()
    finally:
        db.close()

    from app.services.podcasts.tts import OpenAITTSEpisodeRenderer
    from scripts import seed_podcast_episodes

    monkeypatch.setattr(OpenAITTSEpisodeRenderer, "_speech_bytes", failing_speech_bytes)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "seed_podcast_episodes.py",
            "--feed",
            "recommended",
            "--limit",
            "1",
            "--render-audio",
        ],
    )

    try:
        seed_podcast_episodes.main()
        raise AssertionError("seed script should exit with failure when TTS render fails")
    except SystemExit as exc:
        assert exc.code == 1

    output = capsys.readouterr().out
    assert "invalid_api_key" in output
    assert "sk-" not in output

    db = SessionLocal()
    try:
        episode = db.scalar(
            select(models.PodcastEpisode).where(models.PodcastEpisode.issue_id == "issue_podcast_seed_tts_failure"),
        )
        assert episode is not None
        generation = episode.generation_json
        assert generation["seedScript"] == "scripts/seed_podcast_episodes.py"
        assert generation["seedRenderAudio"] is True
        assert generation["ttsStatus"] == "failed"
        assert generation["ttsAttemptCount"] == 2
        assert "invalid_api_key" in generation["ttsError"]
        assert "sk-" not in generation["ttsError"]
        assert all("sk-" not in attempt["error"] for attempt in generation["ttsAttempts"])
    finally:
        db.close()


def test_podcast_operations_audit_reports_staging_readiness_checks() -> None:
    seed_podcast_issue(issue_id="issue_podcast_audit", title="운영 감사 팟캐스트", topic="경제", issue_score=83)

    db = SessionLocal()
    try:
        from app.services.podcasts.generator import generate_podcast_episodes
        from scripts.audit_podcast_operations import REQUIRED_EVENT_TYPES, audit_database, audit_settings
        from scripts.seed_podcast_episodes import attach_fixture_audio, mark_seed_script_episode

        episode = generate_podcast_episodes(
            db,
            feed="recommended",
            issue_id="issue_podcast_audit",
            limit=1,
        )[0]
        attach_fixture_audio(episode)
        mark_seed_script_episode(
            episode,
            feed="recommended",
            fixture_audio=True,
            render_audio=False,
        )
        episode.generation_json = {
            **episode.generation_json,
            "ttsAttempts": [
                {
                    "attempt": 1,
                    "error": "OpenAI TTS authentication failed: invalid_api_key",
                    "status": "failed",
                },
                {
                    "attempt": 2,
                    "error": "OpenAI TTS authentication failed: invalid_api_key",
                    "status": "failed",
                },
            ],
        }
        db.add(
            models.JobAttempt(
                attempts=1,
                id="job_podcast_audit_failed",
                job_type="render_podcast_audio",
                last_error="invalid_api_key",
                max_attempts=3,
                status="failed",
                target_id=episode.id,
            ),
        )
        db.add(
            models.UserInterestProfile(
                event_group_weights_json={"podcast_format:panel_2": 1.2},
                topic_weights_json={"경제": 1.2},
                user_id="user_podcast_audit",
            ),
        )
        for event_type in REQUIRED_EVENT_TYPES:
            db.add(
                models.ProductMetricEvent(
                    event_type=event_type,
                    id=f"metric_{event_type}",
                    issue_id="issue_podcast_audit",
                    metadata_json={"episodeId": episode.id, "podcastCategory": "경제"},
                    user_id="user_podcast_audit",
                ),
            )
        db.commit()

        checks = [
            *audit_settings(db),
            *audit_database(
                db,
                enqueue_scheduler_check=False,
                require_events=True,
                require_failed_job=True,
                require_live_tts=False,
                require_seed_script=True,
                require_tts_retry_evidence=True,
            ),
        ]
    finally:
        db.close()

    by_name = {item["name"]: item for item in checks}
    assert by_name["podcast_episode_seed"]["status"] == "pass"
    assert by_name["podcast_seed_script_run"]["status"] == "pass"
    assert by_name["podcast_audio_storage_path"]["status"] == "pass"
    assert by_name["podcast_failed_jobs"]["status"] == "pass"
    assert by_name["podcast_metric_events"]["status"] == "pass"
    assert by_name["podcast_interest_profiles"]["status"] == "pass"
    assert by_name["podcast_tts_retry_evidence"]["status"] == "pass"
    assert by_name["podcast_effective_settings"]["status"] == "pass"


def test_podcast_operations_audit_payload_summarizes_pass_fail_warning() -> None:
    from scripts.audit_podcast_operations import build_audit_payload

    payload = build_audit_payload(
        [
            {"details": {}, "message": "ok", "name": "ok_check", "status": "pass"},
            {"details": {}, "message": "missing optional evidence", "name": "warn_check", "status": "warn"},
            {"details": {}, "message": "missing required evidence", "name": "fail_check", "status": "fail"},
        ],
    )

    assert payload["status"] == "failed"
    assert payload["passed"] is False
    assert payload["failedChecks"] == ["fail_check"]
    assert payload["warningChecks"] == ["warn_check"]
    assert payload["summary"] == {
        "failed": 1,
        "passed": 1,
        "total": 3,
        "warnings": 1,
    }


def test_podcast_remaining_work_report_redacts_sensitive_command_values() -> None:
    from scripts.verify_podcast_remaining_work import redact_command

    assert redact_command(
        [
            "python",
            "scripts/run_podcast_operational_smoke.py",
            "--admin-password",
            "secret-admin",
            "--password",
            "secret-user",
            "--api-base-url",
            "https://api.example.com",
        ],
    ) == [
        "python",
        "scripts/run_podcast_operational_smoke.py",
        "--admin-password",
        "<redacted>",
        "--password",
        "<redacted>",
        "--api-base-url",
        "https://api.example.com",
    ]


def test_podcast_remaining_work_report_maps_doc_checkboxes() -> None:
    from scripts.audit_podcast_operations import REQUIRED_EVENT_TYPES
    from scripts.verify_podcast_remaining_work import build_remaining_work_report

    smoke_payload = {
        "database": [
            {
                "audioUrl": "storage/podcasts/podcast_live.wav",
                "id": "podcast_live",
                "ttsProvider": "openai",
                "ttsStatus": "completed",
            },
            {
                "id": "job_failed",
                "type": "admin_failed_job",
            },
        ],
        "publicApi": {
            "adminFailedJobs": {
                "count": 1,
                "jobs": [
                    {
                        "jobType": "render_podcast_audio",
                        "status": "dead_letter",
                        "userMessage": "팟캐스트 음성 렌더링 작업이 실패했습니다.",
                    },
                ],
                "status": 200,
            },
            "eventPersistence": {
                "eventCounts": {event_type: 1 for event_type in REQUIRED_EVENT_TYPES},
                "missingEventTypes": [],
                "profile": {
                    "eventGroupWeights": {"podcast_format:solo": 1.0},
                    "topicWeights": {"경제": 1.0},
                },
            },
        },
    }
    audit_payload = {
        "checks": [
            {"details": {}, "message": "ok", "name": "podcast_live_tts_audio", "status": "pass"},
            {"details": {}, "message": "ok", "name": "podcast_live_tts_delivery", "status": "pass"},
            {"details": {}, "message": "ok", "name": "podcast_metric_events", "status": "pass"},
            {"details": {}, "message": "ok", "name": "podcast_interest_profiles", "status": "pass"},
            {"details": {}, "message": "ok", "name": "podcast_failed_jobs", "status": "pass"},
        ],
        "failedChecks": [],
        "passed": True,
        "status": "passed",
    }

    report = build_remaining_work_report(
        smoke_result={"exitCode": 0, "json": smoke_payload},
        audit_result={"exitCode": 0, "json": audit_payload},
    )

    assert report["passed"] is True
    assert report["summary"] == {"failed": 0, "passed": 5, "total": 5}
    assert {item["id"]: item["passed"] for item in report["items"]} == {
        "admin_failed_job_display_data": True,
        "live_tts_audio": True,
        "live_tts_delivery": True,
        "recommendation_events_profile": True,
        "staging_smoke_and_audit": True,
    }


def test_podcast_operations_audit_checks_chrome_and_safari_audio_streams(monkeypatch) -> None:
    from scripts import audit_podcast_operations as audit

    def fake_http_json(url: str, *, timeout: int):
        if url.endswith("/health"):
            return 200, {"status": "ok"}
        if url.endswith("/v1/podcasts/home"):
            return 200, {"sections": []}
        if url.endswith("/v1/podcasts?feed=latest&limit=20"):
            return 200, {"episodes": [{"audioUrl": "/v1/podcasts/podcast_audio/audio"}]}
        raise AssertionError(f"unexpected JSON URL: {url}")

    requested_user_agents: list[str] = []

    def fake_http_bytes(
        url: str,
        *,
        headers: dict[str, str] | None = None,
        timeout: int,
        limit: int = 256_000,
    ):
        if url.endswith("/metrics"):
            return (
                200,
                "text/plain",
                b"facttracer_podcast_draft_episodes 0\n"
                b"facttracer_podcast_jobs_failed 0\n"
                b"facttracer_podcast_tts_pending 0\n",
            )
        requested_user_agents.append((headers or {}).get("User-Agent", ""))
        return 200, "audio/wav", b"RIFF"

    monkeypatch.setattr(audit, "http_json", fake_http_json)
    monkeypatch.setattr(audit, "http_bytes", fake_http_bytes)

    checks = audit.audit_public_api(
        "https://api.example.com",
        require_audio_stream=True,
        timeout=3,
    )

    by_name = {item["name"]: item for item in checks}
    assert by_name["podcast_api_audio_stream"]["status"] == "pass"
    assert by_name["podcast_api_browser_audio_streams"]["status"] == "pass"
    assert {item["browser"] for item in by_name["podcast_api_browser_audio_streams"]["details"]["results"]} == {
        "chrome",
        "safari",
    }
    assert any("Chrome/" in user_agent for user_agent in requested_user_agents)
    assert any("Safari/" in user_agent for user_agent in requested_user_agents)


def test_podcast_operations_audit_resolves_audio_url_from_detail(monkeypatch) -> None:
    from scripts import audit_podcast_operations as audit

    requested_json_urls: list[str] = []

    def fake_http_json(url: str, *, timeout: int):
        requested_json_urls.append(url)
        if url.endswith("/health"):
            return 200, {"status": "ok"}
        if url.endswith("/v1/podcasts/home"):
            return 200, {"sections": []}
        if url.endswith("/v1/podcasts?feed=latest&limit=20"):
            return 200, {"episodes": [{"id": "podcast_without_audio"}, {"id": "podcast_detail_audio"}]}
        if url.endswith("/v1/podcasts/podcast_without_audio"):
            return 200, {"episode": {"audioUrl": None}}
        if url.endswith("/v1/podcasts/podcast_detail_audio"):
            return 200, {"episode": {"audioUrl": "/v1/podcasts/podcast_detail_audio/audio"}}
        raise AssertionError(f"unexpected JSON URL: {url}")

    def fake_http_bytes(
        url: str,
        *,
        headers: dict[str, str] | None = None,
        timeout: int,
        limit: int = 256_000,
    ):
        if url.endswith("/metrics"):
            return (
                200,
                "text/plain",
                b"facttracer_podcast_draft_episodes 0\n"
                b"facttracer_podcast_jobs_failed 0\n"
                b"facttracer_podcast_tts_pending 0\n",
            )
        return 200, "audio/wav", b"RIFF"

    monkeypatch.setattr(audit, "http_json", fake_http_json)
    monkeypatch.setattr(audit, "http_bytes", fake_http_bytes)

    checks = audit.audit_public_api(
        "https://api.example.com",
        require_audio_stream=True,
        timeout=3,
    )

    by_name = {item["name"]: item for item in checks}
    assert by_name["podcast_api_audio_stream"]["status"] == "pass"
    assert by_name["podcast_api_audio_stream"]["details"]["episodeId"] == "podcast_detail_audio"
    assert by_name["podcast_api_browser_audio_streams"]["status"] == "pass"
    assert any(url.endswith("/v1/podcasts/podcast_without_audio") for url in requested_json_urls)
    assert any(url.endswith("/v1/podcasts/podcast_detail_audio") for url in requested_json_urls)


def test_podcast_operations_audit_checks_live_tts_delivery_same_episode(monkeypatch) -> None:
    seed_podcast_issue(issue_id="issue_podcast_live_delivery", title="라이브 TTS 전달 검증", topic="경제", issue_score=83)

    db = SessionLocal()
    try:
        from app.services.podcasts.generator import generate_podcast_episodes
        from scripts import audit_podcast_operations as audit
        from scripts.seed_podcast_episodes import attach_fixture_audio

        episode = generate_podcast_episodes(
            db,
            feed="recommended",
            issue_id="issue_podcast_live_delivery",
            limit=1,
        )[0]
        attach_fixture_audio(episode)
        episode.generation_json = {
            **episode.generation_json,
            "audioStoragePath": episode.audio_url,
            "ttsProvider": "openai",
            "ttsStatus": "completed",
        }
        db.commit()
        episode_id = episode.id

        def fake_http_json(url: str, *, timeout: int):
            if url.endswith(f"/v1/podcasts/{episode_id}"):
                return 200, {"episode": {"audioUrl": f"/v1/podcasts/{episode_id}/audio"}}
            raise AssertionError(f"unexpected JSON URL: {url}")

        def fake_http_bytes(
            url: str,
            *,
            headers: dict[str, str] | None = None,
            timeout: int,
            limit: int = 256_000,
        ):
            assert url.endswith(f"/v1/podcasts/{episode_id}/audio")
            return 200, "audio/wav", b"RIFF"

        monkeypatch.setattr(audit, "http_json", fake_http_json)
        monkeypatch.setattr(audit, "http_bytes", fake_http_bytes)

        checks = audit.audit_live_tts_delivery(
            db,
            "https://api.example.com",
            require_live_tts=True,
            timeout=3,
        )
    finally:
        db.close()

    assert checks[0]["status"] == "pass"
    assert checks[0]["name"] == "podcast_live_tts_delivery"
    delivery = checks[0]["details"]["deliveries"][0]
    assert delivery["episodeId"] == episode_id
    assert delivery["localStorageOk"] is True
    assert delivery["publicUrlMatches"] is True
    assert delivery["streamable"] is True


def test_podcast_operational_smoke_can_seed_fixture_audio() -> None:
    seed_podcast_issue(issue_id="issue_podcast_smoke_seed", title="운영 스모크 팟캐스트", topic="경제", issue_score=83)

    from argparse import Namespace
    from scripts.run_podcast_operational_smoke import generate_smoke_episodes

    results = generate_smoke_episodes(
        Namespace(
            enqueue_scheduler_check=False,
            feed=["recommended"],
            fixture_audio=True,
            force=False,
            format=None,
            limit=1,
            render_audio=False,
            topic=None,
            variant="short",
        ),
    )

    assert len(results) == 1
    assert results[0]["audioUrl"].endswith(".wav")
    assert results[0]["ttsProvider"] == "fixture"
    assert results[0]["ttsStatus"] == "completed"
    assert Path(results[0]["audioUrl"]).exists()


def test_podcast_operational_smoke_can_create_failed_admin_job_evidence() -> None:
    seed_podcast_issue(issue_id="issue_podcast_smoke_failed_job", title="운영 실패 작업 증거", topic="경제", issue_score=83)

    from argparse import Namespace
    from scripts.run_podcast_operational_smoke import generate_smoke_episodes

    results = generate_smoke_episodes(
        Namespace(
            create_admin_failed_job=True,
            enqueue_scheduler_check=False,
            feed=["recommended"],
            fixture_audio=True,
            force=False,
            format=None,
            limit=1,
            render_audio=False,
            topic=None,
            variant="short",
        ),
    )

    failed_job = next(item for item in results if item.get("type") == "admin_failed_job")
    assert failed_job["jobType"] == "render_podcast_audio"
    assert failed_job["status"] == "dead_letter"
    assert failed_job["attempts"] == 1
    assert failed_job["lastError"] == "podcast episode not found"

    db = SessionLocal()
    try:
        saved = db.get(models.JobAttempt, failed_job["id"])
        assert saved is not None
        assert saved.status == "dead_letter"
        assert saved.last_error == "podcast episode not found"
    finally:
        db.close()


def test_podcast_operational_smoke_sanitizes_render_errors(monkeypatch) -> None:
    seed_podcast_issue(issue_id="issue_podcast_smoke_tts_error", title="스모크 TTS 오류", topic="경제", issue_score=83)

    def failing_speech_bytes(self, *, input_text: str, instructions: str, voice: str) -> bytes:
        raise RuntimeError("Incorrect API key provided: sk-proj-secret123456789 invalid_api_key")

    db = SessionLocal()
    try:
        enable_test_openai_tts(db)
        db.commit()
    finally:
        db.close()

    from argparse import Namespace
    from app.services.podcasts.tts import OpenAITTSEpisodeRenderer
    from scripts.run_podcast_operational_smoke import generate_smoke_episodes

    monkeypatch.setattr(OpenAITTSEpisodeRenderer, "_speech_bytes", failing_speech_bytes)
    results = generate_smoke_episodes(
        Namespace(
            enqueue_scheduler_check=False,
            feed=["recommended"],
            fixture_audio=False,
            force=False,
            format=None,
            limit=1,
            render_audio=True,
            topic=None,
            variant="short",
        ),
    )

    assert results[0]["renderError"] == "OpenAI TTS authentication failed: invalid_api_key"
    assert "sk-" not in results[0]["renderError"]


def test_podcast_operational_smoke_checks_generated_episode_audio(monkeypatch) -> None:
    from argparse import Namespace
    from scripts import run_podcast_operational_smoke as smoke

    requested_urls: list[str] = []

    def fake_http_json(method: str, url: str, **_: object):
        requested_urls.append(url)
        if url.endswith("/v1/podcasts/home"):
            return 200, {
                "sections": [
                    {
                        "episodes": [
                            {"id": "podcast_home", "issueId": "issue_home"},
                        ],
                    },
                ],
            }
        if url.endswith("/v1/podcasts/podcast_generated"):
            return 200, {
                "episode": {
                    "audioUrl": "/v1/podcasts/podcast_generated/audio",
                    "category": "경제",
                    "format": "panel_2",
                    "id": "podcast_generated",
                    "issueId": "issue_generated",
                    "sources": [],
                },
            }
        raise AssertionError(f"unexpected URL: {method} {url}")

    def fake_http_bytes(url: str, **_: object):
        assert url.endswith("/v1/podcasts/podcast_generated/audio")
        return 200, "audio/wav", b"RIFF"

    monkeypatch.setattr(smoke, "http_json", fake_http_json)
    monkeypatch.setattr(smoke, "http_bytes", fake_http_bytes)

    result = smoke.exercise_public_api(
        Namespace(
            api_base_url="https://api.example.com",
            check_admin_failed_jobs=False,
            check_audio_stream=True,
            record_events=False,
            timeout=3,
        ),
        [{"id": "podcast_generated"}],
    )

    assert result["episodeId"] == "podcast_generated"
    assert result["episodeSource"] == "generated"
    assert result["audioStream"]["status"] == 200
    assert any(url.endswith("/v1/podcasts/podcast_generated") for url in requested_urls)
    assert not any(url.endswith("/v1/podcasts/podcast_home") for url in requested_urls)


def test_podcast_operational_smoke_reports_generated_episode_api_mismatch(monkeypatch) -> None:
    from argparse import Namespace
    from scripts import run_podcast_operational_smoke as smoke

    def fake_http_json(method: str, url: str, **_: object):
        if url.endswith("/v1/podcasts/home"):
            return 200, {
                "sections": [
                    {
                        "episodes": [
                            {"id": "podcast_home", "issueId": "issue_home"},
                        ],
                    },
                ],
            }
        if url.endswith("/v1/podcasts/podcast_generated"):
            return 404, {"message": "not found"}
        raise AssertionError(f"unexpected URL: {method} {url}")

    monkeypatch.setattr(smoke, "http_json", fake_http_json)

    result = smoke.exercise_public_api(
        Namespace(
            api_base_url="https://api.example.com",
            check_admin_failed_jobs=False,
            check_audio_stream=True,
            record_events=False,
            timeout=3,
        ),
        [{"id": "podcast_generated"}],
    )

    assert result["episodeId"] == "podcast_generated"
    assert result["episodeSource"] == "generated"
    assert result["detailStatus"] == 404
    assert "DB/API target mismatch" in result["error"]


def test_podcast_operational_smoke_failure_gate_requires_operational_evidence() -> None:
    from argparse import Namespace
    from scripts.run_podcast_operational_smoke import public_api_has_failure

    args = Namespace(
        check_admin_failed_jobs=True,
        check_audio_stream=True,
        record_events=True,
    )
    base_result = {
        "adminFailedJobs": {"count": 1, "status": 200},
        "audioStream": {"bytesRead": 4, "contentType": "audio/wav", "status": 200},
        "eventPersistence": {
            "missingEventTypes": [],
            "profile": {
                "eventGroupWeights": {"podcast_format:panel_2": 1.0},
                "topicWeights": {"경제": 1.0},
            },
        },
        "eventResults": [
            {"eventType": event_type, "status": 201}
            for event_type in [
                "podcast_home_impression",
                "podcast_play_start",
                "podcast_progress",
                "podcast_complete",
                "podcast_skip",
                "podcast_source_click",
            ]
        ],
    }

    assert public_api_has_failure(base_result, args) is False

    missing_profile = {
        **base_result,
        "eventPersistence": {"missingEventTypes": [], "profile": None},
    }
    assert public_api_has_failure(missing_profile, args) is True

    failed_stream = {
        **base_result,
        "audioStream": {"bytesRead": 0, "contentType": "application/json", "status": 404},
    }
    assert public_api_has_failure(failed_stream, args) is True

    no_failed_jobs = {
        **base_result,
        "adminFailedJobs": {"count": 0, "status": 200},
    }
    assert public_api_has_failure(no_failed_jobs, args) is True


def test_podcast_operational_smoke_event_payloads_include_personalization_metadata() -> None:
    from scripts.audit_podcast_operations import REQUIRED_EVENT_TYPES
    from scripts.run_podcast_operational_smoke import podcast_event_payloads

    payloads = podcast_event_payloads(
        {
            "category": "경제",
            "format": "panel_2",
            "id": "podcast_smoke_event",
            "issueId": "issue_podcast_smoke_event",
        },
        {
            "sources": [
                {
                    "id": "source_smoke",
                    "sourceType": "official",
                },
            ],
        },
    )

    assert {payload["eventType"] for payload in payloads} == set(REQUIRED_EVENT_TYPES)
    for payload in payloads:
        assert payload["metadata"]["episodeId"] == "podcast_smoke_event"
        assert payload["metadata"]["podcastCategory"] == "경제"
        assert payload["metadata"]["podcastFormat"] == "panel_2"
    source_click = next(payload for payload in payloads if payload["eventType"] == "podcast_source_click")
    assert source_click["metadata"]["sourceId"] == "source_smoke"
    assert source_click["metadata"]["sourceType"] == "official"


def test_podcast_operational_smoke_reports_event_persistence() -> None:
    from scripts.audit_podcast_operations import REQUIRED_EVENT_TYPES
    from scripts.run_podcast_operational_smoke import smoke_event_persistence_evidence

    db = SessionLocal()
    try:
        user = models.User(
            email="podcast-smoke-persistence@example.com",
            id="user_podcast_smoke_persistence",
            name="Podcast Smoke",
            password_hash="hashed",
            role="user",
        )
        db.add(user)
        db.add(
            models.UserInterestProfile(
                event_group_weights_json={"podcast_format:panel_2": 4.8},
                topic_weights_json={"경제": 4.8},
                user_id=user.id,
            ),
        )
        for event_type in REQUIRED_EVENT_TYPES:
            db.add(
                models.ProductMetricEvent(
                    event_type=event_type,
                    id=f"metric_smoke_{event_type}",
                    issue_id="issue_podcast_smoke_persistence",
                    metadata_json={
                        "episodeId": "podcast_smoke_persistence",
                        "surface": "podcast_operational_smoke",
                    },
                    user_id=user.id,
                ),
            )
        db.commit()
    finally:
        db.close()

    evidence = smoke_event_persistence_evidence("podcast-smoke-persistence@example.com")

    assert evidence["missingEventTypes"] == []
    assert set(evidence["eventCounts"]) == set(REQUIRED_EVENT_TYPES)
    assert all(count == 1 for count in evidence["eventCounts"].values())
    assert evidence["profile"]["topicWeights"]["경제"] == 4.8
    assert evidence["profile"]["eventGroupWeights"]["podcast_format:panel_2"] == 4.8


def test_podcast_operational_smoke_filters_admin_failed_podcast_jobs() -> None:
    from scripts.run_podcast_operational_smoke import failed_podcast_jobs_from_admin_payload

    failed = failed_podcast_jobs_from_admin_payload(
        {
            "jobs": [
                {
                    "id": "job_1",
                    "jobType": "render_podcast_audio",
                    "status": "failed",
                    "userMessage": "OpenAI TTS 연결 키 또는 모델 설정을 확인해야 합니다.",
                },
                {
                    "id": "job_2",
                    "jobType": "generate_podcasts",
                    "status": "dead_letter",
                    "userMessage": "팟캐스트 생성 작업을 재시도해야 합니다.",
                },
                {
                    "id": "job_3",
                    "jobType": "generate_podcasts",
                    "status": "completed",
                },
                {
                    "id": "job_4",
                    "jobType": "parse_article",
                    "status": "failed",
                },
            ],
        },
    )

    assert [job["id"] for job in failed] == ["job_1", "job_2"]
    assert all(job["userMessage"] for job in failed)


def test_podcast_tts_applies_pronunciation_lexicon(monkeypatch) -> None:
    seed_podcast_issue(issue_id="issue_podcast_pronunciation", title="AI 보안 TTS 발표", topic="IT", issue_score=82)
    calls: list[str] = []

    def fake_speech_bytes(self, *, input_text: str, instructions: str, voice: str) -> bytes:
        calls.append(input_text)
        return silent_wav_bytes()

    db = SessionLocal()
    try:
        from app.services.podcasts.generator import generate_podcast_episodes
        from app.services.podcasts.tts import OpenAITTSEpisodeRenderer, render_episode_audio

        monkeypatch.setattr(OpenAITTSEpisodeRenderer, "_speech_bytes", fake_speech_bytes)
        enable_test_openai_tts(db)
        db.merge(
            models.SystemSetting(
                description="test pronunciation lexicon",
                group="automation",
                is_secret=False,
                key="podcast_tts_pronunciation_lexicon",
                label="팟캐스트 TTS 발음 사전",
                value="AI=에이아이\nTTS=티티에스",
                value_type="string",
            ),
        )
        episodes = generate_podcast_episodes(
            db,
            episode_format="panel_2",
            feed="recommended",
            issue_id="issue_podcast_pronunciation",
            limit=1,
        )
        episode = render_episode_audio(db, episode=episodes[0], force=True)
        db.commit()

        joined = " ".join(calls)
        assert "에이아이" in joined
        assert "티티에스" in joined
        assert "AI 보안 TTS" not in joined
        assert episode.generation_json["ttsPronunciationTerms"] == ["AI", "TTS"]
    finally:
        db.close()


def test_generate_podcasts_job_renders_openai_tts_when_requested(monkeypatch) -> None:
    seed_podcast_issue(issue_id="issue_podcast_tts_job", title="경제 팟캐스트 TTS", topic="경제", issue_score=81)

    def fake_speech_bytes(self, *, input_text: str, instructions: str, voice: str) -> bytes:
        return silent_wav_bytes()

    db = SessionLocal()
    try:
        from app.services.jobs import enqueue_job, run_due_jobs
        from app.services.podcasts.tts import OpenAITTSEpisodeRenderer

        monkeypatch.setattr(OpenAITTSEpisodeRenderer, "_speech_bytes", fake_speech_bytes)
        enable_test_openai_tts(db)
        job = enqueue_job(
            db,
            input_json={"feed": "recommended", "limit": 1, "render_audio": True},
            job_type="generate_podcasts",
            run_immediately=False,
            target_id="podcast:auto",
        )
        db.commit()

        run_due_jobs(db)
        db.commit()
        db.refresh(job)

        episode = db.scalar(select(models.PodcastEpisode))
        assert job.status == "completed"
        assert episode is not None
        assert episode.audio_url
        assert episode.generation_json["ttsStatus"] == "completed"
        assert job.output_json["rendered_audio_count"] == 1
    finally:
        db.close()


def test_podcast_home_preserves_editorial_sections_after_personalized() -> None:
    seed_podcast_issue(issue_id="issue_podcast_home_daily_a", title="데일리 홈 첫 이슈", topic="정치", issue_score=88)
    seed_podcast_issue(issue_id="issue_podcast_home_daily_b", title="데일리 홈 둘째 이슈", topic="경제", issue_score=84)
    seed_podcast_issue(
        issue_id="issue_podcast_home_urgent",
        title="긴급 후속 검증 이슈",
        topic="재난",
        changed_claims=1,
        issue_score=86,
        needs_review_count=7,
    )
    seed_podcast_issue(
        issue_id="issue_podcast_home_featured",
        title="특집으로 다룰 큰 이슈",
        topic="사회",
        issue_score=93,
    )

    db = SessionLocal()
    try:
        from app.services.podcasts.generator import generate_podcast_episodes

        generate_podcast_episodes(db, feed="daily", limit=2)
        generate_podcast_episodes(db, feed="urgent", issue_id="issue_podcast_home_urgent", limit=1)
        generate_podcast_episodes(db, feed="featured", issue_id="issue_podcast_home_featured", limit=1)
        db.commit()
    finally:
        db.close()

    with TestClient(app) as client:
        session = signup(client, email="podcast-home-sections@example.com")
        response = client.get(
            "/v1/podcasts/home",
            headers={"Authorization": f"Bearer {session['accessToken']}"},
        )

    assert response.status_code == 200
    section_ids = [section["id"] for section in response.json()["sections"]]
    assert section_ids[:4] == ["personalized", "daily", "featured", "urgent"]
    sections = {section["id"]: section for section in response.json()["sections"]}
    assert sections["daily"]["episodes"]
    assert sections["featured"]["episodes"]
    assert sections["urgent"]["episodes"]


def test_podcast_content_samples_match_editorial_operating_rules() -> None:
    sample_specs = [
        ("issue_podcast_sample_politics", "정치 샘플 회차", "정치", 86),
        ("issue_podcast_sample_economy", "경제 샘플 회차", "경제", 84),
        ("issue_podcast_sample_disaster", "재난 샘플 회차", "재난", 82),
        ("issue_podcast_sample_it", "IT 샘플 회차", "IT", 80),
    ]
    for issue_id, title, topic, score in sample_specs:
        seed_podcast_issue(issue_id=issue_id, title=title, topic=topic, issue_score=score)
    for index in range(6):
        seed_podcast_issue(
            issue_id=f"issue_podcast_sample_daily_{index}",
            title=f"데일리 샘플 이슈 {index + 1}",
            topic="사회",
            issue_score=75 + index,
        )
    seed_podcast_issue(
        issue_id="issue_podcast_sample_urgent",
        title="긴급 정정 샘플 이슈",
        topic="재난",
        changed_claims=2,
        issue_score=82,
        needs_review_count=8,
    )
    seed_podcast_issue(
        issue_id="issue_podcast_sample_regular",
        title="일반 고점수 샘플 이슈",
        topic="사회",
        changed_claims=0,
        issue_score=95,
        needs_review_count=1,
    )

    db = SessionLocal()
    try:
        from app.services.podcasts.generator import generate_podcast_episodes

        category_episodes = [
            generate_podcast_episodes(
                db,
                feed="category",
                issue_id=issue_id,
                limit=1,
                topic=topic,
            )[0]
            for issue_id, _, topic, _ in sample_specs
        ]
        daily = generate_podcast_episodes(db, feed="daily", limit=6)[0]
        urgent = generate_podcast_episodes(db, feed="urgent", limit=2)
        db.commit()

        category_tones = {
            episode.category: tuple(host["tone"] for host in episode.host_profiles_json)
            for episode in category_episodes
        }
        assert len(set(category_tones.values())) == len(category_tones)
        assert "공식 기록" in category_tones["정치"][0]
        assert "숫자" in category_tones["경제"][0]
        assert "안전" in category_tones["재난"][0]
        assert "기술" in category_tones["IT"][0]

        assert daily.generation_json["maxScriptIssues"] == 4
        assert daily.generation_json["scriptIssueCount"] == 4
        numbered_daily_segments = [
            segment
            for segment in daily.script_json
            if "번째 이슈" in str(segment.get("text") or "")
        ]
        assert len(numbered_daily_segments) == 4

        assert urgent[0].issue_id == "issue_podcast_sample_urgent"
        assert urgent[0].episode_type == "urgent"
        assert urgent[0].generation_json["correctionPolicy"]["action"] == "prioritize_follow_up"

        reviewed_episodes = [*category_episodes, daily, urgent[0]]
        assert all("국민의 알 권리" in episode.script_json[0]["text"] for episode in reviewed_episodes)
        assert all(episode.source_json for episode in reviewed_episodes)
    finally:
        db.close()


def test_representative_image_selector_prefers_relevant_official_image(monkeypatch) -> None:
    from app.services.images.selector import select_representative_image

    db = SessionLocal()
    try:
        issue = models.Issue(
            id="issue_image_selection",
            title="선관위 투표용지 부족 사태",
            topic="정치",
            summary="공식자료와 보도 이미지를 비교합니다.",
        )
        official = models.ImageCandidate(
            id="image_official",
            issue_id=issue.id,
            url="https://nec.go.kr/briefing.jpg",
            source_url="https://nec.go.kr/briefing",
            publisher="중앙선관위",
            source_type="official",
            width=1200,
            height=630,
            status="candidate",
        )
        logo = models.ImageCandidate(
            id="image_logo",
            issue_id=issue.id,
            url="https://example.com/logo.png",
            source_url="https://example.com/article",
            publisher="예시뉴스",
            source_type="news",
            width=120,
            height=60,
            status="candidate",
        )
        db.add_all([issue, official, logo])
        db.commit()

        selected = select_representative_image(db, issue_id=issue.id)
        db.commit()

        assert selected is not None
        assert selected.id == "image_official"
        assert issue.representative_image_url == "https://nec.go.kr/briefing.jpg"
        assert issue.representative_image_source == "중앙선관위"
        assert issue.representative_image_confidence > 0.7
    finally:
        db.close()


def test_representative_image_selector_clears_stale_image_when_candidates_rejected() -> None:
    from app.services.images.selector import select_representative_image

    old_timestamp = datetime(2026, 1, 1, tzinfo=UTC)
    db = SessionLocal()
    try:
        issue = models.Issue(
            id="issue_image_selection_clears_stale",
            title="선관위 투표용지 부족 사태",
            topic="정치",
            summary="기존 대표 이미지가 더 이상 적합하지 않습니다.",
            representative_image_url="https://example.com/old-selected.jpg",
            representative_image_source="예시뉴스",
            representative_image_source_url="https://example.com/old",
            representative_image_confidence=0.82,
            representative_image_updated_at=old_timestamp,
        )
        rejected = models.ImageCandidate(
            id="image_stale_logo",
            issue_id=issue.id,
            url="https://example.com/logo.png",
            source_url="https://example.com/article",
            publisher="예시뉴스",
            source_type="news",
            width=120,
            height=60,
            status="selected",
            confidence=0.82,
        )
        db.add_all([issue, rejected])
        db.commit()

        selected = select_representative_image(db, issue_id=issue.id)
        db.commit()

        assert selected is None
        assert rejected.status == "rejected"
        assert issue.representative_image_url == ""
        assert issue.representative_image_source == ""
        assert issue.representative_image_source_url == ""
        assert math.isclose(issue.representative_image_confidence, 0.0)
        assert issue.representative_image_updated_at is not None
        assert issue.representative_image_updated_at != old_timestamp
    finally:
        db.close()


def test_set_manual_representative_image_updates_issue_and_candidate() -> None:
    from app.services.admin.issue_operations import set_manual_representative_image

    db = SessionLocal()
    try:
        issue = models.Issue(
            id="issue_manual_image",
            title="선관위 투표용지 부족 사태",
            topic="정치",
            summary="관리자가 대표 이미지를 직접 지정합니다.",
        )
        db.add(issue)
        db.commit()

        candidate = set_manual_representative_image(
            db,
            issue_id=issue.id,
            source="한겨레",
            source_url="https://www.hani.co.kr/news/article.html",
            url="https://img.hani.co.kr/article.jpg",
        )
        db.commit()

        assert candidate.issue_id == issue.id
        assert candidate.status == "selected"
        assert candidate.source_type == "manual"
        assert math.isclose(candidate.confidence, 1.0)
        assert issue.representative_image_url == "https://img.hani.co.kr/article.jpg"
        assert issue.representative_image_source == "한겨레"
        assert issue.representative_image_source_url == "https://www.hani.co.kr/news/article.html"
        assert math.isclose(issue.representative_image_confidence, 1.0)
        assert issue.representative_image_updated_at is not None
    finally:
        db.close()


def test_html_parser_extracts_open_graph_images() -> None:
    from app.services.images.candidates import extract_image_urls_from_html

    html = '''
    <html><head>
      <meta property="og:image" content="https://example.com/og.jpg">
      <meta property="og:image:secure_url" content="/secure-og.jpg">
      <meta name="twitter:image" content="https://example.com/twitter.jpg">
      <meta name="twitter:image:src" content="https://example.com/twitter-src.jpg">
      <link rel="image_src" href="/legacy-image.jpg">
      <script type="application/ld+json">
        {"@type":"NewsArticle","url":"https://example.com/article","image":{"url":"/jsonld.jpg"}}
      </script>
    </head></html>
    '''
    assert extract_image_urls_from_html(html, base_url="https://example.com/news/story") == [
        "https://example.com/og.jpg",
        "https://example.com/secure-og.jpg",
        "https://example.com/twitter.jpg",
        "https://example.com/twitter-src.jpg",
        "https://example.com/legacy-image.jpg",
        "https://example.com/jsonld.jpg",
    ]


def test_image_candidates_link_and_select_after_delayed_issue_assignment() -> None:
    from app.services.images.selector import select_representative_image
    from app.workers.issue_jobs import link_article_image_candidates_to_issue, upsert_collected_article_record

    db = SessionLocal()
    try:
        issue = models.Issue(
            id="issue_delayed_image_link",
            title="선관위 투표용지 부족 사태",
            topic="정치",
            summary="선관위 공식 이미지를 대표 이미지로 선택해야 합니다.",
        )
        db.add(issue)
        db.commit()

        article, _ = upsert_collected_article_record(
            db,
            collected=CollectedArticle(
                body_text="선관위 투표용지 부족 사태 설명자료입니다.",
                image_url="https://nec.go.kr/briefing-delayed.jpg",
                publisher="중앙선관위",
                source_type="official",
                summary="공식 설명자료",
                title="선관위 투표용지 부족 사태 공식 설명",
                url="https://nec.go.kr/briefing-delayed",
            ),
        )
        candidate = db.scalar(
            select(models.ImageCandidate).where(
                models.ImageCandidate.url == "https://nec.go.kr/briefing-delayed.jpg",
            ),
        )
        assert candidate is not None
        assert candidate.issue_id is None

        article.issue_id = issue.id
        linked = link_article_image_candidates_to_issue(db, article=article, issue_id=issue.id)
        selected = select_representative_image(db, issue_id=issue.id)
        db.commit()

        assert linked == [candidate]
        assert candidate.issue_id == issue.id
        assert selected is not None
        assert selected.id == candidate.id
        assert issue.representative_image_url == "https://nec.go.kr/briefing-delayed.jpg"
    finally:
        db.close()


def test_official_source_collection_preserves_parser_image_candidates(monkeypatch) -> None:
    from app.collectors import official_sources
    from app.services.articles.parser import ParsedArticle

    parsed = ParsedArticle(
        body_text="공식 설명자료 본문",
        image_candidates=[
            "https://nec.go.kr/official-og.jpg",
            "https://nec.go.kr/official-twitter.jpg",
        ],
        parse_status="parsed",
        published_at=None,
        publisher="nec.go.kr",
        summary="공식 설명자료 요약",
        title="선관위 공식 설명자료",
    )
    monkeypatch.setattr(official_sources, "fetch_and_parse_url", lambda url: parsed)

    collected = official_sources.collect_official_source("https://nec.go.kr/briefing", publisher="중앙선관위")

    assert collected[0].image_url == "https://nec.go.kr/official-og.jpg"
    assert collected[0].image_candidates == [
        "https://nec.go.kr/official-og.jpg",
        "https://nec.go.kr/official-twitter.jpg",
    ]


def test_upsert_article_persists_parsed_image_candidates_for_issue() -> None:
    from app.services.articles.deduplicator import upsert_article
    from app.services.articles.parser import ParsedArticle

    db = SessionLocal()
    try:
        issue = models.Issue(
            id="issue_parsed_image_candidate",
            title="선관위 투표용지 부족 사태",
            topic="정치",
            summary="직접 파싱한 대표 이미지 후보를 보존합니다.",
        )
        db.add(issue)
        db.commit()

        parsed = ParsedArticle(
            body_text="직접 파싱된 공식 설명자료 본문입니다.",
            image_candidates=["https://nec.go.kr/parsed-official.jpg"],
            parse_status="parsed",
            published_at=None,
            publisher="중앙선관위",
            summary="직접 파싱 공식자료",
            title="선관위 직접 파싱 공식자료",
        )
        article, _ = upsert_article(
            db,
            issue_id=issue.id,
            parsed=parsed,
            source_type="official",
            url="https://nec.go.kr/parsed-briefing",
        )
        db.commit()

        candidate = db.scalar(
            select(models.ImageCandidate).where(
                models.ImageCandidate.url == "https://nec.go.kr/parsed-official.jpg",
            ),
        )
        assert candidate is not None
        assert candidate.article_id == article.id
        assert candidate.issue_id == issue.id
        assert candidate.publisher == "중앙선관위"
        assert candidate.source_type == "official"
        assert candidate.source_url == "https://nec.go.kr/parsed-briefing"
    finally:
        db.close()


def test_upsert_image_candidate_keeps_same_url_for_distinct_articles() -> None:
    from app.services.images.candidates import upsert_image_candidate

    db = SessionLocal()
    try:
        first = models.Article(
            body_text="첫 번째 기사 본문",
            dedup_hash="same-image-url-first",
            id="article_same_image_first",
            publisher="테스트뉴스A",
            source_type="news",
            summary="첫 번째 기사",
            title="첫 번째 기사",
            url="https://example.com/articles/first",
        )
        second = models.Article(
            body_text="두 번째 기사 본문",
            dedup_hash="same-image-url-second",
            id="article_same_image_second",
            publisher="테스트뉴스B",
            source_type="news",
            summary="두 번째 기사",
            title="두 번째 기사",
            url="https://example.com/articles/second",
        )
        db.add_all([first, second])
        db.commit()

        first_candidate = upsert_image_candidate(
            db,
            article_id=first.id,
            publisher=first.publisher,
            source_type=first.source_type,
            source_url=first.url,
            url="https://cdn.example.com/shared.jpg",
        )
        second_candidate = upsert_image_candidate(
            db,
            article_id=second.id,
            publisher=second.publisher,
            source_type=second.source_type,
            source_url=second.url,
            url="https://cdn.example.com/shared.jpg",
        )
        db.commit()

        assert first_candidate is not None
        assert second_candidate is not None
        assert first_candidate.id != second_candidate.id
        assert first_candidate.article_id == first.id
        assert second_candidate.article_id == second.id
        candidates = db.scalars(
            select(models.ImageCandidate).where(models.ImageCandidate.url == "https://cdn.example.com/shared.jpg"),
        ).all()
        assert {candidate.article_id for candidate in candidates} == {first.id, second.id}
    finally:
        db.close()


def test_issue_candidate_matching_links_all_article_images_and_selects(monkeypatch) -> None:
    from app.services.issues import publisher

    db = SessionLocal()
    try:
        issue = models.Issue(
            id="issue_existing_publisher_images",
            title="선관위 투표용지 부족 사태",
            topic="정치",
            summary="기존 이슈에 유사 기사 이미지 후보를 연결합니다.",
        )
        article_a = models.Article(
            body_text="선관위 투표용지 부족 사태 공식 설명자료입니다.",
            dedup_hash="publisher-match-a",
            id="article_publisher_match_a",
            publisher="중앙선관위",
            source_type="official",
            summary="공식 설명자료",
            title="선관위 투표용지 부족 사태 공식 설명",
            url="https://nec.go.kr/publisher-match-a",
        )
        article_b = models.Article(
            body_text="선관위 투표용지 부족 사태 후속 보도입니다.",
            dedup_hash="publisher-match-b",
            id="article_publisher_match_b",
            publisher="테스트뉴스",
            source_type="news",
            summary="후속 보도",
            title="선관위 투표용지 부족 사태 후속 보도",
            url="https://example.com/publisher-match-b",
        )
        official_image = models.ImageCandidate(
            article_id=article_a.id,
            height=630,
            id="image_publisher_match_official",
            publisher="중앙선관위",
            source_type="official",
            source_url=article_a.url,
            status="candidate",
            url="https://nec.go.kr/publisher-match-official.jpg",
            width=1200,
        )
        news_image = models.ImageCandidate(
            article_id=article_b.id,
            height=315,
            id="image_publisher_match_news",
            publisher="테스트뉴스",
            source_type="news",
            source_url=article_b.url,
            status="candidate",
            url="https://example.com/publisher-match-news.jpg",
            width=600,
        )
        db.add_all([issue, article_a, article_b, official_image, news_image])
        db.commit()

        monkeypatch.setattr(
            publisher,
            "score_issue_candidate",
            lambda articles: {
                "score": 85,
                "signals": {"number_count": 1, "publisher_count": 2},
                "topic": "정치",
            },
        )
        monkeypatch.setattr(
            publisher,
            "find_similar_issue",
            lambda db, **kwargs: (issue, 0.95),
        )

        result = publisher.ensure_issue_candidate(db, articles=[article_a, article_b])
        db.commit()

        assert result is None
        assert article_a.issue_id == issue.id
        assert article_b.issue_id == issue.id
        assert official_image.issue_id == issue.id
        assert news_image.issue_id == issue.id
        assert issue.representative_image_url == "https://nec.go.kr/publisher-match-official.jpg"
    finally:
        db.close()


def test_publish_issue_from_candidate_links_assigned_article_images_and_selects() -> None:
    from app.services.issues import publisher

    db = SessionLocal()
    try:
        candidate = models.AdminQueueItem(
            article_count=1,
            id="issue_publish_candidate_images",
            priority="높음",
            reason="이미지 후보 연결 회귀 테스트",
            status="검토 대기",
            title="선관위 투표용지 부족 사태",
            topic="정치",
        )
        article = models.Article(
            body_text="선관위 투표용지 부족 사태 공식 발표입니다.",
            dedup_hash="publisher-publish-article",
            id="article_publisher_publish",
            publisher="중앙선관위",
            source_type="official",
            summary="공식 발표",
            title="선관위 투표용지 부족 사태 공식 발표",
            url="https://nec.go.kr/publisher-publish",
        )
        image = models.ImageCandidate(
            article_id=article.id,
            height=630,
            id="image_publisher_publish_official",
            publisher="중앙선관위",
            source_type="official",
            source_url=article.url,
            status="candidate",
            url="https://nec.go.kr/publisher-publish-official.jpg",
            width=1200,
        )
        db.add_all([candidate, article, image])
        db.commit()

        issue = publisher.publish_issue_from_candidate(db, candidate_id=candidate.id)
        db.commit()

        assert article.issue_id == issue.id
        assert image.issue_id == issue.id
        assert issue.representative_image_url == "https://nec.go.kr/publisher-publish-official.jpg"
        assert issue.representative_image_source == "중앙선관위"
    finally:
        db.close()


def test_merge_issue_moves_image_candidates_and_selects_representative_image() -> None:
    from app.services.admin.issue_operations import merge_issue

    db = SessionLocal()
    try:
        source = models.Issue(
            id="issue_merge_image_source",
            title="선관위 투표용지 부족 사태",
            topic="정치",
            summary="병합될 이미지 후보가 있는 이슈입니다.",
        )
        target = models.Issue(
            id="issue_merge_image_target",
            title="선관위 투표용지 부족 사태 통합",
            topic="정치",
            summary="병합 후 대표 이미지를 선택해야 합니다.",
        )
        article = models.Article(
            body_text="선관위 투표용지 부족 사태 공식 설명자료입니다.",
            dedup_hash="merge-image-article",
            id="article_merge_image_source",
            issue_id=source.id,
            publisher="중앙선관위",
            source_type="official",
            summary="공식 설명자료",
            title="선관위 투표용지 부족 사태 공식 설명",
            url="https://nec.go.kr/merge-image-article",
        )
        source_issue_image = models.ImageCandidate(
            height=630,
            id="image_merge_source_issue",
            issue_id=source.id,
            publisher="중앙선관위",
            source_type="official",
            source_url="https://nec.go.kr/merge-source-image",
            status="candidate",
            url="https://nec.go.kr/merge-source-official.jpg",
            width=1200,
        )
        article_image = models.ImageCandidate(
            article_id=article.id,
            height=315,
            id="image_merge_article_only",
            publisher="테스트뉴스",
            source_type="news",
            source_url=article.url,
            status="candidate",
            url="https://example.com/merge-article-news.jpg",
            width=600,
        )
        db.add_all([source, target, article, source_issue_image, article_image])
        db.commit()

        merged = merge_issue(db, source_issue_id=source.id, target_issue_id=target.id)
        db.commit()

        assert merged.id == target.id
        assert source_issue_image.issue_id == target.id
        assert article_image.issue_id == target.id
        assert article.issue_id == target.id
        assert target.representative_image_url == "https://nec.go.kr/merge-source-official.jpg"
        assert target.representative_image_source == "중앙선관위"
    finally:
        db.close()


def test_split_article_to_issue_links_image_candidate_and_selects() -> None:
    from app.services.admin.issue_operations import split_article_to_issue

    db = SessionLocal()
    try:
        source = models.Issue(
            id="issue_original_split_image_source",
            title="기존 이슈",
            topic="정치",
            summary="분리 전 이슈입니다.",
        )
        article = models.Article(
            body_text="선관위 투표용지 부족 사태 공식 발표입니다.",
            dedup_hash="split-image-article",
            id="article_split_image_source",
            issue_id=source.id,
            publisher="중앙선관위",
            source_type="official",
            summary="공식 발표",
            title="선관위 투표용지 부족 사태 공식 발표",
            url="https://nec.go.kr/split-image-article",
        )
        image = models.ImageCandidate(
            article_id=article.id,
            height=630,
            id="image_split_article_only",
            publisher="중앙선관위",
            source_type="official",
            source_url=article.url,
            status="candidate",
            url="https://nec.go.kr/split-article-official.jpg",
            width=1200,
        )
        db.add_all([source, article, image])
        db.commit()

        issue = split_article_to_issue(
            db,
            article_id=article.id,
            title="선관위 투표용지 부족 사태",
            topic="정치",
        )
        db.commit()

        assert article.issue_id == issue.id
        assert image.issue_id == issue.id
        assert issue.representative_image_url == "https://nec.go.kr/split-article-official.jpg"
        assert issue.representative_image_source == "중앙선관위"
    finally:
        db.close()


def test_split_article_to_issue_refreshes_source_representative_image() -> None:
    from app.services.admin.issue_operations import split_article_to_issue

    old_timestamp = datetime(2026, 1, 1, tzinfo=UTC)
    db = SessionLocal()
    try:
        source = models.Issue(
            id="issue_original_split_refresh_source",
            title="기존 이슈",
            topic="정치",
            summary="분리 전 이슈입니다.",
            representative_image_url="https://nec.go.kr/split-refresh-official.jpg",
            representative_image_source="중앙선관위",
            representative_image_source_url="https://nec.go.kr/split-refresh",
            representative_image_confidence=0.85,
            representative_image_updated_at=old_timestamp,
        )
        article = models.Article(
            body_text="선관위 투표용지 부족 사태 공식 발표입니다.",
            dedup_hash="split-refresh-image-article",
            id="article_split_refresh_image",
            issue_id=source.id,
            publisher="중앙선관위",
            source_type="official",
            summary="공식 발표",
            title="선관위 투표용지 부족 사태 공식 발표",
            url="https://nec.go.kr/split-refresh",
        )
        image = models.ImageCandidate(
            article_id=article.id,
            height=630,
            id="image_split_refresh_source",
            issue_id=source.id,
            publisher="중앙선관위",
            source_type="official",
            source_url=article.url,
            status="selected",
            url="https://nec.go.kr/split-refresh-official.jpg",
            width=1200,
        )
        db.add_all([source, article, image])
        db.commit()

        new_issue = split_article_to_issue(
            db,
            article_id=article.id,
            title="선관위 투표용지 부족 사태",
            topic="정치",
        )
        db.commit()

        assert image.issue_id == new_issue.id
        assert new_issue.representative_image_url == "https://nec.go.kr/split-refresh-official.jpg"
        assert source.representative_image_url == ""
        assert source.representative_image_source == ""
        assert source.representative_image_source_url == ""
        assert math.isclose(source.representative_image_confidence, 0.0)
        assert source.representative_image_updated_at is not None
        assert source.representative_image_updated_at != old_timestamp
    finally:
        db.close()


def test_generic_rss_extracts_media_image_candidates(monkeypatch) -> None:
    from app.collectors.rss import collect_rss

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return None

        def read(self, limit: int) -> bytes:
            return '''
            <rss xmlns:media="http://search.yahoo.com/mrss/">
              <channel>
                <item>
                  <title>선관위 투표용지 부족 사태 공식 설명</title>
                  <link>https://example.com/rss-article</link>
                  <description>공식 설명자료 본문입니다.</description>
                  <media:thumbnail url="https://example.com/thumb.jpg" />
                  <media:content url="https://example.com/content.jpg" medium="image" />
                  <enclosure url="https://example.com/enclosure.jpg" type="image/jpeg" />
                  <link href="https://example.com/link-image.jpg" rel="enclosure" type="image/jpeg" />
                </item>
              </channel>
            </rss>
            '''.encode()

    monkeypatch.setattr("urllib.request.urlopen", lambda request, timeout: FakeResponse())

    collected = collect_rss("https://example.com/feed.xml", publisher="테스트RSS")

    assert len(collected) == 1
    assert collected[0].image_url == "https://example.com/thumb.jpg"
    assert collected[0].image_candidates == [
        "https://example.com/thumb.jpg",
        "https://example.com/content.jpg",
        "https://example.com/enclosure.jpg",
        "https://example.com/link-image.jpg",
    ]


def test_public_issue_contract_includes_taxonomy_image_and_rank_metadata() -> None:
    db = SessionLocal()
    try:
        major = models.MajorTopic(
            id="major_2026_local_election",
            name="2026 지방선거",
            slug="2026-local-election",
            topic="정치",
            summary="2026 지방선거 관련 사건을 묶습니다.",
            keywords_json=["선거", "투표", "선관위"],
            aliases_json=["지방선거"],
            signal_json={"reason": "election terms"},
        )
        event = models.EventGroup(
            id="event_ballot_shortage",
            major_topic_id=major.id,
            name="선관위 투표용지 부족 사태",
            slug="ballot-shortage",
            topic="정치",
            summary="투표용지 부족 관련 후속 보도를 묶습니다.",
            keywords_json=["선관위", "투표용지", "부족"],
            aliases_json=["투표지 부족"],
            signal_json={"reason": "same incident"},
        )
        issue = models.Issue(
            id="issue_contract_taxonomy",
            is_public=True,
            title="선관위 투표용지 부족 사태",
            topic="정치",
            major_topic_id=major.id,
            major_topic_name=major.name,
            event_group_id=event.id,
            event_group_name=event.name,
            representative_image_url="https://example.com/ballot.jpg",
            representative_image_source="예시뉴스",
            representative_image_source_url="https://example.com/article",
            representative_image_confidence=0.87,
            quality_score=82,
            quality_status="sufficient",
            quality_report_json={"missingSignals": []},
            ranking_json={"rankScore": 91.2, "rankReason": "후속 기사 증가"},
            summary="투표용지 부족 논란과 후속 조치를 검증 중입니다.",
        )
        db.add_all([major, event, issue])
        db.commit()
    finally:
        db.close()

    with TestClient(app) as client:
        response = client.get("/v1/issues/home")
        assert response.status_code == 200
        issue_payload = response.json()["issues"][0]
        assert issue_payload["majorTopic"] == "2026 지방선거"
        assert issue_payload["majorTopicId"] == "major_2026_local_election"
        assert issue_payload["eventGroup"] == "선관위 투표용지 부족 사태"
        assert issue_payload["eventGroupId"] == "event_ballot_shortage"
        assert issue_payload["representativeImageUrl"] == "https://example.com/ballot.jpg"
        assert issue_payload["rankScore"] is not None
        assert issue_payload["rankReason"]
        assert issue_payload["rankReason"] != "후속 기사 증가"


def test_home_sort_controversial_prioritizes_high_conflict_issue() -> None:
    db = SessionLocal()
    try:
        db.add_all(
            [
                models.Issue(
                    id="issue_latest_low_conflict",
                    is_public=True,
                    title="최근 단순 업데이트",
                    topic="사회",
                    summary="최근 업데이트됐지만 논란도는 낮습니다.",
                    article_count=2,
                    needs_review_count=0,
                    issue_score=40,
                    updated_at=datetime.now(UTC),
                ),
                models.Issue(
                    id="issue_controversial_election",
                    is_public=True,
                    title="선관위 투표용지 부족 사태",
                    topic="정치",
                    major_topic_name="2026 지방선거",
                    event_group_name="선관위 투표용지 부족 사태",
                    summary="기사와 주장 충돌이 큰 사건입니다.",
                    article_count=30,
                    needs_review_count=8,
                    changed_claims=4,
                    issue_score=91,
                    updated_at=datetime.now(UTC) - timedelta(hours=2),
                ),
            ],
        )
        db.commit()
    finally:
        db.close()

    with TestClient(app) as client:
        response = client.get("/v1/issues/home?sort=controversial")
        assert response.status_code == 200
        assert response.json()["issues"][0]["id"] == "issue_controversial_election"
        assert response.json()["issues"][0]["rankReason"]


def test_home_personalized_sort_uses_interest_profile() -> None:
    from app.core.security import create_access_token

    db = SessionLocal()
    try:
        user = models.User(
            email="personalized@example.com",
            id="user_personalized",
            name="개인화 사용자",
            password_hash="hash",
            role="user",
        )
        profile = models.UserInterestProfile(
            user_id=user.id,
            topic_weights_json={"경제": 10},
        )
        politics = models.Issue(
            id="issue_personalized_politics",
            is_public=True,
            title="정치 일반 이슈",
            topic="정치",
            summary="정치 이슈입니다.",
            issue_score=60,
            updated_at=datetime.now(UTC),
        )
        economy = models.Issue(
            id="issue_personalized_economy",
            is_public=True,
            title="경제 관심 이슈",
            topic="경제",
            summary="사용자가 관심을 둔 경제 이슈입니다.",
            issue_score=60,
            updated_at=datetime.now(UTC) - timedelta(hours=1),
        )
        db.add_all([user, profile, politics, economy])
        db.commit()
        token, _ = create_access_token(user.id, user.role)
    finally:
        db.close()

    with TestClient(app) as client:
        response = client.get(
            "/v1/issues/home?sort=personalized",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["issues"][0]["id"] == "issue_personalized_economy"
        assert response.json()["issues"][0]["rankReason"] == "관심사와 이슈 신호를 함께 반영"


def test_home_major_topic_filter_uses_major_topic_name() -> None:
    db = SessionLocal()
    try:
        db.add_all(
            [
                models.Issue(
                    id="issue_major_election",
                    is_public=True,
                    title="선관위 투표용지 부족 사태",
                    topic="정치",
                    major_topic_name="2026 지방선거",
                    summary="선거 관련 이슈입니다.",
                ),
                models.Issue(
                    id="issue_major_economy",
                    is_public=True,
                    title="부동산 공급 대책",
                    topic="경제",
                    major_topic_name="부동산 공급정책",
                    summary="경제 관련 이슈입니다.",
                ),
            ],
        )
        db.commit()
    finally:
        db.close()

    with TestClient(app) as client:
        response = client.get("/v1/issues/home?majorTopic=2026%20지방선거")
        assert response.status_code == 200
        assert [issue["id"] for issue in response.json()["issues"]] == ["issue_major_election"]


def test_home_event_group_filter_uses_event_group_name() -> None:
    db = SessionLocal()
    try:
        db.add_all(
            [
                models.Issue(
                    id="issue_event_ballot",
                    is_public=True,
                    title="선관위 투표용지 부족 사태",
                    topic="정치",
                    event_group_name="선관위 투표용지 부족 사태",
                    summary="투표용지 부족 관련 이슈입니다.",
                ),
                models.Issue(
                    id="issue_event_votes",
                    is_public=True,
                    title="인천 사전투표 동일 득표 논란",
                    topic="정치",
                    event_group_name="인천 사전투표 동일 득표 논란",
                    summary="별도 선거 사건입니다.",
                ),
            ],
        )
        db.commit()
    finally:
        db.close()

    with TestClient(app) as client:
        response = client.get("/v1/issues/home?eventGroup=선관위%20투표용지%20부족%20사태")
        assert response.status_code == 200
        assert [issue["id"] for issue in response.json()["issues"]] == ["issue_event_ballot"]


def test_home_filtered_selected_issue_must_be_visible() -> None:
    db = SessionLocal()
    try:
        db.add_all(
            [
                models.Issue(
                    id="issue_selected_election",
                    is_public=True,
                    title="선관위 투표용지 부족 사태",
                    topic="정치",
                    major_topic_name="2026 지방선거",
                    summary="선거 관련 이슈입니다.",
                ),
                models.Issue(
                    id="issue_selected_economy",
                    is_public=True,
                    title="부동산 공급 대책",
                    topic="경제",
                    major_topic_name="부동산 공급정책",
                    summary="경제 관련 이슈입니다.",
                ),
            ],
        )
        db.commit()
    finally:
        db.close()

    with TestClient(app) as client:
        response = client.get(
            "/v1/issues/home?majorTopic=2026%20지방선거&issueId=issue_selected_economy",
        )
        assert response.status_code == 200
        payload = response.json()
        assert [issue["id"] for issue in payload["issues"]] == ["issue_selected_election"]
        assert payload["selectedIssue"] is None


def test_home_invalid_bearer_token_is_anonymous() -> None:
    db = SessionLocal()
    try:
        db.add(
            models.Issue(
                id="issue_public_invalid_token",
                is_public=True,
                title="공개 홈 이슈",
                topic="사회",
                summary="잘못된 토큰이 있어도 공개 홈은 익명으로 동작해야 합니다.",
            ),
        )
        db.commit()
    finally:
        db.close()

    with TestClient(app) as client:
        response = client.get("/v1/issues/home", headers={"Authorization": "Bearer invalid"})
        assert response.status_code == 200
        assert response.json()["issues"][0]["id"] == "issue_public_invalid_token"


def test_public_home_normalizes_malformed_ranking_metadata() -> None:
    malformed_rankings = {
        "issue_rank_list": ["rankScore", 92],
        "issue_rank_text": {"rankScore": "not-a-number", "rankReason": "invalid score"},
        "issue_rank_nan": {"rankScore": float("nan"), "rankReason": "non-finite score"},
    }
    db = SessionLocal()
    try:
        for issue_id, ranking_json in malformed_rankings.items():
            db.add(
                models.Issue(
                    id=issue_id,
                    is_public=True,
                    ranking_json=ranking_json,
                    summary="비정상 랭킹 데이터가 있어도 공개 API는 응답해야 합니다.",
                    title=issue_id,
                    topic="정치",
                ),
            )
        db.commit()
    finally:
        db.close()

    with TestClient(app) as client:
        response = client.get("/v1/issues/home")
        assert response.status_code == 200
        issues_by_id = {issue["id"]: issue for issue in response.json()["issues"]}
        for issue_id in malformed_rankings:
            assert issues_by_id[issue_id]["rankScore"] is not None
            assert issues_by_id[issue_id]["rankReason"]


def test_home_recommended_returns_rank_metadata_for_malformed_or_missing_ranking() -> None:
    db = SessionLocal()
    try:
        db.add_all(
            [
                models.Issue(
                    id="issue_rank_malformed_recommended",
                    is_public=True,
                    ranking_json={"rankScore": "not-a-number", "rankReason": ""},
                    summary="기존 랭킹 데이터가 비정상이어도 추천 랭킹을 다시 계산해야 합니다.",
                    title="비정상 랭킹 데이터 이슈",
                    topic="정치",
                    issue_score=75,
                    article_count=12,
                    needs_review_count=3,
                ),
                models.Issue(
                    id="issue_rank_missing_recommended",
                    is_public=True,
                    summary="랭킹 데이터가 없어도 추천 랭킹 메타데이터가 응답되어야 합니다.",
                    title="랭킹 데이터 없는 이슈",
                    topic="사회",
                    issue_score=45,
                    article_count=4,
                ),
            ],
        )
        db.commit()
    finally:
        db.close()

    with TestClient(app) as client:
        response = client.get("/v1/issues/home")
        assert response.status_code == 200
        issues_by_id = {issue["id"]: issue for issue in response.json()["issues"]}
        for issue_id in {"issue_rank_malformed_recommended", "issue_rank_missing_recommended"}:
            assert issues_by_id[issue_id]["rankScore"] is not None
            assert issues_by_id[issue_id]["rankReason"]


def test_home_recommended_recomputes_stale_persisted_ranking_metadata() -> None:
    db = SessionLocal()
    try:
        db.add(
            models.Issue(
                id="issue_stale_recommended_rank",
                is_public=True,
                ranking_json={"rankScore": 999, "rankReason": "이전 개인화 정렬 결과"},
                summary="추천 정렬은 오래된 저장 랭킹을 그대로 재사용하지 않습니다.",
                title="오래된 랭킹 이슈",
                topic="정치",
                issue_score=70,
                article_count=10,
            ),
        )
        db.commit()
    finally:
        db.close()

    with TestClient(app) as client:
        response = client.get("/v1/issues/home")
        assert response.status_code == 200
        issue = response.json()["issues"][0]
        assert issue["rankScore"] != 999
        assert issue["rankReason"] != "이전 개인화 정렬 결과"


def test_home_rank_metadata_is_response_scoped_not_persisted() -> None:
    original_ranking = {"rankScore": "not-a-number", "rankReason": ""}
    db = SessionLocal()
    try:
        db.add(
            models.Issue(
                id="issue_response_scoped_rank",
                is_public=True,
                ranking_json=original_ranking,
                summary="응답 랭킹은 계산하지만 DB 랭킹 필드는 바꾸지 않아야 합니다.",
                title="응답 전용 랭킹 이슈",
                topic="사회",
                issue_score=55,
                article_count=5,
            ),
        )
        db.commit()
    finally:
        db.close()

    with TestClient(app) as client:
        response = client.get("/v1/issues/home")
        assert response.status_code == 200
        issue = response.json()["issues"][0]
        assert issue["rankScore"] is not None
        assert issue["rankReason"]

    db = SessionLocal()
    try:
        persisted = db.get(models.Issue, "issue_response_scoped_rank")
        assert persisted is not None
        assert persisted.ranking_json == original_ranking
    finally:
        db.close()


def test_election_incidents_share_major_topic_but_not_event_group() -> None:
    from app.services.classification.taxonomy import classify_issue_taxonomy

    db = SessionLocal()
    try:
        first = models.Issue(
            id="issue_ballot_shortage",
            title="선관위 투표용지 부족 사태",
            topic="정치",
            summary="투표용지 부족 투표소가 늘었다는 논란입니다.",
        )
        second = models.Issue(
            id="issue_incheon_equal_votes",
            title="인천 사전투표 동일 득표 논란",
            topic="정치",
            summary="사전투표 득표 수치가 동일하다는 별도 논란입니다.",
        )
        db.add_all([first, second])
        db.flush()

        classify_issue_taxonomy(db, issue=first)
        classify_issue_taxonomy(db, issue=second)
        db.commit()

        assert first.major_topic_name == "2026 지방선거"
        assert second.major_topic_name == "2026 지방선거"
        assert first.event_group_id != second.event_group_id
        assert first.event_group_name == "선관위 투표용지 부족 사태"
        assert second.event_group_name == "인천 사전투표 동일 득표 논란"
    finally:
        db.close()


def test_same_incident_followup_reuses_event_group() -> None:
    from app.services.classification.taxonomy import classify_issue_taxonomy

    db = SessionLocal()
    try:
        first = models.Issue(
            id="issue_ballot_shortage_initial",
            title="선관위 투표용지 부족 사태",
            topic="정치",
            summary="투표용지 부족 사태 초기 보도입니다.",
        )
        second = models.Issue(
            id="issue_ballot_shortage_followup",
            title="선관위 투표용지 부족 후속 감사 착수",
            topic="정치",
            summary="투표용지 부족 사태와 관련해 감사가 착수됐습니다.",
        )
        third = models.Issue(
            id="issue_ballot_shortage_rally",
            title="인천 시민단체 선관위 투표용지 부족 사태 규탄 집회",
            topic="정치",
            summary="투표용지 부족 사태 책임을 묻는 집회와 해체 요구가 이어졌습니다.",
        )
        db.add_all([first, second, third])
        db.flush()

        classify_issue_taxonomy(db, issue=first)
        classify_issue_taxonomy(db, issue=second)
        classify_issue_taxonomy(db, issue=third)
        db.commit()

        assert first.event_group_id == second.event_group_id
        assert first.event_group_id == third.event_group_id
        assert second.event_group_name == "선관위 투표용지 부족 사태"
        assert third.event_group_name == "선관위 투표용지 부족 사태"
    finally:
        db.close()


def test_classification_repeat_does_not_touch_unchanged_issue_timestamp() -> None:
    from app.services.classification.taxonomy import classify_issue_taxonomy

    db = SessionLocal()
    try:
        issue = models.Issue(
            id="issue_taxonomy_idempotent",
            title="선관위 투표용지 부족 사태",
            topic="정치",
            summary="투표용지 부족 사태 초기 보도입니다.",
        )
        db.add(issue)
        db.flush()

        classify_issue_taxonomy(db, issue=issue)
        db.commit()
        first_updated_at = issue.updated_at
        first_last_updated_at = issue.last_updated_at

        classify_issue_taxonomy(db, issue=issue)
        db.commit()

        assert issue.updated_at == first_updated_at
        assert issue.last_updated_at == first_last_updated_at
    finally:
        db.close()


def test_election_taxonomy_updates_default_social_issue_topic() -> None:
    from app.services.classification.taxonomy import classify_issue_taxonomy

    db = SessionLocal()
    try:
        issue = models.Issue(
            id="issue_social_default_election",
            title="선관위 투표용지 부족 사태",
            topic="사회",
            summary="투표용지 부족 투표소가 늘었다는 선거 관련 논란입니다.",
        )
        db.add(issue)
        db.flush()

        major_topic, event_group = classify_issue_taxonomy(db, issue=issue)
        db.commit()

        assert issue.topic == "정치"
        assert major_topic.topic == "정치"
        assert event_group.topic == "정치"
    finally:
        db.close()


def test_hidden_event_group_exact_name_is_not_reactivated_or_reused() -> None:
    from app.services.classification.taxonomy import classify_issue_taxonomy

    db = SessionLocal()
    try:
        major = models.MajorTopic(
            id="major_hidden_event_test",
            name="2026 지방선거",
            slug="hidden-event-test",
            topic="정치",
        )
        hidden_event = models.EventGroup(
            id="event_hidden_ballot_shortage",
            major_topic_id=major.id,
            name="선관위 투표용지 부족 사태",
            slug="hidden-ballot-shortage",
            status="숨김",
            topic="정치",
        )
        issue = models.Issue(
            id="issue_hidden_event_reuse",
            title="선관위 투표용지 부족 사태",
            topic="정치",
            summary="투표용지 부족 사태 초기 보도입니다.",
        )
        db.add_all([major, hidden_event, issue])
        db.flush()

        _, event_group = classify_issue_taxonomy(db, issue=issue)
        db.commit()

        assert event_group.id != hidden_event.id
        assert issue.event_group_id != hidden_event.id
        assert hidden_event.status == "숨김"
    finally:
        db.close()


def test_sqlite_schema_helper_backfills_new_issue_contract_columns(tmp_path: Path) -> None:
    db_path = tmp_path / "old_facttracer.db"
    old_engine = create_engine(f"sqlite:///{db_path}")
    with old_engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE issues (
                    id VARCHAR(80) PRIMARY KEY,
                    topic_id VARCHAR,
                    title VARCHAR(240),
                    slug VARCHAR(280),
                    topic VARCHAR(80),
                    status VARCHAR(80),
                    risk VARCHAR(80),
                    sensitivity_level VARCHAR(40),
                    created_at DATETIME,
                    updated_at DATETIME,
                    last_updated_at DATETIME,
                    summary TEXT,
                    issue_score INTEGER,
                    article_count INTEGER,
                    cluster_count INTEGER,
                    verified_count INTEGER,
                    needs_review_count INTEGER,
                    changed_claims INTEGER,
                    is_public BOOLEAN,
                    confirmed_facts JSON,
                    claim_clusters JSON,
                    claims JSON,
                    evidences JSON,
                    perspectives JSON,
                    articles JSON,
                    timeline JSON,
                    source_documents JSON,
                    number_changes JSON
                )
                """,
            ),
        )
        connection.execute(
            text(
                """
                INSERT INTO issues (
                    id,
                    title,
                    topic,
                    status,
                    risk,
                    sensitivity_level,
                    created_at,
                    updated_at,
                    last_updated_at,
                    summary,
                    issue_score,
                    article_count,
                    cluster_count,
                    verified_count,
                    needs_review_count,
                    changed_claims,
                    is_public,
                    confirmed_facts,
                    claim_clusters,
                    claims,
                    evidences,
                    perspectives,
                    articles,
                    timeline,
                    source_documents,
                    number_changes
                ) VALUES (
                    'legacy_issue',
                    '기존 이슈',
                    '정치',
                    '검증 진행',
                    '일반',
                    'normal',
                    '2026-06-10 00:00:00',
                    '2026-06-10 00:00:00',
                    '2026-06-10 00:00:00',
                    '기존 행입니다.',
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    1,
                    '[]',
                    '[]',
                    '[]',
                    '[]',
                    '[]',
                    '[]',
                    '[]',
                    '[]',
                    '[]'
                )
                """,
            ),
        )

    ensure_database_schema(old_engine)

    with old_engine.connect() as connection:
        row = connection.execute(
            text(
                """
                SELECT
                    major_topic_id,
                    event_group_id,
                    major_topic_name,
                    event_group_name,
                    representative_image_url,
                    representative_image_source,
                    representative_image_source_url,
                    representative_image_confidence,
                    representative_image_updated_at,
                    quality_score,
                    quality_status,
                    quality_report_json,
                    quality_attempts,
                    last_quality_checked_at,
                    next_quality_retry_at,
                    ranking_json
                FROM issues
                WHERE id = 'legacy_issue'
                """,
            ),
        ).mappings().one()
        assert row["major_topic_id"] is None
        assert row["event_group_id"] is None
        assert row["major_topic_name"] == ""
        assert row["event_group_name"] == ""
        assert row["representative_image_url"] == ""
        assert row["representative_image_source"] == ""
        assert row["representative_image_source_url"] == ""
        assert math.isclose(row["representative_image_confidence"], 0.0)
        assert row["representative_image_updated_at"] is None
        assert row["quality_score"] == 0
        assert row["quality_status"] == "unchecked"
        assert row["quality_report_json"] == "{}"
        assert row["quality_attempts"] == 0
        assert row["last_quality_checked_at"] is None
        assert row["next_quality_retry_at"] is None
        assert row["ranking_json"] == "{}"

        index_names = {
            row["name"]
            for row in connection.execute(text("PRAGMA index_list(issues)")).mappings()
        }
        assert "ix_issues_major_topic_id" in index_names
        assert "ix_issues_event_group_id" in index_names
        assert "ix_issues_major_topic_name" in index_names
        assert "ix_issues_event_group_name" in index_names
        assert "ix_issues_quality_status" in index_names


def test_sqlite_schema_helper_quotes_reserved_identifiers(tmp_path: Path) -> None:
    db_path = tmp_path / "old_reserved_identifier.db"
    old_engine = create_engine(f"sqlite:///{db_path}")
    with old_engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE system_settings (
                    key VARCHAR(120) PRIMARY KEY,
                    label VARCHAR(160),
                    description TEXT,
                    value JSON,
                    value_type VARCHAR(40),
                    is_secret BOOLEAN,
                    updated_by VARCHAR(80),
                    created_at DATETIME,
                    updated_at DATETIME
                )
                """,
            ),
        )

    ensure_database_schema(old_engine)

    with old_engine.connect() as connection:
        column_names = {
            row["name"]
            for row in connection.execute(text('PRAGMA table_info("system_settings")')).mappings()
        }
        assert "group" in column_names

        index_names = {
            row["name"]
            for row in connection.execute(text('PRAGMA index_list("system_settings")')).mappings()
        }
        assert "ix_system_settings_group" in index_names


def test_sqlite_schema_helper_skips_issue_backfill_when_no_nulls(tmp_path: Path) -> None:
    db_path = tmp_path / "idempotent_schema.db"
    old_engine = create_engine(f"sqlite:///{db_path}")
    ensure_database_schema(old_engine)
    update_statements: list[str] = []

    def collect_updates(_conn, _cursor, statement, _parameters, _context, _executemany) -> None:
        normalized = statement.strip().lower()
        if normalized.startswith('update "issues"') or normalized.startswith("update issues"):
            update_statements.append(statement)

    event.listen(old_engine, "before_cursor_execute", collect_updates)
    try:
        ensure_database_schema(old_engine)
    finally:
        event.remove(old_engine, "before_cursor_execute", collect_updates)

    assert update_statements == []


def test_alembic_additive_migration_updates_existing_0001_schema(
    monkeypatch,
    tmp_path: Path,
) -> None:
    import pytest

    alembic_migration = pytest.importorskip("alembic.migration")
    alembic_operations = pytest.importorskip("alembic.operations")

    db_path = tmp_path / "old_alembic_facttracer.db"
    old_engine = create_engine(f"sqlite:///{db_path}")
    with old_engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE issues (
                    id VARCHAR(80) PRIMARY KEY,
                    title VARCHAR(240),
                    topic VARCHAR(80),
                    status VARCHAR(80)
                )
                """,
            ),
        )
        connection.execute(
            text(
                """
                INSERT INTO issues (id, title, topic, status)
                VALUES ('legacy_issue', '기존 이슈', '정치', '검증 진행')
                """,
            ),
        )

    migration = importlib.import_module(
        "app.db.migrations.versions.0002_collection_classification_ranking",
    )
    with old_engine.begin() as connection:
        context = alembic_migration.MigrationContext.configure(connection)
        monkeypatch.setattr(migration, "op", alembic_operations.Operations(context))
        migration.upgrade()

    with old_engine.connect() as connection:
        table_names = {
            row["name"]
            for row in connection.execute(
                text("SELECT name FROM sqlite_master WHERE type = 'table'"),
            ).mappings()
        }
        assert "major_topics" in table_names
        assert "event_groups" in table_names
        assert "image_candidates" in table_names
        assert "user_interest_profiles" in table_names

        issue_columns = {
            row["name"]
            for row in connection.execute(text("PRAGMA table_info(issues)")).mappings()
        }
        assert "major_topic_id" in issue_columns
        assert "event_group_id" in issue_columns
        assert "representative_image_url" in issue_columns
        assert "quality_report_json" in issue_columns
        assert "ranking_json" in issue_columns

        row = connection.execute(
            text(
                """
                SELECT
                    major_topic_name,
                    event_group_name,
                    representative_image_url,
                    representative_image_confidence,
                    quality_score,
                    quality_status,
                    quality_report_json,
                    quality_attempts,
                    ranking_json
                FROM issues
                WHERE id = 'legacy_issue'
                """,
            ),
        ).mappings().one()
        assert row["major_topic_name"] == ""
        assert row["event_group_name"] == ""
        assert row["representative_image_url"] == ""
        assert math.isclose(row["representative_image_confidence"], 0.0)
        assert row["quality_score"] == 0
        assert row["quality_status"] == "unchecked"
        assert row["quality_report_json"] == "{}"
        assert row["quality_attempts"] == 0
        assert row["ranking_json"] == "{}"

        index_names = {
            row["name"]
            for row in connection.execute(text("PRAGMA index_list(issues)")).mappings()
        }
        assert "ix_issues_major_topic_id" in index_names
        assert "ix_issues_event_group_id" in index_names
        assert "ix_issues_major_topic_name" in index_names
        assert "ix_issues_event_group_name" in index_names
        assert "ix_issues_quality_status" in index_names


def test_podcast_variant_migration_backfills_variant_and_updates_unique_constraint(
    monkeypatch,
    tmp_path: Path,
) -> None:
    import pytest

    alembic_migration = pytest.importorskip("alembic.migration")
    alembic_operations = pytest.importorskip("alembic.operations")

    db_path = tmp_path / "old_podcast_variants.db"
    old_engine = create_engine(f"sqlite:///{db_path}")
    with old_engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE podcast_episodes (
                    id VARCHAR(80) PRIMARY KEY,
                    issue_id VARCHAR(80),
                    episode_format VARCHAR(40) NOT NULL DEFAULT 'solo',
                    generation_json JSON NOT NULL DEFAULT '{}',
                    CONSTRAINT uq_podcast_episode_issue_format UNIQUE (issue_id, episode_format)
                )
                """,
            ),
        )
        connection.execute(
            text(
                """
                INSERT INTO podcast_episodes (
                    id,
                    issue_id,
                    episode_format,
                    generation_json
                ) VALUES (
                    'podcast_old_deep',
                    'issue_old',
                    'panel_2',
                    '{"variant": "deep"}'
                )
                """,
            ),
        )

    migration = importlib.import_module(
        "app.db.migrations.versions.0005_podcast_episode_variants",
    )
    with old_engine.begin() as connection:
        context = alembic_migration.MigrationContext.configure(connection)
        monkeypatch.setattr(migration, "op", alembic_operations.Operations(context))
        migration.upgrade()

    with old_engine.begin() as connection:
        columns = {
            row["name"]
            for row in connection.execute(text("PRAGMA table_info(podcast_episodes)")).mappings()
        }
        assert "variant" in columns
        row = connection.execute(
            text("SELECT variant FROM podcast_episodes WHERE id = 'podcast_old_deep'"),
        ).mappings().one()
        assert row["variant"] == "deep"

        connection.execute(
            text(
                """
                INSERT INTO podcast_episodes (
                    id,
                    issue_id,
                    episode_format,
                    generation_json,
                    variant
                ) VALUES (
                    'podcast_old_standard',
                    'issue_old',
                    'panel_2',
                    '{"variant": "standard"}',
                    'standard'
                )
                """,
            ),
        )
        count = connection.execute(
            text(
                """
                SELECT COUNT(*) AS count
                FROM podcast_episodes
                WHERE issue_id = 'issue_old' AND episode_format = 'panel_2'
                """,
            ),
        ).mappings().one()
        assert count["count"] == 2


def test_topic_normalization_collapses_ai_subtopics() -> None:
    assert normalize_topic("국제정치") == "국제"
    assert normalize_topic("경제정책/물가") == "경제"
    assert normalize_topic("국게 주요 이슈") == "국제"
    assert normalize_topic("과학/기술") == "IT"
    assert normalize_topic("AI 반도체 보안") == "IT"

    db = SessionLocal()
    try:
        db.add_all(
            [
                models.Issue(
                    id="issue_intl_politics",
                    is_public=True,
                    summary="국제정치로 잘못 분리된 이슈입니다.",
                    title="해외 선거 분쟁",
                    topic="국제정치",
                ),
                models.Issue(
                    id="issue_price_policy",
                    is_public=True,
                    summary="경제정책/물가로 잘못 분리된 이슈입니다.",
                    title="물가 대책 논란",
                    topic="경제정책/물가",
                ),
                models.Issue(
                    id="issue_intl_typo",
                    is_public=True,
                    summary="국게 주요 이슈로 잘못 분리된 이슈입니다.",
                    title="국제 제재 협상",
                    topic="국게 주요 이슈",
                ),
            ],
        )
        keywords = seed_search_keywords(
            db,
            generate_variants=False,
            query="물가 대책 논란",
            topic="경제정책/물가",
        )
        db.commit()
        assert keywords[0].topic == "경제"
    finally:
        db.close()

    with TestClient(app) as client:
        international = client.get("/v1/issues/home?topic=국제")
        assert international.status_code == 200
        payload = international.json()
        assert [issue["topic"] for issue in payload["issues"]] == ["국제", "국제"]
        assert {issue["id"] for issue in payload["issues"]} == {
            "issue_intl_politics",
            "issue_intl_typo",
        }
        assert "국제정치" not in payload["topics"]
        assert "경제정책/물가" not in payload["topics"]


def test_same_incident_reuses_existing_issue_for_search_and_discovery() -> None:
    db = SessionLocal()
    try:
        existing = models.Issue(
            id="issue_search_ballot_shortage",
            is_public=True,
            issue_score=70,
            summary="투표용지 부족 사태를 주장 단위로 검증 중입니다.",
            title="선관위 투표용지 부족 사태",
            topic="정치",
        )
        keyword = models.SearchKeyword(
            id="keyword_ballot_shortage",
            priority="high",
            query="선관위 투표용지 부족 91곳",
            seed_query="선관위 투표용지 부족 사태",
            topic="정치",
        )
        db.add_all([existing, keyword])
        db.flush()

        search_issue = issue_jobs._ensure_search_issue(db, keyword=keyword)
        discovery_issue = issue_jobs._ensure_discovery_issue(
            db,
            definition={
                "score": 100,
                "summary": "선관위 투표용지 부족 투표소가 50곳에서 91곳으로 늘어난 사안입니다.",
                "title": "선관위 투표용지 부족 사태 (50곳→91곳)",
                "topic": "선거 감시",
            },
            priority="high",
        )
        db.commit()

        assert search_issue.id == existing.id
        assert discovery_issue.id == existing.id
        assert keyword.issue_id == existing.id
        assert db.query(models.Issue).count() == 1
    finally:
        db.close()


def test_keyword_variants_keep_generic_followup_paths() -> None:
    variants = fallback_keyword_variants("선관위 투표용지 부족 사태")

    assert "선관위 투표용지 부족" in variants
    assert "선관위 투표용지 부족 사태 조사" in variants
    assert "선관위 투표용지 부족 사태 공식자료" in variants
    assert all("중앙선거관리위원회 투표용지 부족" != variant for variant in variants)


def test_active_issue_followup_runs_even_with_enough_sources(monkeypatch) -> None:
    def fake_google_news_search(query: str, **kwargs) -> list[CollectedArticle]:
        return [
            CollectedArticle(
                body_text="감사원이 선관위 투표용지 부족 사태와 관련해 후속 감사에 착수했다.",
                publisher="후속뉴스",
                source_type="news_search",
                summary="선관위 투표용지 부족 사태 후속 감사 착수",
                title=f"{query} 후속 보도",
                url="https://example.com/followup-news-1",
            ),
        ]

    monkeypatch.setattr(issue_jobs, "collect_google_news_search", fake_google_news_search)

    now = datetime.now(UTC)
    db = SessionLocal()
    try:
        db.add(
            models.Issue(
                article_count=3,
                created_at=now - timedelta(days=2),
                id="issue_followup_ballot",
                is_public=True,
                issue_score=91,
                status="검증 진행",
                summary="투표용지 부족 관련 후속 확인이 필요한 이슈입니다.",
                title="선관위 투표용지 부족 사태",
                topic="정치",
                updated_at=now - timedelta(hours=4),
            ),
        )
        db.commit()

        jobs = schedule_due_issue_backfill_jobs(db)
        assert len(jobs) == 1
        assert jobs[0].input_json["force"] is True
        run_due_jobs(db, limit=1)
        db.commit()
    finally:
        db.close()

    db = SessionLocal()
    try:
        article = db.scalar(
            select(models.Article).where(models.Article.url == "https://example.com/followup-news-1"),
        )
        keyword = db.scalar(
            select(models.SearchKeyword).where(models.SearchKeyword.issue_id == "issue_followup_ballot"),
        )
        assert article is not None
        assert article.issue_id == "issue_followup_ballot"
        assert keyword is not None
        assert keyword.source == "issue_followup"
    finally:
        db.close()


def test_issue_quality_detects_missing_signals_and_creates_retry_keywords() -> None:
    from app.services.issues.quality import assess_issue_quality

    db = SessionLocal()
    try:
        issue = models.Issue(
            id="issue_quality_missing",
            title="선관위 투표용지 부족 사태",
            topic="정치",
            summary="기사와 공식자료가 부족한 상태입니다.",
            article_count=1,
            quality_attempts=0,
        )
        db.add(issue)
        db.add(
            models.Article(
                id="article_quality_1",
                issue_id=issue.id,
                title="투표용지 부족 논란",
                publisher="테스트뉴스",
                url="https://example.com/quality-1",
                dedup_hash="quality-1",
                body_text="투표용지 부족 주장이 제기됐다.",
                summary="투표용지 부족 주장",
                source_type="news",
            )
        )
        db.commit()

        report = assess_issue_quality(db, issue_id=issue.id)
        db.commit()

        assert report["status"] == "needs_retry"
        assert "officialCoverage" in report["missingSignals"]
        assert "claimCoverage" in report["missingSignals"]
        keywords = db.scalars(
            select(models.SearchKeyword).where(models.SearchKeyword.issue_id == issue.id)
        ).all()
        assert any(keyword.source == "quality_retry" for keyword in keywords)
        assert issue.quality_attempts == 1
        assert issue.next_quality_retry_at is not None
    finally:
        db.close()


def test_issue_article_quality_rejects_generic_public_pages() -> None:
    from app.services.issues.article_quality import is_generic_article_page

    assert is_generic_article_page(
        publisher="공공데이터포털",
        title="- 공공데이터포털",
        url="https://www.data.go.kr/data/15000000/fileData.do",
    )
    assert is_generic_article_page(
        publisher="대한민국 정책브리핑",
        title="문서뷰어 - 대한민국 정책브리핑",
        url="https://www.korea.kr/archive/expDocView.do",
    )
    assert is_generic_article_page(
        publisher="중앙선거관리위원회",
        title="Untitled - 중앙선거관리위원회",
        url="https://www.nec.go.kr/site/nec/ex/bbs/View.do",
    )


def test_issue_article_quality_requires_issue_relevance() -> None:
    from app.services.issues.article_quality import article_matches_issue

    issue = models.Issue(
        id="issue_fire_relevance",
        title="대전 한화에어로 공장 화재 사고",
        topic="재난",
        status="검증 진행",
        risk="고영향",
    )
    relevant = CollectedArticle(
        title="'7명 사상' 한화에어로스페이스 폭발 화재",
        publisher="연합뉴스",
        url="https://example.com/relevant",
    )
    irrelevant = CollectedArticle(
        title="전세사기피해지원위원회 피해자등 825건 결정",
        publisher="국토교통부",
        url="https://example.com/irrelevant",
    )

    assert article_matches_issue(issue, relevant)
    assert not article_matches_issue(issue, irrelevant)


def test_quality_report_penalizes_low_relevance_articles_and_zero_claims() -> None:
    from app.services.issues.quality import build_issue_quality_report

    db = SessionLocal()
    try:
        issue = models.Issue(
            id="issue_low_relevance_quality",
            title="RSV 전국 유행 주의보",
            topic="보건",
            status="검증 진행",
            risk="고영향",
            issue_score=90,
        )
        db.add(issue)
        db.add(
            models.Article(
                id="article_generic_health",
                issue_id=issue.id,
                title="이달의 건강정보 - 국가건강정보포털",
                publisher="국가건강정보포털",
                url="https://health.example/generic",
                normalized_url="https://health.example/generic",
                dedup_hash="health-generic",
                content_hash="health-generic",
                parse_status="parsed",
            ),
        )
        db.commit()

        report = build_issue_quality_report(db, issue=issue)

        assert "relevanceCoverage" in report["missingSignals"]
        assert "claimCoverage" in report["missingSignals"]
        assert report["score"] <= 60
    finally:
        db.close()


def test_cleanup_redundant_parse_jobs_marks_parsed_article_jobs_completed() -> None:
    from app.services.issues.article_quality import cleanup_redundant_parse_jobs

    db = SessionLocal()
    try:
        article = models.Article(
            id="article_done_parse",
            title="완료 기사",
            publisher="연합뉴스",
            url="https://example.com/done",
            normalized_url="https://example.com/done",
            dedup_hash="done-parse",
            content_hash="done-parse",
            parse_status="parsed",
        )
        db.add(article)
        db.add(
            models.JobAttempt(
                id="job_parse_done",
                input_json={"article_id": article.id},
                job_type="parse_article",
                status="queued",
                target_id=article.id,
            ),
        )
        db.commit()

        result = cleanup_redundant_parse_jobs(db)
        db.commit()

        assert result["completed"] == 1
        assert db.get(models.JobAttempt, "job_parse_done").status == "completed"
    finally:
        db.close()


def test_infer_topic_prioritizes_incident_domain_over_broad_noise() -> None:
    from app.services.issues.scoring import infer_topic

    assert infer_topic("대전 한화에어로 공장 화재 사고 국제 주요 이슈") == "재난"
    assert infer_topic("정부 방첩사 해체 및 국방방첩본부 창설 발표 국제 주요 이슈") == "정치"
    assert infer_topic("이창용 한은 총재 퇴임 및 부동산 해결 발언 국제 주요 이슈") == "경제"
    assert infer_topic("양평 특수교사 사건 부실 검증 논란 사전투표 선관위 선거 논란") == "사회"


def test_infer_event_group_groups_ready_korea_training_aliases() -> None:
    from app.services.classification.taxonomy import infer_event_group_name

    expected = "레디코리아 열차 탈선 항공유 폭발 대응 훈련"
    assert infer_event_group_name("행안부 주관 화물열차 탈선 유류누출 폭발 합동훈련") == expected
    assert infer_event_group_name("레디코리아 훈련: 열차 탈선 및 항공유 폭발 대비 실제 같은 재난 대응 훈련") == expected


def test_repair_information_quality_detaches_bad_articles_and_rebuilds_quality() -> None:
    from app.services.issues.repair import repair_information_quality

    db = SessionLocal()
    try:
        issue = models.Issue(
            id="issue_repair_quality",
            title="선관위 투표용지 부족 사태",
            topic="정치",
            status="검증 진행",
            risk="고영향",
            article_count=4,
            quality_score=100,
            quality_status="sufficient",
            event_group_name="AI 정부 감시 서비스",
        )
        relevant = models.Article(
            id="article_relevant_repair",
            issue_id=issue.id,
            title="선관위 투표용지 부족 사태 현장 혼선",
            publisher="연합뉴스",
            url="https://example.com/relevant-repair",
            normalized_url="https://example.com/relevant-repair",
            dedup_hash="relevant-repair",
            content_hash="relevant-repair",
            parse_status="parsed",
        )
        generic = models.Article(
            id="article_generic_repair",
            issue_id=issue.id,
            title="문서뷰어 - 대한민국 정책브리핑",
            publisher="대한민국 정책브리핑",
            url="https://www.korea.kr/archive/expDocView.do",
            normalized_url="https://www.korea.kr/archive/expDocView.do",
            dedup_hash="generic-repair",
            content_hash="generic-repair",
            parse_status="parsed",
        )
        unrelated = models.Article(
            id="article_unrelated_repair",
            issue_id=issue.id,
            title="전세사기피해지원위원회 피해자등 825건 결정",
            publisher="국토교통부",
            url="https://example.com/unrelated-repair",
            normalized_url="https://example.com/unrelated-repair",
            dedup_hash="unrelated-repair",
            content_hash="unrelated-repair",
            parse_status="parsed",
        )
        claimed_unrelated = models.Article(
            id="article_claimed_unrelated_repair",
            issue_id=issue.id,
            title="국가건강정보포털 이달의 건강정보",
            publisher="국가건강정보포털",
            url="https://health.example/claimed",
            normalized_url="https://health.example/claimed",
            dedup_hash="claimed-unrelated-repair",
            content_hash="claimed-unrelated-repair",
            parse_status="parsed",
        )
        db.add_all([issue, relevant, generic, unrelated, claimed_unrelated])
        db.add(
            models.Claim(
                id="claim_claimed_unrelated_repair",
                issue_id=issue.id,
                article_id=claimed_unrelated.id,
                claim_text="오염 기사에서 이미 추출된 주장은 자동 분리하지 않는다.",
            ),
        )
        db.add(
            models.JobAttempt(
                id="job_generic_parse_repair",
                input_json={"article_id": generic.id},
                job_type="parse_article",
                status="queued",
                target_id=generic.id,
            ),
        )
        db.add(
            models.SearchKeyword(
                id="keyword_broad_retry_repair",
                issue_id=issue.id,
                query="AI 정부 감시 서비스 공식자료 [issue:issue_repair_quality]",
                seed_query="AI 정부 감시 서비스",
                source="quality_retry",
                status="active",
                topic="정치",
            ),
        )
        db.commit()

        result = repair_information_quality(db, apply=True, rebuild_all=False)
        db.commit()
        db.refresh(issue)

        assert result["detachedArticles"] == 2
        assert result["skippedClaimLinkedArticles"] == 1
        assert result["parseJobsCompleted"] == 1
        assert result["broadRetryKeywordsDeactivated"] == 1
        assert result["issuesRebuilt"] == 1
        assert db.get(models.Article, generic.id).issue_id is None
        assert db.get(models.Article, unrelated.id).issue_id is None
        assert db.get(models.Article, claimed_unrelated.id).issue_id == issue.id
        assert db.get(models.JobAttempt, "job_generic_parse_repair").status == "completed"
        assert db.get(models.SearchKeyword, "keyword_broad_retry_repair").status == "inactive"
        assert issue.article_count == 2
        assert issue.quality_status == "needs_retry"
        relevance = issue.quality_report_json["signals"]["relevance"]
        assert relevance["totalArticleCount"] == 2
        assert relevance["relevantArticleCount"] == 1
    finally:
        db.close()


def test_repair_information_quality_reclassifies_topic_event_group_and_risk() -> None:
    from app.services.issues.repair import repair_information_quality

    db = SessionLocal()
    try:
        major = models.MajorTopic(
            id="major_repair_taxonomy_disaster",
            name="재난 주요 이슈",
            slug="repair-taxonomy-disaster",
            topic="재난",
        )
        polluted_event = models.EventGroup(
            id="event_repair_taxonomy_polluted",
            major_topic_id=major.id,
            name="대전 한화에어로 공장 화재 사고 대전 한화에어로 공장 화재 사고 대전 유성구에",
            slug="repair-taxonomy-polluted",
            topic="재난",
        )
        issue = models.Issue(
            id="issue_repair_taxonomy",
            title="대전 한화에어로 공장 화재 사고",
            topic="국제",
            status="검증 진행",
            risk="고영향",
            issue_score=95,
            quality_score=100,
            quality_status="sufficient",
            major_topic_name="국제 주요 이슈",
            event_group_name="실제 재난 가정해 범정부 복합재난 대응역량 강화 - 충청메시지 대전 한화에어로 공장",
        )
        db.add_all([major, polluted_event, issue])
        db.add_all(
            [
                models.Article(
                    id="article_repair_taxonomy_a",
                    issue_id=issue.id,
                    title="대전 한화에어로 공장 폭발 화재 사고 원인 조사",
                    publisher="연합뉴스",
                    url="https://example.com/taxonomy-a",
                    normalized_url="https://example.com/taxonomy-a",
                    dedup_hash="repair-taxonomy-a",
                    content_hash="repair-taxonomy-a",
                    parse_status="parsed",
                ),
                models.Article(
                    id="article_repair_taxonomy_b",
                    issue_id=issue.id,
                    title="한화에어로스페이스 대전 공장 화재로 작업자 부상",
                    publisher="대전일보",
                    url="https://example.com/taxonomy-b",
                    normalized_url="https://example.com/taxonomy-b",
                    dedup_hash="repair-taxonomy-b",
                    content_hash="repair-taxonomy-b",
                    parse_status="parsed",
                ),
            ],
        )
        db.commit()

        result = repair_information_quality(db, apply=True, rebuild_all=True)
        db.commit()
        db.refresh(issue)

        assert result["issuesRebuilt"] == 1
        assert issue.topic == "재난"
        assert issue.major_topic_name == "재난 주요 이슈"
        assert issue.event_group_name == "대전 한화에어로 공장 화재 사고"
        assert issue.risk == "일반"
        assert issue.issue_score < 75
    finally:
        db.close()


def test_recommended_ranking_penalizes_high_volume_unverified_issue() -> None:
    from app.services.issues.ranking import score_issue

    noisy = models.Issue(
        article_count=220,
        changed_claims=0,
        cluster_count=0,
        id="issue_noisy_rank",
        issue_score=100,
        needs_review_count=0,
        quality_score=72,
        quality_status="needs_retry",
        risk="고영향",
        status="검증 진행",
        title="오염된 대량 기사 이슈",
        topic="경제",
        verified_count=0,
    )
    grounded = models.Issue(
        article_count=12,
        changed_claims=1,
        cluster_count=3,
        id="issue_grounded_rank",
        issue_score=72,
        needs_review_count=0,
        quality_score=100,
        quality_status="sufficient",
        risk="일반",
        status="검증 진행",
        title="검증된 소규모 이슈",
        topic="경제",
        verified_count=3,
    )

    noisy_score, _ = score_issue(noisy, sort="recommended")
    grounded_score, _ = score_issue(grounded, sort="recommended")

    assert grounded_score > noisy_score


def test_issue_quality_retry_budget_prevents_infinite_research() -> None:
    from app.services.issues.quality import assess_issue_quality

    db = SessionLocal()
    try:
        issue = models.Issue(
            id="issue_quality_budget",
            title="선관위 투표용지 부족 사태",
            topic="정치",
            summary="반복 재검색 예산을 확인합니다.",
            quality_attempts=5,
        )
        db.add(issue)
        db.commit()

        report = assess_issue_quality(db, issue_id=issue.id)
        db.commit()

        assert report["status"] == "exhausted"
        assert issue.quality_status == "exhausted"
        assert not db.scalars(
            select(models.SearchKeyword).where(models.SearchKeyword.issue_id == issue.id)
        ).all()
    finally:
        db.close()


def test_issue_quality_repeated_assessment_does_not_burn_retry_budget_while_pending() -> None:
    from app.services.issues.quality import assess_issue_quality

    db = SessionLocal()
    try:
        issue = models.Issue(
            id="issue_quality_pending",
            title="선관위 투표용지 부족 사태",
            topic="정치",
            summary="재검색 대기 중 반복 평가를 확인합니다.",
        )
        db.add(issue)
        db.add(
            models.Article(
                id="article_quality_pending",
                issue_id=issue.id,
                title="투표용지 부족 논란",
                publisher="테스트뉴스",
                url="https://example.com/quality-pending",
                dedup_hash="quality-pending",
                body_text="투표용지 부족 주장이 제기됐다.",
                summary="투표용지 부족 주장",
                source_type="news",
            )
        )
        db.commit()

        first = assess_issue_quality(db, issue_id=issue.id)
        db.commit()
        first_keyword_count = len(
            db.scalars(
                select(models.SearchKeyword).where(
                    models.SearchKeyword.issue_id == issue.id,
                    models.SearchKeyword.source == "quality_retry",
                )
            ).all()
        )
        first_job_count = len(db.scalars(select(models.JobAttempt)).all())

        second = assess_issue_quality(db, issue_id=issue.id)
        db.commit()

        assert first["status"] == "needs_retry"
        assert second["status"] == "retry_pending"
        assert issue.quality_attempts == 1
        assert issue.quality_status == "needs_retry"
        assert len(
            db.scalars(
                select(models.SearchKeyword).where(
                    models.SearchKeyword.issue_id == issue.id,
                    models.SearchKeyword.source == "quality_retry",
                )
            ).all()
        ) == first_keyword_count
        assert len(db.scalars(select(models.JobAttempt)).all()) == first_job_count
    finally:
        db.close()


def test_issue_quality_deactivates_retry_keywords_when_sufficient_or_exhausted() -> None:
    from app.services.issues.quality import assess_issue_quality

    db = SessionLocal()
    try:
        exhausted = models.Issue(
            id="issue_quality_deactivate_exhausted",
            title="선관위 투표용지 부족 사태",
            topic="정치",
            summary="예산 소진 시 기존 재검색 키워드를 비활성화합니다.",
            quality_attempts=5,
        )
        sufficient = models.Issue(
            id="issue_quality_deactivate_sufficient",
            title="지역 민원 처리 기준 변경",
            topic="사회",
            summary="충분한 기사와 근거를 확보했습니다.",
            confirmed_facts=[{"text": "공식자료와 기사 근거가 연결됐습니다."}],
        )
        db.add_all([exhausted, sufficient])
        db.add_all(
            [
                models.SearchKeyword(
                    id="keyword_quality_exhausted",
                    issue_id=exhausted.id,
                    query="선관위 투표용지 부족 사태 공식자료",
                    seed_query=exhausted.title,
                    source="quality_retry",
                    status="active",
                    topic="정치",
                ),
                models.SearchKeyword(
                    id="keyword_quality_sufficient",
                    issue_id=sufficient.id,
                    query="지역 민원 처리 기준 변경 공식자료",
                    seed_query=sufficient.title,
                    source="quality_retry",
                    status="active",
                    topic="사회",
                ),
            ]
        )
        suffixes = ["가", "나", "다", "라"]
        for index, suffix in enumerate(suffixes):
            db.add(
                models.Article(
                    id=f"article_quality_sufficient_{suffix}",
                    issue_id=sufficient.id,
                    title=f"지역 민원 처리 기준 변경 보도 {suffix}",
                    publisher="공식기관" if index == 0 else f"테스트뉴스{index % 2}",
                    url=f"https://example.com/quality-sufficient-{suffix}",
                    dedup_hash=f"quality-sufficient-{suffix}",
                    body_text="지역 민원 처리 기준 변경 공식자료가 공개됐다.",
                    summary="지역 민원 처리 기준 변경",
                    source_type="official" if index == 0 else "news",
                )
            )
        claim = models.Claim(
            id="claim_quality_sufficient",
            issue_id=sufficient.id,
            claim_text="지역 민원 처리 기준이 변경됐다.",
            verdict="사실",
            confidence=0.9,
        )
        db.add(claim)
        db.add(
            models.Evidence(
                id="evidence_quality_sufficient",
                claim_id=claim.id,
                title="지역 민원 처리 기준 변경 공식자료",
                url="https://example.com/quality-sufficient-evidence",
                source_domain="example.com",
                source_type="official",
                evidence_text="지역 민원 처리 기준 변경을 설명합니다.",
                credibility_score=0.95,
                relevance_score=0.9,
            )
        )
        db.commit()

        exhausted_report = assess_issue_quality(db, issue_id=exhausted.id)
        sufficient_report = assess_issue_quality(db, issue_id=sufficient.id)
        db.commit()

        assert exhausted_report["status"] == "exhausted"
        assert sufficient_report["status"] == "sufficient"
        assert db.get(models.SearchKeyword, "keyword_quality_exhausted").status == "inactive"
        assert db.get(models.SearchKeyword, "keyword_quality_sufficient").status == "inactive"
        assert exhausted.next_quality_retry_at is None
        assert sufficient.next_quality_retry_at is None
    finally:
        db.close()


def test_quality_retry_keywords_do_not_reassign_between_issues() -> None:
    from app.services.issues.quality import assess_issue_quality

    db = SessionLocal()
    try:
        first_issue = models.Issue(
            id="issue_quality_collision_first",
            title="선관위 투표용지 부족 사태",
            topic="정치",
            summary="첫 번째 이슈입니다.",
        )
        second_issue = models.Issue(
            id="issue_quality_collision_second",
            title="선관위 투표용지 부족 사태",
            topic="정치",
            summary="같은 제목의 두 번째 이슈입니다.",
        )
        db.add_all([first_issue, second_issue])
        db.commit()

        first_report = assess_issue_quality(db, issue_id=first_issue.id)
        db.commit()
        first_keyword_ids = [
            keyword.id
            for keyword in db.scalars(
                select(models.SearchKeyword).where(
                    models.SearchKeyword.issue_id == first_issue.id,
                    models.SearchKeyword.source == "quality_retry",
                )
            ).all()
        ]

        second_report = assess_issue_quality(db, issue_id=second_issue.id)
        db.commit()

        first_keywords = db.scalars(
            select(models.SearchKeyword).where(models.SearchKeyword.id.in_(first_keyword_ids))
        ).all()
        second_keywords = db.scalars(
            select(models.SearchKeyword).where(
                models.SearchKeyword.issue_id == second_issue.id,
                models.SearchKeyword.source == "quality_retry",
            )
        ).all()
        assert first_report["status"] == "needs_retry"
        assert second_report["status"] == "needs_retry"
        assert first_keywords
        assert second_keywords
        assert all(keyword.issue_id == first_issue.id for keyword in first_keywords)
    finally:
        db.close()


def test_execute_job_clears_stale_error_after_success(monkeypatch) -> None:
    from app.services import jobs as job_service

    def successful_handler(target_id: str) -> dict:
        return {"status": "completed", "target": target_id}

    monkeypatch.setattr(job_service, "_handlers", lambda: {"test_retry": successful_handler})
    db = SessionLocal()
    try:
        job = models.JobAttempt(
            id="job_retry_success",
            input_json={},
            job_type="test_retry",
            last_error="실행 중단 감지",
            next_run_at=datetime.now(UTC) + timedelta(minutes=5),
            status="failed",
            target_id="target_001",
        )
        db.add(job)
        db.commit()

        job_service.execute_job(db, job=job)
        db.commit()

        assert job.status == "completed"
        assert job.last_error == ""
        assert job.next_run_at is None
        assert job.output_json == {"status": "completed", "target": "target_001"}
    finally:
        db.close()


def test_scheduler_skips_ineligible_quality_retry_keywords() -> None:
    from app.services.jobs import schedule_due_search_jobs

    db = SessionLocal()
    try:
        now = datetime.now(UTC)
        sufficient = models.Issue(
            id="issue_quality_scheduler_sufficient",
            title="충분한 이슈",
            topic="사회",
            quality_status="sufficient",
        )
        future_retry = models.Issue(
            id="issue_quality_scheduler_future",
            title="대기 중 이슈",
            topic="사회",
            quality_status="needs_retry",
            next_quality_retry_at=now + timedelta(minutes=30),
        )
        exhausted = models.Issue(
            id="issue_quality_scheduler_exhausted",
            title="소진된 이슈",
            topic="사회",
            quality_status="exhausted",
        )
        db.add_all([sufficient, future_retry, exhausted])
        db.add_all(
            [
                models.SearchKeyword(
                    id="keyword_quality_scheduler_sufficient",
                    issue_id=sufficient.id,
                    query="충분한 이슈 공식자료",
                    seed_query=sufficient.title,
                    source="quality_retry",
                    status="active",
                    topic="사회",
                ),
                models.SearchKeyword(
                    id="keyword_quality_scheduler_future",
                    issue_id=future_retry.id,
                    query="대기 중 이슈 공식자료",
                    seed_query=future_retry.title,
                    source="quality_retry",
                    status="active",
                    topic="사회",
                ),
                models.SearchKeyword(
                    id="keyword_quality_scheduler_exhausted",
                    issue_id=exhausted.id,
                    query="소진된 이슈 공식자료",
                    seed_query=exhausted.title,
                    source="quality_retry",
                    status="active",
                    topic="사회",
                ),
                models.SearchKeyword(
                    id="keyword_quality_scheduler_missing",
                    issue_id="missing_issue",
                    query="없는 이슈 공식자료",
                    seed_query="없는 이슈",
                    source="quality_retry",
                    status="active",
                    topic="사회",
                ),
            ]
        )
        db.commit()

        jobs = schedule_due_search_jobs(db)
        db.commit()

        assert jobs == []
        assert not db.scalars(select(models.JobAttempt).where(models.JobAttempt.job_type == "search_news")).all()
    finally:
        db.close()


def test_scheduler_deactivates_low_quality_short_keywords() -> None:
    from app.services.jobs import schedule_due_search_jobs

    db = SessionLocal()
    try:
        keyword = models.SearchKeyword(
            id="keyword_short_noise",
            issue_id="issue_noise",
            priority="normal",
            query="고",
            seed_query="고유가 지원금 지급 논란",
            source="discovery",
            status="active",
            topic="경제",
        )
        db.add(keyword)
        db.commit()

        jobs = schedule_due_search_jobs(db)
        db.commit()

        saved = db.get(models.SearchKeyword, "keyword_short_noise")
        assert jobs == []
        assert saved is not None
        assert saved.status == "inactive"
        assert saved.metadata_json["deactivated_reason"] == "low_quality_query"
        assert db.scalar(select(models.JobAttempt).where(models.JobAttempt.target_id == "keyword_short_noise")) is None
    finally:
        db.close()


def test_stale_queued_quality_retry_search_job_skips_without_collecting(monkeypatch) -> None:
    def fail_if_collected(query: str, **kwargs) -> list[CollectedArticle]:
        raise AssertionError(f"stale quality retry search collected: {query}")

    monkeypatch.setattr(issue_jobs, "collect_google_news_search", fail_if_collected)

    db = SessionLocal()
    try:
        issue = models.Issue(
            id="issue_quality_stale_job",
            title="선관위 투표용지 부족 사태",
            topic="정치",
            quality_status="needs_retry",
        )
        keyword = models.SearchKeyword(
            id="keyword_quality_stale_job",
            issue_id=issue.id,
            query="선관위 투표용지 부족 사태 공식자료 [issue:issue_quality_stale_job]",
            seed_query=issue.title,
            source="quality_retry",
            status="active",
            topic="정치",
            metadata_json={"search_queries": ["선관위 투표용지 부족 사태 공식자료"]},
        )
        job = models.JobAttempt(
            id="job_quality_stale_search",
            input_json={"keyword_id": keyword.id},
            job_type="search_news",
            status="queued",
            target_id=keyword.id,
        )
        db.add_all([issue, keyword, job])
        db.commit()

        issue.quality_status = "sufficient"
        db.commit()

        run_due_jobs(db, limit=10)
        db.commit()

        db.refresh(job)
        db.refresh(keyword)
        assert job.status == "skipped"
        assert job.output_json["status"] == "skipped"
        assert job.output_json["article_count"] == 0
        assert job.output_json["reason"] == "issue_quality_status"
        assert keyword.last_searched_at is None
        assert db.scalars(select(models.CollectorRun)).all() == []
        assert not db.scalars(
            select(models.JobAttempt).where(
                models.JobAttempt.job_type == "assess_issue_quality",
                models.JobAttempt.target_id == issue.id,
            )
        ).all()
    finally:
        db.close()


def test_claims_cluster_by_prd_issue_bucket_not_each_sentence() -> None:
    db = SessionLocal()
    try:
        db.add(
            models.Issue(
                id="issue_cluster_bucket",
                summary="투표용지 부족 수치가 보도마다 다릅니다.",
                title="선관위 투표용지 부족 사태",
                topic="정치",
            ),
        )
        db.flush()

        first = create_claim_from_text(
            db,
            claim_type="수치 주장",
            entities_json={"numbers": ["50"], "dates": [], "organizations": ["선관위"], "places": []},
            issue_id="issue_cluster_bucket",
            source_kind="article",
            text="선관위는 투표용지 부족 투표소가 50곳이라고 발표했다.",
        )
        second = create_claim_from_text(
            db,
            claim_type="수치 주장",
            entities_json={"numbers": ["91"], "dates": [], "organizations": ["선관위"], "places": []},
            issue_id="issue_cluster_bucket",
            source_kind="article",
            text="후속 보도에서는 투표용지 부족 투표소가 91곳으로 늘었다.",
        )
        db.commit()

        assert first.cluster_id == second.cluster_id
        cluster = db.get(models.ClaimCluster, first.cluster_id)
        assert cluster is not None
        assert cluster.title == "발생 규모와 수치"
    finally:
        db.close()


def test_claim_embedding_runs_before_claim_insert(monkeypatch) -> None:
    from app.services.claims import workflow as claim_workflow

    claim_insert_seen = False

    def collect_claim_insert(_conn, _cursor, statement, _parameters, _context, _executemany) -> None:
        nonlocal claim_insert_seen
        if statement.strip().lower().startswith("insert into claims"):
            claim_insert_seen = True

    def fake_embed(_db, claim: models.Claim) -> None:
        assert claim_insert_seen is False
        claim.embedding = [0.1, 0.2]

    monkeypatch.setattr(claim_workflow, "embed_claim_if_possible", fake_embed)
    event.listen(engine, "before_cursor_execute", collect_claim_insert)
    db = SessionLocal()
    try:
        db.add(
            models.Issue(
                id="issue_claim_flush_order",
                summary="투표용지 부족 수치가 보도마다 다릅니다.",
                title="선관위 투표용지 부족 사태",
                topic="정치",
            ),
        )
        db.flush()

        claim = create_claim_from_text(
            db,
            claim_type="수치 주장",
            issue_id="issue_claim_flush_order",
            source_kind="article",
            text="선관위는 투표용지 부족 투표소가 50곳이라고 발표했다.",
        )
        db.commit()

        assert claim.embedding == [0.1, 0.2]
        assert claim_insert_seen is True
    finally:
        event.remove(engine, "before_cursor_execute", collect_claim_insert)
        db.close()


def test_retrieve_evidence_defers_flush_until_caller(monkeypatch) -> None:
    from app.services.evidence import retriever

    evidence_inserts: list[str] = []

    def collect_evidence_insert(_conn, _cursor, statement, _parameters, _context, _executemany) -> None:
        if statement.strip().lower().startswith("insert into evidences"):
            evidence_inserts.append(statement)

    monkeypatch.setattr(
        retriever.DeepSeekAnalysisService,
        "generate_evidence_candidates",
        lambda self, **_kwargs: [],
    )
    event.listen(engine, "before_cursor_execute", collect_evidence_insert)
    db = SessionLocal()
    try:
        issue = models.Issue(
            id="issue_evidence_flush_order",
            summary="공식자료가 필요한 이슈입니다.",
            title="선관위 투표용지 부족 사태",
            topic="정치",
        )
        source = models.SourceDomain(
            id="source_evidence_flush_order",
            collection_url="https://www.nec.go.kr",
            credibility=0.9,
            domain="nec.go.kr",
            name="중앙선거관리위원회",
            source_type="official",
            status="trusted",
        )
        claim = models.Claim(
            id="claim_evidence_flush_order",
            claim_text="선관위는 투표용지 부족 사태에 대한 공식 설명자료를 냈다.",
            issue_id=issue.id,
            sanitized_text="선관위는 투표용지 부족 사태에 대한 공식 설명자료를 냈다.",
            source_kind="article",
        )
        db.add_all([issue, source, claim])
        db.commit()

        evidences = retriever.retrieve_evidence_for_claim(db, claim=claim)

        assert evidences
        assert evidence_inserts == []
        db.flush()
        assert evidence_inserts
    finally:
        event.remove(engine, "before_cursor_execute", collect_evidence_insert)
        db.close()


def test_retrieve_evidence_uses_only_real_documents_from_ai_candidates(monkeypatch) -> None:
    from app.services.evidence import retriever

    def fake_candidates(self, **_kwargs) -> list[dict]:
        return [
            {
                "document_id": "source:source_evidence_registry_only",
                "evidence_text": "공식 사이트에서 확인이 필요합니다.",
                "relevance_score": 0.91,
                "title": "중앙선거관리위원회 출처 후보",
            },
            {
                "document_id": "article:article_evidence_real_doc",
                "evidence_text": "선관위는 투표용지 부족 민원에 대해 설명자료를 냈다.",
                "relevance_score": 0.88,
                "title": "선관위 설명자료 보도",
            },
        ]

    monkeypatch.setattr(retriever.DeepSeekAnalysisService, "generate_evidence_candidates", fake_candidates)
    db = SessionLocal()
    try:
        issue = models.Issue(
            id="issue_evidence_real_documents",
            summary="공식자료와 보도자료 구분이 필요합니다.",
            title="선관위 투표용지 부족 사태",
            topic="정치",
        )
        source = models.SourceDomain(
            id="source_evidence_registry_only",
            collection_url="https://www.nec.go.kr",
            credibility=0.95,
            domain="nec.go.kr",
            name="중앙선거관리위원회",
            source_type="official",
            status="trusted",
        )
        article = models.Article(
            body_text="선관위는 투표용지 부족 민원에 대해 설명자료를 냈다.",
            dedup_hash="article-evidence-real-doc",
            id="article_evidence_real_doc",
            issue_id=issue.id,
            publisher="테스트뉴스",
            source_type="news",
            summary="선관위 설명자료 보도",
            title="선관위 설명자료 보도",
            url="https://example.com/evidence-real-doc",
        )
        claim = models.Claim(
            id="claim_evidence_real_documents",
            claim_text="선관위는 투표용지 부족 사태에 대한 공식 설명자료를 냈다.",
            issue_id=issue.id,
            sanitized_text="선관위는 투표용지 부족 사태에 대한 공식 설명자료를 냈다.",
            source_kind="article",
        )
        db.add_all([issue, source, article, claim])
        db.commit()

        evidences = retriever.retrieve_evidence_for_claim(db, claim=claim)

        assert len(evidences) == 1
        assert evidences[0].retrieval_json["documentId"] == "article:article_evidence_real_doc"
        assert not evidences[0].retrieval_json["documentId"].startswith("source:")
    finally:
        db.close()


def test_retrieve_evidence_falls_back_when_ai_candidates_are_not_real_documents(monkeypatch) -> None:
    from app.services.evidence import retriever

    def fake_candidates(self, **_kwargs) -> list[dict]:
        return [
            {
                "document_id": "source:source_evidence_fallback_only",
                "evidence_text": "공식 사이트에서 확인이 필요합니다.",
                "relevance_score": 0.91,
                "title": "중앙선거관리위원회 출처 후보",
            },
        ]

    monkeypatch.setattr(retriever.DeepSeekAnalysisService, "generate_evidence_candidates", fake_candidates)
    db = SessionLocal()
    try:
        issue = models.Issue(
            id="issue_evidence_invalid_ai_fallback",
            summary="AI 후보가 실제 문서가 아닐 때 fallback이 필요합니다.",
            title="선관위 투표용지 부족 사태",
            topic="정치",
        )
        source = models.SourceDomain(
            id="source_evidence_fallback_only",
            collection_url="https://www.nec.go.kr",
            credibility=0.95,
            domain="nec.go.kr",
            name="중앙선거관리위원회",
            source_type="official",
            status="trusted",
        )
        article = models.Article(
            body_text="선관위 투표용지 부족 사태에 대한 기사 본문입니다.",
            dedup_hash="article-evidence-invalid-ai-fallback",
            id="article_evidence_invalid_ai_fallback",
            issue_id=issue.id,
            publisher="테스트뉴스",
            source_type="news",
            summary="투표용지 부족 후속 보도",
            title="투표용지 부족 후속 보도",
            url="https://example.com/evidence-invalid-ai-fallback",
        )
        claim = models.Claim(
            article_id=article.id,
            id="claim_evidence_invalid_ai_fallback",
            claim_text="선관위 투표용지 부족 사태에 대한 후속 보도가 있었다.",
            issue_id=issue.id,
            sanitized_text="선관위 투표용지 부족 사태에 대한 후속 보도가 있었다.",
            source_kind="article",
        )
        db.add_all([issue, source, article, claim])
        db.commit()

        evidences = retriever.retrieve_evidence_for_claim(db, claim=claim)

        assert any(evidence.url == article.url for evidence in evidences)
    finally:
        db.close()


def test_issue_timeline_lists_reported_events_without_processing_logs() -> None:
    db = SessionLocal()
    try:
        base_time = datetime(2026, 6, 8, 9, 0, tzinfo=UTC)
        db.add(
            models.Issue(
                id="issue_timeline",
                summary="후속 보도 흐름을 확인합니다.",
                title="선관위 투표용지 부족 사태",
                topic="정치",
            ),
        )
        db.add_all(
            [
                models.Article(
                    body_text="2026.06.08 07:30 일부 투표소에서 투표용지 부족 신고가 접수됐다. 초기 보도는 투표용지 부족 투표소를 50곳으로 설명했다.",
                    collected_at=base_time,
                    dedup_hash="timeline-article-1",
                    id="article_timeline_1",
                    issue_id="issue_timeline",
                    published_at=base_time,
                    publisher="테스트뉴스",
                    source_type="news",
                    summary="50곳 초기 보도",
                    title="투표용지 부족 50곳 초기 보도",
                    url="https://example.com/timeline-1",
                ),
                models.Article(
                    body_text="2026.06.08 10:40 선관위는 부족 신고 대상이 91곳으로 늘었다고 밝혔다. 후속 보도는 투표용지 부족 투표소를 91곳으로 설명했다.",
                    collected_at=base_time + timedelta(hours=2),
                    dedup_hash="timeline-article-2",
                    id="article_timeline_2",
                    issue_id="issue_timeline",
                    published_at=base_time + timedelta(hours=2),
                    publisher="테스트뉴스",
                    source_type="news",
                    summary="91곳 후속 보도",
                    title="투표용지 부족 91곳 후속 보도",
                    url="https://example.com/timeline-2",
                ),
                models.UpdateLog(
                    created_at=base_time + timedelta(hours=3),
                    description="후속 보도 기준으로 수치 확인이 필요합니다.",
                    id="update_timeline_1",
                    issue_id="issue_timeline",
                    title="후속 보도 반영",
                    update_type="new_article",
                ),
            ],
        )
        db.commit()

        _, cache = build_issue_cache_payload(db, issue_id="issue_timeline")
        timeline_ids = [event["id"] for event in cache["timeline"]]

        assert all(event_id.startswith("event:") for event_id in timeline_ids)
        assert cache["timeline"][0]["occurredAt"] == "2026-06-08T07:30:00+00:00"
        assert cache["timeline"][1]["occurredAt"] == "2026-06-08T10:40:00+00:00"
        assert all("주장 추출" not in event["description"] for event in cache["timeline"])
        assert all("새 기사 반영" not in event["title"] for event in cache["timeline"])
    finally:
        db.close()


def test_issue_timeline_extracts_multiple_real_world_events_from_one_article() -> None:
    db = SessionLocal()
    try:
        published_at = datetime(2026, 6, 8, 13, 0, tzinfo=UTC)
        db.add(
            models.Issue(
                id="issue_real_timeline",
                summary="현실 사건 진행을 확인합니다.",
                title="선관위 투표용지 부족 사태",
                topic="정치",
            ),
        )
        db.add(
            models.Article(
                body_text=(
                    "6월 8일 오전 7시 일부 투표소에서 투표용지 부족 신고가 접수됐다. "
                    "6월 8일 오전 9시 선관위는 부족 신고 대상이 50곳이라고 발표했다. "
                    "6월 8일 오전 11시 경찰은 관련 고발 사건 조사에 착수했다."
                ),
                collected_at=published_at,
                dedup_hash="real-timeline-article",
                id="article_real_timeline",
                issue_id="issue_real_timeline",
                published_at=published_at,
                publisher="테스트뉴스",
                source_type="news",
                summary="투표용지 부족 사건 진행",
                title="투표용지 부족 사태 종합",
                url="https://example.com/real-timeline",
            ),
        )
        db.commit()

        _, cache = build_issue_cache_payload(db, issue_id="issue_real_timeline")

        assert [event["occurredAt"] for event in cache["timeline"]] == [
            "2026-06-08T07:00:00+00:00",
            "2026-06-08T09:00:00+00:00",
            "2026-06-08T11:00:00+00:00",
        ]
        assert [event["type"] for event in cache["timeline"]] == [
            "incident_event",
            "official_statement",
            "followup_action",
        ]
        assert "투표용지 부족 사태 종합" not in [event["title"] for event in cache["timeline"]]
        assert all("기사" not in event["description"] for event in cache["timeline"])
    finally:
        db.close()


def test_issue_synthesis_enriches_summary_and_missing_signals_without_inventing_facts() -> None:
    from app.services.issues.synthesis import synthesize_issue_cache

    db = SessionLocal()
    try:
        issue = models.Issue(
            id="issue_synthesis",
            title="선관위 투표용지 부족 사태",
            topic="정치",
            summary="",
        )
        article = models.Article(
            id="article_synthesis",
            issue_id=issue.id,
            title="투표용지 부족 후속 보도",
            publisher="테스트뉴스",
            url="https://example.com/synthesis",
            dedup_hash="synthesis",
            body_text="선관위 투표용지 부족 문제와 후속 감사 가능성이 보도됐다.",
            summary="후속 감사 가능성 보도",
        )
        claim = models.Claim(
            id="claim_synthesis",
            issue_id=issue.id,
            article_id=article.id,
            claim_text="투표용지 부족 문제가 일부 투표소에서 발생했다.",
            sanitized_text="투표용지 부족 문제가 일부 투표소에서 발생했다.",
            claim_type="사실 주장",
            verdict="근거 부족",
            status="needs_evidence",
        )
        db.add_all([issue, article, claim])
        db.commit()

        _, cache = build_issue_cache_payload(db, issue_id=issue.id)
        enriched = synthesize_issue_cache(db, issue=issue, payload=cache)

        assert enriched is not cache
        assert "1개 기사" in enriched["computed_summary"]
        assert "officialCoverage" in enriched["quality"]["missingSignals"]
        assert enriched["confirmed_facts"] == []
    finally:
        db.close()


def test_issue_synthesis_merges_ai_detail_sections(monkeypatch) -> None:
    from app.services.issues.synthesis import synthesize_issue_cache

    def fake_detail(self, **_kwargs) -> dict:
        return {
            "summary": "AI가 공급된 기록만 바탕으로 요약한 사건 설명입니다.",
            "missing_context": ["공식 발표 원문", "후속 감사 일정"],
            "section_map": {
                "issue_map": "투표용지 부족 발생 범위와 사후 대응이 핵심 쟁점입니다.",
                "claim_verification": "주장별 근거와 판정을 분리해야 합니다.",
                "article_comparison": "언론사별 기사 차이는 발생 장소와 수치 기준입니다.",
                "timeline": "초기 보도 이후 공식 설명과 후속 조치가 이어졌습니다.",
                "number_changes": "초기 수치와 후속 수치의 기준 차이를 표시해야 합니다.",
            },
            "confirmed_facts": [],
        }

    monkeypatch.setattr(DeepSeekAnalysisService, "synthesize_issue_detail", fake_detail)
    db = SessionLocal()
    try:
        issue = models.Issue(
            id="issue_ai_synthesis_sections",
            title="선관위 투표용지 부족 사태",
            topic="정치",
            summary="",
        )
        db.add(issue)
        db.commit()

        payload = {
            "article_count": 2,
            "articles": [{"id": "article_a", "title": "후속 보도", "outlet": "테스트뉴스"}],
            "changed_claims": 0,
            "claim_clusters": [],
            "claims": [],
            "cluster_count": 0,
            "computed_summary": "",
            "confirmed_facts": [],
            "evidences": [],
            "needs_review_count": 0,
            "number_changes": [],
            "perspectives": [],
            "source_documents": [],
            "timeline": [],
            "verified_count": 0,
        }

        enriched = synthesize_issue_cache(db, issue=issue, payload=payload)

        assert enriched["computed_summary"] == "AI가 공급된 기록만 바탕으로 요약한 사건 설명입니다."
        assert enriched["ai_synthesis"]["sectionMap"]["issue_map"].startswith("투표용지 부족")
        assert "공식 발표 원문" in enriched["ai_synthesis"]["missingContext"]
    finally:
        db.close()


def test_refresh_issue_cache_preserves_existing_ai_synthesis_when_ai_unavailable(monkeypatch) -> None:
    from app.services.issues.page_builder import refresh_issue_cache

    monkeypatch.setattr(DeepSeekAnalysisService, "synthesize_issue_detail", lambda self, **_kwargs: None)
    existing_synthesis = {
        "missingContext": ["공식 원문"],
        "sectionMap": {"issue_map": "기존 쟁점 지도"},
        "summary": "기존 AI 상세 합성",
    }
    db = SessionLocal()
    try:
        issue = models.Issue(
            id="issue_preserve_ai_synthesis",
            quality_report_json={"aiSynthesis": existing_synthesis, "score": 77},
            summary="",
            title="선관위 투표용지 부족 사태",
            topic="정치",
        )
        article = models.Article(
            body_text="선관위 투표용지 부족 후속 보도입니다.",
            dedup_hash="preserve-ai-synthesis",
            id="article_preserve_ai_synthesis",
            issue_id=issue.id,
            publisher="테스트뉴스",
            source_type="news",
            summary="후속 보도",
            title="후속 보도",
            url="https://example.com/preserve-ai-synthesis",
        )
        db.add_all([issue, article])
        db.commit()

        refreshed = refresh_issue_cache(db, issue_id=issue.id)

        assert refreshed is not None
        assert refreshed.quality_report_json["aiSynthesis"] == existing_synthesis
    finally:
        db.close()


def test_refresh_issue_cache_quality_uses_db_grounded_confirmed_facts() -> None:
    from app.services.issues.page_builder import refresh_issue_cache

    db = SessionLocal()
    try:
        issue = models.Issue(
            id="issue_grounded_quality",
            title="선관위 투표용지 부족 사태",
            topic="정치",
            summary="검증된 근거가 연결된 주장입니다.",
        )
        article = models.Article(
            id="article_grounded_quality",
            issue_id=issue.id,
            title="투표용지 부족 공식 확인",
            publisher="테스트뉴스",
            url="https://example.com/grounded-quality",
            dedup_hash="grounded-quality",
            body_text="투표용지 부족 문제가 일부 투표소에서 발생했다는 공식 근거가 제시됐다.",
            summary="공식 근거 확인",
        )
        claim = models.Claim(
            id="claim_grounded_quality",
            issue_id=issue.id,
            article_id=article.id,
            claim_text="투표용지 부족 문제가 일부 투표소에서 발생했다.",
            sanitized_text="투표용지 부족 문제가 일부 투표소에서 발생했다.",
            claim_type="사실 주장",
            verdict="사실",
            status="verified",
        )
        evidence = models.Evidence(
            id="evidence_grounded_quality",
            claim_id=claim.id,
            title="투표용지 부족 공식 확인 자료",
            url="https://example.com/grounded-quality/evidence",
            source_domain="example.com",
            source_type="official",
            evidence_text="일부 투표소에서 투표용지 부족 문제가 발생했다는 확인 자료입니다.",
            credibility_score=0.95,
            relevance_score=0.9,
        )
        db.add_all([issue, article, claim, evidence])
        db.commit()

        refreshed = refresh_issue_cache(db, issue_id=issue.id)

        assert refreshed is not None
        assert refreshed.confirmed_facts
        assert refreshed.confirmed_facts[0]["claimId"] == claim.id
        assert "confirmedFacts" not in refreshed.quality_report_json["missingSignals"]
    finally:
        db.close()


def test_signup_login_and_dashboard() -> None:
    with TestClient(app) as client:
        session = signup(client)
        assert session["user"]["role"] == "admin"
        token = session["accessToken"]

        me = client.get("/v1/users/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200
        assert me.json()["email"] == "admin@example.com"

        login = client.post(
            "/v1/auth/login",
            json={"email": "admin@example.com", "password": "password123"},
        )
        assert login.status_code == 200

        dashboard = client.get(
            "/v1/users/me/dashboard",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert dashboard.status_code == 200
        assert dashboard.json()["savedIssues"] == []


def test_verification_request_accepts_article_url() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/v1/verification-requests",
            json={"articleUrl": "https://example.com/news/1"},
        )
        assert response.status_code == 201
        payload = response.json()
        assert payload["status"] == "queued"
        assert payload["message"] == "분석 요청이 접수되었습니다."


def test_admin_requires_reviewer_role() -> None:
    with TestClient(app) as client:
        admin_session = signup(client, "admin@example.com")
        admin_token = admin_session["accessToken"]

        user_session = signup(client, "user@example.com")
        user_token = user_session["accessToken"]

        forbidden = client.get(
            "/v1/admin/dashboard",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert forbidden.status_code == 403

        ok = client.get(
            "/v1/admin/dashboard",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert ok.status_code == 200
        assert ok.json()["queue"] == []


def test_api_spec_contract_all_declared_endpoints() -> None:
    with TestClient(app) as client:
        admin_session = signup(client, "admin@example.com")
        admin_token = admin_session["accessToken"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        seed_contract_records(admin_session["user"]["id"])

        login = client.post(
            "/v1/auth/login",
            json={"email": "admin@example.com", "password": "password123"},
        )
        assert login.status_code == 200
        assert {"accessToken", "expiresAt", "user"} <= login.json().keys()

        me = client.get("/v1/users/me", headers=admin_headers)
        assert me.status_code == 200
        assert {"id", "email", "name", "role"} <= me.json().keys()

        profile = client.patch("/v1/users/me", headers=admin_headers, json={"name": "검토자"})
        assert profile.status_code == 200
        assert profile.json()["name"] == "검토자"

        dashboard = client.get("/v1/users/me/dashboard", headers=admin_headers)
        assert dashboard.status_code == 200
        assert {"user", "savedIssues", "submittedClaims", "verificationRequests"} <= dashboard.json().keys()

        save = client.put("/v1/users/me/saved-issues/issue_001", headers=admin_headers)
        assert save.status_code == 200
        assert save.json()["status"] == "updated"

        notifications = client.get("/v1/users/me/notifications", headers=admin_headers)
        assert notifications.status_code == 200
        assert {"notifications", "settings", "followedIssues"} <= notifications.json().keys()

        preferences = client.patch(
            "/v1/users/me/preferences",
            headers=admin_headers,
            json={"preferredPerspective": "공식 자료 우선", "dailyDigest": True},
        )
        assert preferences.status_code == 200
        assert preferences.json()["status"] == "updated"

        home = client.get("/v1/issues/home?topic=정치&issueId=issue_001&q=공공")
        assert home.status_code == 200
        assert home.json()["selectedIssue"]["id"] == "issue_001"
        assert "issueGroups" in home.json()

        issue = client.get("/v1/issues/issue_001")
        assert issue.status_code == 200
        assert {"issue", "relatedIssues"} <= issue.json().keys()
        assert "numberChanges" in issue.json()["issue"]

        verification = client.post(
            "/v1/verification-requests",
            headers=admin_headers,
            json={"articleUrl": "https://example.com/news/002", "issueId": "issue_001"},
        )
        assert verification.status_code == 201
        created_request_id = verification.json()["id"]
        assert verification.json()["matchedIssueId"] == "issue_001"

        claim = client.post(
            "/v1/issues/issue_001/claims",
            headers=admin_headers,
            json={
                "issueId": "issue_001",
                "claimText": "일부 현장에서 절차가 지연되었다.",
                "reason": "후속 기사 기준이 기존 발표와 다릅니다.",
                "evidenceUrl": "https://example.com/source",
                "relatedCluster": "현장 절차 지연",
                "claimType": "수치",
                "refutablePoint": "현장별 처리 시각이 확인되면 판정이 바뀔 수 있습니다.",
            },
        )
        assert claim.status_code == 201
        created_claim_id = claim.json()["id"]
        assert claim.json()["status"] == "received"

        report = client.post("/v1/issues/issue_001/report", headers=admin_headers)
        assert report.status_code == 201
        assert {
            "id",
            "issueId",
            "status",
            "downloadUrl",
            "markdownUrl",
            "shareUrl",
            "message",
        } <= report.json().keys()
        markdown = client.get(report.json()["markdownUrl"])
        assert markdown.status_code == 200
        assert "# 고영향 공공 이슈 A" in markdown.text

        content_report = client.post(
            "/v1/issues/issue_001/content-reports",
            headers=admin_headers,
            json={
                "excerpt": "전국적으로 동일 문제가 대규모로 발생했다.",
                "reason": "후속 공식자료와 다른 표현입니다.",
                "reportType": "wrong_verdict",
                "targetId": "claim_public_001",
            },
        )
        assert content_report.status_code == 201
        assert content_report.json()["status"] == "received"

        metric_event = client.post(
            "/v1/analytics/events",
            headers=admin_headers,
            json={
                "eventType": "report_view",
                "issueId": "issue_001",
                "reportId": report.json()["id"],
                "metadata": {"surface": "contract-test"},
            },
        )
        assert metric_event.status_code == 201
        assert metric_event.json()["status"] == "created"

        admin_dashboard = client.get("/v1/admin/dashboard", headers=admin_headers)
        assert admin_dashboard.status_code == 200
        assert {"metrics", "navItems", "queue", "selectedIssue", "claims", "claimClusters", "evidences", "agentRuns"} <= admin_dashboard.json().keys()
        assert any(metric["label"] == "제품 지표" for metric in admin_dashboard.json()["metrics"])

        sync = client.post("/v1/admin/queue/sync", headers=admin_headers)
        assert sync.status_code == 200
        assert sync.json()["message"] == "큐 동기화를 시작했습니다."

        admin_issue = client.get("/v1/admin/issues/issue_001", headers=admin_headers)
        assert admin_issue.status_code == 200
        assert {"issue", "publicIssue", "queue", "claims", "claimClusters", "evidences", "articles", "timeline", "reports"} <= admin_issue.json().keys()

        representative_image = client.post(
            "/v1/admin/issues/issue_001/representative-image",
            headers=admin_headers,
            json={
                "source": "한겨레",
                "sourceUrl": "https://www.hani.co.kr/news/article.html",
                "url": "https://img.hani.co.kr/manual-representative.jpg",
            },
        )
        assert representative_image.status_code == 200
        assert representative_image.json()["message"] == "대표 이미지를 지정했습니다."
        admin_issue_with_image = client.get("/v1/admin/issues/issue_001", headers=admin_headers)
        assert admin_issue_with_image.status_code == 200
        assert (
            admin_issue_with_image.json()["publicIssue"]["representativeImageUrl"]
            == "https://img.hani.co.kr/manual-representative.jpg"
        )

        reverify = client.post(
            "/v1/admin/issues/issue_001/reverify",
            headers=admin_headers,
            json={"priority": "high", "memo": "공식자료 기준 업데이트 후 판정 재계산"},
        )
        assert reverify.status_code == 200
        assert reverify.json()["message"] == "재검증 작업이 큐에 등록되었습니다."

        approve = client.post("/v1/admin/issues/issue_001/approve", headers=admin_headers)
        assert approve.status_code == 200
        assert approve.json()["message"] == "출고 승인되었습니다."

        admin_reports = client.get("/v1/admin/reports", headers=admin_headers)
        assert admin_reports.status_code == 200
        assert any(report["id"] == "report-001" for report in admin_reports.json()["reports"])

        resolve = client.post(
            "/v1/admin/reports/report-001/resolve",
            headers=admin_headers,
            json={"status": "resolved"},
        )
        assert resolve.status_code == 200
        assert resolve.json()["status"] == "updated"

        admin_sources = client.get("/v1/admin/sources", headers=admin_headers)
        assert admin_sources.status_code == 200
        assert admin_sources.json()["sources"][0]["id"] == "domain-001"
        assert admin_sources.json()["sources"][0]["isActive"] is True

        source_create = client.post(
            "/v1/admin/sources",
            headers=admin_headers,
            json={
                "collectionIntervalMinutes": 15,
                "collectionUrl": "https://example.org/rss",
                "credibility": 0.7,
                "domain": "example.org",
                "isActive": True,
                "name": "추가 출처",
                "note": "수집 테스트",
                "sourceType": "rss",
                "status": "watch",
            },
        )
        assert source_create.status_code == 201
        assert source_create.json()["domain"] == "example.org"

        source_update = client.patch(
            "/v1/admin/sources/domain-001",
            headers=admin_headers,
            json={
                "collectionIntervalMinutes": 20,
                "collectionUrl": "https://example.com/feed",
                "domain": "example.com",
                "isActive": False,
                "name": "예시 출처 수정",
                "note": "수정된 메모",
                "sourceType": "rss",
                "status": "watch",
            },
        )
        assert source_update.status_code == 200
        assert source_update.json()["status"] == "updated"

        admin_settings = client.get("/v1/admin/settings", headers=admin_headers)
        assert admin_settings.status_code == 200
        assert {"groups", "updatedAt"} <= admin_settings.json().keys()
        initial_setting_items = [
            item
            for group in admin_settings.json()["groups"]
            for item in group["items"]
        ]
        sensitive_policy = next(
            item
            for item in initial_setting_items
            if item["key"] == "podcast_sensitive_topics_require_official_source"
        )
        quality_score = next(
            item
            for item in initial_setting_items
            if item["key"] == "podcast_min_publish_quality_score"
        )
        recommendation_weight = next(
            item
            for item in initial_setting_items
            if item["key"] == "podcast_recommendation_impact_weight"
        )
        assert sensitive_policy["value"] is True
        assert quality_score["value"] == 70
        assert recommendation_weight["value"] == 0.35

        settings_update = client.patch(
            "/v1/admin/settings",
            headers=admin_headers,
            json={
                "settings": [
                    {"key": "issue_candidate_threshold", "value": 42},
                    {"key": "openai_api_key", "value": "sk-test-key"},
                ],
            },
        )
        assert settings_update.status_code == 200
        setting_items = [
            item
            for group in settings_update.json()["groups"]
            for item in group["items"]
        ]
        candidate_threshold = next(item for item in setting_items if item["key"] == "issue_candidate_threshold")
        openai_key = next(item for item in setting_items if item["key"] == "openai_api_key")
        assert candidate_threshold["value"] == 42
        assert candidate_threshold["source"] == "admin"
        assert openai_key["value"] is None
        assert openai_key["configured"] is True

        admin_agents = client.get("/v1/admin/agents", headers=admin_headers)
        assert admin_agents.status_code == 200
        assert {"agentRuns", "recentEvents"} <= admin_agents.json().keys()

        agent_run = client.post(
            "/v1/admin/agents/run",
            headers=admin_headers,
            json={"agent": "News Watcher"},
        )
        assert agent_run.status_code == 200
        assert agent_run.json()["status"] == "queued"

        delete_saved = client.delete("/v1/users/me/saved-issues/issue_001", headers=admin_headers)
        assert delete_saved.status_code == 200

        delete_claim = client.delete(f"/v1/users/me/submitted-claims/{created_claim_id}", headers=admin_headers)
        assert delete_claim.status_code == 200

        delete_request = client.delete(f"/v1/users/me/verification-requests/{created_request_id}", headers=admin_headers)
        assert delete_request.status_code == 200


def test_api_error_response_uses_spec_shape() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/v1/verification-requests",
            json={"articleUrl": "not-a-url"},
        )
        assert response.status_code == 422
        assert {"message", "code", "details"} <= response.json().keys()
        assert "detail" not in response.json()


def test_manual_text_check_creates_claims_updates_and_notifications() -> None:
    with TestClient(app) as client:
        session = signup(client, "admin@example.com")
        token = session["accessToken"]
        headers = {"Authorization": f"Bearer {token}"}
        seed_contract_records(session["user"]["id"])

        subscribe = client.post("/v1/issues/issue_001/subscribe", headers=headers)
        assert subscribe.status_code == 200

        check = client.post(
            "/v1/checks",
            headers=headers,
            json={
                "inputType": "text",
                "content": "관계 기관은 5곳에서 절차 지연이 발생했다고 발표했다.",
                "issueId": "issue_001",
            },
        )
        assert check.status_code == 201
        assert check.json()["status"] == "queued"
        wait_for_check_result(client, check.json()["id"])

        clusters = client.get("/v1/issues/issue_001/claim-clusters")
        assert clusters.status_code == 200
        assert len(clusters.json()["claimClusters"]) >= 1

        updates = client.get("/v1/issues/issue_001/updates")
        assert updates.status_code == 200
        assert any(item["type"] == "new_article" for item in updates.json()["updates"])

        notifications = client.get("/v1/users/me/notifications", headers=headers)
        assert notifications.status_code == 200
        assert len(notifications.json()["notifications"]) >= 1


def test_process_article_survives_taxonomy_classification_failure(monkeypatch) -> None:
    def failing_classification(db, *, issue, title: str = "", summary: str = ""):
        raise RuntimeError("taxonomy offline")

    monkeypatch.setattr(issue_jobs, "classify_issue_taxonomy", failing_classification)
    monkeypatch.setattr(issue_jobs, "extract_claims_for_article", lambda db, *, article: [])

    db = SessionLocal()
    try:
        db.add_all(
            [
                models.Issue(
                    id="issue_taxonomy_failure_pipeline",
                    title="선관위 투표용지 부족 사태",
                    topic="정치",
                    summary="투표용지 부족 사태를 검증합니다.",
                ),
                models.Article(
                    ai_notes={"analysis": {"cached": True}},
                    body_text="선관위 투표용지 부족 사태 후속 보도입니다.",
                    dedup_hash="taxonomy-failure-article",
                    id="article_taxonomy_failure",
                    issue_id="issue_taxonomy_failure_pipeline",
                    publisher="테스트뉴스",
                    source_type="news",
                    summary="투표용지 부족 후속 보도",
                    title="선관위 투표용지 부족 후속 보도",
                    url="https://example.com/taxonomy-failure",
                ),
            ],
        )
        db.commit()

        article = db.get(models.Article, "article_taxonomy_failure")
        assert article is not None
        claims = process_article(db, article=article)
        db.commit()

        assert claims == []
        assert article.issue_id == "issue_taxonomy_failure_pipeline"
        run = db.scalar(
            select(models.AgentRun).where(
                models.AgentRun.agent == "Taxonomy Classifier",
                models.AgentRun.issue_id == "issue_taxonomy_failure_pipeline",
            ),
        )
        assert run is not None
        assert run.status == "failed"
        assert "taxonomy offline" in run.error_message
    finally:
        db.close()


def test_parse_article_refreshes_taxonomy_image_quality_jobs() -> None:
    db = SessionLocal()
    try:
        issue = models.Issue(
            id="issue_worker_integration",
            title="선관위 투표용지 부족 사태",
            topic="정치",
            summary="작업 연결 테스트입니다.",
        )
        article = models.Article(
            id="article_worker_integration",
            issue_id=issue.id,
            title="선관위 투표용지 부족 후속 보도",
            publisher="테스트뉴스",
            url="https://example.com/worker",
            dedup_hash="worker",
            body_text="선관위 투표용지 부족 후속 보도입니다.",
            summary="후속 보도",
        )
        db.add_all([issue, article])
        db.commit()
    finally:
        db.close()

    result = issue_jobs.parse_article("article_worker_integration")
    assert result["status"] == "completed"

    db = SessionLocal()
    try:
        issue = db.get(models.Issue, "issue_worker_integration")
        assert issue.major_topic_name == "2026 지방선거"
        assert issue.event_group_name == "선관위 투표용지 부족 사태"
        job_types = {
            row.job_type
            for row in db.scalars(select(models.JobAttempt).where(models.JobAttempt.target_id == issue.id)).all()
        }
        assert "assess_issue_quality" in job_types
        assert "select_representative_image" in job_types
        assert "update_issue_page" in job_types
    finally:
        db.close()


def test_parse_article_fetches_remote_image_candidates_and_selects_cover(monkeypatch) -> None:
    from app.services.articles.parser import ParsedArticle

    def fake_fetch_and_parse_url(url: str) -> ParsedArticle:
        assert url == "https://example.com/remote-image-article"
        return ParsedArticle(
            body_text="선관위 투표용지 부족 사태 후속 보도의 원문 본문입니다.",
            image_candidates=["https://img.example.com/nec-ballot-og.jpg"],
            parse_status="parsed",
            published_at=None,
            publisher="선관위뉴스",
            summary="원문 본문 요약",
            title="선관위 투표용지 부족 사태 후속 보도",
        )

    monkeypatch.setattr(issue_jobs, "fetch_and_parse_url", fake_fetch_and_parse_url, raising=False)

    db = SessionLocal()
    try:
        issue = models.Issue(
            id="issue_remote_image_cover",
            title="선관위 투표용지 부족 사태",
            topic="정치",
            summary="원문에서 수집한 관련 이미지를 대표 이미지로 선택해야 합니다.",
        )
        article = models.Article(
            body_text="검색 결과 요약만 있는 기사입니다.",
            dedup_hash="remote-image-cover",
            id="article_remote_image_cover",
            issue_id=issue.id,
            ai_notes={"remoteParseEligible": True},
            publisher="선관위뉴스",
            source_type="news",
            summary="검색 결과 요약",
            title="선관위 투표용지 부족 후속 보도",
            url="https://example.com/remote-image-article",
        )
        db.add_all([issue, article])
        db.commit()
    finally:
        db.close()

    result = issue_jobs.parse_article("article_remote_image_cover")
    assert result["status"] == "completed"

    db = SessionLocal()
    try:
        issue = db.get(models.Issue, "issue_remote_image_cover")
        article = db.get(models.Article, "article_remote_image_cover")
        candidate = db.scalar(
            select(models.ImageCandidate).where(
                models.ImageCandidate.url == "https://img.example.com/nec-ballot-og.jpg",
            ),
        )
        assert article is not None
        assert candidate is not None
        assert candidate.article_id == article.id
        assert candidate.issue_id == issue.id
        assert issue.representative_image_url == "https://img.example.com/nec-ballot-og.jpg"
    finally:
        db.close()


def test_select_representative_image_job_fetches_existing_article_remote_cover(monkeypatch) -> None:
    from app.services.articles.parser import ParsedArticle

    def fake_fetch_and_parse_url(url: str) -> ParsedArticle:
        assert url == "https://example.com/existing-issue-article"
        return ParsedArticle(
            body_text="이미 수집된 기사 원문입니다.",
            image_candidates=["https://img.example.com/existing-issue-og.jpg"],
            parse_status="parsed",
            published_at=None,
            publisher="선관위뉴스",
            summary="이미 수집된 기사 요약",
            title="선관위 투표용지 부족 사태 기존 기사",
        )

    monkeypatch.setattr(issue_jobs, "fetch_and_parse_url", fake_fetch_and_parse_url)

    db = SessionLocal()
    try:
        issue = models.Issue(
            id="issue_existing_remote_cover",
            title="선관위 투표용지 부족 사태",
            topic="정치",
            summary="기존 기사에서도 원문 이미지를 찾아 대표 이미지로 선택해야 합니다.",
        )
        article = models.Article(
            body_text="수집 당시 이미지가 없던 기사입니다.",
            dedup_hash="existing-remote-cover",
            id="article_existing_remote_cover",
            issue_id=issue.id,
            publisher="선관위뉴스",
            source_type="news",
            summary="수집 요약",
            title="선관위 투표용지 부족 사태 기존 기사",
            url="https://example.com/existing-issue-article",
        )
        db.add_all([issue, article])
        db.commit()
    finally:
        db.close()

    result = issue_jobs.select_representative_image_job("issue_existing_remote_cover")

    db = SessionLocal()
    try:
        issue = db.get(models.Issue, "issue_existing_remote_cover")
        assert result["hydrated_image_candidates"] == 1
        assert issue.representative_image_url == "https://img.example.com/existing-issue-og.jpg"
    finally:
        db.close()


def test_parse_article_queues_extract_claims_stage_without_inline_verification(monkeypatch) -> None:
    def fail_claim_extraction(self, **kwargs) -> list[dict]:
        raise AssertionError("parse_article should not extract claims inline")

    monkeypatch.setattr(DeepSeekAnalysisService, "extract_claims_from_article", fail_claim_extraction)

    db = SessionLocal()
    try:
        issue = models.Issue(
            id="issue_async_parse",
            title="선관위 투표용지 부족 사태",
            topic="정치",
            summary="비동기 단계 테스트입니다.",
        )
        article = models.Article(
            body_text="선관위는 3곳 투표소에서 투표용지 부족이 있었다고 설명했다.",
            dedup_hash="async-parse",
            id="article_async_parse",
            issue_id=issue.id,
            publisher="테스트뉴스",
            source_type="news",
            summary="투표용지 부족 설명",
            title="선관위 투표용지 부족 후속 보도",
            url="https://example.com/async-parse",
        )
        db.add_all([issue, article])
        db.commit()
    finally:
        db.close()

    result = issue_jobs.parse_article("article_async_parse")

    db = SessionLocal()
    try:
        assert result["status"] == "completed"
        assert result["stage"] == "parsed"
        assert db.scalar(select(models.Claim).where(models.Claim.article_id == "article_async_parse")) is None
        extract_job = db.scalar(
            select(models.JobAttempt).where(
                models.JobAttempt.job_type == "extract_claims",
                models.JobAttempt.target_id == "article_async_parse",
            ),
        )
        assert extract_job is not None
    finally:
        db.close()


def test_extract_claims_queues_evidence_retrieval_instead_of_inline_verification(monkeypatch) -> None:
    def fake_claim_extraction(self, **kwargs) -> list[dict]:
        return [
            {
                "canonical_question": "부족 투표소는 몇 곳인가?",
                "claim_text": "선관위는 3곳 투표소에서 투표용지 부족이 있었다고 설명했다.",
                "claim_type": "수치 주장",
                "entities_json": {"numbers": ["3"], "dates": [], "organizations": ["선관위"], "places": []},
                "importance": 0.9,
            },
        ]

    def fail_evidence_candidates(self, **kwargs) -> list[dict]:
        raise AssertionError("extract_claims should not retrieve evidence inline")

    monkeypatch.setattr(DeepSeekAnalysisService, "extract_claims_from_article", fake_claim_extraction)
    monkeypatch.setattr(DeepSeekAnalysisService, "generate_evidence_candidates", fail_evidence_candidates)

    db = SessionLocal()
    try:
        issue = models.Issue(
            id="issue_async_extract",
            title="선관위 투표용지 부족 사태",
            topic="정치",
            summary="비동기 주장 추출 테스트입니다.",
        )
        article = models.Article(
            body_text="선관위는 3곳 투표소에서 투표용지 부족이 있었다고 설명했다.",
            dedup_hash="async-extract",
            id="article_async_extract",
            issue_id=issue.id,
            publisher="테스트뉴스",
            source_type="news",
            summary="투표용지 부족 설명",
            title="선관위 투표용지 부족 후속 보도",
            url="https://example.com/async-extract",
        )
        db.add_all([issue, article])
        db.commit()
    finally:
        db.close()

    result = issue_jobs.extract_claims("article_async_extract")

    db = SessionLocal()
    try:
        claim = db.scalar(select(models.Claim).where(models.Claim.article_id == "article_async_extract"))
        assert result["status"] == "completed"
        assert result["stage"] == "claims_extracted"
        assert claim is not None
        assert claim.status == "needs_evidence"
        retrieve_job = db.scalar(
            select(models.JobAttempt).where(
                models.JobAttempt.job_type == "retrieve_evidence",
                models.JobAttempt.target_id == claim.id,
            ),
        )
        assert retrieve_job is not None
        assert db.scalar(select(models.Evidence).where(models.Evidence.claim_id == claim.id)) is None
    finally:
        db.close()


def test_extract_claims_merges_ai_and_rule_based_article_candidates(monkeypatch) -> None:
    def sparse_claim_extraction(self, **kwargs) -> list[dict]:
        return [
            {
                "canonical_question": "부족 투표소는 몇 곳인가?",
                "claim_text": "선관위는 3곳 투표소에서 투표용지 부족이 있었다고 설명했다.",
                "claim_type": "수치 주장",
                "entities_json": {"numbers": ["3곳"], "dates": [], "organizations": ["선관위"], "places": []},
                "importance": 0.9,
            },
        ]

    monkeypatch.setattr(DeepSeekAnalysisService, "extract_claims_from_article", sparse_claim_extraction)

    db = SessionLocal()
    try:
        issue = models.Issue(
            id="issue_claim_merge",
            title="선관위 투표용지 부족 사태",
            topic="정치",
            summary="AI가 적게 반환해도 기사 본문에서 확인 가능한 주장을 보강합니다.",
        )
        article = models.Article(
            body_text=(
                "선관위는 3곳 투표소에서 투표용지 부족이 있었다고 설명했다. "
                "감시단체는 현장 관리 부실 책임을 선관위가 져야 한다고 주장했다. "
                "야당은 재발 방지 대책이 필요하다고 촉구했다."
            ),
            dedup_hash="claim-merge",
            id="article_claim_merge",
            issue_id=issue.id,
            publisher="테스트뉴스",
            source_type="news",
            summary="투표용지 부족 주장 보강",
            title="선관위 투표용지 부족 후속 보도",
            url="https://example.com/claim-merge",
        )
        db.add_all([issue, article])
        db.commit()

        claims = issue_jobs.extract_claims_for_article(db, article=article)

        claim_texts = [claim.claim_text for claim in claims]
        assert len(claim_texts) >= 3
        assert claim_texts.count("선관위는 3곳 투표소에서 투표용지 부족이 있었다고 설명했다.") == 1
        assert "감시단체는 현장 관리 부실 책임을 선관위가 져야 한다고 주장했다" in claim_texts
        assert "야당은 재발 방지 대책이 필요하다고 촉구했다" in claim_texts
    finally:
        db.close()


def test_ai_article_pipeline_uses_model_outputs(monkeypatch) -> None:
    def fake_article_analysis(self, **kwargs) -> dict:
        return {
            "normalized_title": "공공기관 절차 지연 집계 확인",
            "summary": "공공기관이 5곳에서 절차 지연을 확인했다는 보도입니다.",
            "topic": "사회",
            "risk_level": "medium",
            "key_numbers": ["5곳"],
            "key_entities": ["공공기관"],
            "extraction_focus": ["발생 규모"],
        }

    def fake_claim_extraction(self, **kwargs) -> list[dict]:
        return [
            {
                "claim_text": "공공기관은 5곳에서 절차 지연이 발생했다고 밝혔다.",
                "claim_type": "수치 주장",
                "canonical_question": "절차 지연 발생 장소는 몇 곳인가?",
                "entities_json": {
                    "numbers": ["5"],
                    "dates": [],
                    "organizations": ["공공기관"],
                    "places": [],
                },
                "importance": 0.9,
            },
        ]

    def fake_evidence_candidates(self, **kwargs) -> list[dict]:
        return [
            {
                "document_id": "article:article-ai-001",
                "relevance_score": 0.86,
                "evidence_text": "공공기관은 5곳에서 절차 지연이 발생했다고 설명했다.",
                "title": "공공기관 절차 지연 집계 확인",
                "supports": True,
                "conflicts": False,
            },
        ]

    def fake_verdict(self, **kwargs) -> dict:
        return {
            "verdict": "대체로 사실",
            "confidence": 0.84,
            "reason": "기사 본문과 주장 수치가 일치합니다.",
            "missing_context": "",
            "evidence_ids": ["article:article-ai-001"],
        }

    def fake_perspectives(self, **kwargs) -> list[dict]:
        return [
            {
                "name": "발생 규모 확인",
                "summary": "공식 설명과 기사 본문 기준으로 발생 규모를 확인합니다.",
                "core_arguments": ["5곳에서 절차 지연이 발생했다는 주장"],
                "conflicts": [],
                "common_ground": ["발생 규모는 근거 문서의 집계 기준으로 확인해야 합니다."],
            },
        ]

    monkeypatch.setattr(DeepSeekAnalysisService, "analyze_article_content", fake_article_analysis)
    monkeypatch.setattr(DeepSeekAnalysisService, "extract_claims_from_article", fake_claim_extraction)
    monkeypatch.setattr(DeepSeekAnalysisService, "generate_evidence_candidates", fake_evidence_candidates)
    monkeypatch.setattr(DeepSeekAnalysisService, "verify_claim_against_evidence", fake_verdict)
    monkeypatch.setattr(DeepSeekAnalysisService, "build_perspectives", fake_perspectives)
    monkeypatch.setattr(DeepSeekAnalysisService, "synthesize_issue_detail", lambda self, **_kwargs: None)

    db = SessionLocal()
    try:
        db.add_all(
            [
                models.SystemSetting(
                    key="ai_processing_enabled",
                    group="ai",
                    label="AI 처리",
                    value=True,
                    value_type="boolean",
                ),
                models.SystemSetting(
                    key="openai_api_key",
                    group="ai",
                    label="OpenAI API 키",
                    value="",
                    value_type="string",
                    is_secret=True,
                ),
                models.Issue(
                    id="issue_ai_001",
                    title="공공기관 절차 지연 논란",
                    topic="사회",
                    summary="절차 지연 발생 규모를 검증합니다.",
                ),
                models.Article(
                    body_text="공공기관은 5곳에서 절차 지연이 발생했다고 설명했다.",
                    dedup_hash="ai-dedup-001",
                    id="article-ai-001",
                    issue_id="issue_ai_001",
                    publisher="테스트뉴스",
                    source_type="news",
                    title="https://example.com/ai",
                    url="https://example.com/ai",
                ),
            ],
        )
        db.commit()

        article = db.get(models.Article, "article-ai-001")
        assert article is not None
        claims = process_article(db, article=article)
        db.commit()
        assert len(claims) == 1
        claim_id = claims[0].id
    finally:
        db.close()

    db = SessionLocal()
    try:
        article = db.get(models.Article, "article-ai-001")
        claim = db.get(models.Claim, claim_id)
        evidences = db.query(models.Evidence).filter(models.Evidence.claim_id == claim_id).all()
        perspectives = db.query(models.Perspective).filter(models.Perspective.issue_id == "issue_ai_001").all()
        assert article is not None
        assert article.title == "공공기관 절차 지연 집계 확인"
        assert article.summary == "공공기관이 5곳에서 절차 지연을 확인했다는 보도입니다."
        assert claim is not None
        assert claim.claim_type == "수치 주장"
        assert claim.verdict == "대체로 사실"
        assert claim.confidence == 0.84
        assert claim.ai_notes["source"] == "deepseek"
        assert claim.ai_notes["verification"]["verdict"] == "대체로 사실"
        assert len(evidences) == 1
        assert evidences[0].retrieval_json["source"] == "deepseek"
        assert perspectives[0].name == "발생 규모 확인"
    finally:
        db.close()


def test_search_scheduler_collects_news_into_issue_pipeline(monkeypatch) -> None:
    def fake_google_news_search(query: str, **kwargs) -> list[CollectedArticle]:
        return [
            CollectedArticle(
                body_text="선관위는 3곳 투표소에서 투표용지 부족이 발생했다고 밝혔다.",
                publisher="테스트뉴스",
                source_type="news_search",
                summary="선관위 투표용지 부족 발생 설명",
                title=f"{query} 관련 보도 1",
                url="https://example.com/search-news-1",
            ),
            CollectedArticle(
                body_text="중앙선관위는 투표용지 부족 신고를 확인하고 추가 배송이 필요했다고 발표했다.",
                publisher="테스트뉴스2",
                source_type="news_search",
                summary="중앙선관위 추가 배송 설명",
                title=f"{query} 관련 보도 2",
                url="https://example.com/search-news-2",
            ),
        ]

    monkeypatch.setattr(issue_jobs, "collect_google_news_search", fake_google_news_search)

    db = SessionLocal()
    try:
        keywords = seed_search_keywords(
            db,
            generate_variants=False,
            interval_minutes=5,
            priority="high",
            query="선관위 투표용지 부족 사태",
            source="test",
            topic="정치",
        )
        assert len(keywords) == 1
        result = tick_scheduler_once(db, owner_id="test")
        for _ in range(2):
            run_due_jobs(db, limit=2)
        db.commit()
        assert result["scheduledSearches"] == 1
        assert result["executed"] == 1
    finally:
        db.close()

    db = SessionLocal()
    try:
        keyword = db.scalar(
            select(models.SearchKeyword).where(models.SearchKeyword.query == "선관위 투표용지 부족 사태"),
        )
        assert keyword is not None
        assert keyword.last_result_count == 2
        assert keyword.last_new_article_count == 2
        assert keyword.issue_id is not None

        issue = db.get(models.Issue, keyword.issue_id)
        assert issue is not None
        assert issue.title == "선관위 투표용지 부족 사태"

        articles = db.scalars(select(models.Article).where(models.Article.issue_id == keyword.issue_id)).all()
        extract_jobs = db.scalars(
            select(models.JobAttempt).where(
                models.JobAttempt.job_type == "extract_claims",
                models.JobAttempt.target_id.in_([article.id for article in articles]),
            ),
        ).all()
        runs = db.scalars(select(models.CollectorRun).where(models.CollectorRun.collector == "news_search")).all()
        heartbeat = db.get(models.SchedulerHeartbeat, "default")
        assert len(articles) == 2
        assert len(extract_jobs) == 2
        assert runs[0].status == "completed"
        assert heartbeat is not None
        assert heartbeat.last_tick_json["scheduledSearches"] == 1
    finally:
        db.close()


def test_discovery_topic_defines_incident_and_expands_keywords(monkeypatch) -> None:
    def fake_google_news_search(query: str, **kwargs) -> list[CollectedArticle]:
        return [
            CollectedArticle(
                body_text="선관위는 일부 투표소에서 투표용지 부족 신고가 접수됐다고 밝혔다.",
                publisher="테스트뉴스A",
                source_type="news_search",
                summary="선관위 투표용지 부족 신고 접수",
                title="선관위 투표용지 부족 신고 접수",
                url="https://example.com/discovery-1",
            ),
            CollectedArticle(
                body_text="중앙선관위는 투표용지 부족 사례가 91곳으로 늘었다고 발표했다.",
                publisher="테스트뉴스B",
                source_type="news_search",
                summary="투표용지 부족 사례 91곳 발표",
                title="투표용지 부족 사례 91곳으로 늘어",
                url="https://example.com/discovery-2",
            ),
        ]

    monkeypatch.setattr(issue_jobs, "collect_google_news_search", fake_google_news_search)

    db = SessionLocal()
    try:
        topic = upsert_discovery_topic(
            db,
            base_queries=["선관위"],
            interval_minutes=5,
            max_results_per_query=5,
            min_cluster_size=2,
            name="선거 감시",
            priority="high",
            topic="정치",
        )
        result = tick_scheduler_once(db, owner_id="test-discovery")
        db.commit()
        assert result["scheduledDiscoveries"] == 1
        assert result["executed"] == 1
        topic_id = topic.id
    finally:
        db.close()

    db = SessionLocal()
    try:
        topic = db.get(models.DiscoveryTopic, topic_id)
        incidents = db.scalars(select(models.DiscoveredIncident)).all()
        assert topic is not None
        assert topic.last_result_count == 2
        assert topic.last_candidate_count == 1
        assert len(incidents) == 1
        assert incidents[0].issue_id is not None
        assert len(incidents[0].keyword_ids_json) >= 1
        articles = db.scalars(select(models.Article).where(models.Article.issue_id == incidents[0].issue_id)).all()
        keywords = db.scalars(select(models.SearchKeyword).where(models.SearchKeyword.issue_id == incidents[0].issue_id)).all()
        assert len(articles) == 2
        assert len(keywords) >= 1
    finally:
        db.close()


def test_define_incident_treats_string_keyword_payload_as_one_keyword(monkeypatch) -> None:
    from app.services.discovery.incident_detector import define_incident

    def fake_define_incident_candidate(self, **kwargs) -> dict:
        return {
            "score": 88,
            "search_keywords": "선관위",
            "summary": "선관위 투표용지 부족 후속 보도입니다.",
            "title": "선관위 투표용지 부족 사태",
            "topic": "정치",
        }

    monkeypatch.setattr(DeepSeekAnalysisService, "define_incident_candidate", fake_define_incident_candidate)

    db = SessionLocal()
    try:
        definition = define_incident(
            db,
            articles=[
                CollectedArticle(
                    body_text="선관위는 일부 투표소의 투표용지 부족 신고를 확인했다.",
                    publisher="테스트뉴스",
                    source_type="news_search",
                    summary="투표용지 부족 신고 확인",
                    title="선관위 투표용지 부족 신고",
                    url="https://example.com/string-keywords",
                ),
            ],
            topic="정치",
            topic_name="정치 주요 이슈",
        )

        assert "선관위" in definition["keywords"]
        assert all(len(keyword) >= 2 for keyword in definition["keywords"])
        assert "선" not in definition["keywords"]
    finally:
        db.close()


def test_admin_extended_operations_and_source_policy() -> None:
    with TestClient(app) as client:
        session = signup(client, "admin@example.com")
        headers = {"Authorization": f"Bearer {session['accessToken']}"}
        seed_contract_records(session["user"]["id"])

        candidates = client.get("/v1/admin/issue-candidates", headers=headers)
        assert candidates.status_code == 200
        assert candidates.json()["queue"][0]["id"] == "issue_001"

        source = client.patch(
            "/v1/admin/sources/domain-001/credibility",
            headers=headers,
            json={"credibility": 0.81, "status": "trusted", "collectionIntervalMinutes": 5},
        )
        assert source.status_code == 200
        assert source.json()["status"] == "updated"

        setting = client.patch(
            "/v1/admin/settings",
            headers=headers,
            json={"settings": [{"key": "claim_similarity_threshold", "value": 0.5}]},
        )
        assert setting.status_code == 200
        reset = client.patch(
            "/v1/admin/settings",
            headers=headers,
            json={"settings": [{"key": "claim_similarity_threshold", "reset": True}]},
        )
        assert reset.status_code == 200

        hidden = client.post("/v1/admin/issues/issue_001/hide", headers=headers)
        assert hidden.status_code == 200
        assert hidden.json()["status"] == "updated"

        jobs = client.get("/v1/admin/jobs", headers=headers)
        assert jobs.status_code == 200
        assert "jobs" in jobs.json()


def test_file_input_device_token_and_job_retry_flow() -> None:
    with TestClient(app) as client:
        session = signup(client, "admin@example.com")
        headers = {"Authorization": f"Bearer {session['accessToken']}"}
        seed_contract_records(session["user"]["id"])

        token = client.post(
            "/v1/users/me/device-tokens",
            headers=headers,
            json={"platform": "expo", "token": "ExponentPushToken[testtoken]"},
        )
        assert token.status_code == 200

        raw_text = "관계 기관은 7곳에서 절차 지연이 발생했다고 발표했다."
        file_response = client.post(
            "/v1/files",
            headers=headers,
            json={
                "filename": "source.txt",
                "contentType": "text/plain",
                "sizeBytes": len(raw_text.encode()),
                "contentBase64": base64.b64encode(raw_text.encode()).decode(),
            },
        )
        assert file_response.status_code == 201
        file_id = file_response.json()["id"]
        assert file_response.json()["safetyStatus"] == "accepted"

        check = client.post(
            "/v1/checks",
            headers=headers,
            json={"inputType": "file", "content": file_id, "issueId": "issue_001"},
        )
        assert check.status_code == 201
        assert check.json()["status"] == "queued"
        wait_for_check_result(client, check.json()["id"])

        db = SessionLocal()
        try:
            uploaded = db.get(models.UploadedFile, file_id)
            assert uploaded is not None
            assert uploaded.parse_status == "parsed"
            assert "7곳" in uploaded.extracted_text
            job = models.JobAttempt(
                id="job-test-001",
                job_type="update_issue_page",
                target_id="issue_001",
                status="failed",
                attempts=0,
            )
            db.add(job)
            db.commit()
        finally:
            db.close()

        retry = client.post("/v1/admin/jobs/job-test-001/retry", headers=headers)
        assert retry.status_code == 200
        assert retry.json()["status"] == "completed"


def test_research_run_persists_collection_evidence() -> None:
    db = SessionLocal()
    try:
        issue = models.Issue(
            id="issue_research_trace",
            title="선거 투표용지 부족 논란",
            topic="정치",
            status="검증 진행",
            is_public=True,
        )
        run = models.ResearchRun(
            id="research_trace_1",
            issue_id=issue.id,
            trigger_type="quality_gap",
            seed_query="선거 투표용지 부족 논란",
            status="completed",
            round_index=1,
            plan_json={"queries": [{"query": "선관위 투표용지 부족", "purpose": "core"}]},
            source_routes_json=[{"sourceType": "official", "domain": "nec.go.kr"}],
            executed_queries_json=[{"provider": "google_news", "query": "선관위 투표용지 부족"}],
            result_urls_json=[{"url": "https://example.com/a", "selected": True, "reason": "new article"}],
            selected_article_ids_json=["article_1"],
            missing_signals_json=["officialCoverage"],
        )
        db.add(issue)
        db.add(run)
        db.commit()

        saved = db.get(models.ResearchRun, "research_trace_1")
        assert saved is not None
        assert saved.issue_id == "issue_research_trace"
        assert saved.source_routes_json[0]["domain"] == "nec.go.kr"
        assert saved.result_urls_json[0]["selected"] is True
    finally:
        db.close()


def test_research_planner_builds_purpose_based_queries_without_narrow_default_topic() -> None:
    from app.services.research.planner import build_research_plan

    db = SessionLocal()
    try:
        issue = models.Issue(
            id="issue_research_plan",
            title="선관위 투표용지 부족 사태",
            topic="정치",
            major_topic_name="2026 지방선거",
            event_group_name="선관위 투표용지 부족 사태",
            quality_report_json={"missingSignals": ["officialCoverage", "timelineCoverage"]},
        )
        db.add(issue)
        db.commit()

        plan = build_research_plan(
            db,
            issue=issue,
            missing_signals=["officialCoverage", "timelineCoverage"],
            trigger_type="quality_gap",
        )

        purposes = {query["purpose"] for query in plan["queries"]}
        assert {"core", "official", "followup"}.issubset(purposes)
        assert any("중앙선관위" in query["query"] or "선관위" in query["query"] for query in plan["queries"])
        assert any(route["sourceType"] == "official" for route in plan["sourceRoutes"])
        assert plan["topic"] == "정치"
        assert plan["majorTopic"] == "2026 지방선거"
    finally:
        db.close()


def test_ai_prompt_registry_defines_agent_contracts() -> None:
    from app.services.ai.prompts import PROMPTS

    expected = {
        "article_triage",
        "claim_extraction",
        "claim_verification",
        "evidence_ranking",
        "incident_definition",
        "issue_detail_synthesis",
        "research_planning",
        "search_keyword_generation",
    }
    assert expected.issubset(PROMPTS.keys())
    assert "officialTargets" in PROMPTS["research_planning"].system
    assert "majorTopic" in PROMPTS["incident_definition"].system
    assert "section_map" in PROMPTS["issue_detail_synthesis"].system
    assert PROMPTS["evidence_ranking"].version


def test_research_router_prioritizes_ai_domain_hints() -> None:
    from app.services.research.router import route_sources_for_plan

    db = SessionLocal()
    try:
        db.add_all(
            [
                models.SourceDomain(
                    collection_url="https://www.example-public.go.kr",
                    credibility=0.99,
                    domain="example-public.go.kr",
                    id="source_high_cred_unrelated",
                    is_active=True,
                    name="무관한 고신뢰 기관",
                    note="무관한 공식자료",
                    source_type="official",
                    status="watch",
                ),
                models.SourceDomain(
                    collection_url="https://www.nec.go.kr",
                    credibility=0.8,
                    domain="nec.go.kr",
                    id="source_nec_hint",
                    is_active=True,
                    name="중앙선거관리위원회",
                    note="선거 공식자료",
                    source_type="official",
                    status="watch",
                ),
            ],
        )
        db.commit()
        plan = {
            "queries": [{"purpose": "official", "query": "선관위 투표용지 부족"}],
            "sourceRoutes": [
                {
                    "domainHint": "nec.go.kr",
                    "reason": "선관위 공식 확인 필요",
                    "sourceType": "official",
                },
            ],
            "officialTargets": [{"domain": "nec.go.kr", "reason": "선거관리 공식 출처"}],
            "topic": "정치",
        }

        routes = route_sources_for_plan(db, plan=plan)
        site_routes = [route for route in routes if route["provider"] == "site_query"]

        assert site_routes[0]["domain"] == "nec.go.kr"
        assert site_routes[0]["reason"] == "선거관리 공식 출처"
    finally:
        db.close()


def test_discovery_issue_uses_ai_taxonomy_fields() -> None:
    db = SessionLocal()
    try:
        definition = {
            "event_group_name": "인천 사전투표 동일 득표 논란",
            "major_topic_name": "2026 지방선거",
            "score": 82,
            "summary": "인천 지역 사전투표 득표 수치 논란입니다.",
            "title": "인천 득표 수치 논란",
            "topic": "정치",
        }

        issue = issue_jobs._ensure_discovery_issue(
            db,
            definition=definition,
            existing_issue_id=None,
            priority="high",
        )

        assert issue.major_topic_name == "2026 지방선거"
        assert issue.event_group_name == "인천 사전투표 동일 득표 논란"
        assert issue.topic == "정치"
    finally:
        db.close()


def test_source_router_adds_official_domains_for_public_issue() -> None:
    from app.services.research.router import route_sources_for_plan

    db = SessionLocal()
    try:
        db.add(
            models.SourceDomain(
                collection_url="https://www.nec.go.kr",
                credibility=0.95,
                domain="nec.go.kr",
                id="source_nec",
                is_active=True,
                name="중앙선거관리위원회",
                note="선거 공식자료",
                source_type="official",
                status="watch",
            ),
        )
        db.commit()
        plan = {
            "queries": [{"purpose": "official", "query": "선관위 투표용지 부족"}],
            "sourceRoutes": [{"reason": "official gap", "sourceType": "official"}],
            "topic": "정치",
        }
        routes = route_sources_for_plan(db, plan=plan)
        assert any(route["provider"] == "site_query" for route in routes)
        assert any(route["domain"] == "nec.go.kr" for route in routes)
    finally:
        db.close()


def test_seed_default_source_domains_are_broad_categories() -> None:
    from app.services.bootstrap.sources import seed_default_source_domains

    db = SessionLocal()
    try:
        seed_default_source_domains(db)
        db.commit()
        domains = {row.domain for row in db.query(models.SourceDomain).all()}
        assert "korea.kr" in domains
        assert "law.go.kr" in domains
        assert "nec.go.kr" in domains
        assert "mohw.go.kr" in domains
        assert db.query(models.SourceDomain).count() >= 10
    finally:
        db.close()


def test_site_query_provider_builds_site_restricted_google_news_query(monkeypatch) -> None:
    from app.services.research.providers import SiteQueryProvider

    captured: list[str] = []

    def fake_collect(query: str, *, max_items: int = 30, publisher: str = "Google News", **kwargs):
        captured.append(query)
        return [
            CollectedArticle(
                publisher="중앙선거관리위원회",
                title="선관위 설명자료",
                url="https://www.nec.go.kr/notice",
            ),
        ]

    monkeypatch.setattr("app.services.research.providers.collect_google_news_search", fake_collect)
    provider = SiteQueryProvider()
    results = provider.search(
        max_items=3,
        query="선관위 투표용지 부족",
        route={"domain": "nec.go.kr", "name": "중앙선거관리위원회", "sourceType": "official"},
    )
    assert captured == ["site:nec.go.kr 선관위 투표용지 부족"]
    assert results[0].source_type == "official"
    assert results[0].publisher == "중앙선거관리위원회"


def test_openai_web_search_provider_disabled_without_setting() -> None:
    from app.services.ai.openai_web_search import OpenAIWebSearchProvider

    db = SessionLocal()
    try:
        provider = OpenAIWebSearchProvider(db)
        assert provider.enabled is False
        assert provider.search_sources("선관위 투표용지 부족", max_items=3) == []
    finally:
        db.close()


def test_research_issue_collects_articles_and_writes_trace(monkeypatch) -> None:
    from app.workers.issue_jobs import research_issue

    def fake_execute_provider_query(*, db, max_items, provider, query, route):
        return [
            CollectedArticle(
                publisher="예시뉴스",
                source_type="news_search",
                summary="후속 보도 요약",
                title="선관위 투표용지 부족 후속 보도",
                url="https://example.com/research-article",
            ),
        ]

    monkeypatch.setattr("app.services.research.executor._execute_provider_query", fake_execute_provider_query)

    db = SessionLocal()
    try:
        issue = models.Issue(
            id="issue_research_job",
            is_public=True,
            quality_report_json={"missingSignals": ["officialCoverage"]},
            title="선관위 투표용지 부족 사태",
            topic="정치",
        )
        db.add(issue)
        db.commit()
    finally:
        db.close()

    result = research_issue(issue_id="issue_research_job", trigger_type="quality_gap")
    assert result["status"] == "completed"
    assert result["created"] == 1
    assert result["research_run_id"]

    db = SessionLocal()
    try:
        trace = db.get(models.ResearchRun, result["research_run_id"])
        assert trace is not None
        assert trace.issue_id == "issue_research_job"
        assert trace.selected_article_ids_json
        article = db.query(models.Article).filter(models.Article.url == "https://example.com/research-article").one()
        assert article.issue_id == "issue_research_job"
    finally:
        db.close()


def test_research_executor_adds_openai_fallback_route_when_enabled(monkeypatch) -> None:
    from app.services.admin.settings import update_admin_settings
    from app.workers.issue_jobs import research_issue

    seen_routes: list[dict] = []

    def fake_execute_provider_query(*, db, max_items, provider, query, route):
        seen_routes.append(route)
        return []

    monkeypatch.setattr("app.services.research.executor._execute_provider_query", fake_execute_provider_query)

    db = SessionLocal()
    try:
        issue = models.Issue(
            id="issue_openai_route",
            is_public=True,
            title="고영향 공공 이슈",
            topic="정치",
        )
        db.add(issue)
        update_admin_settings(
            db,
            payload=[
                schemas.AdminSettingUpdate(key="openai_web_search_enabled", value=True),
                schemas.AdminSettingUpdate(key="openai_api_key", value="test-key"),
                schemas.AdminSettingUpdate(key="research_openai_fallback_after_round", value=1),
            ],
            user_id="test",
        )
        db.commit()
    finally:
        db.close()

    result = research_issue(issue_id="issue_openai_route", round_index=1, trigger_type="quality_gap")
    assert result["status"] == "completed"
    assert any(route.get("provider") == "openai_web_search" for route in seen_routes)

    db = SessionLocal()
    try:
        trace = db.get(models.ResearchRun, result["research_run_id"])
        assert trace is not None
        assert any(route.get("provider") == "openai_web_search" for route in trace.source_routes_json)
    finally:
        db.close()


def test_research_result_urls_keep_openai_provider_route(monkeypatch) -> None:
    from app.collectors.base import CollectedArticle
    from app.services.admin.settings import update_admin_settings
    from app.workers.issue_jobs import research_issue

    def fake_execute_provider_query(*, db, max_items, provider, query, route):
        if route.get("provider") != "openai_web_search":
            return []
        return [
            CollectedArticle(
                publisher="OpenAI Web Search",
                source_type="web_search",
                title="OpenAI fallback collected article",
                url="https://example.com/openai-collected",
            ),
        ]

    monkeypatch.setattr("app.services.research.executor._execute_provider_query", fake_execute_provider_query)

    db = SessionLocal()
    try:
        issue = models.Issue(
            id="issue_openai_result_route",
            is_public=True,
            title="OpenAI fallback 감사 추적 이슈",
            topic="정치",
        )
        db.add(issue)
        update_admin_settings(
            db,
            payload=[
                schemas.AdminSettingUpdate(key="openai_web_search_enabled", value=True),
                schemas.AdminSettingUpdate(key="openai_api_key", value="test-key"),
                schemas.AdminSettingUpdate(key="research_openai_fallback_after_round", value=1),
            ],
            user_id="test",
        )
        db.commit()
    finally:
        db.close()

    result = research_issue(issue_id="issue_openai_result_route", round_index=1, trigger_type="quality_gap")
    assert result["status"] == "completed"

    db = SessionLocal()
    try:
        trace = db.get(models.ResearchRun, result["research_run_id"])
        assert trace is not None
        result_url = next(row for row in trace.result_urls_json if row["url"] == "https://example.com/openai-collected")
        assert result_url["provider"] == "openai_web_search"
        assert result_url["route"]["provider"] == "openai_web_search"
        assert result_url["route"]["sourceType"] == "web_search"
    finally:
        db.close()


def test_research_executor_respects_openai_daily_issue_limit(monkeypatch) -> None:
    from app.services.admin.settings import update_admin_settings
    from app.workers.issue_jobs import research_issue

    seen_routes: list[dict] = []

    def fake_execute_provider_query(*, db, max_items, provider, query, route):
        seen_routes.append(route)
        return []

    monkeypatch.setattr("app.services.research.executor._execute_provider_query", fake_execute_provider_query)

    db = SessionLocal()
    try:
        issue = models.Issue(
            id="issue_openai_limit",
            is_public=True,
            title="고영향 일일 상한 이슈",
            topic="정치",
        )
        prior = models.ResearchRun(
            id="research_openai_prior",
            issue_id=issue.id,
            seed_query=issue.title,
            source_routes_json=[{"provider": "openai_web_search"}],
            status="completed",
            trigger_type="quality_gap",
        )
        db.add_all([issue, prior])
        update_admin_settings(
            db,
            payload=[
                schemas.AdminSettingUpdate(key="openai_web_search_enabled", value=True),
                schemas.AdminSettingUpdate(key="openai_api_key", value="test-key"),
                schemas.AdminSettingUpdate(key="openai_web_search_daily_issue_limit", value=1),
                schemas.AdminSettingUpdate(key="research_openai_fallback_after_round", value=1),
            ],
            user_id="test",
        )
        db.commit()
    finally:
        db.close()

    result = research_issue(issue_id="issue_openai_limit", round_index=1, trigger_type="quality_gap")
    assert result["status"] == "completed"
    assert not any(route.get("provider") == "openai_web_search" for route in seen_routes)


def test_research_executor_caps_openai_queries_per_round(monkeypatch) -> None:
    from app.services.admin.settings import update_admin_settings
    from app.workers.issue_jobs import research_issue

    openai_queries: list[str] = []

    def fake_execute_provider_query(*, db, max_items, provider, query, route):
        if route.get("provider") == "openai_web_search":
            openai_queries.append(query)
        return []

    monkeypatch.setattr("app.services.research.executor._execute_provider_query", fake_execute_provider_query)

    db = SessionLocal()
    try:
        issue = models.Issue(
            id="issue_openai_query_cap",
            is_public=True,
            title="고영향 쿼리 상한 이슈",
            topic="정치",
        )
        db.add(issue)
        update_admin_settings(
            db,
            payload=[
                schemas.AdminSettingUpdate(key="openai_web_search_enabled", value=True),
                schemas.AdminSettingUpdate(key="openai_api_key", value="test-key"),
                schemas.AdminSettingUpdate(key="openai_web_search_max_queries_per_round", value=1),
                schemas.AdminSettingUpdate(key="research_max_queries_per_round", value=8),
                schemas.AdminSettingUpdate(key="research_max_rounds", value=1),
                schemas.AdminSettingUpdate(key="research_openai_fallback_after_round", value=1),
            ],
            user_id="test",
        )
        db.commit()
    finally:
        db.close()

    result = research_issue(issue_id="issue_openai_query_cap", round_index=1, trigger_type="quality_gap")
    assert result["status"] == "completed"
    assert len(openai_queries) == 1


def test_research_executor_persists_partial_success_when_provider_fails(monkeypatch) -> None:
    from app.collectors.base import CollectedArticle
    from app.services.admin.settings import update_admin_settings
    from app.workers.issue_jobs import research_issue

    def fake_execute_provider_query(*, db, max_items, provider, query, route):
        if route.get("provider") == "site_query":
            raise RuntimeError("official source timeout")
        return [
            CollectedArticle(
                publisher="예시뉴스",
                source_type="news_search",
                title="부분 성공 기사",
                url="https://example.com/partial-success",
            ),
        ]

    monkeypatch.setattr("app.services.research.executor._execute_provider_query", fake_execute_provider_query)

    db = SessionLocal()
    try:
        issue = models.Issue(
            id="issue_partial_research",
            is_public=True,
            quality_report_json={"missingSignals": ["officialCoverage"]},
            title="부분 성공 이슈",
            topic="정치",
        )
        source = models.SourceDomain(
            collection_url="https://www.nec.go.kr",
            credibility=0.95,
            domain="nec.go.kr",
            id="source_partial_nec",
            is_active=True,
            name="중앙선거관리위원회",
            source_type="official",
            status="watch",
        )
        db.add_all([issue, source])
        update_admin_settings(
            db,
            payload=[schemas.AdminSettingUpdate(key="research_max_queries_per_round", value=1)],
            user_id="test",
        )
        db.commit()
    finally:
        db.close()

    result = research_issue(issue_id="issue_partial_research", trigger_type="quality_gap")
    assert result["status"] == "completed"
    assert result["created"] == 1

    db = SessionLocal()
    try:
        trace = db.get(models.ResearchRun, result["research_run_id"])
        assert trace is not None
        assert any(row.get("status") == "failed" for row in trace.executed_queries_json)
        article = db.query(models.Article).filter(models.Article.url == "https://example.com/partial-success").one()
        assert article.issue_id == "issue_partial_research"
    finally:
        db.close()


def test_site_query_provider_uses_official_site_search_before_google_news(monkeypatch) -> None:
    from app.services.research.providers import SiteQueryProvider

    def fake_official_site_search(collection_url: str, query: str, **kwargs) -> list[CollectedArticle]:
        return [
            CollectedArticle(
                body_text="중앙선관위 공식 설명자료입니다.",
                publisher="중앙선거관리위원회",
                source_type="official",
                summary="공식 설명자료",
                title="투표용지 부족 관련 설명자료",
                url="https://www.nec.go.kr/notice/1",
            ),
        ]

    def fail_google_news_search(*args, **kwargs) -> list[CollectedArticle]:
        raise AssertionError("official route should search the source site before Google News fallback")

    monkeypatch.setattr("app.services.research.providers.collect_official_site_search", fake_official_site_search, raising=False)
    monkeypatch.setattr("app.services.research.providers.collect_google_news_search", fail_google_news_search)

    rows = SiteQueryProvider().search(
        max_items=5,
        query="투표용지 부족 설명자료",
        route={
            "collectionUrl": "https://www.nec.go.kr",
            "domain": "nec.go.kr",
            "name": "중앙선거관리위원회",
            "sourceType": "official",
        },
    )

    assert len(rows) == 1
    assert rows[0].source_type == "official"
    assert rows[0].publisher == "중앙선거관리위원회"


def test_research_issue_replans_when_first_round_has_no_articles(monkeypatch) -> None:
    from app.services.admin.settings import update_admin_settings
    from app.workers.issue_jobs import research_issue

    calls = 0

    def fake_execute_provider_query(*, db, max_items, provider, query, route):
        nonlocal calls
        calls += 1
        if calls == 1:
            return []
        return [
            CollectedArticle(
                body_text="선관위가 투표용지 부족 후속 조치를 발표했다.",
                publisher="테스트뉴스",
                source_type="news_search",
                summary="후속 조치 발표",
                title="선관위 투표용지 부족 후속 조치",
                url="https://example.com/research-retry",
            ),
        ]

    monkeypatch.setattr("app.services.research.executor._execute_provider_query", fake_execute_provider_query)

    db = SessionLocal()
    try:
        issue = models.Issue(
            id="issue_research_replan",
            is_public=True,
            quality_report_json={"missingSignals": ["articleCoverage"]},
            title="선관위 투표용지 부족 사태",
            topic="정치",
        )
        db.add(issue)
        update_admin_settings(
            db,
            payload=[
                schemas.AdminSettingUpdate(key="research_max_queries_per_round", value=1),
                schemas.AdminSettingUpdate(key="research_max_rounds", value=2),
            ],
            user_id="test",
        )
        db.commit()
    finally:
        db.close()

    result = research_issue(issue_id="issue_research_replan", trigger_type="quality_gap")

    db = SessionLocal()
    try:
        runs = db.scalars(
            select(models.ResearchRun)
            .where(models.ResearchRun.issue_id == "issue_research_replan")
            .order_by(models.ResearchRun.round_index.asc()),
        ).all()
        assert result["status"] == "completed"
        assert result["created"] == 1
        assert result["rounds"] == 2
        assert calls == 2
        assert [run.round_index for run in runs] == [1, 2]
    finally:
        db.close()


def test_returned_failed_job_gets_retry_backoff() -> None:
    import app.services.jobs as jobs_module
    from app.services.jobs import execute_job

    db = SessionLocal()
    try:
        job = models.JobAttempt(
            id="job_returned_failure",
            job_type="research_issue",
            max_attempts=3,
            status="queued",
            target_id="issue_missing",
        )
        db.add(job)
        db.commit()

        original_handlers = jobs_module._handlers
        jobs_module._handlers = lambda: {"research_issue": lambda *args, **kwargs: {"status": "failed", "error": "temporary"}}
        try:
            execute_job(db, job=job)
        finally:
            jobs_module._handlers = original_handlers

        assert job.status == "failed"
        assert job.next_run_at is not None
        assert job.last_error == "temporary"
    finally:
        db.close()


def test_claim_due_jobs_marks_jobs_running_before_execution() -> None:
    from app.services.jobs import claim_due_jobs

    db = SessionLocal()
    try:
        db.add_all(
            [
                models.JobAttempt(id="job_claim_parse", job_type="parse_article", target_id="article_1", status="queued"),
                models.JobAttempt(id="job_claim_research", job_type="research_issue", target_id="issue_1", status="queued"),
            ],
        )
        db.commit()

        claimed = claim_due_jobs(db, limit=2)
        db.commit()

        assert claimed == ["job_claim_parse", "job_claim_research"]
        research = db.get(models.JobAttempt, "job_claim_research")
        parse = db.get(models.JobAttempt, "job_claim_parse")
        assert research is not None
        assert parse is not None
        assert research.status == "running"
        assert parse.status == "running"
        assert research.attempts == 1
        assert parse.attempts == 1
        assert claim_due_jobs(db, limit=2) == []
    finally:
        db.close()


def test_claim_due_jobs_skips_candidate_claimed_by_another_session(monkeypatch) -> None:
    from app.services.jobs import claim_due_jobs

    setup_db = SessionLocal()
    try:
        setup_db.add(
            models.JobAttempt(
                id="job_atomic_claim",
                job_type="parse_article",
                status="queued",
                target_id="article_atomic",
            ),
        )
        setup_db.commit()
    finally:
        setup_db.close()

    db = SessionLocal()
    original_scalars = db.scalars
    interfered = False

    def scalars_with_interference(statement, *args, **kwargs):
        result = original_scalars(statement, *args, **kwargs)

        class ResultProxy:
            def all(self) -> list:
                nonlocal interfered
                rows = result.all()
                if not interfered and any(
                    row == "job_atomic_claim"
                    or (isinstance(row, models.JobAttempt) and row.id == "job_atomic_claim")
                    for row in rows
                ):
                    interfered = True
                    other = SessionLocal()
                    try:
                        job = other.get(models.JobAttempt, "job_atomic_claim")
                        assert job is not None
                        job.status = "running"
                        job.attempts = 1
                        other.commit()
                    finally:
                        other.close()
                return rows

        return ResultProxy()

    monkeypatch.setattr(db, "scalars", scalars_with_interference)
    try:
        claimed = claim_due_jobs(db, limit=1)
        db.commit()

        assert claimed == []
        saved = db.get(models.JobAttempt, "job_atomic_claim")
        assert saved is not None
        assert saved.status == "running"
        assert saved.attempts == 1
    finally:
        db.close()


def test_execute_claimed_job_by_id_does_not_increment_attempts_twice() -> None:
    import app.services.jobs as jobs_module
    from app.services.jobs import claim_due_jobs, execute_claimed_job_by_id

    db = SessionLocal()
    try:
        job = models.JobAttempt(
            id="job_claimed_noop",
            job_type="noop",
            status="queued",
            target_id="target_1",
        )
        db.add(job)
        db.commit()

        assert claim_due_jobs(db, limit=1) == ["job_claimed_noop"]
        db.commit()
    finally:
        db.close()

    original_handlers = jobs_module._handlers
    jobs_module._handlers = lambda: {"noop": lambda *args, **kwargs: {"status": "completed", "handled": True}}
    try:
        result = execute_claimed_job_by_id("job_claimed_noop")
    finally:
        jobs_module._handlers = original_handlers

    db = SessionLocal()
    try:
        saved = db.get(models.JobAttempt, "job_claimed_noop")
        assert saved is not None
        assert result["status"] == "completed"
        assert saved.status == "completed"
        assert saved.attempts == 1
        assert saved.output_json["handled"] is True
    finally:
        db.close()


def test_seed_default_source_domains_preserves_existing_admin_overrides() -> None:
    from app.services.bootstrap.sources import seed_default_source_domains

    db = SessionLocal()
    try:
        existing = models.SourceDomain(
            collection_url="https://custom.example.com",
            credibility=0.1,
            domain="korea.kr",
            id="source_custom_korea",
            is_active=False,
            name="Custom",
            note="admin override",
            source_type="public",
            status="blocked",
        )
        db.add(existing)
        db.commit()

        seed_default_source_domains(db)
        db.commit()

        saved = db.get(models.SourceDomain, "source_custom_korea")
        assert saved is not None
        assert saved.is_active is False
        assert saved.status == "blocked"
        assert saved.collection_url == "https://custom.example.com"
        assert saved.credibility == 0.1
        assert saved.note == "admin override"
    finally:
        db.close()


def test_quality_report_includes_research_trigger_metadata() -> None:
    from app.services.issues.quality import assess_issue_quality

    db = SessionLocal()
    try:
        issue = models.Issue(
            id="issue_quality_research_trigger",
            is_public=True,
            title="근거 부족 이슈",
            topic="정치",
        )
        db.add(issue)
        db.commit()

        result = assess_issue_quality(db, issue_id=issue.id)
        db.commit()
        assert result["status"] == "needs_retry"
        assert result["researchTrigger"]["issueId"] == issue.id

        saved = db.get(models.Issue, issue.id)
        assert saved is not None
        assert saved.quality_report_json["researchTrigger"]["reason"] == "quality_gap"
    finally:
        db.close()


def test_quality_report_omits_research_trigger_when_retry_exhausted() -> None:
    from app.services.issues.quality import assess_issue_quality

    db = SessionLocal()
    try:
        issue = models.Issue(
            id="issue_quality_exhausted_no_trigger",
            is_public=True,
            quality_attempts=3,
            title="재검색 소진 이슈",
            topic="사회",
        )
        db.add(issue)
        db.commit()

        result = assess_issue_quality(db, issue_id=issue.id)
        db.commit()
        assert result["status"] == "exhausted"
        assert "researchTrigger" not in result

        saved = db.get(models.Issue, issue.id)
        assert saved is not None
        assert "researchTrigger" not in saved.quality_report_json
    finally:
        db.close()


def test_discovery_promoted_issue_queues_research_before_parse() -> None:
    from app.workers.issue_jobs import _enqueue_research_issue_job

    db = SessionLocal()
    try:
        issue = models.Issue(
            id="issue_research_queue",
            is_public=True,
            title="큰 사건",
            topic="사회",
        )
        db.add(issue)
        db.commit()
    finally:
        db.close()

    db = SessionLocal()
    try:
        queued = _enqueue_research_issue_job(db, issue_id="issue_research_queue", trigger_type="discovery_burst")
        db.commit()
        assert queued is True
        jobs = db.query(models.JobAttempt).filter(models.JobAttempt.target_id == "issue_research_queue").all()
        assert [job.job_type for job in jobs] == ["research_issue"]
        assert jobs[0].input_json["trigger_type"] == "discovery_burst"
    finally:
        db.close()

def test_parse_jobs_have_priority_over_additional_collection_backlog() -> None:
    executed: list[str] = []

    db = SessionLocal()
    try:
        db.add_all(
            [
                models.JobAttempt(id="job_parse_backlog", job_type="parse_article", target_id="article_1", status="queued"),
                models.JobAttempt(id="job_search_backlog", job_type="search_news", target_id="keyword_1", status="queued"),
            ],
        )
        db.commit()

        import app.services.jobs as jobs_module

        original_execute_job = jobs_module.execute_job

        def fake_execute_job(db, *, job):
            executed.append(job.job_type)
            job.status = "completed"
            return job

        jobs_module.execute_job = fake_execute_job
        try:
            run_due_jobs(db, limit=1)
        finally:
            jobs_module.execute_job = original_execute_job

        assert executed == ["parse_article"]
    finally:
        db.close()


def test_claim_extraction_jobs_have_priority_over_parse_backlog() -> None:
    executed: list[str] = []

    db = SessionLocal()
    try:
        older = datetime.now(UTC) - timedelta(minutes=5)
        db.add_all(
            [
                models.JobAttempt(
                    created_at=older,
                    id="job_old_parse_backlog",
                    job_type="parse_article",
                    status="queued",
                    target_id="article_old",
                ),
                models.JobAttempt(
                    id="job_new_extract",
                    job_type="extract_claims",
                    status="queued",
                    target_id="article_new",
                ),
            ],
        )
        db.commit()

        import app.services.jobs as jobs_module

        original_execute_job = jobs_module.execute_job

        def fake_execute_job(db, *, job):
            executed.append(job.job_type)
            job.status = "completed"
            return job

        jobs_module.execute_job = fake_execute_job
        try:
            run_due_jobs(db, limit=1)
        finally:
            jobs_module.execute_job = original_execute_job

        assert executed == ["extract_claims"]
    finally:
        db.close()


def test_evidence_retrieval_jobs_have_priority_over_extract_backlog() -> None:
    executed: list[str] = []

    db = SessionLocal()
    try:
        older = datetime.now(UTC) - timedelta(minutes=5)
        db.add_all(
            [
                models.JobAttempt(
                    created_at=older,
                    id="job_old_extract_backlog",
                    job_type="extract_claims",
                    status="queued",
                    target_id="article_old",
                ),
                models.JobAttempt(
                    id="job_new_retrieve",
                    job_type="retrieve_evidence",
                    status="queued",
                    target_id="claim_new",
                ),
            ],
        )
        db.commit()

        import app.services.jobs as jobs_module

        original_execute_job = jobs_module.execute_job

        def fake_execute_job(db, *, job):
            executed.append(job.job_type)
            job.status = "completed"
            return job

        jobs_module.execute_job = fake_execute_job
        try:
            run_due_jobs(db, limit=1)
        finally:
            jobs_module.execute_job = original_execute_job

        assert executed == ["retrieve_evidence"]
    finally:
        db.close()


def test_admin_can_read_issue_research_runs() -> None:
    from app.core.security import create_access_token, hash_password

    db = SessionLocal()
    try:
        admin = models.User(
            email="admin-research@example.com",
            id="admin_research_runs",
            name="Admin",
            password_hash=hash_password("password123"),
            role="admin",
        )
        issue = models.Issue(
            id="issue_admin_research",
            is_public=True,
            title="수집 근거 테스트",
            topic="사회",
        )
        run = models.ResearchRun(
            executed_queries_json=[{"provider": "google_news", "query": "수집 근거 테스트"}],
            id="research_admin_1",
            issue_id=issue.id,
            plan_json={"queries": [{"purpose": "core", "query": "수집 근거 테스트"}]},
            result_urls_json=[{"selected": True, "url": "https://example.com"}],
            seed_query="수집 근거 테스트",
            status="completed",
            trigger_type="manual",
        )
        db.add_all([admin, issue, run])
        db.commit()
        token, _ = create_access_token("admin_research_runs", "admin")
    finally:
        db.close()

    with TestClient(app) as client:
        response = client.get(
            "/v1/admin/issues/issue_admin_research/research-runs",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["items"][0]["id"] == "research_admin_1"
        assert payload["items"][0]["executedQueries"][0]["provider"] == "google_news"


def test_generic_keyword_fallback_does_not_inject_election_terms_for_unrelated_queries() -> None:
    variants = fallback_keyword_variants("병원 진료 대기 논란")
    joined = " ".join(variants)
    assert "선관위" not in joined
    assert "투표용지" not in joined
    assert any("후속" in value or "해명" in value for value in variants)
