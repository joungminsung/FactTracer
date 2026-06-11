export type VerdictTone = "positive" | "warning" | "danger" | "negative" | "neutral";

export type IssueSortMode =
  | "recommended"
  | "latest"
  | "controversial"
  | "highImpact"
  | "needsReview"
  | "officialUpdated"
  | "personalized";

export type UserRole = "user" | "reviewer" | "admin";

export type AuthUser = {
  id: string;
  email: string;
  name: string;
  role: UserRole;
  createdAt?: string;
  lastLoginAt?: string;
};

export type AuthSession = {
  accessToken: string;
  refreshToken?: string;
  expiresAt: string;
  user: AuthUser;
};

export type LoginRequest = {
  email: string;
  password: string;
};

export type SignupRequest = {
  email: string;
  password: string;
  name: string;
};

export type Issue = {
  id: string;
  title: string;
  topic: string;
  status: string;
  risk: string;
  updatedAt: string;
  summary: string;
  issueScore: number;
  articleCount: number;
  clusterCount: number;
  verifiedCount: number;
  needsReviewCount: number;
  changedClaims: number;
  majorTopic?: string | null;
  majorTopicId?: string | null;
  eventGroup?: string | null;
  eventGroupId?: string | null;
  representativeImageUrl?: string | null;
  representativeImageSource?: string | null;
  rankScore?: number | null;
  rankReason?: string | null;
};

export type ConfirmedFact = {
  label: string;
  text: string;
  verdict: string;
  tone: VerdictTone;
};

export type ClaimCluster = {
  title: string;
  question: string;
  claims: string[];
  conflict: string;
  commonGround: string;
  verdict: string;
  tone: VerdictTone;
};

export type Evidence = {
  id?: string;
  label: string;
  source: string;
  date: string;
  summary: string;
  credibility: number;
  url?: string | null;
  sourceType?: string | null;
};

export type Perspective = {
  name: string;
  core: string;
  uses: string;
  challengedBy: string;
  commonGround: string;
};

export type Claim = {
  id?: string;
  text: string;
  type: string;
  verdict: string;
  tone: VerdictTone;
  confidence: number;
  evidence: string;
  status: string;
  relatedArticles?: ClaimArticleReference[];
  evidences?: ClaimEvidenceReference[];
  rebuttals?: string[];
  updateHistory?: ClaimHistoryEvent[];
};

export type ClaimArticleReference = {
  id: string;
  title: string;
  outlet: string;
  publishedAt: string;
  url: string;
};

export type ClaimEvidenceReference = {
  id: string;
  title: string;
  source: string;
  sourceType: string;
  url: string;
  credibility: number;
  summary: string;
};

export type ClaimHistoryEvent = {
  id: string;
  previousVerdict: string;
  currentVerdict: string;
  reason: string;
  changedAt: string;
};

export type UpdateLog = {
  time: string;
  type: string;
  title: string;
  description: string;
  issueId?: string;
  issueTitle?: string | null;
};

export type IssueDetail = Issue & {
  confirmedFacts: ConfirmedFact[];
  claimClusters: ClaimCluster[];
  claims: Claim[];
  evidences: Evidence[];
  perspectives: Perspective[];
  articles?: ArticleComparison[];
  timeline?: IssueTimelineEvent[];
  sourceDocuments?: SourceDocument[];
  numberChanges?: NumberChangeEvent[];
};

export type PublicHomeResponse = {
  topics: string[];
  issues: Issue[];
  selectedIssue: IssueDetail | null;
  updateLogs: UpdateLog[];
  issueGroups?: Record<string, Issue[]>;
};

export type ArticleComparison = {
  id: string;
  title: string;
  outlet: string;
  publishedAt: string;
  url: string;
  claimCount: number;
  outdatedClaims: number;
  officialSourceCount: number;
  verdict: string;
  tone: VerdictTone;
  note: string;
};

export type IssueTimelineEvent = {
  id: string;
  occurredAt: string;
  type: string;
  title: string;
  description: string;
};

export type NumberChangeEvent = {
  id: string;
  label: string;
  previousValue: string;
  currentValue: string;
  changedAt: string;
  source: string;
  note: string;
  tone?: VerdictTone;
};

export type SourceDocument = {
  id: string;
  title: string;
  publisher: string;
  publishedAt: string;
  url: string;
  sourceType: "official" | "media" | "statistics" | "law" | "social" | string;
  credibility: number;
};

export type IssueDetailResponse = {
  issue: IssueDetail | null;
  relatedIssues: Issue[];
};

export type AdminQueueItem = {
  id: string;
  title: string;
  topic: string;
  articleCount: number;
  firstDetectedAt: string;
  status: string;
  priority: string;
  reason: string;
};

export type AgentRun = {
  agent: string;
  status: "completed" | "running" | "needs_review" | string;
  target: string;
  finishedAt: string;
  failureReason?: string;
};

export type AdminDashboardMetric = {
  label: string;
  value: string;
};

export type AdminDashboardNavItem = {
  label: string;
  value: string;
};

export type AdminDashboardResponse = {
  metrics: AdminDashboardMetric[];
  navItems: AdminDashboardNavItem[];
  queue: AdminQueueItem[];
  selectedIssue: AdminQueueItem | null;
  claims: Claim[];
  claimClusters: ClaimCluster[];
  evidences: Evidence[];
  agentRuns: AgentRun[];
};

export type ArticleVerificationRequest = {
  articleUrl: string;
  issueId?: string;
};

export type ArticleVerificationResponse = {
  id: string;
  status: "queued" | "running" | "completed";
  matchedIssueId?: string;
  message: string;
};

export type ClaimSubmissionRequest = {
  issueId: string;
  claimText: string;
  evidenceUrl?: string;
  reason: string;
  relatedCluster?: string;
  claimType: string;
  refutablePoint: string;
};

export type ClaimSubmissionResponse = {
  id: string;
  status: "received" | "needs_review" | "merged";
  clusterId?: string;
};

export type ReverificationRequest = {
  priority: "high" | "medium" | "low";
  memo?: string;
};

export type MutationResponse = {
  id: string;
  status: string;
  message: string;
};

export type IssueReportResponse = {
  id: string;
  issueId: string;
  status: "created" | "updated";
  downloadUrl?: string;
  markdownUrl?: string;
  shareUrl?: string;
  message: string;
};

export type ManualCheckRequest = {
  inputType: "url" | "text" | "youtube" | "image" | "pdf" | "file";
  content: string;
  issueId?: string;
};

export type ManualCheckResponse = {
  id: string;
  status: "queued" | "running" | "completed" | "rejected" | string;
  inputType: string;
  matchedIssueId?: string | null;
  standaloneResultId?: string | null;
  message: string;
};

export type FileRegistrationRequest = {
  filename: string;
  contentType: string;
  sizeBytes: number;
  storageUrl?: string | null;
  contentBase64?: string | null;
};

export type FileRegistrationResponse = {
  id: string;
  status: string;
  safetyStatus: string;
  message: string;
};

export type IssueContentReportRequest = {
  targetType: "issue" | "claim" | "source" | string;
  targetId?: string | null;
  reason: string;
  excerpt?: string;
};

export type AnalyticsEventRequest = {
  eventType: string;
  issueId?: string | null;
  reportId?: string | null;
  metadata?: Record<string, unknown>;
};

export type PodcastHost = {
  id: string;
  name: string;
  role: string;
  tone: string;
};

export type PodcastScriptSegment = {
  speakerId: string;
  speakerName: string;
  role: string;
  text: string;
  startsAt: number;
  expressionReview?: Record<string, unknown>;
  sourceRefs?: Array<Record<string, unknown>>;
};

export type PodcastSource = {
  id: string;
  title: string;
  publisher: string;
  url: string;
  sourceType: string;
  credibility: number;
};

export type PodcastEpisodeSummary = {
  id: string;
  issueId?: string | null;
  issueTitle?: string | null;
  title: string;
  subtitle: string;
  category: string;
  format: "solo" | "panel_2" | "panel_3" | string;
  durationSeconds: number;
  thumbnailUrl?: string | null;
  publishedAt: string;
  rankScore?: number | null;
  rankReason?: string | null;
  sourceCount: number;
  status: string;
  variant: "short" | "standard" | "deep" | string;
  publicationGateMissingSignals: string[];
  publicationGateQualityScore?: number | null;
  publicationGateStatus?: string | null;
  publicationGateWarnings: string[];
  ttsStatus: string;
};

export type PodcastEpisodeDetail = PodcastEpisodeSummary & {
  summary: string;
  hosts: PodcastHost[];
  script: PodcastScriptSegment[];
  sources: PodcastSource[];
  audioUrl?: string | null;
  autoPublished: boolean;
  correctionPolicy: Record<string, unknown>;
  notationReview: Record<string, unknown>;
  playback: Record<string, unknown>;
  publicationGate: Record<string, unknown>;
};

export type PodcastSection = {
  id: string;
  title: string;
  description: string;
  episodes: PodcastEpisodeSummary[];
};

export type PodcastHomeResponse = {
  sections: PodcastSection[];
  nowPlaying: PodcastEpisodeSummary | null;
};

export type PodcastFeedResponse = {
  episodes: PodcastEpisodeSummary[];
};

export type PodcastDetailResponse = {
  episode: PodcastEpisodeDetail;
  nextQueue: PodcastEpisodeSummary[];
};

export type PodcastGenerateResponse = {
  episodes: PodcastEpisodeSummary[];
  generatedCount: number;
};

export type AdminJob = {
  id: string;
  jobType: string;
  targetId: string;
  status: string;
  attempts: number;
  maxAttempts: number;
  lastError: string;
  userMessage?: string;
  user_message?: string;
  createdAt: string;
  updatedAt: string;
};

export type AdminJobsResponse = {
  jobs: AdminJob[];
};

export type PodcastPlaybackState = {
  currentTime: number;
  duration: number;
  isBuffering: boolean;
  isExpanded: boolean;
  isPlaying: boolean;
  playbackRate: number;
  selectedEpisode: PodcastEpisodeDetail | null;
  queue: PodcastEpisodeSummary[];
};

export type SourceDomain = {
  id: string;
  domain: string;
  name: string;
  sourceType: string;
  credibility: number;
  status: "trusted" | "watch" | "blocked" | string;
  isActive: boolean;
  lastReviewedAt: string;
  note: string;
  collectionUrl?: string | null;
  collectionIntervalMinutes?: number | null;
  lastCollectionStatus?: string | null;
};

export type ModerationReport = {
  id: string;
  issueId: string;
  issueTitle: string;
  targetType: "claim" | "comment" | "source" | "issue" | string;
  reason: string;
  status: "open" | "resolved" | "dismissed" | string;
  priority: string;
  submittedAt: string;
  excerpt: string;
};

export type AdminIssueResponse = {
  issue: AdminQueueItem | null;
  publicIssue: IssueDetail | null;
  queue: AdminQueueItem[];
  claims: Claim[];
  claimClusters: ClaimCluster[];
  evidences: Evidence[];
  articles: ArticleComparison[];
  timeline: IssueTimelineEvent[];
  reports: ModerationReport[];
};

export type AdminReportsResponse = {
  reports: ModerationReport[];
};

export type AdminSourcesResponse = {
  sources: SourceDomain[];
};

export type AdminAgentsResponse = {
  agentRuns: AgentRun[];
  recentEvents: IssueTimelineEvent[];
};

export type AdminSettingValue = string | number | boolean | string[] | null;

export type AdminSettingItem = {
  key: string;
  label: string;
  description: string;
  group: string;
  valueType: "boolean" | "integer" | "float" | "list" | "select" | "string";
  value: AdminSettingValue;
  defaultValue: AdminSettingValue;
  options: string[];
  min?: number | null;
  max?: number | null;
  step?: number | null;
  unit?: string | null;
  isSecret: boolean;
  isRuntimeMutable: boolean;
  configured: boolean;
  source: "admin" | "env" | "default" | string;
  updatedAt?: string | null;
};

export type AdminSettingsGroup = {
  id: string;
  label: string;
  description: string;
  items: AdminSettingItem[];
};

export type AdminSettingsResponse = {
  groups: AdminSettingsGroup[];
  updatedAt: string;
};

export type UserSavedIssue = {
  id: string;
  title: string;
  status: string;
  updatedAt: string;
};

export type UserSubmittedClaim = {
  id: string;
  issueTitle: string;
  text: string;
  status: string;
  submittedAt: string;
};

export type UserVerificationRequest = {
  id: string;
  articleUrl: string;
  status: string;
  requestedAt: string;
};

export type UserDashboardResponse = {
  user: AuthUser;
  savedIssues: UserSavedIssue[];
  submittedClaims: UserSubmittedClaim[];
  verificationRequests: UserVerificationRequest[];
};

export type UserProfileUpdateRequest = {
  name: string;
};

export type NotificationSettings = {
  officialSourceChanges: boolean;
  numberChanges: boolean;
  reviewCompleted: boolean;
  timelineUpdates: boolean;
  dailyDigest: boolean;
  preferredPerspective: string;
};

export type UserNotification = {
  id: string;
  type: string;
  title: string;
  issueTitle?: string;
  occurredAt: string;
  read: boolean;
  href?: string;
};

export type UserNotificationsResponse = {
  notifications: UserNotification[];
  settings: NotificationSettings;
  followedIssues: UserSavedIssue[];
};

export type UserPreferencesUpdateRequest = Partial<NotificationSettings>;
