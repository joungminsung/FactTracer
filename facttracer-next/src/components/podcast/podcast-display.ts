import type { PodcastEpisodeSummary } from "@/lib/api/types";

export function formatPodcastDuration(seconds?: number | null) {
  if (!seconds || seconds < 1) return "길이 확인 전";
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = Math.floor(seconds % 60);
  if (minutes >= 60) {
    const hours = Math.floor(minutes / 60);
    const restMinutes = minutes % 60;
    return `${hours}시간 ${restMinutes}분`;
  }
  return `${minutes}:${String(remainingSeconds).padStart(2, "0")}`;
}

export function formatPodcastTime(seconds?: number | null) {
  if (!seconds || seconds < 1) return "0:00";
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = Math.floor(seconds % 60);
  return `${minutes}:${String(remainingSeconds).padStart(2, "0")}`;
}

export function formatPodcastDate(value?: string | null) {
  if (!value) return "공개 시점 확인 전";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  const hour = String(date.getHours()).padStart(2, "0");
  const minute = String(date.getMinutes()).padStart(2, "0");
  return `${month}.${day} ${hour}:${minute}`;
}

export function formatPodcastFormat(value?: string | null) {
  switch (value) {
    case "solo":
      return "1인 진행";
    case "panel_2":
      return "2인 대화";
    case "panel_3":
      return "3인 토론";
    default:
      return value || "포맷 확인 전";
  }
}

export function formatPodcastVariant(value?: string | null) {
  switch (value) {
    case "short":
      return "짧은 브리핑";
    case "standard":
      return "표준 회차";
    case "deep":
      return "심층 정리";
    default:
      return value || "길이 유형 확인 전";
  }
}

export function podcastStatusLabel(value?: string | null) {
  switch (value) {
    case "published":
      return "공개";
    case "draft":
      return "초안";
    case "archived":
      return "보관";
    default:
      return value || "상태 확인 전";
  }
}

export function ttsStatusLabel(value?: string | null) {
  switch (value) {
    case "ready":
    case "rendered":
      return "오디오 준비됨";
    case "rendering":
      return "오디오 생성 중";
    case "failed":
      return "오디오 실패";
    case "unconfigured":
      return "TTS 설정 필요";
    case "script_ready":
      return "대본 준비됨";
    case "loading":
      return "불러오는 중";
    default:
      return value || "오디오 확인 전";
  }
}

export function hostLine(episode: PodcastEpisodeSummary) {
  return [
    formatPodcastFormat(episode.format),
    formatPodcastVariant(episode.variant),
    episode.category,
    episode.sourceCount ? `출처 ${episode.sourceCount}개` : null,
  ]
    .filter(Boolean)
    .join(" · ");
}
