import math
from typing import Any

from app import models
from app.schemas import (
    AdminQueueItem,
    AgentRun,
    AuthUser,
    DiscoveredIncident,
    DiscoveryTopic,
    Issue,
    IssueDetail,
    ModerationReport,
    PodcastEpisodeCard,
    PodcastEpisodeDetail,
    SearchKeyword,
    SourceDomain,
    UserNotification,
    UserSavedIssue,
    UserSubmittedClaim,
    UserVerificationRequest,
)
from app.services.topics import normalize_topic
from app.services.podcasts.tts import public_episode_audio_url
from app.utils import to_iso


def _safe_finite_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def auth_user(user: models.User) -> AuthUser:
    return AuthUser(
        createdAt=to_iso(user.created_at),
        email=user.email,
        id=user.id,
        lastLoginAt=to_iso(user.last_login_at) if user.last_login_at else None,
        name=user.name,
        role=user.role,
    )


def issue_summary(issue: models.Issue, cache: dict[str, Any] | None = None) -> Issue:
    cache = cache or {}
    transient_ranking = getattr(issue, "_rank_metadata", None)
    ranking = (
        transient_ranking
        if isinstance(transient_ranking, dict)
        else issue.ranking_json if isinstance(issue.ranking_json, dict) else {}
    )
    return Issue(
        articleCount=cache.get("article_count", issue.article_count),
        changedClaims=cache.get("changed_claims", issue.changed_claims),
        clusterCount=cache.get("cluster_count", issue.cluster_count),
        eventGroup=issue.event_group_name or None,
        eventGroupId=issue.event_group_id,
        id=issue.id,
        issueScore=issue.issue_score,
        majorTopic=issue.major_topic_name or None,
        majorTopicId=issue.major_topic_id,
        needsReviewCount=cache.get("needs_review_count", issue.needs_review_count),
        rankReason=str(ranking.get("rankReason") or "") or None,
        rankScore=_safe_finite_float(ranking.get("rankScore")),
        representativeImageSource=issue.representative_image_source or None,
        representativeImageUrl=issue.representative_image_url or None,
        risk=issue.risk,
        status=issue.status,
        summary=issue.summary or cache.get("computed_summary", ""),
        title=issue.title,
        topic=normalize_topic(issue.topic),
        updatedAt=to_iso(issue.updated_at),
        verifiedCount=cache.get("verified_count", issue.verified_count),
    )


def issue_detail(issue: models.Issue, cache: dict[str, Any] | None = None) -> IssueDetail:
    cache = cache or {}
    quality = issue.quality_report_json if isinstance(issue.quality_report_json, dict) else {}
    ai_synthesis = cache.get("ai_synthesis")
    if not isinstance(ai_synthesis, dict):
        ai_synthesis = quality.get("aiSynthesis") if isinstance(quality.get("aiSynthesis"), dict) else {}
    return IssueDetail(
        **issue_summary(issue, cache).model_dump(),
        aiSynthesis=ai_synthesis,
        articles=cache.get("articles", issue.articles or []),
        claimClusters=cache.get("claim_clusters", issue.claim_clusters or []),
        claims=cache.get("claims", issue.claims or []),
        confirmedFacts=cache.get("confirmed_facts", issue.confirmed_facts or []),
        evidences=cache.get("evidences", issue.evidences or []),
        numberChanges=cache.get("number_changes", issue.number_changes or []),
        perspectives=cache.get("perspectives", issue.perspectives or []),
        sourceDocuments=cache.get("source_documents", issue.source_documents or []),
        timeline=cache.get("timeline", issue.timeline or []),
    )


def podcast_episode_card(
    episode: models.PodcastEpisode,
    issue: models.Issue | None = None,
) -> PodcastEpisodeCard:
    ranking = episode.rank_json if isinstance(episode.rank_json, dict) else {}
    generation = episode.generation_json if isinstance(episode.generation_json, dict) else {}
    gate = generation.get("publicationGate") if isinstance(generation.get("publicationGate"), dict) else {}
    sources = episode.source_json if isinstance(episode.source_json, list) else []
    return PodcastEpisodeCard(
        category=normalize_topic(episode.category),
        durationSeconds=episode.duration_seconds,
        format=episode.episode_format,
        id=episode.id,
        issueId=episode.issue_id,
        issueTitle=issue.title if issue else generation.get("issueTitle"),
        publishedAt=to_iso(episode.published_at or episode.created_at),
        rankReason=str(ranking.get("rankReason") or "") or None,
        rankScore=_safe_finite_float(ranking.get("rankScore")),
        sourceCount=len([source for source in sources if isinstance(source, dict)]),
        status=episode.status,
        subtitle=episode.subtitle,
        thumbnailUrl=episode.thumbnail_url or None,
        title=episode.title,
        variant=episode.variant or str(generation.get("variant") or "standard"),
        publicationGateMissingSignals=[
            str(item)
            for item in gate.get("missingSignals", [])
            if isinstance(item, str) and item.strip()
        ],
        publicationGateQualityScore=_safe_finite_float(gate.get("qualityScore")),
        publicationGateStatus=str(gate.get("status") or "") or None,
        publicationGateWarnings=[
            str(item)
            for item in gate.get("warnings", [])
            if isinstance(item, str) and item.strip()
        ],
        ttsStatus=str(generation.get("ttsStatus") or "script_ready"),
    )


def podcast_episode_detail(
    episode: models.PodcastEpisode,
    issue: models.Issue | None = None,
) -> PodcastEpisodeDetail:
    generation = episode.generation_json if isinstance(episode.generation_json, dict) else {}
    return PodcastEpisodeDetail(
        **podcast_episode_card(episode, issue).model_dump(),
        audioUrl=public_episode_audio_url(episode),
        autoPublished=episode.auto_published,
        correctionPolicy=generation.get("correctionPolicy") if isinstance(generation.get("correctionPolicy"), dict) else {},
        hosts=episode.host_profiles_json or [],
        notationReview=generation.get("notationReview") if isinstance(generation.get("notationReview"), dict) else {},
        playback={
            "defaultSpeed": 1.0,
            "supportsTranscript": True,
            "supportsQueue": True,
        },
        publicationGate=generation.get("publicationGate") if isinstance(generation.get("publicationGate"), dict) else {},
        script=episode.script_json or [],
        sources=episode.source_json or [],
        summary=episode.summary,
    )


def saved_issue(issue: models.Issue) -> UserSavedIssue:
    return UserSavedIssue(
        id=issue.id,
        status=issue.status,
        title=issue.title,
        updatedAt=to_iso(issue.updated_at),
    )


def submitted_claim(
    claim: models.SubmittedClaim,
    issue: models.Issue | None,
) -> UserSubmittedClaim:
    return UserSubmittedClaim(
        id=claim.id,
        issueTitle=issue.title if issue else claim.issue_id,
        status=claim.status,
        submittedAt=to_iso(claim.submitted_at),
        text=claim.claim_text,
    )


def verification_request(request: models.VerificationRequest) -> UserVerificationRequest:
    return UserVerificationRequest(
        articleUrl=request.article_url,
        id=request.id,
        requestedAt=to_iso(request.requested_at),
        status=request.status,
    )


def user_notification(notification: models.Notification, issue: models.Issue | None = None) -> UserNotification:
    return UserNotification(
        href=notification.href or (f"/issues/{notification.issue_id}" if notification.issue_id else None),
        id=notification.id,
        issueTitle=issue.title if issue else None,
        occurredAt=to_iso(notification.created_at),
        read=notification.read,
        title=notification.title,
        type=notification.type,
    )


def admin_queue_item(item: models.AdminQueueItem) -> AdminQueueItem:
    return AdminQueueItem(
        articleCount=item.article_count,
        firstDetectedAt=to_iso(item.first_detected_at),
        id=item.id,
        priority=item.priority,
        reason=item.reason,
        status=item.status,
        title=item.title,
        topic=normalize_topic(item.topic),
    )


def agent_run(run: models.AgentRun) -> AgentRun:
    return AgentRun(
        agent=run.agent,
        failureReason=run.failure_reason,
        finishedAt=to_iso(run.finished_at),
        status=run.status,
        target=run.target,
    )


def moderation_report(report: models.ModerationReport) -> ModerationReport:
    return ModerationReport(
        excerpt=report.excerpt,
        id=report.id,
        issueId=report.issue_id,
        issueTitle=report.issue_title,
        priority=report.priority,
        reason=report.reason,
        status=report.status,
        submittedAt=to_iso(report.submitted_at),
        targetType=report.target_type,
    )


def source_domain(source: models.SourceDomain) -> SourceDomain:
    return SourceDomain(
        collectionIntervalMinutes=source.collection_interval_minutes,
        collectionUrl=source.collection_url or None,
        credibility=source.credibility,
        domain=source.domain,
        id=source.id,
        isActive=source.is_active,
        lastCollectionStatus=source.last_collection_status,
        lastReviewedAt=to_iso(source.last_reviewed_at),
        name=source.name,
        note=source.note,
        sourceType=source.source_type,
        status=source.status,
    )


def search_keyword(keyword: models.SearchKeyword) -> SearchKeyword:
    return SearchKeyword(
        id=keyword.id,
        issueId=keyword.issue_id,
        lastNewArticleCount=keyword.last_new_article_count,
        lastResultCount=keyword.last_result_count,
        lastSearchedAt=to_iso(keyword.last_searched_at) if keyword.last_searched_at else None,
        priority=keyword.priority,
        query=keyword.query,
        searchIntervalMinutes=keyword.search_interval_minutes,
        seedQuery=keyword.seed_query,
        source=keyword.source,
        status=keyword.status,
        topic=normalize_topic(keyword.topic),
    )


def discovery_topic(topic: models.DiscoveryTopic) -> DiscoveryTopic:
    return DiscoveryTopic(
        baseQueries=[str(query) for query in (topic.base_queries_json or [])],
        discoveryIntervalMinutes=topic.discovery_interval_minutes,
        id=topic.id,
        lastCandidateCount=topic.last_candidate_count,
        lastDiscoveredAt=to_iso(topic.last_discovered_at) if topic.last_discovered_at else None,
        lastResultCount=topic.last_result_count,
        maxResultsPerQuery=topic.max_results_per_query,
        minClusterSize=topic.min_cluster_size,
        name=topic.name,
        priority=topic.priority,
        status=topic.status,
        topic=normalize_topic(topic.topic),
    )


def discovered_incident(incident: models.DiscoveredIncident) -> DiscoveredIncident:
    return DiscoveredIncident(
        articleIds=[str(article_id) for article_id in (incident.article_ids_json or [])],
        discoveryTopicId=incident.discovery_topic_id,
        id=incident.id,
        issueId=incident.issue_id,
        keywordIds=[str(keyword_id) for keyword_id in (incident.keyword_ids_json or [])],
        lastSeenAt=to_iso(incident.last_seen_at),
        score=incident.score,
        signals=incident.signals_json or {},
        status=incident.status,
        summary=incident.summary,
        title=incident.title,
        topic=normalize_topic(incident.topic),
    )
