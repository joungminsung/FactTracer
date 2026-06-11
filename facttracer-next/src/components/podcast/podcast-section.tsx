"use client";

import { ChevronRight } from "lucide-react";
import { PodcastEpisodeCard } from "@/components/podcast/podcast-episode-card";
import type { PodcastEpisodeSummary, PodcastSection as Section } from "@/lib/api/types";

export function PodcastSection({
  section,
  variant = "rail",
}: {
  section: Section;
  variant?: "grid" | "rail";
}) {
  if (section.episodes.length === 0) return null;

  const queueFor = (episode: PodcastEpisodeSummary) =>
    section.episodes.filter((item) => item.id !== episode.id);

  return (
    <section aria-labelledby={`podcast-section-${section.id}`} className="py-8">
      <div className="flex flex-wrap items-end justify-between gap-3 border-b border-gray-200 pb-3">
        <div>
          <h2
            id={`podcast-section-${section.id}`}
            className="text-[22px] font-extrabold tracking-[-0.01em] text-gray-950"
          >
            {section.title}
          </h2>
          <p className="mt-1 max-w-2xl text-sm leading-6 text-gray-500">
            {section.description}
          </p>
        </div>
        <button
          type="button"
          className="inline-flex h-9 items-center gap-1 rounded-md border border-gray-200 px-3 text-xs font-bold text-gray-700 hover:bg-gray-50"
        >
          모두 보기
          <ChevronRight className="size-4" aria-hidden="true" />
        </button>
      </div>

      {variant === "grid" ? (
        <div className="mt-2 grid gap-x-6 sm:grid-cols-2 lg:grid-cols-3">
          {section.episodes.map((episode) => (
            <PodcastEpisodeCard
              episode={episode}
              key={episode.id}
              queue={queueFor(episode)}
            />
          ))}
        </div>
      ) : (
        <div className="-mx-5 mt-3 flex gap-4 overflow-x-auto px-5 pb-2 sm:-mx-7 sm:px-7 lg:-mx-9 lg:px-9">
          {section.episodes.map((episode) => (
            <div
              key={episode.id}
              className="w-[280px] shrink-0 sm:w-[320px] lg:w-[360px]"
            >
              <PodcastEpisodeCard episode={episode} queue={queueFor(episode)} />
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
