"use client";

import { Play } from "lucide-react";
import {
  formatPodcastDuration,
  formatPodcastFormat,
} from "@/components/podcast/podcast-display";
import { usePodcastPlayer } from "@/components/podcast/podcast-player-provider";
import type { PodcastEpisodeSummary } from "@/lib/api/types";

export function PodcastQueue({ queue }: { queue: PodcastEpisodeSummary[] }) {
  const { playEpisode } = usePodcastPlayer();

  if (queue.length === 0) {
    return (
      <p className="border-y border-gray-200 py-5 text-sm leading-7 text-gray-500">
        다음 재생 후보가 없습니다.
      </p>
    );
  }

  return (
    <div className="divide-y divide-gray-200 border-y border-gray-200">
      {queue.map((episode, index) => (
        <button
          type="button"
          key={episode.id}
          onClick={() => void playEpisode(episode, queue.slice(index + 1))}
          className="grid w-full grid-cols-[40px_minmax(0,1fr)_auto] items-center gap-3 py-4 text-left hover:bg-blue-50/40"
        >
          <span className="grid size-9 place-items-center rounded-full border border-gray-200 text-gray-500">
            <Play className="ml-0.5 size-4" aria-hidden="true" />
          </span>
          <span className="min-w-0">
            <span className="block truncate text-sm font-extrabold text-gray-950">
              {episode.title}
            </span>
            <span className="mt-1 block truncate text-xs font-semibold text-gray-500">
              {episode.category} · {formatPodcastFormat(episode.format)}
            </span>
          </span>
          <span className="text-xs font-bold text-gray-500">
            {formatPodcastDuration(episode.durationSeconds)}
          </span>
        </button>
      ))}
    </div>
  );
}
