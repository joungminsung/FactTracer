from typing import Any

from pydantic import BaseModel, EmailStr, Field, HttpUrl


class ErrorResponse(BaseModel):
    message: str
    code: str
    details: dict = Field(default_factory=dict)


class AuthUser(BaseModel):
    id: str
    email: EmailStr
    name: str
    role: str
    createdAt: str | None = None
    lastLoginAt: str | None = None


class AuthSession(BaseModel):
    accessToken: str
    refreshToken: str | None = None
    expiresAt: str
    user: AuthUser


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class SignupRequest(LoginRequest):
    name: str = Field(min_length=1, max_length=120)


class UserProfileUpdateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class NotificationSettings(BaseModel):
    officialSourceChanges: bool = True
    numberChanges: bool = True
    reviewCompleted: bool = True
    timelineUpdates: bool = True
    dailyDigest: bool = False
    preferredPerspective: str = "균형"


class UserPreferencesUpdateRequest(BaseModel):
    officialSourceChanges: bool | None = None
    numberChanges: bool | None = None
    reviewCompleted: bool | None = None
    timelineUpdates: bool | None = None
    dailyDigest: bool | None = None
    preferredPerspective: str | None = None


class UserSavedIssue(BaseModel):
    id: str
    title: str
    status: str
    updatedAt: str


class UserSubmittedClaim(BaseModel):
    id: str
    issueTitle: str
    text: str
    status: str
    submittedAt: str


class UserVerificationRequest(BaseModel):
    id: str
    articleUrl: str
    status: str
    requestedAt: str


class UserDashboardResponse(BaseModel):
    user: AuthUser
    savedIssues: list[UserSavedIssue]
    submittedClaims: list[UserSubmittedClaim]
    verificationRequests: list[UserVerificationRequest]


class UserNotification(BaseModel):
    id: str
    type: str
    title: str
    issueTitle: str | None = None
    occurredAt: str
    read: bool
    href: str | None = None


class UserNotificationsResponse(BaseModel):
    notifications: list[UserNotification]
    settings: NotificationSettings
    followedIssues: list[UserSavedIssue]


class MutationResponse(BaseModel):
    id: str
    status: str
    message: str


class Issue(BaseModel):
    id: str
    title: str
    topic: str
    status: str
    risk: str
    updatedAt: str
    summary: str
    issueScore: int
    articleCount: int
    clusterCount: int
    verifiedCount: int
    needsReviewCount: int
    changedClaims: int
    majorTopic: str | None = None
    majorTopicId: str | None = None
    eventGroup: str | None = None
    eventGroupId: str | None = None
    representativeImageUrl: str | None = None
    representativeImageSource: str | None = None
    rankScore: float | None = None
    rankReason: str | None = None


class ConfirmedFact(BaseModel):
    label: str
    text: str
    verdict: str
    tone: str


class ClaimCluster(BaseModel):
    title: str
    question: str
    claims: list[str]
    conflict: str
    commonGround: str
    verdict: str
    tone: str


class ClaimArticleReference(BaseModel):
    id: str
    title: str
    outlet: str
    publishedAt: str
    url: str


class ClaimEvidenceReference(BaseModel):
    id: str
    title: str
    source: str
    sourceType: str
    url: str
    credibility: float
    summary: str


class ClaimHistoryEvent(BaseModel):
    id: str
    previousVerdict: str
    currentVerdict: str
    reason: str
    changedAt: str


class Claim(BaseModel):
    id: str | None = None
    text: str
    type: str
    verdict: str
    tone: str
    confidence: float
    evidence: str
    status: str
    relatedArticles: list[ClaimArticleReference] = Field(default_factory=list)
    evidences: list[ClaimEvidenceReference] = Field(default_factory=list)
    rebuttals: list[str] = Field(default_factory=list)
    updateHistory: list[ClaimHistoryEvent] = Field(default_factory=list)


class Evidence(BaseModel):
    id: str | None = None
    label: str
    source: str
    date: str
    summary: str
    credibility: float
    url: str | None = None
    sourceType: str | None = None


class Perspective(BaseModel):
    name: str
    core: str
    uses: str
    challengedBy: str
    commonGround: str


class ArticleComparison(BaseModel):
    id: str
    title: str
    outlet: str
    publishedAt: str
    url: str
    claimCount: int
    outdatedClaims: int
    officialSourceCount: int
    verdict: str
    tone: str
    note: str


class IssueTimelineEvent(BaseModel):
    id: str
    occurredAt: str
    type: str
    title: str
    description: str


class SourceDocument(BaseModel):
    id: str
    title: str
    publisher: str
    publishedAt: str
    url: str
    sourceType: str
    credibility: float


class NumberChangeEvent(BaseModel):
    id: str
    label: str
    previousValue: str
    currentValue: str
    changedAt: str
    source: str
    note: str
    tone: str | None = None


class IssueDetail(Issue):
    aiSynthesis: dict[str, Any] = Field(default_factory=dict)
    confirmedFacts: list[ConfirmedFact]
    claimClusters: list[ClaimCluster]
    claims: list[Claim]
    evidences: list[Evidence]
    perspectives: list[Perspective]
    articles: list[ArticleComparison] = Field(default_factory=list)
    timeline: list[IssueTimelineEvent] = Field(default_factory=list)
    sourceDocuments: list[SourceDocument] = Field(default_factory=list)
    numberChanges: list[NumberChangeEvent] = Field(default_factory=list)


class PublicHomeResponse(BaseModel):
    topics: list[str]
    issues: list[Issue]
    selectedIssue: IssueDetail | None
    updateLogs: list[dict]
    issueGroups: dict[str, list[Issue]] = Field(default_factory=dict)


class PodcastHost(BaseModel):
    id: str
    name: str
    role: str
    tone: str


class PodcastScriptSegment(BaseModel):
    speakerId: str
    speakerName: str
    role: str
    text: str
    startsAt: int
    expressionReview: dict[str, Any] = Field(default_factory=dict)
    sourceRefs: list[dict[str, Any]] = Field(default_factory=list)


class PodcastSource(BaseModel):
    id: str
    title: str
    publisher: str
    url: str
    sourceType: str
    credibility: float


class PodcastEpisodeCard(BaseModel):
    id: str
    issueId: str | None = None
    issueTitle: str | None = None
    title: str
    subtitle: str
    category: str
    format: str
    durationSeconds: int
    thumbnailUrl: str | None = None
    publishedAt: str
    rankScore: float | None = None
    rankReason: str | None = None
    sourceCount: int
    status: str
    variant: str = "standard"
    publicationGateMissingSignals: list[str] = Field(default_factory=list)
    publicationGateQualityScore: float | None = None
    publicationGateStatus: str | None = None
    publicationGateWarnings: list[str] = Field(default_factory=list)
    ttsStatus: str = "script_ready"


class PodcastEpisodeDetail(PodcastEpisodeCard):
    summary: str
    hosts: list[PodcastHost]
    script: list[PodcastScriptSegment]
    sources: list[PodcastSource]
    audioUrl: str | None = None
    ttsStatus: str
    autoPublished: bool
    correctionPolicy: dict[str, Any] = Field(default_factory=dict)
    notationReview: dict[str, Any] = Field(default_factory=dict)
    playback: dict[str, Any] = Field(default_factory=dict)
    publicationGate: dict[str, Any] = Field(default_factory=dict)


class PodcastSection(BaseModel):
    id: str
    title: str
    description: str
    episodes: list[PodcastEpisodeCard]


class PodcastHomeResponse(BaseModel):
    sections: list[PodcastSection]
    nowPlaying: PodcastEpisodeCard | None = None


class PodcastFeedResponse(BaseModel):
    episodes: list[PodcastEpisodeCard]


class PodcastDetailResponse(BaseModel):
    episode: PodcastEpisodeDetail
    nextQueue: list[PodcastEpisodeCard]


class PodcastGenerateResponse(BaseModel):
    episodes: list[PodcastEpisodeCard]
    generatedCount: int


class IssueDetailResponse(BaseModel):
    issue: IssueDetail | None
    relatedIssues: list[Issue]


class ArticleVerificationRequest(BaseModel):
    articleUrl: HttpUrl
    issueId: str | None = None


class ArticleVerificationResponse(BaseModel):
    id: str
    status: str
    matchedIssueId: str | None = None
    message: str


class ManualCheckRequest(BaseModel):
    inputType: str = Field(pattern="^(url|text|youtube|image|pdf|file)$")
    content: str = Field(min_length=1)
    issueId: str | None = None


class ManualCheckResponse(BaseModel):
    id: str
    status: str
    inputType: str
    matchedIssueId: str | None = None
    standaloneResultId: str | None = None
    message: str


class FileRegistrationRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=260)
    contentType: str
    sizeBytes: int = Field(ge=0)
    storageUrl: str | None = None
    contentBase64: str | None = None


class FileRegistrationResponse(BaseModel):
    id: str
    status: str
    safetyStatus: str
    message: str


class ClaimSubmissionRequest(BaseModel):
    issueId: str
    claimText: str = Field(min_length=2)
    evidenceUrl: HttpUrl | None = None
    reason: str = Field(min_length=2)
    relatedCluster: str | None = None
    claimType: str = Field(min_length=1)
    refutablePoint: str = Field(min_length=2)


class ClaimSubmissionResponse(BaseModel):
    id: str
    status: str
    clusterId: str | None = None


class ReverificationRequest(BaseModel):
    priority: str
    memo: str | None = None


class IssueReportResponse(BaseModel):
    id: str
    issueId: str
    status: str
    downloadUrl: str | None = None
    markdownUrl: str | None = None
    shareUrl: str | None = None
    message: str


class IssueContentReportRequest(BaseModel):
    targetType: str = Field(default="issue", min_length=2, max_length=80)
    targetId: str | None = Field(default=None, max_length=120)
    reason: str = Field(min_length=2, max_length=500)
    excerpt: str = Field(default="", max_length=1000)


class AnalyticsEventRequest(BaseModel):
    eventType: str = Field(min_length=2, max_length=80)
    issueId: str | None = Field(default=None, max_length=80)
    reportId: str | None = Field(default=None, max_length=80)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AdminDashboardMetric(BaseModel):
    label: str
    value: str


class AdminDashboardNavItem(BaseModel):
    label: str
    value: str


class AdminQueueItem(BaseModel):
    id: str
    title: str
    topic: str
    articleCount: int
    firstDetectedAt: str
    status: str
    priority: str
    reason: str


class AgentRun(BaseModel):
    agent: str
    status: str
    target: str
    finishedAt: str
    failureReason: str | None = None


class AdminDashboardResponse(BaseModel):
    metrics: list[AdminDashboardMetric]
    navItems: list[AdminDashboardNavItem]
    queue: list[AdminQueueItem]
    selectedIssue: AdminQueueItem | None
    claims: list[Claim]
    claimClusters: list[ClaimCluster]
    evidences: list[Evidence]
    agentRuns: list[AgentRun]


class ModerationReport(BaseModel):
    id: str
    issueId: str
    issueTitle: str
    targetType: str
    reason: str
    status: str
    priority: str
    submittedAt: str
    excerpt: str


class SourceDomain(BaseModel):
    id: str
    domain: str
    name: str
    sourceType: str
    credibility: float
    status: str
    isActive: bool = True
    lastReviewedAt: str
    note: str
    collectionUrl: str | None = None
    collectionIntervalMinutes: int | None = None
    lastCollectionStatus: str | None = None


class AdminIssueResponse(BaseModel):
    issue: AdminQueueItem | None
    publicIssue: IssueDetail | None
    queue: list[AdminQueueItem]
    claims: list[Claim]
    claimClusters: list[ClaimCluster]
    evidences: list[Evidence]
    articles: list[ArticleComparison]
    timeline: list[IssueTimelineEvent]
    reports: list[ModerationReport]


class AdminReportsResponse(BaseModel):
    reports: list[ModerationReport]


class AdminSourcesResponse(BaseModel):
    sources: list[SourceDomain]


class SearchKeyword(BaseModel):
    id: str
    query: str
    seedQuery: str
    topic: str
    priority: str
    status: str
    source: str
    issueId: str | None = None
    searchIntervalMinutes: int
    lastSearchedAt: str | None = None
    lastResultCount: int
    lastNewArticleCount: int


class SearchKeywordSeedRequest(BaseModel):
    query: str = Field(min_length=2, max_length=300)
    topic: str = "사회"
    priority: str = "high"
    intervalMinutes: int = Field(default=30, ge=5, le=1440)
    generateVariants: bool = True
    runImmediately: bool = True


class SearchKeywordsResponse(BaseModel):
    keywords: list[SearchKeyword]


class DiscoveryTopic(BaseModel):
    id: str
    name: str
    topic: str
    baseQueries: list[str]
    priority: str
    status: str
    discoveryIntervalMinutes: int
    maxResultsPerQuery: int
    minClusterSize: int
    lastDiscoveredAt: str | None = None
    lastResultCount: int
    lastCandidateCount: int


class DiscoveryTopicCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    topic: str = "사회"
    baseQueries: list[str] = Field(default_factory=list)
    priority: str = "normal"
    intervalMinutes: int = Field(default=60, ge=5, le=1440)
    maxResultsPerQuery: int = Field(default=12, ge=1, le=30)
    minClusterSize: int = Field(default=2, ge=1, le=10)
    runImmediately: bool = True


class DiscoveryTopicsResponse(BaseModel):
    topics: list[DiscoveryTopic]


class DiscoveredIncident(BaseModel):
    id: str
    discoveryTopicId: str | None = None
    issueId: str | None = None
    title: str
    summary: str
    topic: str
    score: int
    status: str
    articleIds: list[str]
    keywordIds: list[str]
    signals: dict
    lastSeenAt: str


class DiscoveredIncidentsResponse(BaseModel):
    incidents: list[DiscoveredIncident]


class SchedulerStatusResponse(BaseModel):
    id: str
    ownerId: str
    status: str
    lockedUntil: str | None = None
    lastHeartbeatAt: str | None = None
    lastTickStartedAt: str | None = None
    lastTickFinishedAt: str | None = None
    tickCount: int
    lastTick: dict = Field(default_factory=dict)
    errorMessage: str = ""


class AdminAgentsResponse(BaseModel):
    agentRuns: list[AgentRun]
    recentEvents: list[IssueTimelineEvent]


class IssueUpdatesResponse(BaseModel):
    updates: list[dict]


class IssueArticlesResponse(BaseModel):
    articles: list[ArticleComparison]


class IssueClaimClustersResponse(BaseModel):
    claimClusters: list[ClaimCluster]


class IssuePerspectivesResponse(BaseModel):
    perspectives: list[Perspective]


class CollectorRunRequest(BaseModel):
    sourceIds: list[str] | None = None


class CollectorRunResponse(BaseModel):
    id: str
    status: str
    message: str
    result: dict = Field(default_factory=dict)


class CollectorRunsResponse(BaseModel):
    runs: list[dict]


class JobListResponse(BaseModel):
    jobs: list[dict]


class ResearchRunItem(BaseModel):
    id: str
    issueId: str | None = None
    triggerType: str
    seedQuery: str
    status: str
    roundIndex: int
    plan: dict = Field(default_factory=dict)
    sourceRoutes: list = Field(default_factory=list)
    executedQueries: list = Field(default_factory=list)
    resultUrls: list = Field(default_factory=list)
    selectedArticleIds: list = Field(default_factory=list)
    missingSignals: list = Field(default_factory=list)
    errorMessage: str = ""
    startedAt: str | None = None
    finishedAt: str | None = None
    durationMs: int = 0


class ResearchRunListResponse(BaseModel):
    items: list[ResearchRunItem]


class IssueMergeRequest(BaseModel):
    targetIssueId: str


class IssueSplitRequest(BaseModel):
    articleId: str
    title: str
    topic: str


class SourcePolicyRequest(BaseModel):
    status: str | None = None
    credibility: float | None = Field(default=None, ge=0, le=1)
    collectionIntervalMinutes: int | None = Field(default=None, ge=1)


class SourceCreateRequest(BaseModel):
    domain: str = Field(min_length=3, max_length=255)
    name: str = Field(min_length=1, max_length=200)
    sourceType: str = Field(default="rss", min_length=1, max_length=80)
    credibility: float = Field(default=0.5, ge=0, le=1)
    status: str = "watch"
    collectionUrl: str | None = None
    collectionIntervalMinutes: int = Field(default=30, ge=1)
    isActive: bool = True
    note: str = ""


class SourceUpdateRequest(BaseModel):
    domain: str | None = Field(default=None, min_length=3, max_length=255)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    sourceType: str | None = Field(default=None, min_length=1, max_length=80)
    credibility: float | None = Field(default=None, ge=0, le=1)
    status: str | None = None
    collectionUrl: str | None = None
    collectionIntervalMinutes: int | None = Field(default=None, ge=1)
    isActive: bool | None = None
    note: str | None = None


class AdminSettingItem(BaseModel):
    key: str
    label: str
    description: str
    group: str
    valueType: str
    value: Any = None
    defaultValue: Any = None
    options: list[str] = Field(default_factory=list)
    min: float | None = None
    max: float | None = None
    step: float | None = None
    unit: str | None = None
    isSecret: bool = False
    isRuntimeMutable: bool = True
    configured: bool = False
    source: str
    updatedAt: str | None = None


class AdminSettingsGroup(BaseModel):
    id: str
    label: str
    description: str
    items: list[AdminSettingItem]


class AdminSettingsResponse(BaseModel):
    groups: list[AdminSettingsGroup]
    updatedAt: str


class AdminSettingUpdate(BaseModel):
    key: str
    value: Any = None
    reset: bool = False
    clear: bool = False


class AdminSettingsUpdateRequest(BaseModel):
    settings: list[AdminSettingUpdate] = Field(min_length=1)


class DeviceTokenRequest(BaseModel):
    platform: str = "expo"
    token: str = Field(min_length=8)
