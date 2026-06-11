from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def now_utc() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(24), default="user")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    preferences: Mapped[dict] = mapped_column(JSON, default=dict)


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    slug: Mapped[str] = mapped_column(String(140), unique=True, index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class MajorTopic(Base):
    __tablename__ = "major_topics"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    slug: Mapped[str] = mapped_column(String(240), unique=True, index=True)
    topic: Mapped[str] = mapped_column(String(80), default="사회", index=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(60), default="active", index=True)
    keywords_json: Mapped[list] = mapped_column(JSON, default=list)
    aliases_json: Mapped[list] = mapped_column(JSON, default=list)
    signal_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class EventGroup(Base):
    __tablename__ = "event_groups"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    major_topic_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    topic: Mapped[str] = mapped_column(String(80), default="사회", index=True)
    name: Mapped[str] = mapped_column(String(240), index=True)
    slug: Mapped[str] = mapped_column(String(280), default="", index=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(60), default="active", index=True)
    keywords_json: Mapped[list] = mapped_column(JSON, default=list)
    aliases_json: Mapped[list] = mapped_column(JSON, default=list)
    signal_json: Mapped[dict] = mapped_column(JSON, default=dict)
    article_count: Mapped[int] = mapped_column(Integer, default=0)
    issue_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Issue(Base):
    __tablename__ = "issues"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    topic_id: Mapped[str | None] = mapped_column(ForeignKey("topics.id"), nullable=True)
    major_topic_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    event_group_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    major_topic_name: Mapped[str] = mapped_column(String(200), default="", index=True)
    event_group_name: Mapped[str] = mapped_column(String(240), default="", index=True)
    title: Mapped[str] = mapped_column(String(240), index=True)
    slug: Mapped[str] = mapped_column(String(280), default="", index=True)
    topic: Mapped[str] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(String(80), default="검증 진행")
    risk: Mapped[str] = mapped_column(String(80), default="일반")
    sensitivity_level: Mapped[str] = mapped_column(String(40), default="normal")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    last_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    summary: Mapped[str] = mapped_column(Text, default="")
    issue_score: Mapped[int] = mapped_column(Integer, default=0)
    article_count: Mapped[int] = mapped_column(Integer, default=0)
    cluster_count: Mapped[int] = mapped_column(Integer, default=0)
    verified_count: Mapped[int] = mapped_column(Integer, default=0)
    needs_review_count: Mapped[int] = mapped_column(Integer, default=0)
    changed_claims: Mapped[int] = mapped_column(Integer, default=0)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True)
    representative_image_url: Mapped[str] = mapped_column(Text, default="")
    representative_image_source: Mapped[str] = mapped_column(String(200), default="")
    representative_image_source_url: Mapped[str] = mapped_column(Text, default="")
    representative_image_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    representative_image_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    quality_score: Mapped[int] = mapped_column(Integer, default=0)
    quality_status: Mapped[str] = mapped_column(String(60), default="unchecked", index=True)
    quality_report_json: Mapped[dict] = mapped_column(JSON, default=dict)
    quality_attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_quality_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_quality_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ranking_json: Mapped[dict] = mapped_column(JSON, default=dict)
    confirmed_facts: Mapped[list] = mapped_column(JSON, default=list)
    claim_clusters: Mapped[list] = mapped_column(JSON, default=list)
    claims: Mapped[list] = mapped_column(JSON, default=list)
    evidences: Mapped[list] = mapped_column(JSON, default=list)
    perspectives: Mapped[list] = mapped_column(JSON, default=list)
    articles: Mapped[list] = mapped_column(JSON, default=list)
    timeline: Mapped[list] = mapped_column(JSON, default=list)
    source_documents: Mapped[list] = mapped_column(JSON, default=list)
    number_changes: Mapped[list] = mapped_column(JSON, default=list)


class VerificationRequest(Base):
    __tablename__ = "verification_requests"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    input_type: Mapped[str] = mapped_column(String(40), default="url")
    article_url: Mapped[str] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text, default="")
    content_hash: Mapped[str] = mapped_column(String(128), default="", index=True)
    parsed_content: Mapped[dict] = mapped_column(JSON, default=dict)
    issue_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    matched_issue_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    result_issue_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    standalone_result_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    uploaded_file_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="queued")
    ai_status: Mapped[str] = mapped_column(String(80), default="queued")
    ai_summary: Mapped[str] = mapped_column(Text, default="")
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class SubmittedClaim(Base):
    __tablename__ = "submitted_claims"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    issue_id: Mapped[str] = mapped_column(String(80), index=True)
    claim_text: Mapped[str] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(Text)
    evidence_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    related_cluster: Mapped[str | None] = mapped_column(String(160), nullable=True)
    claim_type: Mapped[str] = mapped_column(String(80))
    refutable_point: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(60), default="received")
    moderation_status: Mapped[str] = mapped_column(String(60), default="pending")
    sanitized_text: Mapped[str] = mapped_column(Text, default="")
    moderation_reason: Mapped[str] = mapped_column(Text, default="")
    cluster_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    duplicate_cluster_candidate: Mapped[str | None] = mapped_column(String(80), nullable=True)
    embedding: Mapped[list | None] = mapped_column(JSON, nullable=True)
    ai_notes: Mapped[dict] = mapped_column(JSON, default=dict)
    approved_by: Mapped[str | None] = mapped_column(String(80), nullable=True)
    reflected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class SavedIssue(Base):
    __tablename__ = "saved_issues"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    issue_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class IssueReport(Base):
    __tablename__ = "issue_reports"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    issue_id: Mapped[str] = mapped_column(String(80), index=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    markdown_report: Mapped[str] = mapped_column(Text, default="")
    share_token: Mapped[str] = mapped_column(String(120), default="", index=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    report_type: Mapped[str] = mapped_column(String(40), default="issue")
    status: Mapped[str] = mapped_column(String(40), default="created")
    download_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class AdminQueueItem(Base):
    __tablename__ = "admin_queue_items"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    title: Mapped[str] = mapped_column(String(240))
    topic: Mapped[str] = mapped_column(String(80))
    article_count: Mapped[int] = mapped_column(Integer, default=0)
    first_detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    status: Mapped[str] = mapped_column(String(80), default="검토 대기")
    priority: Mapped[str] = mapped_column(String(40), default="보통")
    reason: Mapped[str] = mapped_column(Text, default="")


class ModerationReport(Base):
    __tablename__ = "moderation_reports"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    issue_id: Mapped[str] = mapped_column(String(80), index=True)
    issue_title: Mapped[str] = mapped_column(String(240))
    target_type: Mapped[str] = mapped_column(String(80))
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), default="open")
    priority: Mapped[str] = mapped_column(String(40), default="보통")
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    excerpt: Mapped[str] = mapped_column(Text, default="")


class SourceDomain(Base):
    __tablename__ = "source_domains"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    domain: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    source_type: Mapped[str] = mapped_column(String(80))
    credibility: Mapped[float] = mapped_column(Float, default=0.5)
    status: Mapped[str] = mapped_column(String(40), default="watch")
    collection_url: Mapped[str] = mapped_column(Text, default="")
    collection_interval_minutes: Mapped[int] = mapped_column(Integer, default=30)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_collected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_collection_status: Mapped[str] = mapped_column(String(80), default="idle")
    robots_policy: Mapped[str] = mapped_column(String(80), default="unknown")
    last_reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    note: Mapped[str] = mapped_column(Text, default="")


class SearchKeyword(Base):
    __tablename__ = "search_keywords"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    query: Mapped[str] = mapped_column(String(300), unique=True, index=True)
    seed_query: Mapped[str] = mapped_column(String(300), default="", index=True)
    topic: Mapped[str] = mapped_column(String(80), default="사회", index=True)
    priority: Mapped[str] = mapped_column(String(40), default="normal")
    status: Mapped[str] = mapped_column(String(60), default="active", index=True)
    source: Mapped[str] = mapped_column(String(80), default="manual")
    issue_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    search_interval_minutes: Mapped[int] = mapped_column(Integer, default=30)
    last_searched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_result_count: Mapped[int] = mapped_column(Integer, default=0)
    last_new_article_count: Mapped[int] = mapped_column(Integer, default=0)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class DiscoveryTopic(Base):
    __tablename__ = "discovery_topics"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    topic: Mapped[str] = mapped_column(String(80), default="사회", index=True)
    base_queries_json: Mapped[list] = mapped_column(JSON, default=list)
    priority: Mapped[str] = mapped_column(String(40), default="normal")
    status: Mapped[str] = mapped_column(String(60), default="active", index=True)
    discovery_interval_minutes: Mapped[int] = mapped_column(Integer, default=60)
    max_results_per_query: Mapped[int] = mapped_column(Integer, default=12)
    min_cluster_size: Mapped[int] = mapped_column(Integer, default=2)
    last_discovered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_result_count: Mapped[int] = mapped_column(Integer, default=0)
    last_candidate_count: Mapped[int] = mapped_column(Integer, default=0)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class DiscoveredIncident(Base):
    __tablename__ = "discovered_incidents"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    discovery_topic_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    issue_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(240), index=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    topic: Mapped[str] = mapped_column(String(80), default="사회", index=True)
    score: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(60), default="candidate", index=True)
    article_ids_json: Mapped[list] = mapped_column(JSON, default=list)
    keyword_ids_json: Mapped[list] = mapped_column(JSON, default=list)
    signals_json: Mapped[dict] = mapped_column(JSON, default=dict)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class SchedulerHeartbeat(Base):
    __tablename__ = "scheduler_heartbeats"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(120), default="")
    status: Mapped[str] = mapped_column(String(60), default="idle")
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_tick_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_tick_finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    tick_count: Mapped[int] = mapped_column(Integer, default=0)
    last_tick_json: Mapped[dict] = mapped_column(JSON, default=dict)
    error_message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class SystemSetting(Base):
    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    group: Mapped[str] = mapped_column(String(80), index=True)
    label: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    value: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    value_type: Mapped[str] = mapped_column(String(40))
    is_secret: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_by: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    agent: Mapped[str] = mapped_column(String(120))
    agent_name: Mapped[str] = mapped_column(String(120), default="")
    issue_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    article_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    claim_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(60), default="running")
    target: Mapped[str] = mapped_column(String(240), default="")
    input_json: Mapped[dict] = mapped_column(JSON, default=dict)
    output_json: Mapped[dict] = mapped_column(JSON, default=dict)
    error_message: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    failure_reason: Mapped[str] = mapped_column(Text, default="")


class Article(Base):
    __tablename__ = "articles"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    issue_id: Mapped[str | None] = mapped_column(String(80), index=True, nullable=True)
    source_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(500), index=True)
    publisher: Mapped[str] = mapped_column(String(200), default="")
    url: Mapped[str] = mapped_column(Text)
    normalized_url: Mapped[str] = mapped_column(Text, default="")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    body_text: Mapped[str] = mapped_column(Text, default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    dedup_hash: Mapped[str] = mapped_column(String(128), index=True)
    content_hash: Mapped[str] = mapped_column(String(128), default="", index=True)
    source_type: Mapped[str] = mapped_column(String(80), default="news")
    parse_status: Mapped[str] = mapped_column(String(80), default="pending")
    ai_notes: Mapped[dict] = mapped_column(JSON, default=dict)
    language: Mapped[str] = mapped_column(String(20), default="ko")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class ImageCandidate(Base):
    __tablename__ = "image_candidates"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    issue_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    article_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    url: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(Text, default="")
    publisher: Mapped[str] = mapped_column(String(200), default="")
    source_type: Mapped[str] = mapped_column(String(80), default="news")
    width: Mapped[int] = mapped_column(Integer, default=0)
    height: Mapped[int] = mapped_column(Integer, default=0)
    mime_type: Mapped[str] = mapped_column(String(120), default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(60), default="candidate", index=True)
    reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class UserInterestProfile(Base):
    __tablename__ = "user_interest_profiles"

    user_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    topic_weights_json: Mapped[dict] = mapped_column(JSON, default=dict)
    major_topic_weights_json: Mapped[dict] = mapped_column(JSON, default=dict)
    event_group_weights_json: Mapped[dict] = mapped_column(JSON, default=dict)
    publisher_weights_json: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class PodcastEpisode(Base):
    __tablename__ = "podcast_episodes"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    issue_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(260), index=True)
    subtitle: Mapped[str] = mapped_column(String(260), default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(80), default="사회", index=True)
    episode_type: Mapped[str] = mapped_column(String(60), default="issue", index=True)
    episode_format: Mapped[str] = mapped_column(String(40), default="solo")
    variant: Mapped[str] = mapped_column(String(40), default="standard", index=True)
    status: Mapped[str] = mapped_column(String(40), default="published", index=True)
    audio_url: Mapped[str] = mapped_column(Text, default="")
    thumbnail_url: Mapped[str] = mapped_column(Text, default="")
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)
    host_profiles_json: Mapped[list] = mapped_column(JSON, default=list)
    script_json: Mapped[list] = mapped_column(JSON, default=list)
    source_json: Mapped[list] = mapped_column(JSON, default=list)
    rank_json: Mapped[dict] = mapped_column(JSON, default=dict)
    generation_json: Mapped[dict] = mapped_column(JSON, default=dict)
    auto_published: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=now_utc)

    __table_args__ = (
        UniqueConstraint(
            "issue_id",
            "episode_format",
            "variant",
            name="uq_podcast_episode_issue_format_variant",
        ),
    )


class ClaimCluster(Base):
    __tablename__ = "claim_clusters"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    issue_id: Mapped[str] = mapped_column(String(80), index=True)
    title: Mapped[str] = mapped_column(String(240))
    canonical_question: Mapped[str] = mapped_column(Text, default="")
    description: Mapped[str] = mapped_column(Text, default="")
    cluster_type: Mapped[str] = mapped_column(String(80), default="fact")
    status: Mapped[str] = mapped_column(String(60), default="active")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Claim(Base):
    __tablename__ = "claims"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    issue_id: Mapped[str] = mapped_column(String(80), index=True)
    article_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    cluster_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    submitted_claim_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    claim_text: Mapped[str] = mapped_column(Text)
    sanitized_text: Mapped[str] = mapped_column(Text, default="")
    claim_type: Mapped[str] = mapped_column(String(80), default="사실 주장")
    entities_json: Mapped[dict] = mapped_column(JSON, default=dict)
    ai_notes: Mapped[dict] = mapped_column(JSON, default=dict)
    embedding: Mapped[list | None] = mapped_column(JSON, nullable=True)
    verdict: Mapped[str] = mapped_column(String(80), default="근거 부족")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(80), default="needs_evidence")
    source_kind: Mapped[str] = mapped_column(String(60), default="article")
    spread_count: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Evidence(Base):
    __tablename__ = "evidences"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    claim_id: Mapped[str] = mapped_column(String(80), index=True)
    title: Mapped[str] = mapped_column(String(500))
    url: Mapped[str] = mapped_column(Text)
    source_domain: Mapped[str] = mapped_column(String(255), default="", index=True)
    source_type: Mapped[str] = mapped_column(String(80), default="news")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    evidence_text: Mapped[str] = mapped_column(Text, default="")
    retrieval_json: Mapped[dict] = mapped_column(JSON, default=dict)
    credibility_score: Mapped[float] = mapped_column(Float, default=0.5)
    relevance_score: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class VerdictHistory(Base):
    __tablename__ = "verdict_histories"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    claim_id: Mapped[str] = mapped_column(String(80), index=True)
    previous_verdict: Mapped[str] = mapped_column(String(80), default="")
    current_verdict: Mapped[str] = mapped_column(String(80))
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    reason: Mapped[str] = mapped_column(Text, default="")
    evidence_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Perspective(Base):
    __tablename__ = "perspectives"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    issue_id: Mapped[str] = mapped_column(String(80), index=True)
    name: Mapped[str] = mapped_column(String(200))
    summary: Mapped[str] = mapped_column(Text, default="")
    core_arguments_json: Mapped[list] = mapped_column(JSON, default=list)
    common_ground_json: Mapped[list] = mapped_column(JSON, default=list)
    conflicts_json: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class UpdateLog(Base):
    __tablename__ = "update_logs"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    issue_id: Mapped[str] = mapped_column(String(80), index=True)
    update_type: Mapped[str] = mapped_column(String(80))
    title: Mapped[str] = mapped_column(String(240))
    description: Mapped[str] = mapped_column(Text, default="")
    related_claim_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    related_article_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(80), index=True)
    issue_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    type: Mapped[str] = mapped_column(String(80))
    title: Mapped[str] = mapped_column(String(240))
    body: Mapped[str] = mapped_column(Text, default="")
    href: Mapped[str] = mapped_column(String(240), default="")
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    delivery_status: Mapped[str] = mapped_column(String(80), default="created")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class DeviceToken(Base):
    __tablename__ = "device_tokens"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(80), index=True)
    platform: Mapped[str] = mapped_column(String(40), default="expo")
    token: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    __table_args__ = (UniqueConstraint("user_id", "token", name="uq_device_tokens_user_token"),)


class CollectorRun(Base):
    __tablename__ = "collector_runs"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    source_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    collector: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(80), default="running")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    article_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str] = mapped_column(Text, default="")
    output_json: Mapped[dict] = mapped_column(JSON, default=dict)


class ResearchRun(Base):
    __tablename__ = "research_runs"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    issue_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    discovery_topic_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    keyword_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    trigger_type: Mapped[str] = mapped_column(String(80), default="manual", index=True)
    seed_query: Mapped[str] = mapped_column(String(300), default="")
    status: Mapped[str] = mapped_column(String(80), default="running", index=True)
    round_index: Mapped[int] = mapped_column(Integer, default=1)
    plan_json: Mapped[dict] = mapped_column(JSON, default=dict)
    source_routes_json: Mapped[list] = mapped_column(JSON, default=list)
    executed_queries_json: Mapped[list] = mapped_column(JSON, default=list)
    result_urls_json: Mapped[list] = mapped_column(JSON, default=list)
    selected_article_ids_json: Mapped[list] = mapped_column(JSON, default=list)
    missing_signals_json: Mapped[list] = mapped_column(JSON, default=list)
    error_message: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)


class JobAttempt(Base):
    __tablename__ = "job_attempts"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    job_type: Mapped[str] = mapped_column(String(120), index=True)
    target_id: Mapped[str] = mapped_column(String(120), index=True)
    status: Mapped[str] = mapped_column(String(80), default="queued")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str] = mapped_column(Text, default="")
    input_json: Mapped[dict] = mapped_column(JSON, default=dict)
    output_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    filename: Mapped[str] = mapped_column(String(260))
    content_type: Mapped[str] = mapped_column(String(120), default="")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    storage_url: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(80), default="received")
    safety_status: Mapped[str] = mapped_column(String(80), default="pending")
    parse_status: Mapped[str] = mapped_column(String(80), default="pending")
    extracted_text: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class ProductMetricEvent(Base):
    __tablename__ = "product_metric_events"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    issue_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    report_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
