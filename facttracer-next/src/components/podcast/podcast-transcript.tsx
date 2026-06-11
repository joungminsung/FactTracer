"use client";

import { formatPodcastTime } from "@/components/podcast/podcast-display";
import type { PodcastEpisodeDetail } from "@/lib/api/types";

export function PodcastTranscript({
  currentTime,
  episode,
}: {
  currentTime: number;
  episode: PodcastEpisodeDetail;
}) {
  if (episode.script.length === 0) {
    return (
      <p className="border-y border-gray-200 py-5 text-sm leading-7 text-gray-500">
        표시할 대사가 아직 없습니다.
      </p>
    );
  }

  return (
    <div className="divide-y divide-gray-200 border-y border-gray-200">
      {episode.script.map((segment, index) => {
        const nextSegment = episode.script[index + 1];
        const isActive =
          currentTime >= segment.startsAt &&
          (!nextSegment || currentTime < nextSegment.startsAt);

        return (
          <div
            key={`${segment.speakerId}-${segment.startsAt}-${index}`}
            className={`grid gap-3 py-4 sm:grid-cols-[128px_minmax(0,1fr)] ${
              isActive ? "bg-blue-50/55 px-3 sm:-mx-3" : ""
            }`}
          >
            <div>
              <p className="text-sm font-extrabold text-gray-950">
                {segment.speakerName}
              </p>
              <p className="mt-1 text-xs font-semibold text-gray-500">
                {segment.role} · {formatPodcastTime(segment.startsAt)}
              </p>
            </div>
            <p className="text-[15px] leading-7 text-gray-700">
              {segment.text}
            </p>
          </div>
        );
      })}
    </div>
  );
}
