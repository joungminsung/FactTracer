import Link from "next/link";
import { notFound } from "next/navigation";
import {
  AdminPodcastRenderButton,
  AdminPodcastStatusButtons,
} from "@/components/admin/admin-podcast-actions";
import {
  formatPodcastDuration,
  formatPodcastFormat,
  formatPodcastVariant,
  ttsStatusLabel,
} from "@/components/podcast/podcast-display";
import { getAdminPodcastDetail, getPodcastDetail } from "@/lib/api/podcasts";
import { getServerAccessToken } from "@/lib/auth/server-session";
import { formatCredibility, formatSourceType } from "@/lib/display";

function asString(value: unknown, fallback = "") {
  return typeof value === "string" && value.trim() ? value : fallback;
}

function asNumber(value: unknown) {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function asStringList(value: unknown) {
  return Array.isArray(value)
    ? value.filter(
        (item): item is string => typeof item === "string" && item.trim().length > 0,
      )
    : [];
}

export default async function AdminPodcastDetailPage({
  params,
}: {
  params: Promise<{ episodeId: string }>;
}) {
  const { episodeId } = await params;
  const accessToken = await getServerAccessToken();
  const detail = await getAdminPodcastDetail(episodeId, accessToken).catch(() =>
    getPodcastDetail(episodeId, accessToken).catch(() => null),
  );

  if (!detail) notFound();

  const episode = detail.episode;

  return (
    <div className="space-y-8">
      <section className="border-b border-gray-200 py-6">
        <Link
          href="/admin/podcasts"
          className="text-sm font-medium text-blue-600 hover:underline"
        >
          팟캐스트 운영
        </Link>
        <div className="mt-4 flex flex-wrap items-start justify-between gap-5">
          <div className="min-w-0">
            <p className="text-sm font-bold text-blue-700">
              {episode.category} · {formatPodcastFormat(episode.format)} ·{" "}
              {formatPodcastVariant(episode.variant)} ·{" "}
              {formatPodcastDuration(episode.durationSeconds)}
            </p>
            <h1 className="mt-2 max-w-4xl text-3xl font-bold leading-tight text-gray-900 sm:text-4xl">
              {episode.title}
            </h1>
            <p className="mt-4 max-w-3xl text-base leading-8 text-gray-600">
              {episode.summary || episode.subtitle}
            </p>
          </div>
          <div className="grid gap-3">
            <AdminPodcastRenderButton episodeId={episode.id} />
            <AdminPodcastStatusButtons
              currentStatus={episode.status}
              episodeId={episode.id}
            />
          </div>
        </div>
      </section>

      <section className="grid gap-4 sm:grid-cols-5">
        {[
          ["상태", episode.status],
          ["TTS", ttsStatusLabel(episode.ttsStatus)],
          ["길이 유형", formatPodcastVariant(episode.variant)],
          ["출처", `${episode.sources.length}개`],
          ["자동발행", episode.autoPublished ? "예" : "아니오"],
        ].map(([label, value]) => (
          <div key={label} className="border-y border-gray-200 py-4">
            <p className="text-xs font-bold text-gray-500">{label}</p>
            <p className="mt-1 text-lg font-extrabold text-gray-950">{value}</p>
          </div>
        ))}
      </section>

      <section className="grid gap-6 lg:grid-cols-3">
        <article className="border-y border-gray-200 py-5">
          <p className="text-xs font-bold uppercase tracking-[0.14em] text-blue-600">
            Publication gate
          </p>
          <h2 className="mt-2 text-xl font-bold text-gray-900">발행 기준</h2>
          <dl className="mt-4 space-y-3 text-sm">
            <div className="flex justify-between gap-4">
              <dt className="font-bold text-gray-500">상태</dt>
              <dd className="font-extrabold text-gray-950">
                {asString(episode.publicationGate.status, "확인 전")}
              </dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="font-bold text-gray-500">품질 점수</dt>
              <dd className="font-extrabold text-gray-950">
                {asNumber(episode.publicationGate.qualityScore) ?? "-"}
              </dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="font-bold text-gray-500">최소 출처</dt>
              <dd className="font-extrabold text-gray-950">
                {asNumber(episode.publicationGate.minSources) ?? "-"}
              </dd>
            </div>
          </dl>
          <p className="mt-4 text-sm leading-6 text-gray-600">
            누락 신호:{" "}
            {asStringList(episode.publicationGate.missingSignals).join(", ") ||
              "없음"}
          </p>
        </article>

        <article className="border-y border-gray-200 py-5">
          <p className="text-xs font-bold uppercase tracking-[0.14em] text-blue-600">
            Notation
          </p>
          <h2 className="mt-2 text-xl font-bold text-gray-900">표기 후보</h2>
          <p className="mt-4 text-sm font-bold text-gray-500">
            {asString(episode.notationReview.status, "후보 없음")}
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            {asStringList(episode.notationReview.terms).length > 0 ? (
              asStringList(episode.notationReview.terms).map((term) => (
                <span
                  key={term}
                  className="rounded-md border border-gray-200 px-2 py-1 text-xs font-bold text-gray-700"
                >
                  {term}
                </span>
              ))
            ) : (
              <p className="text-sm leading-6 text-gray-500">
                검수할 표기 후보가 없습니다.
              </p>
            )}
          </div>
        </article>

        <article className="border-y border-gray-200 py-5">
          <p className="text-xs font-bold uppercase tracking-[0.14em] text-blue-600">
            Correction
          </p>
          <h2 className="mt-2 text-xl font-bold text-gray-900">정정 정책</h2>
          <dl className="mt-4 space-y-3 text-sm">
            <div className="flex justify-between gap-4">
              <dt className="font-bold text-gray-500">처리</dt>
              <dd className="font-extrabold text-gray-950">
                {asString(episode.correctionPolicy.action, "monitor")}
              </dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="font-bold text-gray-500">후속 회차</dt>
              <dd className="font-extrabold text-gray-950">
                {episode.correctionPolicy.requiresUpdateEpisode ? "필요" : "불필요"}
              </dd>
            </div>
          </dl>
          <p className="mt-4 text-sm leading-6 text-gray-600">
            {asString(episode.correctionPolicy.reason, "변경 신호 없음")}
          </p>
        </article>
      </section>

      <section className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_380px]">
        <article className="min-w-0">
          <h2 className="text-2xl font-bold text-gray-900">생성 스크립트</h2>
          <div className="mt-4 divide-y divide-gray-200 border-y border-gray-200">
            {episode.script.length > 0 ? (
              episode.script.map((segment, index) => (
                <div
                  key={`${segment.speakerId}-${segment.startsAt}-${index}`}
                  className="grid gap-3 py-4 sm:grid-cols-[132px_minmax(0,1fr)]"
                >
                  <div>
                    <p className="text-sm font-extrabold text-gray-950">
                      {segment.speakerName}
                    </p>
                    <p className="mt-1 text-xs font-semibold text-gray-500">
                      {segment.role}
                    </p>
                  </div>
                  <p className="text-sm leading-7 text-gray-700">
                    {segment.text}
                  </p>
                </div>
              ))
            ) : (
              <p className="py-5 text-sm leading-7 text-gray-500">
                생성된 스크립트가 없습니다.
              </p>
            )}
          </div>
        </article>

        <aside className="min-w-0">
          <h2 className="text-2xl font-bold text-gray-900">출처 매핑</h2>
          <div className="mt-4 divide-y divide-gray-200 border-y border-gray-200">
            {episode.sources.length > 0 ? (
              episode.sources.map((source) => (
                <a
                  href={source.url}
                  key={source.id}
                  target="_blank"
                  rel="noreferrer"
                  className="block py-4 hover:bg-blue-50/40"
                >
                  <p className="font-extrabold leading-6 text-gray-950">
                    {source.title}
                  </p>
                  <p className="mt-1 text-sm font-semibold text-gray-500">
                    {source.publisher} · {formatSourceType(source.sourceType)}
                  </p>
                  <p className="mt-2 text-xs font-bold text-gray-500">
                    {formatCredibility(source.credibility)}
                  </p>
                </a>
              ))
            ) : (
              <p className="py-5 text-sm leading-7 text-gray-500">
                연결된 출처가 없습니다.
              </p>
            )}
          </div>
        </aside>
      </section>
    </div>
  );
}
