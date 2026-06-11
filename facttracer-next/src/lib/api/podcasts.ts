import {
  createApiNotConfiguredError,
  isApiConfigured,
  buildApiUrl,
} from "@/lib/api/config";
import { apiFetch } from "@/lib/api/http";
import type {
  PodcastDetailResponse,
  PodcastEpisodeDetail,
  PodcastEpisodeSummary,
  PodcastFeedResponse,
  PodcastGenerateResponse,
  PodcastHomeResponse,
  MutationResponse,
  AdminJobsResponse,
} from "@/lib/api/types";

export const emptyPodcastHome: PodcastHomeResponse = {
  nowPlaying: null,
  sections: [],
};

export async function getPodcastHome(
  token?: string | null,
): Promise<PodcastHomeResponse> {
  if (!isApiConfigured()) return emptyPodcastHome;

  return apiFetch<PodcastHomeResponse>("/v1/podcasts/home", {
    cache: "no-store",
    token,
  });
}

export async function getPodcastFeed({
  feed = "recommended",
  limit = 20,
  token,
  topic,
}: {
  feed?: string;
  limit?: number;
  token?: string | null;
  topic?: string | null;
} = {}): Promise<PodcastFeedResponse> {
  if (!isApiConfigured()) return { episodes: [] };

  return apiFetch<PodcastFeedResponse>("/v1/podcasts", {
    cache: "no-store",
    searchParams: { feed, limit, topic },
    token,
  });
}

export async function getAdminPodcastFeed({
  limit = 50,
  status = "all",
  token,
}: {
  limit?: number;
  status?: "all" | "archived" | "draft" | "published" | string;
  token?: string | null;
} = {}): Promise<PodcastFeedResponse> {
  if (!isApiConfigured()) return { episodes: [] };

  return apiFetch<PodcastFeedResponse>("/v1/admin/podcasts", {
    cache: "no-store",
    searchParams: { limit, status },
    token,
  });
}

export async function getAdminPodcastJobs(
  token?: string | null,
): Promise<AdminJobsResponse> {
  if (!isApiConfigured()) return { jobs: [] };

  return apiFetch<AdminJobsResponse>("/v1/admin/jobs", {
    cache: "no-store",
    token,
  });
}

export async function getAdminPodcastDetail(
  episodeId: string,
  token?: string | null,
): Promise<PodcastDetailResponse> {
  if (!isApiConfigured()) throw createApiNotConfiguredError();

  return apiFetch<PodcastDetailResponse>(`/v1/admin/podcasts/${episodeId}`, {
    cache: "no-store",
    token,
  });
}

export async function updateAdminPodcastStatus(
  episodeId: string,
  status: "archived" | "draft" | "published",
  token?: string | null,
) {
  if (!isApiConfigured()) throw createApiNotConfiguredError();

  return apiFetch<MutationResponse>(
    `/v1/admin/podcasts/${episodeId}/status`,
    {
      body: { status },
      method: "PATCH",
      token,
    },
  );
}

export async function getPodcastDetail(
  episodeId: string,
  token?: string | null,
): Promise<PodcastDetailResponse> {
  if (!isApiConfigured()) throw createApiNotConfiguredError();

  return apiFetch<PodcastDetailResponse>(`/v1/podcasts/${episodeId}`, {
    cache: "no-store",
    token,
  });
}

export async function renderPodcastAudio(
  episodeId: string,
  {
    force = false,
    token,
  }: {
    force?: boolean;
    token?: string | null;
  } = {},
): Promise<PodcastDetailResponse> {
  if (!isApiConfigured()) throw createApiNotConfiguredError();

  return apiFetch<PodcastDetailResponse>(
    `/v1/podcasts/${episodeId}/render-audio`,
    {
      method: "POST",
      searchParams: { force },
      token,
    },
  );
}

export async function generatePodcasts({
  feed = "recommended",
  force = false,
  format,
  issueId,
  limit = 6,
  renderAudio = true,
  token,
  topic,
  variant,
}: {
  feed?: string;
  force?: boolean;
  format?: string | null;
  issueId?: string | null;
  limit?: number;
  renderAudio?: boolean;
  token?: string | null;
  topic?: string | null;
  variant?: "deep" | "short" | "standard" | string | null;
} = {}): Promise<PodcastGenerateResponse> {
  if (!isApiConfigured()) throw createApiNotConfiguredError();

  return apiFetch<PodcastGenerateResponse>("/v1/podcasts/generate", {
    method: "POST",
    searchParams: { feed, force, format, issueId, limit, renderAudio, topic, variant },
    token,
  });
}

export function buildPodcastAudioUrl(audioUrl?: string | null) {
  if (!audioUrl) return null;
  if (/^https?:\/\//i.test(audioUrl)) return audioUrl;
  if (!isApiConfigured()) return null;
  return buildApiUrl(audioUrl);
}

export function buildPlayableEpisodeFromSummary(
  episode: PodcastEpisodeSummary,
): PodcastEpisodeDetail {
  return {
    ...episode,
    audioUrl: null,
    autoPublished: false,
    correctionPolicy: {},
    hosts: [],
    notationReview: {},
    playback: {},
    publicationGate: {},
    script: [],
    sources: [],
    summary: episode.subtitle,
    ttsStatus: "loading",
  };
}
