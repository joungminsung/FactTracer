import {
  createApiNotConfiguredError,
  isApiConfigured,
} from "@/lib/api/config";
import { apiFetch } from "@/lib/api/http";
import type {
  AnalyticsEventRequest,
  AdminAgentsResponse,
  AdminDashboardResponse,
  AdminIssueResponse,
  AdminReportsResponse,
  AdminSettingsResponse,
  AdminSettingValue,
  AdminSourcesResponse,
  ArticleVerificationRequest,
  ArticleVerificationResponse,
  ClaimSubmissionRequest,
  ClaimSubmissionResponse,
  FileRegistrationRequest,
  FileRegistrationResponse,
  IssueContentReportRequest,
  IssueDetailResponse,
  IssueReportResponse,
  IssueSortMode,
  ManualCheckRequest,
  ManualCheckResponse,
  MutationResponse,
  PublicHomeResponse,
  ReverificationRequest,
  SourceDomain,
} from "@/lib/api/types";

export const topicFilters = ["전체", "정치", "사회", "경제", "국제", "재난", "보건", "IT"];

const emptyPublicHome: PublicHomeResponse = {
  issueGroups: {},
  issues: [],
  selectedIssue: null,
  topics: topicFilters,
  updateLogs: [],
};

const emptyAdminDashboard: AdminDashboardResponse = {
  agentRuns: [],
  claimClusters: [],
  claims: [],
  evidences: [],
  metrics: [],
  navItems: [
    { label: "검토 목록", value: "" },
    { label: "민감 이슈", value: "" },
    { label: "신고 표현", value: "" },
    { label: "출처 관리", value: "" },
    { label: "자동 처리 기록", value: "" },
    { label: "운영 설정", value: "" },
  ],
  queue: [],
  selectedIssue: null,
};

const emptyAdminSettings: AdminSettingsResponse = {
  groups: [],
  updatedAt: "",
};

export async function getPublicHome({
  eventGroup,
  issueId,
  majorTopic,
  query,
  sort,
  token,
  topic,
}: {
  eventGroup?: string;
  issueId?: string;
  majorTopic?: string;
  query?: string;
  sort?: IssueSortMode;
  token?: string | null;
  topic?: string;
} = {}): Promise<PublicHomeResponse> {
  if (!isApiConfigured()) return emptyPublicHome;

  return apiFetch<PublicHomeResponse>("/v1/issues/home", {
    cache: "no-store",
    searchParams: { eventGroup, issueId, majorTopic, q: query, sort, topic },
    token,
  });
}

export async function getIssueDetail(
  issueId: string,
): Promise<IssueDetailResponse> {
  if (!isApiConfigured()) {
    return { issue: null, relatedIssues: [] };
  }

  return apiFetch<IssueDetailResponse>(`/v1/issues/${issueId}`, {
    cache: "no-store",
  });
}

export async function submitArticleVerification(
  payload: ArticleVerificationRequest,
  token?: string | null,
): Promise<ArticleVerificationResponse> {
  if (!isApiConfigured()) throw createApiNotConfiguredError();

  return apiFetch<ArticleVerificationResponse>("/v1/verification-requests", {
    body: payload,
    method: "POST",
    token,
  });
}

export async function submitClaim(
  payload: ClaimSubmissionRequest,
  token?: string | null,
): Promise<ClaimSubmissionResponse> {
  if (!isApiConfigured()) throw createApiNotConfiguredError();

  return apiFetch<ClaimSubmissionResponse>(
    `/v1/issues/${payload.issueId}/claims`,
    {
      body: payload,
      method: "POST",
      token,
    },
  );
}

export async function saveIssue(issueId: string, token?: string | null) {
  if (!isApiConfigured()) throw createApiNotConfiguredError();

  return apiFetch<MutationResponse>(`/v1/users/me/saved-issues/${issueId}`, {
    method: "PUT",
    token,
  });
}

export async function removeSavedIssue(issueId: string, token?: string | null) {
  if (!isApiConfigured()) throw createApiNotConfiguredError();

  return apiFetch<MutationResponse>(`/v1/users/me/saved-issues/${issueId}`, {
    method: "DELETE",
    token,
  });
}

export async function withdrawSubmittedClaim(
  claimId: string,
  token?: string | null,
) {
  if (!isApiConfigured()) throw createApiNotConfiguredError();

  return apiFetch<MutationResponse>(`/v1/users/me/submitted-claims/${claimId}`, {
    method: "DELETE",
    token,
  });
}

export async function cancelVerificationRequest(
  requestId: string,
  token?: string | null,
) {
  if (!isApiConfigured()) throw createApiNotConfiguredError();

  return apiFetch<MutationResponse>(
    `/v1/users/me/verification-requests/${requestId}`,
    {
      method: "DELETE",
      token,
    },
  );
}

export async function createIssueReport(issueId: string, token?: string | null) {
  if (!isApiConfigured()) throw createApiNotConfiguredError();

  return apiFetch<IssueReportResponse>(`/v1/issues/${issueId}/report`, {
    method: "POST",
    token,
  });
}

export async function submitManualCheck(
  payload: ManualCheckRequest,
  token?: string | null,
): Promise<ManualCheckResponse> {
  if (!isApiConfigured()) throw createApiNotConfiguredError();

  return apiFetch<ManualCheckResponse>("/v1/checks", {
    body: payload,
    method: "POST",
    token,
  });
}

export async function registerVerificationFile(
  payload: FileRegistrationRequest,
  token?: string | null,
): Promise<FileRegistrationResponse> {
  if (!isApiConfigured()) throw createApiNotConfiguredError();

  return apiFetch<FileRegistrationResponse>("/v1/files", {
    body: payload,
    method: "POST",
    token,
  });
}

export async function submitIssueContentReport(
  issueId: string,
  payload: IssueContentReportRequest,
  token?: string | null,
) {
  if (!isApiConfigured()) throw createApiNotConfiguredError();

  return apiFetch<MutationResponse>(`/v1/issues/${issueId}/content-reports`, {
    body: payload,
    method: "POST",
    token,
  });
}

export async function recordAnalyticsEvent(
  payload: AnalyticsEventRequest,
  token?: string | null,
) {
  if (!isApiConfigured()) return null;

  return apiFetch<MutationResponse>("/v1/analytics/events", {
    body: { ...payload, metadata: payload.metadata ?? {} },
    method: "POST",
    token,
  });
}

export async function getAdminDashboard(
  token?: string | null,
  options: { fallbackToEmpty?: boolean } = {},
): Promise<AdminDashboardResponse> {
  if (!isApiConfigured() || options.fallbackToEmpty) return emptyAdminDashboard;

  return apiFetch<AdminDashboardResponse>("/v1/admin/dashboard", {
    cache: "no-store",
    token,
  });
}

export async function syncAdminQueue(token?: string | null) {
  if (!isApiConfigured()) throw createApiNotConfiguredError();

  return apiFetch<MutationResponse>("/v1/admin/queue/sync", {
    method: "POST",
    token,
  });
}

export async function approveAdminIssue(issueId: string, token?: string | null) {
  if (!isApiConfigured()) throw createApiNotConfiguredError();

  return apiFetch<MutationResponse>(`/v1/admin/issues/${issueId}/approve`, {
    method: "POST",
    token,
  });
}

export async function runIssueReverification(
  issueId: string,
  payload: ReverificationRequest,
  token?: string | null,
) {
  if (!isApiConfigured()) throw createApiNotConfiguredError();

  return apiFetch<MutationResponse>(`/v1/admin/issues/${issueId}/reverify`, {
    body: payload,
    method: "POST",
    token,
  });
}

export async function getAdminIssue(
  issueId: string,
  token?: string | null,
): Promise<AdminIssueResponse> {
  if (!isApiConfigured()) {
    return {
      articles: [],
      claimClusters: [],
      claims: [],
      evidences: [],
      issue: null,
      publicIssue: null,
      queue: [],
      reports: [],
      timeline: [],
    };
  }

  return apiFetch<AdminIssueResponse>(`/v1/admin/issues/${issueId}`, {
    cache: "no-store",
    token,
  });
}

export async function getAdminReports(
  token?: string | null,
): Promise<AdminReportsResponse> {
  if (!isApiConfigured()) return { reports: [] };

  return apiFetch<AdminReportsResponse>("/v1/admin/reports", {
    cache: "no-store",
    token,
  });
}

export async function resolveAdminReport(
  reportId: string,
  status: "resolved" | "dismissed",
  token?: string | null,
) {
  if (!isApiConfigured()) throw createApiNotConfiguredError();

  return apiFetch<MutationResponse>(`/v1/admin/reports/${reportId}/resolve`, {
    body: { status },
    method: "POST",
    token,
  });
}

export async function getAdminSources(
  token?: string | null,
): Promise<AdminSourcesResponse> {
  if (!isApiConfigured()) return { sources: [] };

  return apiFetch<AdminSourcesResponse>("/v1/admin/sources", {
    cache: "no-store",
    token,
  });
}

export async function getAdminSettings(
  token?: string | null,
): Promise<AdminSettingsResponse> {
  if (!isApiConfigured()) return emptyAdminSettings;

  return apiFetch<AdminSettingsResponse>("/v1/admin/settings", {
    cache: "no-store",
    token,
  });
}

export async function updateAdminSettings(
  settings: Array<{
    clear?: boolean;
    key: string;
    reset?: boolean;
    value?: AdminSettingValue;
  }>,
  token?: string | null,
) {
  if (!isApiConfigured()) throw createApiNotConfiguredError();

  return apiFetch<AdminSettingsResponse>("/v1/admin/settings", {
    body: { settings },
    method: "PATCH",
    token,
  });
}

export async function updateSourceDomainStatus(
  domainId: string,
  status: "trusted" | "watch" | "blocked",
  token?: string | null,
) {
  if (!isApiConfigured()) throw createApiNotConfiguredError();

  return apiFetch<MutationResponse>(`/v1/admin/sources/${domainId}`, {
    body: { status },
    method: "PATCH",
    token,
  });
}

export async function createSourceDomain(
  payload: {
    collectionIntervalMinutes?: number;
    collectionUrl?: string | null;
    credibility?: number;
    domain: string;
    isActive?: boolean;
    name: string;
    note?: string;
    sourceType?: string;
    status?: string;
  },
  token?: string | null,
) {
  if (!isApiConfigured()) throw createApiNotConfiguredError();

  return apiFetch<SourceDomain>("/v1/admin/sources", {
    body: payload,
    method: "POST",
    token,
  });
}

export async function updateSourceDomainConfig(
  domainId: string,
  payload: {
    collectionIntervalMinutes?: number | null;
    collectionUrl?: string | null;
    credibility?: number | null;
    domain?: string | null;
    isActive?: boolean | null;
    name?: string | null;
    note?: string | null;
    sourceType?: string | null;
    status?: string | null;
  },
  token?: string | null,
) {
  if (!isApiConfigured()) throw createApiNotConfiguredError();

  return apiFetch<MutationResponse>(`/v1/admin/sources/${domainId}`, {
    body: payload,
    method: "PATCH",
    token,
  });
}

export async function updateSourceDomainPolicy(
  domainId: string,
  payload: {
    collectionIntervalMinutes?: number | null;
    credibility?: number | null;
    status?: string | null;
  },
  token?: string | null,
) {
  if (!isApiConfigured()) throw createApiNotConfiguredError();

  return apiFetch<MutationResponse>(`/v1/admin/sources/${domainId}/credibility`, {
    body: payload,
    method: "PATCH",
    token,
  });
}

export async function getAdminAgents(
  token?: string | null,
): Promise<AdminAgentsResponse> {
  if (!isApiConfigured()) {
    return {
      agentRuns: [],
      recentEvents: [],
    };
  }

  return apiFetch<AdminAgentsResponse>("/v1/admin/agents", {
    cache: "no-store",
    token,
  });
}

export async function triggerAdminAgent(agent: string, token?: string | null) {
  if (!isApiConfigured()) throw createApiNotConfiguredError();

  return apiFetch<MutationResponse>("/v1/admin/agents/run", {
    body: { agent },
    method: "POST",
    token,
  });
}
