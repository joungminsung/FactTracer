from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.api.dependencies import reviewer_user
from app.db.session import get_db
from app.schemas import (
    AdminAgentsResponse,
    AdminDashboardResponse,
    AdminDashboardMetric,
    AdminDashboardNavItem,
    AdminSettingsResponse,
    AdminSettingsUpdateRequest,
    AdminIssueResponse,
    AdminReportsResponse,
    AdminSourcesResponse,
    CollectorRunRequest,
    CollectorRunResponse,
    CollectorRunsResponse,
    DiscoveredIncidentsResponse,
    DiscoveryTopicCreateRequest,
    DiscoveryTopicsResponse,
    IssueMergeRequest,
    IssueSplitRequest,
    JobListResponse,
    MutationResponse,
    PodcastDetailResponse,
    PodcastFeedResponse,
    ReverificationRequest,
    ResearchRunItem,
    ResearchRunListResponse,
    SchedulerStatusResponse,
    SearchKeywordSeedRequest,
    SearchKeywordsResponse,
    SourcePolicyRequest,
    SourceCreateRequest,
    SourceDomain as SourceDomainSchema,
    SourceUpdateRequest,
)
from app.serializers import (
    admin_queue_item,
    agent_run,
    discovered_incident,
    discovery_topic,
    issue_detail,
    moderation_report,
    search_keyword,
    source_domain,
    podcast_episode_card,
    podcast_episode_detail,
)
from app.services.ai.pipeline import process_reverification_request
from app.services.admin.issue_operations import hide_issue, merge_issue, set_manual_representative_image, split_article_to_issue
from app.services.admin.recheck import reverify_single_claim
from app.services.admin.settings import get_admin_settings, get_effective_setting, update_admin_settings
from app.services.admin.source_policy import update_source_policy
from app.services.discovery.incident_detector import upsert_discovery_topic
from app.services.issues.publisher import publish_issue_from_candidate
from app.services.jobs import (
    enqueue_job,
    execute_job,
    run_due_jobs,
    schedule_due_collector_jobs,
    schedule_due_discovery_jobs,
    schedule_due_issue_backfill_jobs,
    schedule_due_search_jobs,
)
from app.services.podcasts.generator import get_episode_issue, list_podcast_episodes
from app.services.scheduler.runtime import scheduler_status, tick_scheduler_once
from app.services.search.keywords import seed_search_keywords
from app.utils import new_id, to_iso

router = APIRouter(prefix="/admin", tags=["admin"])


class ReportResolutionRequest(BaseModel):
    status: str


class SourceStatusRequest(BaseModel):
    status: str


class AgentRunRequest(BaseModel):
    agent: str


class RepresentativeImageRequest(BaseModel):
    source: str = ""
    sourceUrl: str = ""
    url: str


class PodcastStatusRequest(BaseModel):
    status: str


def scheduler_response(row: models.SchedulerHeartbeat) -> SchedulerStatusResponse:
    return SchedulerStatusResponse(
        errorMessage=row.error_message,
        id=row.id,
        lastHeartbeatAt=row.last_heartbeat_at.isoformat() if row.last_heartbeat_at else None,
        lastTick=row.last_tick_json or {},
        lastTickFinishedAt=row.last_tick_finished_at.isoformat() if row.last_tick_finished_at else None,
        lastTickStartedAt=row.last_tick_started_at.isoformat() if row.last_tick_started_at else None,
        lockedUntil=row.locked_until.isoformat() if row.locked_until else None,
        ownerId=row.owner_id,
        status=row.status,
        tickCount=row.tick_count,
    )


def queue_items(db: Session) -> list[models.AdminQueueItem]:
    return db.scalars(
        select(models.AdminQueueItem).order_by(models.AdminQueueItem.first_detected_at.desc()),
    ).all()


def recent_agent_runs(db: Session) -> list[models.AgentRun]:
    return db.scalars(
        select(models.AgentRun).order_by(models.AgentRun.finished_at.desc()).limit(20),
    ).all()


def podcast_issue_map(
    db: Session,
    episodes: list[models.PodcastEpisode],
) -> dict[str, models.Issue]:
    issue_ids = {episode.issue_id for episode in episodes if episode.issue_id}
    if not issue_ids:
        return {}
    rows = db.scalars(select(models.Issue).where(models.Issue.id.in_(issue_ids))).all()
    return {issue.id: issue for issue in rows}


def job_user_message(row: models.JobAttempt) -> str:
    if not row.last_error:
        return ""
    error = row.last_error.lower()
    if row.job_type == "render_podcast_audio":
        if "openai" in error or "api key" in error or "invalid_api_key" in error:
            return "OpenAI TTS 연결 키 또는 모델 설정을 확인해야 합니다."
        if "audio" in error or "file" in error or "storage" in error:
            return "오디오 파일 생성 또는 저장 경로를 확인해야 합니다."
        return "팟캐스트 음성 렌더링 작업이 실패했습니다. TTS 설정과 회차 대본을 확인해 주세요."
    if row.job_type == "generate_podcasts":
        if "source" in error or "official" in error:
            return "출처 조건을 충족하지 못해 팟캐스트 생성 또는 발행이 보류됐습니다."
        return "팟캐스트 자동 생성 작업이 실패했습니다. 연결 이슈와 생성 설정을 확인해 주세요."
    return row.last_error


@router.get("/dashboard", response_model=AdminDashboardResponse)
def dashboard(
    _: Annotated[models.User, Depends(reviewer_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AdminDashboardResponse:
    queue = queue_items(db)
    reports_count = len(db.scalars(select(models.ModerationReport)).all())
    source_count = len(db.scalars(select(models.SourceDomain)).all())
    metric_event_count = len(db.scalars(select(models.ProductMetricEvent)).all())
    selected = queue[0] if queue else None

    public_issue = db.get(models.Issue, selected.id) if selected else None
    claims = public_issue.claims if public_issue else []
    clusters = public_issue.claim_clusters if public_issue else []
    evidences = public_issue.evidences if public_issue else []

    return AdminDashboardResponse(
        agentRuns=[agent_run(run) for run in recent_agent_runs(db)],
        claimClusters=clusters or [],
        claims=claims or [],
        evidences=evidences or [],
        metrics=[
            AdminDashboardMetric(label="대기 이슈", value=str(len(queue))),
            AdminDashboardMetric(label="신고 표현", value=str(reports_count)),
            AdminDashboardMetric(label="출처", value=str(source_count)),
            AdminDashboardMetric(label="제품 지표", value=str(metric_event_count)),
        ],
        navItems=[
            AdminDashboardNavItem(label="검토 목록", value=str(len(queue))),
            AdminDashboardNavItem(label="민감 이슈", value=str(len(queue))),
            AdminDashboardNavItem(label="신고 표현", value=str(reports_count)),
            AdminDashboardNavItem(label="출처 관리", value=str(source_count)),
            AdminDashboardNavItem(label="자동 처리 기록", value=str(len(recent_agent_runs(db)))),
            AdminDashboardNavItem(label="운영 설정", value=""),
        ],
        queue=[admin_queue_item(item) for item in queue],
        selectedIssue=admin_queue_item(selected) if selected else None,
    )


@router.post("/queue/sync", response_model=MutationResponse)
def sync_queue(
    _: Annotated[models.User, Depends(reviewer_user)],
    db: Annotated[Session, Depends(get_db)],
) -> MutationResponse:
    scheduled = schedule_due_collector_jobs(db)
    scheduled_discovery = schedule_due_discovery_jobs(db)
    scheduled_search = schedule_due_search_jobs(db)
    scheduled_backfill = schedule_due_issue_backfill_jobs(db)
    executed = run_due_jobs(db)
    db.add(
        models.AgentRun(
            agent="Queue Sync",
            agent_name="Queue Sync",
            id=new_id("run"),
            output_json={
                "scheduledBackfills": len(scheduled_backfill),
                "scheduled": len(scheduled),
                "scheduledDiscoveries": len(scheduled_discovery),
                "scheduledSearches": len(scheduled_search),
                "executed": len(executed),
            },
            status="completed",
            target="검토 목록",
        ),
    )
    db.commit()
    return MutationResponse(id="admin-queue", message="큐 동기화를 시작했습니다.", status="queued")


@router.get("/podcasts", response_model=PodcastFeedResponse)
def admin_podcasts(
    _: Annotated[models.User, Depends(reviewer_user)],
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
) -> PodcastFeedResponse:
    query = select(models.PodcastEpisode)
    if status_filter and status_filter != "all":
        query = query.where(models.PodcastEpisode.status == status_filter)
    episodes = db.scalars(
        query.order_by(models.PodcastEpisode.created_at.desc()).limit(limit),
    ).all()
    issues = podcast_issue_map(db, episodes)
    return PodcastFeedResponse(
        episodes=[
            podcast_episode_card(episode, issues.get(episode.issue_id or ""))
            for episode in episodes
        ],
    )


@router.get("/podcasts/{episode_id}", response_model=PodcastDetailResponse)
def admin_podcast_detail(
    episode_id: str,
    _: Annotated[models.User, Depends(reviewer_user)],
    db: Annotated[Session, Depends(get_db)],
) -> PodcastDetailResponse:
    episode = db.get(models.PodcastEpisode, episode_id)
    if not episode:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "해당 팟캐스트를 찾을 수 없습니다.", "code": "NOT_FOUND"},
        )
    return PodcastDetailResponse(
        episode=podcast_episode_detail(episode, get_episode_issue(db, episode)),
        nextQueue=[
            podcast_episode_card(next_episode, get_episode_issue(db, next_episode))
            for next_episode in list_podcast_episodes(
                db,
                exclude_episode_id=episode.id,
                feed="recommended",
                limit=12,
            )
        ],
    )


@router.patch("/podcasts/{episode_id}/status", response_model=MutationResponse)
def update_admin_podcast_status(
    episode_id: str,
    payload: PodcastStatusRequest,
    _: Annotated[models.User, Depends(reviewer_user)],
    db: Annotated[Session, Depends(get_db)],
) -> MutationResponse:
    episode = db.get(models.PodcastEpisode, episode_id)
    if not episode:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "해당 팟캐스트를 찾을 수 없습니다.", "code": "NOT_FOUND"},
        )
    if payload.status not in {"draft", "published", "archived"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "지원하지 않는 팟캐스트 상태입니다.", "code": "INVALID_STATUS"},
        )

    episode.status = payload.status
    episode.updated_at = datetime.now(UTC)
    if payload.status == "published" and not episode.published_at:
        episode.published_at = episode.updated_at
    db.commit()
    return MutationResponse(
        id=episode.id,
        message="팟캐스트 상태를 변경했습니다.",
        status=episode.status,
    )


@router.get("/issue-candidates", response_model=AdminDashboardResponse)
def issue_candidates(
    _: Annotated[models.User, Depends(reviewer_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AdminDashboardResponse:
    return dashboard(_, db)


@router.post("/issue-candidates/{candidate_id}/approve", response_model=MutationResponse)
def approve_issue_candidate(
    candidate_id: str,
    _: Annotated[models.User, Depends(reviewer_user)],
    db: Annotated[Session, Depends(get_db)],
) -> MutationResponse:
    try:
        issue = publish_issue_from_candidate(db, candidate_id=candidate_id, is_public=True)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "해당 항목을 찾을 수 없습니다.", "code": "NOT_FOUND"},
        ) from None
    db.commit()
    return MutationResponse(id=issue.id, message="이슈 후보를 공개 이슈로 승인했습니다.", status="updated")


@router.get("/issues/{issue_id}", response_model=AdminIssueResponse)
def issue_detail_for_admin(
    issue_id: str,
    _: Annotated[models.User, Depends(reviewer_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AdminIssueResponse:
    queue = queue_items(db)
    queue_item = db.get(models.AdminQueueItem, issue_id)
    public_issue = db.get(models.Issue, issue_id)
    reports = db.scalars(select(models.ModerationReport).where(models.ModerationReport.issue_id == issue_id)).all()

    return AdminIssueResponse(
        articles=public_issue.articles if public_issue else [],
        claimClusters=public_issue.claim_clusters if public_issue else [],
        claims=public_issue.claims if public_issue else [],
        evidences=public_issue.evidences if public_issue else [],
        issue=admin_queue_item(queue_item) if queue_item else None,
        publicIssue=issue_detail(public_issue) if public_issue else None,
        queue=[admin_queue_item(item) for item in queue],
        reports=[moderation_report(report) for report in reports],
        timeline=public_issue.timeline if public_issue else [],
    )


@router.get("/issues/{issue_id}/research-runs", response_model=ResearchRunListResponse)
def list_issue_research_runs(
    issue_id: str,
    _: Annotated[models.User, Depends(reviewer_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ResearchRunListResponse:
    rows = db.scalars(
        select(models.ResearchRun)
        .where(models.ResearchRun.issue_id == issue_id)
        .order_by(models.ResearchRun.started_at.desc())
        .limit(20),
    ).all()
    return ResearchRunListResponse(
        items=[
            ResearchRunItem(
                durationMs=row.duration_ms,
                errorMessage=row.error_message,
                executedQueries=row.executed_queries_json or [],
                finishedAt=to_iso(row.finished_at),
                id=row.id,
                issueId=row.issue_id,
                missingSignals=row.missing_signals_json or [],
                plan=row.plan_json or {},
                resultUrls=row.result_urls_json or [],
                roundIndex=row.round_index,
                seedQuery=row.seed_query,
                selectedArticleIds=row.selected_article_ids_json or [],
                sourceRoutes=row.source_routes_json or [],
                startedAt=to_iso(row.started_at),
                status=row.status,
                triggerType=row.trigger_type,
            )
            for row in rows
        ],
    )


@router.post("/issues/{issue_id}/approve", response_model=MutationResponse)
def approve_issue(
    issue_id: str,
    _: Annotated[models.User, Depends(reviewer_user)],
    db: Annotated[Session, Depends(get_db)],
) -> MutationResponse:
    queue_item = db.get(models.AdminQueueItem, issue_id)
    public_issue = db.get(models.Issue, issue_id)
    if not queue_item and not public_issue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "해당 항목을 찾을 수 없습니다.", "code": "NOT_FOUND"},
        )
    if public_issue:
        public_issue.is_public = True
        public_issue.status = "검증 완료"
    if queue_item:
        try:
            publish_issue_from_candidate(db, candidate_id=issue_id, is_public=True)
        except ValueError:
            queue_item.status = "출고 승인"
    db.commit()
    return MutationResponse(id=issue_id, message="출고 승인되었습니다.", status="updated")


@router.post("/issues/{issue_id}/merge", response_model=MutationResponse)
def merge_issue_route(
    issue_id: str,
    payload: IssueMergeRequest,
    _: Annotated[models.User, Depends(reviewer_user)],
    db: Annotated[Session, Depends(get_db)],
) -> MutationResponse:
    try:
        target = merge_issue(db, source_issue_id=issue_id, target_issue_id=payload.targetIssueId)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "해당 항목을 찾을 수 없습니다.", "code": "NOT_FOUND"},
        ) from None
    db.commit()
    return MutationResponse(id=target.id, message="이슈를 병합했습니다.", status="updated")


@router.post("/issues/{issue_id}/split", response_model=MutationResponse)
def split_issue_route(
    issue_id: str,
    payload: IssueSplitRequest,
    _: Annotated[models.User, Depends(reviewer_user)],
    db: Annotated[Session, Depends(get_db)],
) -> MutationResponse:
    try:
        issue = split_article_to_issue(db, article_id=payload.articleId, title=payload.title, topic=payload.topic)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "해당 항목을 찾을 수 없습니다.", "code": "NOT_FOUND"},
        ) from None
    db.commit()
    return MutationResponse(id=issue.id, message="기사 기준으로 새 이슈 후보를 분리했습니다.", status="updated")


@router.post("/issues/{issue_id}/hide", response_model=MutationResponse)
def hide_issue_route(
    issue_id: str,
    _: Annotated[models.User, Depends(reviewer_user)],
    db: Annotated[Session, Depends(get_db)],
) -> MutationResponse:
    hide_issue(db, issue_id=issue_id)
    db.commit()
    return MutationResponse(id=issue_id, message="이슈를 숨김 처리했습니다.", status="updated")


@router.post("/issues/{issue_id}/representative-image", response_model=MutationResponse)
def set_representative_image_route(
    issue_id: str,
    payload: RepresentativeImageRequest,
    _: Annotated[models.User, Depends(reviewer_user)],
    db: Annotated[Session, Depends(get_db)],
) -> MutationResponse:
    try:
        set_manual_representative_image(
            db,
            issue_id=issue_id,
            source=payload.source,
            source_url=payload.sourceUrl,
            url=payload.url,
        )
    except ValueError as exc:
        code = "INVALID_IMAGE_URL" if "invalid" in str(exc) else "NOT_FOUND"
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND if code == "NOT_FOUND" else status.HTTP_400_BAD_REQUEST,
            detail={"message": "대표 이미지 URL을 확인할 수 없습니다.", "code": code},
        ) from None
    db.commit()
    return MutationResponse(id=issue_id, message="대표 이미지를 지정했습니다.", status="updated")


@router.post("/issues/{issue_id}/reverify", response_model=MutationResponse)
def reverify_issue(
    issue_id: str,
    payload: ReverificationRequest,
    background_tasks: BackgroundTasks,
    _: Annotated[models.User, Depends(reviewer_user)],
    db: Annotated[Session, Depends(get_db)],
) -> MutationResponse:
    target = db.get(models.AdminQueueItem, issue_id) or db.get(models.Issue, issue_id)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "해당 항목을 찾을 수 없습니다.", "code": "NOT_FOUND"},
        )
    db.add(
        models.AgentRun(
            agent="Reverification",
            id=new_id("run"),
            status="running",
            target=f"{issue_id}:{payload.priority}",
        ),
    )
    db.commit()
    background_tasks.add_task(
        process_reverification_request,
        issue_id,
        memo=payload.memo,
        priority=payload.priority,
    )
    return MutationResponse(id=issue_id, message="재검증 작업이 큐에 등록되었습니다.", status="queued")


@router.get("/reports", response_model=AdminReportsResponse)
def reports(
    _: Annotated[models.User, Depends(reviewer_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AdminReportsResponse:
    rows = db.scalars(
        select(models.ModerationReport).order_by(models.ModerationReport.submitted_at.desc()),
    ).all()
    return AdminReportsResponse(reports=[moderation_report(report) for report in rows])


@router.post("/reports/{report_id}/resolve", response_model=MutationResponse)
def resolve_report(
    report_id: str,
    payload: ReportResolutionRequest,
    _: Annotated[models.User, Depends(reviewer_user)],
    db: Annotated[Session, Depends(get_db)],
) -> MutationResponse:
    report = db.get(models.ModerationReport, report_id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "해당 항목을 찾을 수 없습니다.", "code": "NOT_FOUND"},
        )
    report.status = payload.status
    if report.target_type == "claim":
        claim = db.scalar(select(models.Claim).where(models.Claim.issue_id == report.issue_id))
        if claim:
            claim.status = "needs_review"
    db.add(
        models.AgentRun(
            agent="Moderation",
            agent_name="Moderation",
            id=new_id("run"),
            input_json={"report_id": report_id, "status": payload.status},
            issue_id=report.issue_id,
            status="completed",
            target=report.target_type,
        ),
    )
    db.commit()
    return MutationResponse(id=report_id, message="신고 처리를 저장했습니다.", status="updated")


@router.get("/sources", response_model=AdminSourcesResponse)
def sources(
    _: Annotated[models.User, Depends(reviewer_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AdminSourcesResponse:
    rows = db.scalars(
        select(models.SourceDomain).order_by(models.SourceDomain.last_reviewed_at.desc()),
    ).all()
    return AdminSourcesResponse(sources=[source_domain(source) for source in rows])


@router.post("/sources", response_model=SourceDomainSchema, status_code=status.HTTP_201_CREATED)
def create_source(
    payload: SourceCreateRequest,
    _: Annotated[models.User, Depends(reviewer_user)],
    db: Annotated[Session, Depends(get_db)],
) -> SourceDomainSchema:
    domain = payload.domain.strip().lower()
    existing = db.scalar(select(models.SourceDomain).where(models.SourceDomain.domain == domain))
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": "이미 등록된 출처입니다.", "code": "SOURCE_EXISTS"},
        )
    source = models.SourceDomain(
        collection_interval_minutes=payload.collectionIntervalMinutes,
        collection_url=payload.collectionUrl or "",
        credibility=payload.credibility,
        domain=domain,
        id=new_id("domain"),
        is_active=payload.isActive,
        name=payload.name,
        note=payload.note,
        source_type=payload.sourceType,
        status=payload.status,
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    return source_domain(source)


@router.get("/settings", response_model=AdminSettingsResponse)
def settings(
    _: Annotated[models.User, Depends(reviewer_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AdminSettingsResponse:
    return get_admin_settings(db)


@router.patch("/settings", response_model=AdminSettingsResponse)
def update_settings(
    payload: AdminSettingsUpdateRequest,
    user: Annotated[models.User, Depends(reviewer_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AdminSettingsResponse:
    try:
        return update_admin_settings(db, payload=payload.settings, user_id=user.id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": str(exc), "code": "INVALID_SETTING"},
        ) from None


@router.get("/discovery-topics", response_model=DiscoveryTopicsResponse)
def discovery_topics(
    _: Annotated[models.User, Depends(reviewer_user)],
    db: Annotated[Session, Depends(get_db)],
) -> DiscoveryTopicsResponse:
    rows = db.scalars(
        select(models.DiscoveryTopic).order_by(models.DiscoveryTopic.updated_at.desc()).limit(200),
    ).all()
    return DiscoveryTopicsResponse(topics=[discovery_topic(row) for row in rows])


@router.post("/discovery-topics", response_model=DiscoveryTopicsResponse, status_code=status.HTTP_201_CREATED)
def create_discovery_topic(
    payload: DiscoveryTopicCreateRequest,
    _: Annotated[models.User, Depends(reviewer_user)],
    db: Annotated[Session, Depends(get_db)],
) -> DiscoveryTopicsResponse:
    row = upsert_discovery_topic(
        db,
        base_queries=payload.baseQueries or [payload.name],
        interval_minutes=payload.intervalMinutes,
        max_results_per_query=payload.maxResultsPerQuery,
        min_cluster_size=payload.minClusterSize,
        name=payload.name,
        priority=payload.priority,
        topic=payload.topic,
    )
    if payload.runImmediately:
        enqueue_job(
            db,
            input_json={"topic_id": row.id},
            job_type="discover_topic",
            target_id=row.id,
        )
    db.commit()
    return DiscoveryTopicsResponse(topics=[discovery_topic(row)])


@router.post("/discovery-topics/{topic_id}/run", response_model=CollectorRunResponse)
def run_discovery_topic(
    topic_id: str,
    _: Annotated[models.User, Depends(reviewer_user)],
    db: Annotated[Session, Depends(get_db)],
) -> CollectorRunResponse:
    topic = db.get(models.DiscoveryTopic, topic_id)
    if not topic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "해당 감시 주제를 찾을 수 없습니다.", "code": "NOT_FOUND"},
        )
    job = enqueue_job(
        db,
        input_json={"topic_id": topic.id},
        job_type="discover_topic",
        target_id=topic.id,
    )
    db.commit()
    return CollectorRunResponse(
        id=job.id,
        message="사건 discovery 작업을 실행했습니다.",
        result=job.output_json or {"jobId": job.id},
        status=job.status,
    )


@router.get("/discovered-incidents", response_model=DiscoveredIncidentsResponse)
def discovered_incidents(
    _: Annotated[models.User, Depends(reviewer_user)],
    db: Annotated[Session, Depends(get_db)],
) -> DiscoveredIncidentsResponse:
    rows = db.scalars(
        select(models.DiscoveredIncident).order_by(models.DiscoveredIncident.last_seen_at.desc()).limit(200),
    ).all()
    return DiscoveredIncidentsResponse(incidents=[discovered_incident(row) for row in rows])


@router.get("/search-keywords", response_model=SearchKeywordsResponse)
def search_keywords(
    _: Annotated[models.User, Depends(reviewer_user)],
    db: Annotated[Session, Depends(get_db)],
) -> SearchKeywordsResponse:
    rows = db.scalars(
        select(models.SearchKeyword).order_by(models.SearchKeyword.updated_at.desc()).limit(200),
    ).all()
    return SearchKeywordsResponse(keywords=[search_keyword(row) for row in rows])


@router.post("/search-keywords/seed", response_model=SearchKeywordsResponse, status_code=status.HTTP_201_CREATED)
def seed_keywords(
    payload: SearchKeywordSeedRequest,
    _: Annotated[models.User, Depends(reviewer_user)],
    db: Annotated[Session, Depends(get_db)],
) -> SearchKeywordsResponse:
    rows = seed_search_keywords(
        db,
        generate_variants=payload.generateVariants,
        interval_minutes=payload.intervalMinutes,
        priority=payload.priority,
        query=payload.query,
        source="admin",
        topic=payload.topic,
    )
    if payload.runImmediately:
        for row in rows:
            enqueue_job(
                db,
                input_json={"keyword_id": row.id},
                job_type="search_news",
                target_id=row.id,
            )
    db.commit()
    return SearchKeywordsResponse(keywords=[search_keyword(row) for row in rows])


@router.post("/search-keywords/{keyword_id}/run", response_model=CollectorRunResponse)
def run_search_keyword(
    keyword_id: str,
    _: Annotated[models.User, Depends(reviewer_user)],
    db: Annotated[Session, Depends(get_db)],
) -> CollectorRunResponse:
    keyword = db.get(models.SearchKeyword, keyword_id)
    if not keyword:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "해당 검색 키워드를 찾을 수 없습니다.", "code": "NOT_FOUND"},
        )
    job = enqueue_job(
        db,
        input_json={"keyword_id": keyword.id},
        job_type="search_news",
        target_id=keyword.id,
    )
    db.commit()
    return CollectorRunResponse(
        id=job.id,
        message="검색 수집 작업을 실행했습니다.",
        result=job.output_json or {"jobId": job.id},
        status=job.status,
    )


@router.post("/issues/source-backfill/run", response_model=CollectorRunResponse)
def run_issue_source_backfill(
    _: Annotated[models.User, Depends(reviewer_user)],
    db: Annotated[Session, Depends(get_db)],
) -> CollectorRunResponse:
    job = enqueue_job(
        db,
        input_json={"limit": int(get_effective_setting(db, "issue_source_backfill_limit") or 8)},
        job_type="backfill_issue_sources",
        target_id="source-backfill",
    )
    db.commit()
    return CollectorRunResponse(
        id=job.id,
        message="출처 부족 이슈 보강 작업을 실행했습니다.",
        result=job.output_json or {"jobId": job.id},
        status=job.status,
    )


@router.get("/scheduler", response_model=SchedulerStatusResponse)
def scheduler(
    _: Annotated[models.User, Depends(reviewer_user)],
    db: Annotated[Session, Depends(get_db)],
) -> SchedulerStatusResponse:
    return scheduler_response(scheduler_status(db))


@router.post("/scheduler/tick", response_model=SchedulerStatusResponse)
def scheduler_tick(
    _: Annotated[models.User, Depends(reviewer_user)],
    db: Annotated[Session, Depends(get_db)],
) -> SchedulerStatusResponse:
    tick_scheduler_once(db, owner_id="admin")
    db.commit()
    return scheduler_response(scheduler_status(db))


@router.patch("/sources/{source_id}", response_model=MutationResponse)
def update_source(
    source_id: str,
    payload: SourceUpdateRequest,
    _: Annotated[models.User, Depends(reviewer_user)],
    db: Annotated[Session, Depends(get_db)],
) -> MutationResponse:
    source = db.get(models.SourceDomain, source_id)
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "해당 항목을 찾을 수 없습니다.", "code": "NOT_FOUND"},
        )
    if payload.domain is not None:
        next_domain = payload.domain.strip().lower()
        duplicate = db.scalar(
            select(models.SourceDomain).where(
                models.SourceDomain.domain == next_domain,
                models.SourceDomain.id != source_id,
            ),
        )
        if duplicate:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"message": "이미 등록된 출처입니다.", "code": "SOURCE_EXISTS"},
            )
        source.domain = next_domain
    if payload.name is not None:
        source.name = payload.name
    if payload.sourceType is not None:
        source.source_type = payload.sourceType
    if payload.status is not None:
        source.status = payload.status
    if payload.credibility is not None:
        source.credibility = payload.credibility
    if payload.collectionUrl is not None:
        source.collection_url = payload.collectionUrl
    if payload.collectionIntervalMinutes is not None:
        source.collection_interval_minutes = payload.collectionIntervalMinutes
    if payload.isActive is not None:
        source.is_active = payload.isActive
    if payload.note is not None:
        source.note = payload.note
    source.last_reviewed_at = models.now_utc()
    db.commit()
    return MutationResponse(id=source_id, message="출처 설정을 저장했습니다.", status="updated")


@router.patch("/sources/{source_id}/credibility", response_model=MutationResponse)
def update_source_credibility(
    source_id: str,
    payload: SourcePolicyRequest,
    _: Annotated[models.User, Depends(reviewer_user)],
    db: Annotated[Session, Depends(get_db)],
) -> MutationResponse:
    try:
        update_source_policy(
            db,
            collection_interval_minutes=payload.collectionIntervalMinutes,
            credibility=payload.credibility,
            source_id=source_id,
            status=payload.status,
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "해당 항목을 찾을 수 없습니다.", "code": "NOT_FOUND"},
        ) from None
    db.commit()
    return MutationResponse(id=source_id, message="출처 신뢰도 정책을 저장했습니다.", status="updated")


@router.post("/collectors/run", response_model=CollectorRunResponse)
def run_collectors(
    payload: CollectorRunRequest,
    _: Annotated[models.User, Depends(reviewer_user)],
    db: Annotated[Session, Depends(get_db)],
) -> CollectorRunResponse:
    job = enqueue_job(
        db,
        input_json={"source_ids": payload.sourceIds},
        job_type="collect_sources",
        target_id=",".join(payload.sourceIds or ["all"]),
    )
    db.commit()
    result = job.output_json or {"jobId": job.id}
    return CollectorRunResponse(
        id=job.id,
        message="수집 작업을 실행했습니다.",
        result=result,
        status=job.status,
    )


@router.get("/collectors/runs", response_model=CollectorRunsResponse)
def collector_runs(
    _: Annotated[models.User, Depends(reviewer_user)],
    db: Annotated[Session, Depends(get_db)],
) -> CollectorRunsResponse:
    rows = db.scalars(
        select(models.CollectorRun).order_by(models.CollectorRun.started_at.desc()).limit(50),
    ).all()
    return CollectorRunsResponse(
        runs=[
            {
                "id": row.id,
                "sourceId": row.source_id,
                "collector": row.collector,
                "status": row.status,
                "articleCount": row.article_count,
                "errorMessage": row.error_message,
                "startedAt": row.started_at.isoformat(),
                "finishedAt": row.finished_at.isoformat() if row.finished_at else None,
            }
            for row in rows
        ],
    )


@router.get("/jobs", response_model=JobListResponse)
def jobs(
    _: Annotated[models.User, Depends(reviewer_user)],
    db: Annotated[Session, Depends(get_db)],
) -> JobListResponse:
    rows = db.scalars(select(models.JobAttempt).order_by(models.JobAttempt.created_at.desc()).limit(100)).all()
    return JobListResponse(
        jobs=[
            {
                "id": row.id,
                "jobType": row.job_type,
                "targetId": row.target_id,
                "status": row.status,
                "attempts": row.attempts,
                "maxAttempts": row.max_attempts,
                "lastError": row.last_error,
                "userMessage": job_user_message(row),
                "createdAt": row.created_at.isoformat(),
                "updatedAt": row.updated_at.isoformat(),
            }
            for row in rows
        ],
    )


@router.post("/jobs/{job_id}/retry", response_model=MutationResponse)
def retry_job(
    job_id: str,
    _: Annotated[models.User, Depends(reviewer_user)],
    db: Annotated[Session, Depends(get_db)],
) -> MutationResponse:
    job = db.get(models.JobAttempt, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "해당 항목을 찾을 수 없습니다.", "code": "NOT_FOUND"},
        )
    job.status = "queued"
    job.updated_at = models.now_utc()
    execute_job(db, job=job)
    db.commit()
    return MutationResponse(id=job_id, message="작업을 재시도했습니다.", status=job.status)


@router.get("/agents", response_model=AdminAgentsResponse)
def agents(
    _: Annotated[models.User, Depends(reviewer_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AdminAgentsResponse:
    return AdminAgentsResponse(
        agentRuns=[agent_run(run) for run in recent_agent_runs(db)],
        recentEvents=[],
    )


@router.post("/agents/run", response_model=MutationResponse)
def run_agent(
    payload: AgentRunRequest,
    _: Annotated[models.User, Depends(reviewer_user)],
    db: Annotated[Session, Depends(get_db)],
) -> MutationResponse:
    run = models.AgentRun(
        agent=payload.agent,
        id=new_id("run"),
        status="running",
        target="수동 실행",
    )
    db.add(run)
    db.commit()
    return MutationResponse(id=run.id, message="자동 처리 작업을 시작했습니다.", status="queued")


@router.post("/claims/{claim_id}/reverify", response_model=MutationResponse)
def reverify_claim_route(
    claim_id: str,
    _: Annotated[models.User, Depends(reviewer_user)],
    db: Annotated[Session, Depends(get_db)],
) -> MutationResponse:
    try:
        claim = reverify_single_claim(db, claim_id=claim_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "해당 항목을 찾을 수 없습니다.", "code": "NOT_FOUND"},
        ) from None
    db.commit()
    return MutationResponse(id=claim.id, message="주장을 재검증했습니다.", status="updated")
