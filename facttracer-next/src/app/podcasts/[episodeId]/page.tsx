import Link from "next/link";
import { notFound } from "next/navigation";
import { SiteHeader } from "@/components/site-header";
import {
  formatPodcastDuration,
  formatPodcastFormat,
} from "@/components/podcast/podcast-display";
import { PodcastQueue } from "@/components/podcast/podcast-queue";
import { PodcastSharePlayer } from "@/components/podcast/podcast-share-player";
import { PodcastSources } from "@/components/podcast/podcast-sources";
import { PodcastTranscript } from "@/components/podcast/podcast-transcript";
import { getPodcastDetail } from "@/lib/api/podcasts";
import { getServerAccessToken } from "@/lib/auth/server-session";

export default async function PodcastSharePage({
  params,
}: {
  params: Promise<{ episodeId: string }>;
}) {
  const { episodeId } = await params;
  const accessToken = await getServerAccessToken();
  const detail = await getPodcastDetail(episodeId, accessToken).catch(() => null);

  if (!detail) notFound();

  const episode = detail.episode;

  return (
    <div className="min-h-screen bg-white pb-24 text-gray-950">
      <SiteHeader />
      <main className="mx-auto max-w-[1520px] px-5 pb-14 pt-6 sm:px-7 lg:px-9">
        <section className="grid gap-8 border-b border-gray-200 pb-8 lg:grid-cols-[minmax(0,1fr)_380px]">
          <div className="min-w-0">
            <Link
              href="/podcasts"
              className="text-sm font-bold text-blue-700 hover:underline"
            >
              팟캐스트
            </Link>
            <p className="mt-4 text-sm font-extrabold text-gray-500">
              {episode.category} · {formatPodcastFormat(episode.format)} ·{" "}
              {formatPodcastDuration(episode.durationSeconds)}
            </p>
            <h1 className="mt-3 max-w-4xl text-[32px] font-extrabold leading-tight tracking-[-0.02em] text-gray-950 sm:text-[44px]">
              {episode.title}
            </h1>
            <p className="mt-4 max-w-3xl text-[15px] leading-7 text-gray-600">
              {episode.summary || episode.subtitle}
            </p>
            <div className="mt-6">
              <PodcastSharePlayer episode={episode} queue={detail.nextQueue} />
            </div>
          </div>

          <aside className="min-w-0 border-y border-gray-200 py-4 lg:border-l lg:border-y-0 lg:pl-6">
            <h2 className="text-xl font-extrabold text-gray-950">진행</h2>
            <div className="mt-4 grid gap-3">
              {episode.hosts.map((host) => (
                <div key={host.id} className="flex items-center gap-3">
                  <span className="grid size-9 place-items-center rounded-full bg-blue-50 text-sm font-extrabold text-blue-700">
                    {host.name.slice(0, 1)}
                  </span>
                  <span>
                    <span className="block text-sm font-extrabold text-gray-950">
                      {host.name}
                    </span>
                    <span className="text-xs font-semibold text-gray-500">
                      {host.role} · {host.tone}
                    </span>
                  </span>
                </div>
              ))}
            </div>
          </aside>
        </section>

        <section className="grid gap-8 py-8 lg:grid-cols-[minmax(0,1fr)_380px]">
          <article className="min-w-0">
            <h2 className="text-2xl font-extrabold text-gray-950">대사</h2>
            <div className="mt-4">
              <PodcastTranscript currentTime={0} episode={episode} />
            </div>
          </article>
          <aside className="min-w-0">
            <h2 className="text-2xl font-extrabold text-gray-950">출처</h2>
            <div className="mt-4">
              <PodcastSources episode={episode} />
            </div>
            <h2 className="mt-8 text-2xl font-extrabold text-gray-950">
              다음 재생
            </h2>
            <div className="mt-4">
              <PodcastQueue queue={detail.nextQueue} />
            </div>
          </aside>
        </section>
      </main>
    </div>
  );
}
