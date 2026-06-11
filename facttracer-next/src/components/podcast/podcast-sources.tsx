"use client";

import { ExternalLink, ShieldCheck } from "lucide-react";
import { useAuth } from "@/components/auth/auth-provider";
import { recordAnalyticsEvent } from "@/lib/api/facttracer";
import type { PodcastEpisodeDetail } from "@/lib/api/types";
import { formatCredibility, formatSourceType } from "@/lib/display";

export function PodcastSources({ episode }: { episode: PodcastEpisodeDetail }) {
  const { token } = useAuth();

  if (episode.sources.length === 0) {
    return (
      <p className="border-y border-gray-200 py-5 text-sm leading-7 text-gray-500">
        연결된 출처가 없습니다.
      </p>
    );
  }

  return (
    <div className="divide-y divide-gray-200 border-y border-gray-200">
      {episode.sources.map((source) => (
        <a
          href={source.url}
          key={source.id}
          target="_blank"
          rel="noreferrer"
          onClick={() => {
            void recordAnalyticsEvent(
              {
                eventType: "podcast_source_click",
                issueId: episode.issueId ?? null,
                metadata: {
                  episodeId: episode.id,
                  podcastCategory: episode.category,
                  podcastFormat: episode.format,
                  sourceId: source.id,
                  sourceType: source.sourceType,
                },
              },
              token,
            );
          }}
          className="grid gap-3 py-4 hover:bg-blue-50/40 sm:grid-cols-[minmax(0,1fr)_180px]"
        >
          <span className="min-w-0">
            <span className="flex items-start gap-2">
              <ShieldCheck
                className="mt-1 size-4 text-emerald-600"
                aria-hidden="true"
              />
              <span className="min-w-0">
                <span className="block font-extrabold leading-6 text-gray-950">
                  {source.title}
                </span>
                <span className="mt-1 block text-sm font-semibold text-gray-500">
                  {source.publisher} · {formatSourceType(source.sourceType)}
                </span>
              </span>
            </span>
          </span>
          <span className="flex items-center justify-between gap-3 text-xs font-bold text-gray-500 sm:justify-end">
            {formatCredibility(source.credibility)}
            <ExternalLink className="size-4" aria-hidden="true" />
          </span>
        </a>
      ))}
    </div>
  );
}
