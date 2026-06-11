"use client";

import { ChevronUp, Loader2, Pause, Play, SkipForward, X } from "lucide-react";
import {
  formatPodcastTime,
  ttsStatusLabel,
} from "@/components/podcast/podcast-display";
import { usePodcastPlayer } from "@/components/podcast/podcast-player-provider";

export function PodcastMiniPlayer() {
  const {
    canPlayAudio,
    close,
    currentTime,
    duration,
    errorMessage,
    expand,
    goNext,
    isBuffering,
    isLoadingDetail,
    isPlaying,
    selectedEpisode,
    togglePlayback,
  } = usePodcastPlayer();

  if (!selectedEpisode) return null;

  const progress = duration ? Math.min(100, (currentTime / duration) * 100) : 0;

  return (
    <div className="fixed inset-x-0 bottom-[72px] z-50 border-t border-gray-200 bg-white/95 shadow-[0_-16px_38px_rgba(15,23,42,0.12)] backdrop-blur sm:bottom-0">
      <div className="h-1 bg-gray-200">
        <div className="h-full bg-blue-600" style={{ width: `${progress}%` }} />
      </div>
      <div className="mx-auto flex min-h-[72px] max-w-[1520px] items-center gap-3 px-3 py-2 sm:px-6 lg:px-9">
        <button
          type="button"
          onClick={() => void togglePlayback()}
          className="grid size-11 shrink-0 place-items-center rounded-full bg-gray-950 text-white disabled:opacity-40"
          disabled={isLoadingDetail}
          aria-label={isPlaying ? "팟캐스트 일시정지" : "팟캐스트 재생"}
        >
          {isLoadingDetail || isBuffering ? (
            <Loader2 className="size-5 animate-spin" aria-hidden="true" />
          ) : isPlaying ? (
            <Pause className="size-5" aria-hidden="true" />
          ) : (
            <Play className="ml-0.5 size-5" aria-hidden="true" />
          )}
        </button>

        <button
          type="button"
          onClick={expand}
          className="min-w-0 flex-1 text-left"
        >
          <p className="truncate text-sm font-extrabold text-gray-950">
            {selectedEpisode.title}
          </p>
          <p className="mt-0.5 truncate text-xs font-semibold text-gray-500">
            {selectedEpisode.hosts.length > 0
              ? selectedEpisode.hosts.map((host) => host.name).join(" · ")
              : selectedEpisode.category}{" "}
            · {canPlayAudio ? `${formatPodcastTime(currentTime)} / ${formatPodcastTime(duration)}` : ttsStatusLabel(selectedEpisode.ttsStatus)}
          </p>
          {errorMessage ? (
            <p className="mt-0.5 truncate text-xs font-bold text-red-600">
              {errorMessage}
            </p>
          ) : null}
        </button>

        <div className="flex shrink-0 items-center gap-1">
          <button
            type="button"
            onClick={() => void goNext()}
            className="hidden size-10 place-items-center rounded-md border border-gray-200 text-gray-700 hover:bg-gray-50 sm:grid"
            aria-label="다음 팟캐스트"
          >
            <SkipForward className="size-5" aria-hidden="true" />
          </button>
          <button
            type="button"
            onClick={expand}
            className="grid size-10 place-items-center rounded-md border border-gray-200 text-gray-700 hover:bg-gray-50"
            aria-label="팟캐스트 플레이어 열기"
          >
            <ChevronUp className="size-5" aria-hidden="true" />
          </button>
          <button
            type="button"
            onClick={close}
            className="grid size-10 place-items-center rounded-md border border-gray-200 text-gray-700 hover:bg-gray-50"
            aria-label="팟캐스트 닫기"
          >
            <X className="size-5" aria-hidden="true" />
          </button>
        </div>
      </div>
    </div>
  );
}
