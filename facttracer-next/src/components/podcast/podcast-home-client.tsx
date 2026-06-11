"use client";

import { useEffect, useMemo } from "react";
import { Radio, ShieldCheck } from "lucide-react";
import { useAuth } from "@/components/auth/auth-provider";
import { PodcastEpisodeCard } from "@/components/podcast/podcast-episode-card";
import { PodcastSection } from "@/components/podcast/podcast-section";
import { recordAnalyticsEvent } from "@/lib/api/facttracer";
import type {
  PodcastEpisodeSummary,
  PodcastHomeResponse,
  PodcastSection as PodcastSectionType,
} from "@/lib/api/types";

function flattenEpisodes(sections: PodcastSectionType[]) {
  const seen = new Set<string>();
  const episodes: PodcastEpisodeSummary[] = [];
  sections.forEach((section) => {
    section.episodes.forEach((episode) => {
      if (seen.has(episode.id)) return;
      seen.add(episode.id);
      episodes.push(episode);
    });
  });
  return episodes;
}

export function PodcastHomeClient({ home }: { home: PodcastHomeResponse }) {
  return <PodcastHomeContent home={home} />;
}

function PodcastHomeContent({ home }: { home: PodcastHomeResponse }) {
  const { token, user } = useAuth();
  const nonEmptySections = useMemo(
    () => home.sections.filter((section) => section.episodes.length > 0),
    [home.sections],
  );
  const allEpisodes = useMemo(() => flattenEpisodes(home.sections), [home.sections]);
  const leadEpisode = home.nowPlaying ?? allEpisodes[0] ?? null;
  const leadQueue = allEpisodes.filter((episode) => episode.id !== leadEpisode?.id);
  const firstSection = nonEmptySections[0];
  const remainingSections = nonEmptySections.filter(
    (section) => section.id !== firstSection?.id,
  );

  useEffect(() => {
    if (allEpisodes.length === 0) return;
    void recordAnalyticsEvent(
      {
        eventType: "podcast_home_impression",
        metadata: {
          episodeIds: allEpisodes.slice(0, 20).map((episode) => episode.id),
          sectionIds: nonEmptySections.map((section) => section.id),
        },
      },
      token,
    );
  }, [allEpisodes, nonEmptySections, token]);

  if (!leadEpisode) {
    return (
      <div className="border-y border-gray-200 py-16">
        <div className="mx-auto max-w-2xl text-center">
          <Radio className="mx-auto size-9 text-blue-600" aria-hidden="true" />
          <h1 className="mt-4 text-2xl font-extrabold tracking-[-0.01em] text-gray-950">
            공개된 팟캐스트가 아직 없습니다
          </h1>
          <p className="mt-3 text-sm leading-7 text-gray-500">
            자동 생성 파이프라인이 회차를 발행하면 이 화면에 개인화 추천,
            특집, 최신 회차가 표시됩니다.
          </p>
        </div>
      </div>
    );
  }

  return (
    <>
      <section
        aria-labelledby="podcast-top-pick"
        className="grid gap-7 border-b border-gray-200 pb-8 lg:grid-cols-[minmax(0,1fr)_360px]"
      >
        <div className="min-w-0 lg:border-r lg:border-gray-200 lg:pr-7">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="text-sm font-extrabold text-blue-700">
                {user?.name ? `${user.name}님을 위한 오디오 브리핑` : "오늘의 오디오 브리핑"}
              </p>
              <h1
                id="podcast-top-pick"
                className="mt-2 max-w-3xl text-[30px] font-extrabold leading-tight tracking-[-0.02em] text-gray-950 sm:text-[38px]"
              >
                국민의 알 권리를 위해, 사건의 맥락을 듣습니다
              </h1>
            </div>
            <span className="inline-flex h-10 items-center gap-2 rounded-md border border-gray-200 px-3 text-xs font-bold text-gray-700">
              <ShieldCheck className="size-4 text-emerald-600" aria-hidden="true" />
              출처 기반 자동 생성
            </span>
          </div>

          <div className="mt-6">
            <PodcastEpisodeCard
              episode={leadEpisode}
              queue={leadQueue}
              size="large"
            />
          </div>
        </div>

        <aside className="min-w-0">
          <h2 className="text-[21px] font-extrabold tracking-[-0.01em] text-gray-950">
            다음 재생 후보
          </h2>
          <div className="mt-3 divide-y divide-gray-200 border-b border-gray-200">
            {leadQueue.slice(0, 4).map((episode) => (
              <PodcastEpisodeCard
                episode={episode}
                key={episode.id}
                queue={leadQueue.filter((item) => item.id !== episode.id)}
                size="compact"
              />
            ))}
          </div>
        </aside>
      </section>

      {firstSection ? <PodcastSection section={firstSection} variant="grid" /> : null}

      {remainingSections.map((section, index) => (
        <PodcastSection
          key={section.id}
          section={section}
          variant={index % 2 === 0 ? "rail" : "grid"}
        />
      ))}
    </>
  );
}
