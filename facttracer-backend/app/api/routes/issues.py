import threading
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.responses import PlainTextResponse
from sqlalchemy import or_, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app import models
from app.api.dependencies import current_user, optional_current_user, optional_public_current_user
from app.db.session import get_db
from app.schemas import (
    AnalyticsEventRequest,
    ArticleVerificationRequest,
    ArticleVerificationResponse,
    ClaimSubmissionRequest,
    ClaimSubmissionResponse,
    IssueContentReportRequest,
    FileRegistrationRequest,
    FileRegistrationResponse,
    IssueArticlesResponse,
    IssueClaimClustersResponse,
    IssueDetailResponse,
    IssuePerspectivesResponse,
    IssueReportResponse,
    IssueUpdatesResponse,
    ManualCheckRequest,
    ManualCheckResponse,
    MutationResponse,
    PublicHomeResponse,
)
from app.serializers import issue_detail, issue_summary
from app.services.ai.pipeline import process_submitted_claim, process_verification_request
from app.services.files.security import validate_upload_metadata
from app.services.files.parser import extract_text_from_file
from app.services.files.storage import store_base64_file
from app.services.issues.page_builder import build_issue_cache_payload
from app.services.issues.ranking import rank_issues
from app.services.manual_checks.workflow import create_manual_check, process_manual_check_request
from app.services.topics import TOPIC_FILTERS, normalize_topic, normalize_topic_filter, public_topic_filters
from app.utils import new_id

router = APIRouter(tags=["issues"])

TOPICS = list(TOPIC_FILTERS)

PODCAST_EVENT_WEIGHTS = {
    "podcast_complete": 2.0,
    "podcast_play_start": 1.2,
    "podcast_progress": 0.5,
    "podcast_resume": 0.3,
    "podcast_source_click": 0.8,
    "podcast_skip": -0.7,
    "podcast_home_impression": 0.1,
}


def _bump_weight(weights: dict, key: str, delta: float) -> dict:
    if not key:
        return weights
    current = float(weights.get(key, 0) or 0)
    weights[key] = round(max(0.0, current + delta), 4)
    return weights


def _update_podcast_interest_profile(
    db: Session,
    *,
    payload: AnalyticsEventRequest,
    user: models.User | None,
) -> None:
    if not user or not payload.eventType.startswith("podcast_"):
        return

    metadata = payload.metadata or {}
    issue = db.get(models.Issue, payload.issueId) if payload.issueId else None
    category = str(metadata.get("podcastCategory") or (issue.topic if issue else "")).strip()
    podcast_format = str(metadata.get("podcastFormat") or "").strip()
    if not category and not podcast_format:
        return

    delta = PODCAST_EVENT_WEIGHTS.get(payload.eventType, 0.2)
    profile = db.get(models.UserInterestProfile, user.id)
    if not profile:
        profile = models.UserInterestProfile(user_id=user.id)
        db.add(profile)

    if category:
        profile.topic_weights_json = _bump_weight(
            dict(profile.topic_weights_json or {}),
            category,
            delta,
        )
    if podcast_format:
        profile.event_group_weights_json = _bump_weight(
            dict(profile.event_group_weights_json or {}),
            f"podcast_format:{podcast_format}",
            delta,
        )
    profile.updated_at = models.now_utc()


def _public_update_log(row: models.UpdateLog, issue: models.Issue | None = None) -> dict:
    return {
        "time": row.created_at.isoformat(),
        "type": row.update_type,
        "title": row.title,
        "description": row.description,
        "issueId": row.issue_id,
        "issueTitle": issue.title if issue else None,
    }


def _issue_groups(issues: list[models.Issue]) -> dict:
    def top(rows: list[models.Issue]) -> list:
        return [issue_summary(row) for row in rows[:6]]

    return {
        "inProgress": top([issue for issue in issues if "진행" in issue.status or issue.needs_review_count > 0]),
        "newlyDetected": top(sorted(issues, key=lambda item: item.created_at, reverse=True)),
        "numberChanged": top([issue for issue in issues if issue.changed_claims > 0 or issue.number_changes]),
        "officialUpdates": top(
            [
                issue
                for issue in issues
                if any(
                    str(source.get("sourceType", "")).lower() in {"official", "public", "statistics", "law"}
                    for source in (issue.source_documents or [])
                    if isinstance(source, dict)
                )
            ],
        ),
        "popular": top(sorted(issues, key=lambda item: (item.article_count, item.issue_score), reverse=True)),
    }


def _report_markdown(issue: models.Issue, cache: dict) -> str:
    lines = [
        f"# {issue.title}",
        "",
        f"- 토픽: {issue.topic}",
        f"- 상태: {issue.status}",
        f"- 마지막 업데이트: {issue.updated_at.isoformat()}",
        f"- 기사: {cache.get('article_count', issue.article_count)}건",
        f"- 쟁점: {cache.get('cluster_count', issue.cluster_count)}개",
        f"- 검증 완료: {cache.get('verified_count', issue.verified_count)}개",
        "",
        "## 요약",
        issue.summary or cache.get("computed_summary", ""),
        "",
        "## 핵심 팩트",
    ]
    facts = cache.get("confirmed_facts") or issue.confirmed_facts or []
    lines.extend(f"- [{fact.get('verdict', '')}] {fact.get('text', '')}" for fact in facts[:12])
    lines.extend(["", "## 쟁점 지도"])
    for cluster in (cache.get("claim_clusters") or issue.claim_clusters or [])[:12]:
        lines.extend(
            [
                f"### {cluster.get('title', '쟁점')}",
                f"- 질문: {cluster.get('question', '')}",
                f"- 충돌 지점: {cluster.get('conflict', '')}",
                f"- 공통분모: {cluster.get('commonGround', '')}",
            ],
        )
        lines.extend(f"  - 주장: {claim}" for claim in cluster.get("claims", [])[:6])
    lines.extend(["", "## 주장별 검증"])
    for claim in (cache.get("claims") or issue.claims or [])[:30]:
        lines.extend(
            [
                f"### {claim.get('text', '')}",
                f"- 유형: {claim.get('type', '')}",
                f"- 판정: {claim.get('verdict', '')}",
                f"- 신뢰도: {claim.get('confidence', '')}",
                f"- 대표 근거: {claim.get('evidence', '')}",
            ],
        )
        for evidence in claim.get("evidences", [])[:4]:
            lines.append(f"  - 근거: {evidence.get('title', '')} ({evidence.get('url', '')})")
    lines.extend(["", "## 원문 자료"])
    for source in (cache.get("source_documents") or issue.source_documents or [])[:30]:
        lines.append(f"- {source.get('title', '')} / {source.get('publisher', '')} / {source.get('url', '')}")
    return "\n".join(lines).strip() + "\n"


@router.get("/issues/home", response_model=PublicHomeResponse)
def home(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[models.User | None, Depends(optional_public_current_user)] = None,
    issue_id: Annotated[str | None, Query(alias="issueId")] = None,
    q: str | None = None,
    topic: str | None = None,
    sort: str = "recommended",
    major_topic: Annotated[str | None, Query(alias="majorTopic")] = None,
    event_group: Annotated[str | None, Query(alias="eventGroup")] = None,
) -> PublicHomeResponse:
    query = select(models.Issue).where(models.Issue.is_public.is_(True))
    if q:
        query = query.where(or_(models.Issue.title.contains(q), models.Issue.summary.contains(q)))
    query = query.order_by(models.Issue.updated_at.desc())
    requested_topic = normalize_topic_filter(topic)
    issues = [
        issue
        for issue in db.scalars(query).all()
        if not requested_topic or normalize_topic(issue.topic) == requested_topic
    ]
    if major_topic:
        issues = [
            issue
            for issue in issues
            if issue.major_topic_id == major_topic or issue.major_topic_name == major_topic
        ]
    if event_group:
        issues = [
            issue
            for issue in issues
            if issue.event_group_id == event_group or issue.event_group_name == event_group
        ]
    interest_profile = db.get(models.UserInterestProfile, user.id) if user else None
    issues = rank_issues(issues, interest_profile=interest_profile, sort=sort, user=user)
    visible_issue_ids = {issue.id for issue in issues}

    selected = None
    if issue_id and issue_id in visible_issue_ids:
        selected = db.get(models.Issue, issue_id)
        if selected and not selected.is_public:
            selected = None
    selected_cache = {}
    if selected:
        selected, selected_cache = build_issue_cache_payload(db, issue_id=selected.id)

    dynamic_topics = db.scalars(select(models.Issue.topic).distinct()).all()
    topics = public_topic_filters(dynamic_topics)

    recent_logs = db.scalars(
        select(models.UpdateLog).order_by(models.UpdateLog.created_at.desc()).limit(20),
    ).all()
    issue_by_id = {
        issue.id: issue
        for issue in issues
        if any(log.issue_id == issue.id for log in recent_logs)
    }

    return PublicHomeResponse(
        issues=[issue_summary(issue) for issue in issues],
        selectedIssue=issue_detail(selected, selected_cache) if selected else None,
        topics=topics,
        updateLogs=[_public_update_log(log, issue_by_id.get(log.issue_id)) for log in recent_logs],
        issueGroups=_issue_groups(issues),
    )


@router.get("/issues/{issue_id}", response_model=IssueDetailResponse)
def issue(issue_id: str, db: Annotated[Session, Depends(get_db)]) -> IssueDetailResponse:
    item = db.get(models.Issue, issue_id)
    if not item or not item.is_public:
        return IssueDetailResponse(issue=None, relatedIssues=[])
    item, item_cache = build_issue_cache_payload(db, issue_id=item.id)
    if not item:
        return IssueDetailResponse(issue=None, relatedIssues=[])
    related_candidates = db.scalars(
        select(models.Issue)
        .where(models.Issue.id != item.id, models.Issue.is_public.is_(True))
        .limit(40),
    ).all()
    related = [
        related_issue
        for related_issue in related_candidates
        if normalize_topic(related_issue.topic) == normalize_topic(item.topic)
    ][:4]
    return IssueDetailResponse(
        issue=issue_detail(item, item_cache),
        relatedIssues=[issue_summary(related_issue) for related_issue in related],
    )


@router.get("/issues/{issue_id}/updates", response_model=IssueUpdatesResponse)
def issue_updates(issue_id: str, db: Annotated[Session, Depends(get_db)]) -> IssueUpdatesResponse:
    rows = db.scalars(
        select(models.UpdateLog)
        .where(models.UpdateLog.issue_id == issue_id)
        .order_by(models.UpdateLog.created_at.desc()),
    ).all()
    return IssueUpdatesResponse(
        updates=[
            {
                "id": row.id,
                "type": row.update_type,
                "title": row.title,
                "description": row.description,
                "createdAt": row.created_at.isoformat(),
                "relatedClaimId": row.related_claim_id,
                "relatedArticleId": row.related_article_id,
            }
            for row in rows
        ],
    )


@router.get("/issues/{issue_id}/articles", response_model=IssueArticlesResponse)
def issue_articles(issue_id: str, db: Annotated[Session, Depends(get_db)]) -> IssueArticlesResponse:
    item, cache = build_issue_cache_payload(db, issue_id=issue_id)
    return IssueArticlesResponse(articles=(cache.get("articles", item.articles) if item else []))


@router.get("/issues/{issue_id}/claim-clusters", response_model=IssueClaimClustersResponse)
def issue_claim_clusters(issue_id: str, db: Annotated[Session, Depends(get_db)]) -> IssueClaimClustersResponse:
    item, cache = build_issue_cache_payload(db, issue_id=issue_id)
    return IssueClaimClustersResponse(claimClusters=(cache.get("claim_clusters", item.claim_clusters) if item else []))


@router.get("/issues/{issue_id}/perspectives", response_model=IssuePerspectivesResponse)
def issue_perspectives(issue_id: str, db: Annotated[Session, Depends(get_db)]) -> IssuePerspectivesResponse:
    item, cache = build_issue_cache_payload(db, issue_id=issue_id)
    return IssuePerspectivesResponse(perspectives=(cache.get("perspectives", item.perspectives) if item else []))


@router.post("/issues/{issue_id}/subscribe", response_model=MutationResponse)
def subscribe_issue(
    issue_id: str,
    user: Annotated[models.User, Depends(current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> MutationResponse:
    issue = db.get(models.Issue, issue_id)
    if not issue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "해당 항목을 찾을 수 없습니다.", "code": "NOT_FOUND"},
        )
    if not db.get(models.SavedIssue, {"user_id": user.id, "issue_id": issue_id}):
        db.add(models.SavedIssue(issue_id=issue_id, user_id=user.id))
        db.commit()
    return MutationResponse(id=issue_id, message="관심 이슈 알림을 켰습니다.", status="updated")


@router.delete("/issues/{issue_id}/subscribe", response_model=MutationResponse)
def unsubscribe_issue(
    issue_id: str,
    user: Annotated[models.User, Depends(current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> MutationResponse:
    row = db.get(models.SavedIssue, {"user_id": user.id, "issue_id": issue_id})
    if row:
        db.delete(row)
        db.commit()
    return MutationResponse(id=issue_id, message="관심 이슈 알림을 껐습니다.", status="updated")


@router.post("/verification-requests", response_model=ArticleVerificationResponse, status_code=status.HTTP_201_CREATED)
def create_verification_request(
    payload: ArticleVerificationRequest,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[models.User | None, Depends(optional_current_user)],
) -> ArticleVerificationResponse:
    matched_issue_id = payload.issueId if payload.issueId and db.get(models.Issue, payload.issueId) else None
    request = models.VerificationRequest(
        article_url=str(payload.articleUrl),
        id=new_id("vr"),
        issue_id=payload.issueId,
        matched_issue_id=matched_issue_id,
        status="queued",
        user_id=user.id if user else None,
    )
    db.add(request)
    db.commit()
    background_tasks.add_task(process_verification_request, request.id)
    return ArticleVerificationResponse(
        id=request.id,
        matchedIssueId=matched_issue_id,
        message="분석 요청이 접수되었습니다.",
        status="queued",
    )


@router.post("/issues/{issue_id}/claims", response_model=ClaimSubmissionResponse, status_code=status.HTTP_201_CREATED)
def submit_claim(
    issue_id: str,
    payload: ClaimSubmissionRequest,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[models.User | None, Depends(optional_current_user)],
) -> ClaimSubmissionResponse:
    issue = db.get(models.Issue, issue_id)
    if not issue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "해당 항목을 찾을 수 없습니다.", "code": "NOT_FOUND"},
        )
    claim = models.SubmittedClaim(
        claim_text=payload.claimText,
        claim_type=payload.claimType,
        evidence_url=str(payload.evidenceUrl) if payload.evidenceUrl else None,
        id=new_id("claim"),
        issue_id=issue_id,
        reason=payload.reason,
        refutable_point=payload.refutablePoint,
        related_cluster=payload.relatedCluster,
        status="received",
        user_id=user.id if user else None,
    )
    db.add(claim)
    db.commit()
    background_tasks.add_task(process_submitted_claim, claim.id)
    return ClaimSubmissionResponse(id=claim.id, status="received", clusterId=claim.cluster_id)


@router.post("/issues/{issue_id}/report", response_model=IssueReportResponse, status_code=status.HTTP_201_CREATED)
def create_report(
    issue_id: str,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[models.User | None, Depends(optional_current_user)],
) -> IssueReportResponse:
    issue = db.get(models.Issue, issue_id)
    if not issue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "해당 항목을 찾을 수 없습니다.", "code": "NOT_FOUND"},
        )
    _, cache = build_issue_cache_payload(db, issue_id=issue_id)
    markdown = _report_markdown(issue, cache)
    report = models.IssueReport(
        download_url=f"/v1/reports/report-{issue_id}/markdown",
        id=f"report-{issue_id}",
        issue_id=issue_id,
        markdown_report=markdown,
        share_token=new_id("share"),
        summary=(issue.summary or cache.get("computed_summary", ""))[:1000],
        status="created",
        user_id=user.id if user else None,
    )
    db.merge(report)
    db.commit()
    return IssueReportResponse(
        downloadUrl=report.download_url,
        id=report.id,
        issueId=issue_id,
        markdownUrl=report.download_url,
        message="이슈 리포트가 저장되었습니다.",
        shareUrl=f"/reports/{issue_id}?share={report.share_token}",
        status="created",
    )


@router.get("/reports/{report_id}/markdown", response_class=PlainTextResponse)
def report_markdown(report_id: str, db: Annotated[Session, Depends(get_db)]) -> PlainTextResponse:
    report = db.get(models.IssueReport, report_id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "해당 항목을 찾을 수 없습니다.", "code": "NOT_FOUND"},
        )
    return PlainTextResponse(report.markdown_report or report.summary or "")


@router.post("/issues/{issue_id}/content-reports", response_model=MutationResponse, status_code=status.HTTP_201_CREATED)
def create_content_report(
    issue_id: str,
    payload: IssueContentReportRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[models.User | None, Depends(optional_current_user)],
) -> MutationResponse:
    issue = db.get(models.Issue, issue_id)
    if not issue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "해당 항목을 찾을 수 없습니다.", "code": "NOT_FOUND"},
        )
    report_id = new_id("moderation")
    db.add(
        models.ModerationReport(
            excerpt=payload.excerpt,
            id=report_id,
            issue_id=issue_id,
            issue_title=issue.title,
            priority="보통",
            reason=payload.reason,
            status="open",
            target_type=payload.targetType,
        ),
    )
    db.add(
        models.AgentRun(
            agent="User Report",
            agent_name="User Report",
            id=new_id("run"),
            input_json={
                "targetId": payload.targetId,
                "targetType": payload.targetType,
                "userId": user.id if user else None,
            },
            issue_id=issue_id,
            status="needs_review",
            target=payload.reason[:200],
        ),
    )
    db.commit()
    return MutationResponse(id=report_id, message="신고가 검토 목록에 접수되었습니다.", status="received")


@router.post("/analytics/events", response_model=MutationResponse, status_code=status.HTTP_201_CREATED)
def record_analytics_event(
    payload: AnalyticsEventRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[models.User | None, Depends(optional_current_user)],
) -> MutationResponse:
    event = models.ProductMetricEvent(
        event_type=payload.eventType,
        id=new_id("metric"),
        issue_id=payload.issueId,
        metadata_json=payload.metadata,
        report_id=payload.reportId,
        user_id=user.id if user else None,
    )
    db.add(event)
    _update_podcast_interest_profile(db, payload=payload, user=user)
    try:
        db.commit()
    except OperationalError:
        db.rollback()
        return MutationResponse(id=event.id, message="제품 지표 이벤트 기록을 건너뛰었습니다.", status="skipped")
    return MutationResponse(id=event.id, message="제품 지표 이벤트가 기록되었습니다.", status="created")


@router.post("/checks", response_model=ManualCheckResponse, status_code=status.HTTP_201_CREATED)
def create_check(
    payload: ManualCheckRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[models.User | None, Depends(optional_current_user)],
) -> ManualCheckResponse:
    request = create_manual_check(
        db,
        content=payload.content,
        input_type=payload.inputType,
        issue_id=payload.issueId,
        user_id=user.id if user else None,
    )
    db.commit()
    if request.status != "rejected":
        threading.Thread(
            target=process_manual_check_request,
            args=(request.id,),
            daemon=True,
            name=f"manual-check-{request.id}",
        ).start()
    return ManualCheckResponse(
        id=request.id,
        inputType=request.input_type,
        matchedIssueId=request.matched_issue_id,
        message="분석 요청이 접수되었습니다." if request.status != "rejected" else request.ai_summary,
        standaloneResultId=request.standalone_result_id,
        status=request.status,
    )


@router.get("/checks/{check_id}", response_model=ManualCheckResponse)
def get_check(check_id: str, db: Annotated[Session, Depends(get_db)]) -> ManualCheckResponse:
    request = db.get(models.VerificationRequest, check_id)
    if not request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "해당 항목을 찾을 수 없습니다.", "code": "NOT_FOUND"},
        )
    return ManualCheckResponse(
        id=request.id,
        inputType=request.input_type,
        matchedIssueId=request.matched_issue_id,
        message=request.ai_summary or "분석 요청 상태를 반환합니다.",
        standaloneResultId=request.standalone_result_id,
        status=request.status,
    )


@router.post("/files", response_model=FileRegistrationResponse, status_code=status.HTTP_201_CREATED)
def register_file(
    payload: FileRegistrationRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[models.User | None, Depends(optional_current_user)],
) -> FileRegistrationResponse:
    ok, reason = validate_upload_metadata(content_type=payload.contentType, db=db, size_bytes=payload.sizeBytes)
    file_id = new_id("file")
    storage_url = payload.storageUrl or ""
    size_bytes = payload.sizeBytes
    if ok and payload.contentBase64:
        try:
            storage_url, size_bytes = store_base64_file(
                content_base64=payload.contentBase64,
                file_id=file_id,
                filename=payload.filename,
            )
            ok, reason = validate_upload_metadata(content_type=payload.contentType, db=db, size_bytes=size_bytes)
        except Exception:
            ok, reason = False, "파일 저장 중 오류가 발생했습니다."
    uploaded = models.UploadedFile(
        content_type=payload.contentType,
        filename=payload.filename,
        id=file_id,
        safety_status="accepted" if ok else "rejected",
        size_bytes=size_bytes,
        status="received" if ok else "rejected",
        storage_url=storage_url,
        user_id=user.id if user else None,
    )
    if ok and uploaded.storage_url:
        text, parse_status = extract_text_from_file(
            content_type=uploaded.content_type,
            storage_url=uploaded.storage_url,
        )
        uploaded.extracted_text = text
        uploaded.parse_status = parse_status
    db.add(uploaded)
    db.commit()
    return FileRegistrationResponse(
        id=uploaded.id,
        message="파일 검증 준비가 완료되었습니다." if ok else reason,
        safetyStatus=uploaded.safety_status,
        status=uploaded.status,
    )
