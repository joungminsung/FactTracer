from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.core.config import get_settings
from app.schemas import AdminSettingItem, AdminSettingsGroup, AdminSettingsResponse
from app.utils import to_iso


@dataclass(frozen=True)
class SettingGroup:
    id: str
    label: str
    description: str


@dataclass(frozen=True)
class SettingDefinition:
    key: str
    group: str
    label: str
    description: str
    value_type: str
    default_attr: str | None = None
    options: tuple[str, ...] = ()
    min_value: float | None = None
    max_value: float | None = None
    step: float | None = None
    unit: str | None = None
    is_secret: bool = False
    is_runtime_mutable: bool = True
    default_value: Any = None


GROUPS: tuple[SettingGroup, ...] = (
    SettingGroup("automation", "자동화", "작업 방식, 큐, 수집 주기를 조정합니다."),
    SettingGroup("review", "판정 기준", "이슈 후보, 자동 공개, 주장 묶음 기준을 조정합니다."),
    SettingGroup("ai", "AI 연결", "분석 모델과 외부 AI 연결 정보를 관리합니다."),
    SettingGroup("content", "입력·파일", "업로드 제한과 허용 파일 형식을 관리합니다."),
    SettingGroup("notifications", "알림", "사용자 알림 발송 채널을 관리합니다."),
    SettingGroup("security", "보안·접속", "토큰, CORS, 요청 제한 정책을 관리합니다."),
)


DEFINITIONS: tuple[SettingDefinition, ...] = (
    SettingDefinition("ai_processing_enabled", "automation", "자동 처리", "수집 후 분석 작업 실행 여부", "boolean"),
    SettingDefinition(
        "bootstrap_default_discovery_enabled",
        "automation",
        "기본 감시 주제 생성",
        "새 DB 시작 시 주요 분야 감시 주제를 자동 생성할지 여부",
        "boolean",
        is_runtime_mutable=False,
    ),
    SettingDefinition(
        "embedded_scheduler_enabled",
        "automation",
        "내장 스케줄러",
        "API 서버 시작 시 검색·수집 스케줄러를 함께 실행할지 여부",
        "boolean",
        is_runtime_mutable=False,
    ),
    SettingDefinition(
        "embedded_worker_enabled",
        "automation",
        "내장 워커",
        "API 서버 시작 시 큐에 쌓인 수집·분석 작업을 함께 실행할지 여부",
        "boolean",
        is_runtime_mutable=False,
    ),
    SettingDefinition(
        "worker_backend",
        "automation",
        "작업 실행 방식",
        "백그라운드 작업 실행 방식",
        "select",
        options=("inline", "rq"),
    ),
    SettingDefinition(
        "redis_url",
        "automation",
        "Redis 주소",
        "RQ 작업 큐 사용 시 연결 주소",
        "string",
        is_secret=True,
    ),
    SettingDefinition(
        "scheduler_poll_seconds",
        "automation",
        "스케줄러 간격",
        "수집 대상 확인 주기",
        "integer",
        min_value=5,
        max_value=3600,
        unit="초",
        is_runtime_mutable=False,
    ),
    SettingDefinition(
        "embedded_worker_poll_seconds",
        "automation",
        "워커 확인 간격",
        "큐에 쌓인 작업을 확인하는 주기",
        "integer",
        min_value=1,
        max_value=300,
        unit="초",
        is_runtime_mutable=False,
    ),
    SettingDefinition(
        "embedded_worker_batch_size",
        "automation",
        "워커 배치 크기",
        "내장 워커가 한 번에 처리할 작업 수",
        "integer",
        min_value=1,
        max_value=50,
        is_runtime_mutable=False,
    ),
    SettingDefinition(
        "embedded_worker_concurrency",
        "automation",
        "워커 병렬 처리 수",
        "내장 워커가 동시에 실행할 작업 수",
        "integer",
        min_value=1,
        max_value=16,
        is_runtime_mutable=False,
    ),
    SettingDefinition(
        "job_stale_after_minutes",
        "automation",
        "작업 복구 기준",
        "실행 중 상태로 멈춘 작업을 실패 처리 후 재시도 대상으로 되돌리는 기준",
        "integer",
        min_value=1,
        max_value=1440,
        unit="분",
    ),
    SettingDefinition(
        "search_max_results_per_keyword",
        "automation",
        "키워드당 검색 수",
        "정기 검색 수집에서 키워드 하나가 가져오는 기본 기사 수",
        "integer",
        min_value=1,
        max_value=30,
        unit="건",
    ),
    SettingDefinition(
        "search_recent_days",
        "automation",
        "최근 검색 기간",
        "검색 수집에서 최근성 조건으로 함께 조회할 기간",
        "integer",
        min_value=1,
        max_value=60,
        unit="일",
    ),
    SettingDefinition(
        "research_max_rounds",
        "automation",
        "리서치 최대 라운드",
        "이슈 하나당 자동 재탐색 라운드 상한",
        "integer",
        min_value=1,
        max_value=5,
    ),
    SettingDefinition(
        "research_max_queries_per_round",
        "automation",
        "라운드당 검색어 수",
        "리서치 라운드 하나에서 실행할 검색어 상한",
        "integer",
        min_value=1,
        max_value=50,
    ),
    SettingDefinition(
        "research_max_results_per_query",
        "automation",
        "검색어당 결과 수",
        "리서치 검색어 하나에서 가져올 결과 상한",
        "integer",
        min_value=1,
        max_value=30,
    ),
    SettingDefinition(
        "research_openai_fallback_after_round",
        "automation",
        "OpenAI 검색 전환 라운드",
        "해당 라운드 이후에도 근거가 부족하면 OpenAI web_search를 사용할 수 있습니다",
        "integer",
        min_value=1,
        max_value=5,
    ),
    SettingDefinition(
        "issue_followup_window_days",
        "automation",
        "이슈 후속 추적 기간",
        "공개 이슈를 생성 후 며칠 동안 후속 기사 추적 대상으로 유지할지",
        "integer",
        min_value=1,
        max_value=30,
        unit="일",
    ),
    SettingDefinition(
        "issue_followup_interval_minutes",
        "automation",
        "이슈 후속 추적 간격",
        "이미 출처가 충분한 공개 이슈를 다시 검색하는 최소 간격",
        "integer",
        min_value=5,
        max_value=1440,
        unit="분",
    ),
    SettingDefinition(
        "issue_followup_limit",
        "automation",
        "이슈 후속 추적 수",
        "스케줄러 한 번에 후속 검색할 공개 이슈 수",
        "integer",
        min_value=1,
        max_value=100,
        unit="개",
    ),
    SettingDefinition(
        "issue_min_sources_for_public",
        "automation",
        "공개 최소 출처 수",
        "공개 이슈로 유지하기 위해 필요한 최소 기사 출처 수",
        "integer",
        min_value=1,
        max_value=10,
        unit="건",
    ),
    SettingDefinition(
        "issue_source_backfill_limit",
        "automation",
        "출처 보강 대상 수",
        "스케줄러 한 번에 자동 보강할 출처 부족 이슈 수",
        "integer",
        min_value=1,
        max_value=50,
        unit="개",
    ),
    SettingDefinition(
        "podcast_generation_enabled",
        "automation",
        "팟캐스트 자동 생성",
        "공개 이슈에서 팟캐스트 회차를 자동 생성할지 여부",
        "boolean",
    ),
    SettingDefinition(
        "podcast_generation_interval_minutes",
        "automation",
        "팟캐스트 생성 간격",
        "팟캐스트 자동 생성 작업을 예약하는 최소 간격",
        "integer",
        min_value=5,
        max_value=1440,
        unit="분",
    ),
    SettingDefinition(
        "podcast_generation_limit",
        "automation",
        "팟캐스트 생성 수",
        "자동 생성 작업 한 번에 처리할 최대 회차 수",
        "integer",
        min_value=1,
        max_value=30,
        unit="개",
    ),
    SettingDefinition(
        "podcast_tts_enabled",
        "automation",
        "팟캐스트 TTS",
        "자동 생성된 팟캐스트 대사를 OpenAI TTS로 렌더링할지 여부",
        "boolean",
    ),
    SettingDefinition(
        "podcast_tts_render_on_generate",
        "automation",
        "생성 시 오디오 렌더링",
        "팟캐스트 생성 작업에서 스크립트와 함께 오디오 파일을 즉시 만들지 여부",
        "boolean",
    ),
    SettingDefinition(
        "podcast_min_sources_for_publish",
        "automation",
        "팟캐스트 공개 최소 출처 수",
        "자동 생성 팟캐스트를 공개하기 위해 필요한 최소 출처 수",
        "integer",
        min_value=1,
        max_value=10,
        unit="건",
    ),
    SettingDefinition(
        "podcast_min_publish_quality_score",
        "automation",
        "팟캐스트 자동발행 최소 품질 점수",
        "자동 생성 팟캐스트를 공개하기 위해 필요한 최소 품질 점수",
        "integer",
        min_value=0,
        max_value=100,
        unit="점",
    ),
    SettingDefinition(
        "podcast_sensitive_topics_require_official_source",
        "automation",
        "민감 주제 공식 출처 요구",
        "정치, 재난, 보건 등 민감 주제 팟캐스트 공개 전에 공식 출처를 요구할지 여부",
        "boolean",
    ),
    SettingDefinition(
        "podcast_recommendation_impact_weight",
        "automation",
        "팟캐스트 추천 영향도 가중치",
        "비로그인 추천에서 사회적 영향도 신호가 차지하는 비중",
        "float",
        min_value=0,
        max_value=1,
        step=0.01,
    ),
    SettingDefinition(
        "podcast_recommendation_verification_weight",
        "automation",
        "팟캐스트 추천 검증 필요도 가중치",
        "비로그인 추천에서 미검증 쟁점과 검토 필요도 신호가 차지하는 비중",
        "float",
        min_value=0,
        max_value=1,
        step=0.01,
    ),
    SettingDefinition(
        "podcast_recommendation_freshness_weight",
        "automation",
        "팟캐스트 추천 최신성 가중치",
        "비로그인 추천에서 최근 업데이트 신호가 차지하는 비중",
        "float",
        min_value=0,
        max_value=1,
        step=0.01,
    ),
    SettingDefinition(
        "podcast_recommendation_controversy_weight",
        "automation",
        "팟캐스트 추천 논란도 가중치",
        "비로그인 추천에서 충돌 신호와 확산 신호가 차지하는 비중",
        "float",
        min_value=0,
        max_value=1,
        step=0.01,
    ),
    SettingDefinition(
        "podcast_recommendation_momentum_weight",
        "automation",
        "팟캐스트 추천 모멘텀 가중치",
        "비로그인 추천에서 기사량과 정정 움직임 신호가 차지하는 비중",
        "float",
        min_value=0,
        max_value=1,
        step=0.01,
    ),
    SettingDefinition(
        "podcast_personalization_interest_weight",
        "automation",
        "팟캐스트 개인화 관심사 가중치",
        "로그인 추천에서 사용자 관심 프로필이 차지하는 비중",
        "float",
        min_value=0,
        max_value=1,
        step=0.01,
    ),
    SettingDefinition(
        "podcast_tts_pronunciation_lexicon",
        "automation",
        "팟캐스트 TTS 발음 사전",
        "줄바꿈 또는 쉼표로 구분한 원문=읽을말 목록",
        "string",
    ),
    SettingDefinition(
        "collector_user_agent",
        "automation",
        "수집 User-Agent",
        "외부 문서 수집 요청 식별자",
        "string",
        is_runtime_mutable=False,
    ),
    SettingDefinition(
        "collector_timeout_seconds",
        "automation",
        "수집 제한 시간",
        "외부 요청 대기 제한",
        "integer",
        min_value=3,
        max_value=60,
        unit="초",
        is_runtime_mutable=False,
    ),
    SettingDefinition(
        "issue_candidate_threshold",
        "review",
        "이슈 후보 기준",
        "새 이슈 후보로 올리는 최소 점수",
        "integer",
        min_value=0,
        max_value=100,
        unit="점",
    ),
    SettingDefinition(
        "issue_auto_publish_threshold",
        "review",
        "자동 공개 기준",
        "검토 없이 공개 가능한 최소 점수",
        "integer",
        min_value=0,
        max_value=100,
        unit="점",
    ),
    SettingDefinition(
        "claim_similarity_threshold",
        "review",
        "주장 묶음 유사도",
        "기존 주장 묶음에 합치는 최소 유사도",
        "float",
        min_value=0,
        max_value=1,
        step=0.01,
    ),
    SettingDefinition(
        "issue_quality_max_attempts",
        "review",
        "품질 재검색 최대 횟수",
        "일반 이슈의 품질 보강 재검색을 허용하는 최대 횟수",
        "integer",
        min_value=0,
        max_value=20,
        unit="회",
    ),
    SettingDefinition(
        "issue_quality_high_impact_max_attempts",
        "review",
        "고영향 품질 재검색 횟수",
        "정치·재난·보건·경제 이슈의 품질 보강 재검색 최대 횟수",
        "integer",
        min_value=0,
        max_value=30,
        unit="회",
    ),
    SettingDefinition(
        "issue_quality_retry_cooldown_minutes",
        "review",
        "품질 재검색 대기 시간",
        "부족 신호가 남은 이슈를 다시 평가하기 전 대기 시간",
        "integer",
        min_value=1,
        max_value=1440,
        unit="분",
    ),
    SettingDefinition(
        "issue_quality_min_articles",
        "review",
        "품질 최소 기사 수",
        "충분한 이슈 품질로 보기 위한 최소 기사 수",
        "integer",
        min_value=1,
        max_value=100,
        unit="건",
    ),
    SettingDefinition(
        "issue_quality_min_publishers",
        "review",
        "품질 최소 매체 수",
        "충분한 이슈 품질로 보기 위한 최소 출처 매체 수",
        "integer",
        min_value=1,
        max_value=50,
        unit="개",
    ),
    SettingDefinition("openai_api_key", "ai", "OpenAI API Key", "임베딩 생성 연결 키", "string", is_secret=True),
    SettingDefinition(
        "openai_podcast_script_model",
        "ai",
        "OpenAI 팟캐스트 대본 모델",
        "팟캐스트 대화 대본 JSON 생성에 사용할 모델",
        "string",
    ),
    SettingDefinition("openai_web_search_enabled", "ai", "OpenAI Web Search", "OpenAI Responses API web_search 보조 사용 여부", "boolean"),
    SettingDefinition("openai_web_search_model", "ai", "OpenAI Web Search 모델", "web_search 도구 호출에 사용할 모델", "string"),
    SettingDefinition(
        "openai_web_search_max_queries_per_round",
        "ai",
        "OpenAI 검색 라운드당 쿼리 수",
        "리서치 라운드 하나에서 OpenAI web_search로 실행할 최대 검색어 수",
        "integer",
        min_value=1,
        max_value=10,
    ),
    SettingDefinition(
        "openai_web_search_daily_issue_limit",
        "ai",
        "OpenAI 검색 일일 상한",
        "이슈 하나가 하루에 OpenAI web_search를 사용할 수 있는 최대 리서치 라운드 수",
        "integer",
        min_value=0,
        max_value=20,
    ),
    SettingDefinition(
        "openai_embedding_model",
        "ai",
        "임베딩 모델",
        "주장·문서 임베딩 생성 모델",
        "string",
    ),
    SettingDefinition(
        "openai_embedding_dimensions",
        "ai",
        "임베딩 차원",
        "모델 기본값 사용 시 비워둡니다.",
        "integer",
        min_value=1,
        max_value=3072,
    ),
    SettingDefinition("openai_tts_model", "ai", "OpenAI TTS 모델", "팟캐스트 음성 생성 모델", "string"),
    SettingDefinition(
        "openai_tts_response_format",
        "ai",
        "OpenAI TTS 출력 형식",
        "다인 진행자 오디오 병합을 위해 기본값은 wav입니다.",
        "select",
        options=("wav", "mp3"),
    ),
    SettingDefinition(
        "openai_tts_speed",
        "ai",
        "OpenAI TTS 속도",
        "팟캐스트 음성 생성 속도 배율",
        "float",
        min_value=0.25,
        max_value=4,
        step=0.05,
    ),
    SettingDefinition(
        "openai_tts_timeout_seconds",
        "ai",
        "OpenAI TTS 제한 시간",
        "음성 생성 요청 최대 대기 시간",
        "integer",
        min_value=10,
        max_value=600,
        unit="초",
    ),
    SettingDefinition("deepseek_api_key", "ai", "DeepSeek API Key", "기사·주장 분석 연결 키", "string", is_secret=True),
    SettingDefinition("deepseek_base_url", "ai", "DeepSeek Base URL", "DeepSeek 호환 API 주소", "string"),
    SettingDefinition("deepseek_flash_model", "ai", "빠른 분석 모델", "일반 분석 작업 모델", "string"),
    SettingDefinition("deepseek_pro_model", "ai", "정밀 검토 모델", "재검증·고위험 작업 모델", "string"),
    SettingDefinition(
        "upload_max_bytes",
        "content",
        "최대 업로드 크기",
        "검증 입력 파일 크기 제한",
        "integer",
        min_value=1024,
        max_value=104857600,
        unit="bytes",
    ),
    SettingDefinition("object_storage_path", "content", "파일 저장 경로", "서버 로컬 저장 경로", "string", is_runtime_mutable=False),
    SettingDefinition(
        "allowed_upload_mime_types",
        "content",
        "허용 파일 형식",
        "업로드 가능한 MIME 타입 목록",
        "list",
    ),
    SettingDefinition("expo_push_enabled", "notifications", "Expo 푸시", "모바일 푸시 발송 여부", "boolean"),
    SettingDefinition("expo_push_url", "notifications", "Expo 푸시 URL", "푸시 발송 API 주소", "string"),
    SettingDefinition(
        "rate_limit_per_minute",
        "security",
        "분당 요청 제한",
        "IP별 요청 제한",
        "integer",
        min_value=0,
        max_value=10000,
        unit="회",
        is_runtime_mutable=False,
    ),
    SettingDefinition(
        "access_token_minutes",
        "security",
        "로그인 유지 시간",
        "새로 발급되는 액세스 토큰 유효 시간",
        "integer",
        min_value=5,
        max_value=43200,
        unit="분",
        is_runtime_mutable=False,
    ),
    SettingDefinition(
        "cors_origins",
        "security",
        "허용 웹 주소",
        "브라우저 접근을 허용할 프론트 주소",
        "list",
        is_runtime_mutable=False,
    ),
    SettingDefinition(
        "jwt_secret",
        "security",
        "JWT 서명 키",
        "토큰 서명에 사용하는 서버 키",
        "string",
        is_secret=True,
        is_runtime_mutable=False,
    ),
)

DEFINITION_BY_KEY = {definition.key: definition for definition in DEFINITIONS}
GROUP_BY_ID = {group.id: group for group in GROUPS}


def _base_value(definition: SettingDefinition) -> Any:
    settings = get_settings()
    attr = definition.default_attr or definition.key
    return getattr(settings, attr, definition.default_value)


def _coerce_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        source = value.replace("\n", ",")
        return [item.strip() for item in source.split(",") if item.strip()]
    return [str(value).strip()] if str(value).strip() else []


def _coerce_value(definition: SettingDefinition, value: Any) -> Any:
    if definition.value_type == "boolean":
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on", "enabled"}
        return bool(value)
    if definition.value_type == "integer":
        if value in ("", None):
            return None
        coerced = int(value)
        if definition.min_value is not None and coerced < definition.min_value:
            raise ValueError(f"{definition.label} 값이 허용 범위보다 작습니다.")
        if definition.max_value is not None and coerced > definition.max_value:
            raise ValueError(f"{definition.label} 값이 허용 범위보다 큽니다.")
        return coerced
    if definition.value_type == "float":
        if value in ("", None):
            return None
        coerced = float(value)
        if definition.min_value is not None and coerced < definition.min_value:
            raise ValueError(f"{definition.label} 값이 허용 범위보다 작습니다.")
        if definition.max_value is not None and coerced > definition.max_value:
            raise ValueError(f"{definition.label} 값이 허용 범위보다 큽니다.")
        return coerced
    if definition.value_type == "list":
        return _coerce_list(value)
    if definition.value_type == "select":
        coerced = str(value)
        if definition.options and coerced not in definition.options:
            raise ValueError(f"{definition.label} 값이 허용된 옵션이 아닙니다.")
        return coerced
    return "" if value is None else str(value)


def _settings_by_key(db: Session) -> dict[str, models.SystemSetting]:
    rows = db.scalars(select(models.SystemSetting)).all()
    return {row.key: row for row in rows}


def get_effective_setting(db: Session | None, key: str, default: Any = None) -> Any:
    definition = DEFINITION_BY_KEY.get(key)
    if not definition:
        return default
    base = _base_value(definition)
    if db is None:
        return base
    row = db.get(models.SystemSetting, key)
    if row is None or row.value is None:
        return base
    return _coerce_value(definition, row.value)


def _item_from_definition(
    definition: SettingDefinition,
    row: models.SystemSetting | None,
) -> AdminSettingItem:
    base = _base_value(definition)
    has_override = row is not None and row.value is not None
    raw_value = row.value if has_override else base
    source = "admin" if has_override else "env" if base not in (None, "", []) else "default"
    configured = bool(raw_value not in (None, "", []))
    value = None if definition.is_secret else _coerce_value(definition, raw_value)
    default_value = None if definition.is_secret else _coerce_value(definition, base)

    return AdminSettingItem(
        configured=configured,
        defaultValue=default_value,
        description=definition.description,
        group=definition.group,
        isRuntimeMutable=definition.is_runtime_mutable,
        isSecret=definition.is_secret,
        key=definition.key,
        label=definition.label,
        max=definition.max_value,
        min=definition.min_value,
        options=list(definition.options),
        source=source,
        step=definition.step,
        unit=definition.unit,
        updatedAt=to_iso(row.updated_at) if row else None,
        value=value,
        valueType=definition.value_type,
    )


def get_admin_settings(db: Session) -> AdminSettingsResponse:
    rows = _settings_by_key(db)
    groups: list[AdminSettingsGroup] = []
    latest_updated = None
    for group in GROUPS:
        items = [
            _item_from_definition(definition, rows.get(definition.key))
            for definition in DEFINITIONS
            if definition.group == group.id
        ]
        if not items:
            continue
        groups.append(
            AdminSettingsGroup(
                description=group.description,
                id=group.id,
                items=items,
                label=group.label,
            ),
        )

    for row in rows.values():
        if latest_updated is None or row.updated_at > latest_updated:
            latest_updated = row.updated_at

    return AdminSettingsResponse(
        groups=groups,
        updatedAt=to_iso(latest_updated or models.now_utc()),
    )


def update_admin_settings(db: Session, *, payload: list[Any], user_id: str) -> AdminSettingsResponse:
    for item in payload:
        definition = DEFINITION_BY_KEY.get(item.key)
        if definition is None:
            raise ValueError(f"관리할 수 없는 설정입니다: {item.key}")

        existing = db.get(models.SystemSetting, item.key)
        if item.reset or item.clear:
            if existing:
                db.delete(existing)
            continue

        if definition.is_secret and item.value in (None, "", "********", "••••••••"):
            continue

        coerced = _coerce_value(definition, item.value)
        if existing is None:
            existing = models.SystemSetting(
                description=definition.description,
                group=definition.group,
                is_secret=definition.is_secret,
                key=definition.key,
                label=definition.label,
                value_type=definition.value_type,
            )
            db.add(existing)
        existing.description = definition.description
        existing.group = definition.group
        existing.is_secret = definition.is_secret
        existing.label = definition.label
        existing.updated_at = models.now_utc()
        existing.updated_by = user_id
        existing.value = coerced
        existing.value_type = definition.value_type

    db.commit()
    return get_admin_settings(db)
