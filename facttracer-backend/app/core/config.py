from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="FACTTRACER_",
        extra="ignore",
    )

    app_name: str = "FactTracer Backend"
    env: str = "local"
    api_prefix: str = "/v1"
    database_url: str = "sqlite:///./facttracer.db"
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 60 * 24
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: [
            "http://localhost:3002",
            "http://127.0.0.1:3002",
            "http://localhost:3003",
            "http://127.0.0.1:3003",
        ],
    )

    ai_processing_enabled: bool = True
    bootstrap_default_discovery_enabled: bool = True
    embedded_scheduler_enabled: bool = True
    embedded_worker_enabled: bool = True
    redis_url: str = "redis://localhost:6379/0"
    worker_backend: str = "inline"
    scheduler_poll_seconds: int = 30
    embedded_worker_poll_seconds: int = 5
    embedded_worker_batch_size: int = 5
    embedded_worker_concurrency: int = 1
    job_stale_after_minutes: int = 15
    search_max_results_per_keyword: int = 5
    search_recent_days: int = 14
    research_max_rounds: int = 2
    research_max_queries_per_round: int = 16
    research_max_results_per_query: int = 8
    research_openai_fallback_after_round: int = 2
    openai_web_search_max_queries_per_round: int = 2
    openai_web_search_daily_issue_limit: int = 2
    issue_followup_window_days: int = 7
    issue_followup_interval_minutes: int = 180
    issue_followup_limit: int = 12
    issue_min_sources_for_public: int = 1
    issue_source_backfill_limit: int = 8
    issue_quality_max_attempts: int = 3
    issue_quality_high_impact_max_attempts: int = 5
    issue_quality_retry_cooldown_minutes: int = 30
    issue_quality_min_articles: int = 4
    issue_quality_min_publishers: int = 2
    rate_limit_per_minute: int = 600
    collector_user_agent: str = "FactTracerBot/0.1"
    collector_timeout_seconds: int = 12
    issue_candidate_threshold: int = 55
    issue_auto_publish_threshold: int = 88
    claim_similarity_threshold: float = 0.78
    upload_max_bytes: int = 10 * 1024 * 1024
    object_storage_path: str = "./storage"
    expo_push_enabled: bool = False
    expo_push_url: str = "https://exp.host/--/api/v2/push/send"
    allowed_upload_mime_types: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: [
            "application/pdf",
            "image/jpeg",
            "image/png",
            "image/webp",
            "text/plain",
        ],
    )

    openai_api_key: str | None = Field(default=None, validation_alias="OPENAI_API_KEY")
    openai_web_search_enabled: bool = False
    openai_web_search_model: str = Field(default="gpt-5.5", validation_alias="OPENAI_WEB_SEARCH_MODEL")
    openai_podcast_script_model: str = Field(
        default="gpt-4o-mini",
        validation_alias="OPENAI_PODCAST_SCRIPT_MODEL",
    )
    openai_embedding_model: str = Field(
        default="text-embedding-3-small",
        validation_alias="OPENAI_EMBEDDING_MODEL",
    )
    openai_embedding_dimensions: int | None = Field(
        default=None,
        validation_alias="OPENAI_EMBEDDING_DIMENSIONS",
    )
    openai_tts_model: str = Field(
        default="gpt-4o-mini-tts",
        validation_alias="OPENAI_TTS_MODEL",
    )
    openai_tts_response_format: str = Field(
        default="wav",
        validation_alias="OPENAI_TTS_RESPONSE_FORMAT",
    )
    openai_tts_speed: float = Field(
        default=1.0,
        validation_alias="OPENAI_TTS_SPEED",
    )
    openai_tts_timeout_seconds: int = Field(
        default=120,
        validation_alias="OPENAI_TTS_TIMEOUT_SECONDS",
    )
    podcast_generation_enabled: bool = True
    podcast_generation_interval_minutes: int = 60
    podcast_generation_limit: int = 6
    podcast_tts_enabled: bool = True
    podcast_tts_render_on_generate: bool = True
    podcast_min_publish_quality_score: int = 70
    podcast_min_sources_for_publish: int = 1
    podcast_sensitive_topics_require_official_source: bool = True
    podcast_recommendation_impact_weight: float = 0.35
    podcast_recommendation_verification_weight: float = 0.25
    podcast_recommendation_freshness_weight: float = 0.20
    podcast_recommendation_controversy_weight: float = 0.10
    podcast_recommendation_momentum_weight: float = 0.10
    podcast_personalization_interest_weight: float = 0.35
    podcast_tts_pronunciation_lexicon: str = ""

    deepseek_api_key: str | None = Field(
        default=None,
        validation_alias="DEEPSEEK_API_KEY",
    )
    deepseek_base_url: str = Field(
        default="https://api.deepseek.com",
        validation_alias="DEEPSEEK_BASE_URL",
    )
    deepseek_flash_model: str = Field(
        default="deepseek-v4-flash",
        validation_alias="DEEPSEEK_FLASH_MODEL",
    )
    deepseek_pro_model: str = Field(
        default="deepseek-v4-pro",
        validation_alias="DEEPSEEK_PRO_MODEL",
    )
    deepseek_model: str | None = Field(
        default=None,
        validation_alias="DEEPSEEK_MODEL",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("allowed_upload_mime_types", mode="before")
    @classmethod
    def parse_upload_mime_types(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @property
    def effective_deepseek_flash_model(self) -> str:
        return self.deepseek_model or self.deepseek_flash_model


@lru_cache
def get_settings() -> Settings:
    return Settings()
