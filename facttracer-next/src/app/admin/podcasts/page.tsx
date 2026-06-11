import Link from "next/link";
import { AlertTriangle, Headphones, ShieldCheck } from "lucide-react";
import {
  AdminPodcastGenerateForm,
  AdminPodcastRenderButton,
  AdminPodcastStatusButtons,
} from "@/components/admin/admin-podcast-actions";
import {
  formatPodcastDate,
  formatPodcastDuration,
  formatPodcastFormat,
  formatPodcastVariant,
  podcastStatusLabel,
} from "@/components/podcast/podcast-display";
import {
  getAdminPodcastFeed,
  getAdminPodcastJobs,
  getPodcastFeed,
} from "@/lib/api/podcasts";
import { getServerAccessToken } from "@/lib/auth/server-session";

export default async function AdminPodcastsPage() {
  const accessToken = await getServerAccessToken();
  const [feed, heldFeed] = await Promise.all([
    getAdminPodcastFeed({
      limit: 30,
      status: "all",
      token: accessToken,
    }).catch(() =>
      getPodcastFeed({
        feed: "latest",
        limit: 30,
        token: accessToken,
      }),
    ),
    getAdminPodcastFeed({
      limit: 12,
      status: "draft",
      token: accessToken,
    }).catch(() => ({ episodes: [] })),
  ]);
  const jobs = await getAdminPodcastJobs(accessToken).catch(() => ({ jobs: [] }));
  const failedPodcastJobs = jobs.jobs
    .filter(
      (job) =>
        ["generate_podcasts", "render_podcast_audio"].includes(job.jobType) &&
        ["dead_letter", "failed"].includes(job.status),
    )
    .slice(0, 6);

  return (
    <div className="space-y-8">
      <section className="py-6">
        <p className="text-sm font-bold uppercase tracking-[0.16em] text-blue-600">
          팟캐스트 운영
        </p>
        <h1 className="mt-2 max-w-4xl text-3xl font-bold leading-tight text-gray-900 sm:text-4xl">
          자동 생성 회차를 확인하고 음성 렌더링을 관리합니다
        </h1>
        <p className="mt-4 max-w-3xl text-base leading-8 text-gray-600">
          큰 사건, 데일리 브리핑, 카테고리별 회차를 생성하고 TTS 상태를
          확인합니다.
        </p>
      </section>

      <section>
        <div className="flex items-center gap-2">
          <Headphones className="size-5 text-blue-600" aria-hidden="true" />
          <h2 className="text-2xl font-bold text-gray-900">회차 생성</h2>
        </div>
        <AdminPodcastGenerateForm />
      </section>

      {failedPodcastJobs.length > 0 ? (
        <section>
          <h2 className="text-2xl font-bold text-gray-900">실패한 작업</h2>
          <div className="mt-4 divide-y divide-red-100 border-y border-red-200 bg-red-50/40">
            {failedPodcastJobs.map((job) => (
              <div
                key={job.id}
                className="grid gap-3 px-4 py-4 text-sm lg:grid-cols-[180px_minmax(0,1fr)_120px]"
              >
                <div className="font-bold text-red-700">
                  {job.jobType}
                  <p className="mt-1 text-xs text-red-500">{job.targetId}</p>
                </div>
                <p className="min-w-0 leading-6 text-red-700">
                  {job.userMessage ||
                    job.user_message ||
                    job.lastError ||
                    "실패 이유가 기록되지 않았습니다."}
                </p>
                <p className="text-xs font-bold text-red-500">
                  {job.attempts}/{job.maxAttempts}회
                </p>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      {heldFeed.episodes.length > 0 ? (
        <section>
          <div className="flex items-center gap-2">
            <AlertTriangle className="size-5 text-amber-600" aria-hidden="true" />
            <h2 className="text-2xl font-bold text-gray-900">발행 보류 회차</h2>
          </div>
          <p className="mt-2 text-sm leading-6 text-gray-500">
            출처 부족, 공식 출처 미확인, 표현 검수 경고로 자동발행이 보류된
            회차입니다.
          </p>
          <div className="mt-4 divide-y divide-amber-100 border-y border-amber-200 bg-amber-50/35">
            {heldFeed.episodes.map((episode) => (
              <article
                key={episode.id}
                className="grid gap-4 px-4 py-4 lg:grid-cols-[minmax(0,1fr)_220px_180px]"
              >
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2 text-xs font-bold text-amber-700">
                    <span>{episode.category}</span>
                    <span aria-hidden="true">·</span>
                    <span>{formatPodcastFormat(episode.format)}</span>
                    <span aria-hidden="true">·</span>
                    <span>품질 {episode.publicationGateQualityScore ?? "-"}</span>
                  </div>
                  <Link href={`/admin/podcasts/${episode.id}`}>
                    <h3 className="mt-2 text-lg font-extrabold leading-6 text-gray-950 hover:text-blue-700">
                      {episode.title}
                    </h3>
                  </Link>
                  <p className="mt-2 text-sm leading-6 text-amber-800">
                    누락 신호:{" "}
                    {episode.publicationGateMissingSignals.join(", ") || "없음"}
                  </p>
                  {episode.publicationGateWarnings.length > 0 ? (
                    <p className="mt-1 text-sm leading-6 text-amber-800">
                      경고: {episode.publicationGateWarnings.join(", ")}
                    </p>
                  ) : null}
                </div>
                <div className="text-sm font-semibold text-gray-600">
                  <p className="font-bold text-gray-900">보완 대상</p>
                  <p className="mt-1 leading-6">
                    {episode.issueTitle ?? episode.issueId ?? "데일리 회차"}
                  </p>
                </div>
                <div className="flex flex-col items-start gap-2">
                  <Link
                    href={`/admin/podcasts/${episode.id}`}
                    className="inline-flex h-9 items-center rounded-md border border-amber-300 px-3 text-sm font-bold text-amber-800 hover:bg-amber-100"
                  >
                    회차 검수
                  </Link>
                  {episode.issueId ? (
                    <Link
                      href={`/admin/issues/${episode.issueId}`}
                      className="inline-flex h-9 items-center rounded-md border border-gray-300 px-3 text-sm font-bold text-gray-700 hover:bg-gray-50"
                    >
                      이슈 보완
                    </Link>
                  ) : null}
                </div>
              </article>
            ))}
          </div>
        </section>
      ) : null}

      <section>
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-gray-200 pb-4">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">최근 회차</h2>
            <p className="mt-1 text-sm text-gray-500">
              공개 피드 기준으로 최근 팟캐스트를 확인합니다.
            </p>
          </div>
          <Link
            href="/podcasts"
            className="inline-flex h-10 items-center rounded-md border border-gray-300 px-4 text-sm font-bold text-gray-700 hover:bg-gray-50"
          >
            공개 화면 보기
          </Link>
        </div>

        <div className="divide-y divide-gray-200 border-b border-gray-200">
          {feed.episodes.length > 0 ? (
            feed.episodes.map((episode) => (
              <article
                key={episode.id}
                className="grid gap-4 py-5 lg:grid-cols-[minmax(0,1fr)_160px_150px]"
              >
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2 text-xs font-bold text-gray-500">
                    <span>{episode.category}</span>
                    <span aria-hidden="true">·</span>
                    <span>{formatPodcastFormat(episode.format)}</span>
                    <span aria-hidden="true">·</span>
                    <span>{formatPodcastVariant(episode.variant)}</span>
                    <span aria-hidden="true">·</span>
                    <span>{formatPodcastDate(episode.publishedAt)}</span>
                  </div>
                  <Link href={`/admin/podcasts/${episode.id}`}>
                    <h3 className="mt-2 text-lg font-extrabold leading-6 text-gray-950 hover:text-blue-700">
                      {episode.title}
                    </h3>
                  </Link>
                  <p className="mt-2 line-clamp-2 text-sm leading-6 text-gray-500">
                    {episode.subtitle}
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2 text-xs font-bold text-gray-600">
                    <span className="inline-flex items-center gap-1 rounded-md border border-gray-200 px-2 py-1">
                      <ShieldCheck className="size-4 text-emerald-600" aria-hidden="true" />
                      출처 {episode.sourceCount}개
                    </span>
                    <span className="rounded-md border border-gray-200 px-2 py-1">
                      {formatPodcastDuration(episode.durationSeconds)}
                    </span>
                    <span className="rounded-md border border-gray-200 px-2 py-1">
                      {podcastStatusLabel(episode.status)}
                    </span>
                  </div>
                </div>
                <div className="text-sm font-semibold text-gray-500">
                  <p className="font-bold text-gray-900">연결 이슈</p>
                  <p className="mt-1 leading-6">
                    {episode.issueTitle ?? episode.issueId ?? "이슈 없음"}
                  </p>
                </div>
                <div className="flex flex-col items-start gap-3">
                  <AdminPodcastRenderButton episodeId={episode.id} />
                  <AdminPodcastStatusButtons
                    currentStatus={episode.status}
                    episodeId={episode.id}
                  />
                </div>
              </article>
            ))
          ) : (
            <p className="py-8 text-sm leading-7 text-gray-500">
              아직 생성된 팟캐스트 회차가 없습니다.
            </p>
          )}
        </div>
      </section>
    </div>
  );
}
