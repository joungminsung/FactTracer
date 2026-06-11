"use client";

import {
  MessageCircle,
  Play,
  Radio,
  ShieldCheck,
  UsersRound,
} from "lucide-react";
import {
  formatPodcastDate,
  formatPodcastDuration,
  formatPodcastFormat,
  hostLine,
} from "@/components/podcast/podcast-display";
import { usePodcastPlayer } from "@/components/podcast/podcast-player-provider";
import type { PodcastEpisodeSummary } from "@/lib/api/types";

function FormatIcon({ format }: { format: string }) {
  if (format === "solo") {
    return <Radio className="size-4 text-blue-600" aria-hidden="true" />;
  }
  if (format === "panel_2" || format === "panel_3") {
    return <UsersRound className="size-4 text-blue-600" aria-hidden="true" />;
  }
  return <MessageCircle className="size-4 text-blue-600" aria-hidden="true" />;
}

export function PodcastEpisodeCard({
  episode,
  queue,
  size = "default",
}: {
  episode: PodcastEpisodeSummary;
  queue: PodcastEpisodeSummary[];
  size?: "default" | "large" | "compact";
}) {
  const { playEpisode, selectedEpisode, isPlaying } = usePodcastPlayer();
  const isSelected = selectedEpisode?.id === episode.id;
  const isLarge = size === "large";
  const isCompact = size === "compact";

  return (
    <button
      type="button"
      onClick={() => void playEpisode(episode, queue)}
      className={`group grid w-full min-w-0 gap-3 border-y border-gray-200 py-4 text-left transition-colors hover:border-blue-200 hover:bg-blue-50/35 focus-visible:bg-blue-50 ${
        isLarge ? "lg:grid-cols-[180px_minmax(0,1fr)] lg:gap-5" : ""
      } ${isSelected ? "border-blue-300 bg-blue-50/50" : ""}`}
    >
      <div
        className={`relative grid place-items-center overflow-hidden rounded-md border border-gray-200 bg-gray-100 ${
          isCompact
            ? "aspect-[1.35/1] min-h-24"
            : isLarge
              ? "aspect-[1.18/1] min-h-36"
              : "aspect-[1.25/1] min-h-32"
        }`}
      >
        {episode.thumbnailUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={episode.thumbnailUrl}
            alt=""
            className="h-full w-full object-cover"
          />
        ) : (
          <div className="flex h-full w-full flex-col justify-between bg-[linear-gradient(135deg,#f8fafc_0%,#e8f0ff_42%,#ffffff_100%)] p-4">
            <span className="inline-flex w-fit items-center gap-2 rounded-md border border-blue-100 bg-white px-2.5 py-1 text-xs font-bold text-blue-700">
              <FormatIcon format={episode.format} />
              {formatPodcastFormat(episode.format)}
            </span>
            <div>
              <p className="text-xs font-bold text-gray-500">FactTracer Audio</p>
              <p className="mt-1 line-clamp-2 text-lg font-extrabold leading-6 text-gray-950">
                {episode.category}
              </p>
            </div>
          </div>
        )}
        <span className="absolute bottom-3 right-3 grid size-10 place-items-center rounded-full bg-gray-950 text-white shadow-sm transition-transform group-hover:scale-105">
          <Play
            className={`ml-0.5 size-5 ${isSelected && isPlaying ? "fill-white" : ""}`}
            aria-hidden="true"
          />
        </span>
      </div>

      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2 text-xs font-bold text-gray-500">
          <span>{episode.category}</span>
          <span aria-hidden="true">·</span>
          <span>{formatPodcastDate(episode.publishedAt)}</span>
          <span aria-hidden="true">·</span>
          <span>{formatPodcastDuration(episode.durationSeconds)}</span>
        </div>
        <h3
          className={`mt-2 line-clamp-2 font-extrabold leading-tight tracking-[-0.01em] text-gray-950 group-hover:text-blue-700 ${
            isLarge ? "text-2xl sm:text-[28px]" : "text-[17px]"
          }`}
        >
          {episode.title}
        </h3>
        <p
          className={`mt-2 line-clamp-2 leading-6 text-gray-600 ${
            isLarge ? "text-[15px]" : "text-sm"
          }`}
        >
          {episode.subtitle}
        </p>
        <div className="mt-4 flex flex-wrap items-center gap-2 text-xs font-bold text-gray-600">
          <span className="inline-flex items-center gap-1 rounded-md border border-gray-200 px-2 py-1">
            <FormatIcon format={episode.format} />
            {hostLine(episode)}
          </span>
          <span className="inline-flex items-center gap-1 rounded-md border border-gray-200 px-2 py-1">
            <ShieldCheck className="size-4 text-emerald-600" aria-hidden="true" />
            자동 생성 · 출처 기반
          </span>
        </div>
        {episode.rankReason ? (
          <p className="mt-3 line-clamp-2 text-xs font-semibold leading-5 text-blue-700">
            추천 이유: {episode.rankReason}
          </p>
        ) : null}
      </div>
    </button>
  );
}
