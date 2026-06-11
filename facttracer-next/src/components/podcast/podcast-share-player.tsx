"use client";

import { Play } from "lucide-react";
import { usePodcastPlayer } from "@/components/podcast/podcast-player-provider";
import type {
  PodcastEpisodeDetail,
  PodcastEpisodeSummary,
} from "@/lib/api/types";

export function PodcastSharePlayer({
  episode,
  queue,
}: {
  episode: PodcastEpisodeDetail;
  queue: PodcastEpisodeSummary[];
}) {
  const { playEpisode } = usePodcastPlayer();

  return (
    <button
      type="button"
      onClick={() => void playEpisode(episode, queue)}
      className="inline-flex h-11 items-center gap-2 rounded-md bg-gray-950 px-4 text-sm font-bold text-white"
    >
      <Play className="size-5" aria-hidden="true" />
      재생
    </button>
  );
}
