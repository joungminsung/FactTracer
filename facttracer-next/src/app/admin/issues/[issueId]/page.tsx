import Link from "next/link";
import { FileText, GitCompareArrows, ShieldAlert } from "lucide-react";
import {
  AdminIssueActionButtons,
  AdminReverificationForm,
  AdminReportResolveButtons,
} from "@/components/admin/admin-actions";
import { AdminIssuePodcastGenerateButton } from "@/components/admin/admin-podcast-actions";
import { statusTone } from "@/components/admin/admin-workspace-utils";
import {
  AdminMetricStrip,
  AdminPageHeader,
} from "@/components/common/design-system";
import { EmptyState } from "@/components/common/empty-state";
import { StatusBadge } from "@/components/status-badge";
import { getAdminIssue } from "@/lib/api/facttracer";
import { ApiError } from "@/lib/api/http";
import { getServerAccessToken } from "@/lib/auth/server-session";
import {
  formatCredibility,
  formatDateTime,
  formatStatus,
  formatTargetType,
} from "@/lib/display";

type AdminDetailState = "not_found" | "private" | "unauthorized" | "deleted" | "failed";

const adminStateCopy: Record<
  AdminDetailState,
  { title: string; description: string; emptyTitle: string }
> = {
  deleted: {
    description: "이미 처리된 검토 항목입니다.",
    emptyTitle: "처리된 검토 항목",
    title: "이미 처리된 검토 항목입니다",
  },
  failed: {
    description: "잠시 후 다시 시도하거나 검토 목록에서 다시 선택해 주세요.",
    emptyTitle: "내용을 불러오지 못함",
    title: "검토 대상을 찾을 수 없습니다",
  },
  not_found: {
    description: "아직 공개되지 않았거나 이미 처리된 항목일 수 있습니다.",
    emptyTitle: "검토 항목 없음",
    title: "검토 대상을 찾을 수 없습니다",
  },
  private: {
    description: "아직 공개되지 않은 검토 항목입니다.",
    emptyTitle: "공개되지 않은 항목",
    title: "아직 공개되지 않은 검토 항목입니다",
  },
  unauthorized: {
    description: "로그인 상태를 확인하거나 계정을 전환해 주세요.",
    emptyTitle: "권한 확인 필요",
    title: "검토 대상을 찾을 수 없습니다",
  },
};

export default async function AdminIssueDetailPage({
  params,
}: {
  params: Promise<{ issueId: string }>;
}) {
  const { issueId } = await params;
  const token = await getServerAccessToken();
  let detailState: AdminDetailState = "not_found";
  let detail: Awaited<ReturnType<typeof getAdminIssue>> | null = null;

  try {
    detail = await getAdminIssue(issueId, token);
  } catch (error) {
    if (error instanceof ApiError) {
      detailState =
        error.status === 401 || error.status === 403
          ? "unauthorized"
          : error.status === 404
            ? "not_found"
            : error.status === 409
              ? "deleted"
              : error.status === 423
                ? "private"
                : "failed";
    } else {
      detailState = "failed";
    }
  }

  if (!detail?.issue) {
    const copy = adminStateCopy[detailState];

    return (
      <div className="space-y-8">
        <AdminPageHeader
          backHref="/admin"
          backLabel="검토 목록으로 돌아가기"
          eyebrow={`검토 상세 · ${issueId}`}
          title={copy.title}
          description={copy.description}
        />

        <section className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_320px]">
          <article className="min-w-0">
            <section className="border-y border-gray-200 py-6">
              <EmptyState
                title={copy.emptyTitle}
                description="목록에서 다른 항목을 선택하거나 다시 갱신해 주세요."
                action={
                  <div className="flex flex-wrap gap-2">
                    <Link
                      href="/admin"
                      className="inline-flex h-10 items-center rounded-md bg-blue-600 px-4 text-sm font-medium text-white"
                    >
                      검토 목록으로 이동
                    </Link>
                    <Link
                      href={`/?q=${encodeURIComponent(issueId)}`}
                      className="inline-flex h-10 items-center rounded-md border border-gray-200 px-4 text-sm font-bold text-gray-700"
                    >
                      홈에서 검색
                    </Link>
                  </div>
                }
              />
            </section>
            <ReviewWorkflow />
            <div className="grid gap-8 py-7 xl:grid-cols-2">
              <section>
                <h2 className="text-xl font-bold text-gray-900">주장 검수</h2>
                <p className="mt-4 border-t border-gray-200 py-4 text-sm leading-7 text-gray-500">
                  검수할 주장이 없습니다.
                </p>
              </section>
              <section>
                <h2 className="text-xl font-bold text-gray-900">
                  출고 전 확인
                </h2>
                <p className="mt-4 border-t border-gray-200 py-4 text-sm leading-7 text-gray-500">
                  항목을 찾은 뒤 확인 목록이 표시됩니다.
                </p>
              </section>
            </div>
          </article>
          <aside className="xl:sticky xl:top-8 xl:self-start">
            <section className="border-y border-gray-200 py-6">
              <h2 className="text-base font-bold text-gray-900">다음 행동</h2>
              <div className="mt-4 divide-y divide-gray-100 border-t border-gray-200">
                <Link
                  href="/admin"
                  className="block py-4 text-sm font-semibold text-gray-700"
                >
                  검토 목록 확인
                </Link>
                <Link
                  href="/admin"
                  className="block py-4 text-sm font-semibold text-gray-700"
                >
                  목록 갱신
                </Link>
                <Link
                  href={`/?q=${encodeURIComponent(issueId)}`}
                  className="block py-4 text-sm font-semibold text-gray-700"
                >
                  공개 이슈 검색
                </Link>
              </div>
            </section>
          </aside>
        </section>
      </div>
    );
  }

  const issueMetrics = [
    { label: "주장", value: detail.claims.length },
    { label: "근거", value: detail.evidences.length },
    { label: "비교 기사", value: detail.articles.length },
    { label: "신고", value: detail.reports.length },
  ];

  return (
    <div className="space-y-8">
      <AdminPageHeader
        backHref="/admin"
        backLabel="검토 목록으로 돌아가기"
        eyebrow={`${detail.issue.topic} · ${detail.issue.id}`}
        title={detail.issue.title}
        description={detail.issue.reason}
      >
        <div className="flex flex-wrap gap-2 border-y border-gray-200 py-4">
          <StatusBadge tone={statusTone(detail.issue.priority)}>
            우선순위 {formatStatus(detail.issue.priority)}
          </StatusBadge>
          <StatusBadge tone={statusTone(detail.issue.status)}>
            {formatStatus(detail.issue.status)}
          </StatusBadge>
        </div>
        <AdminMetricStrip metrics={issueMetrics} />
      </AdminPageHeader>

      <section className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_340px]">
        <article className="min-w-0">
            <ReviewWorkflow />

            <section className="border-b border-gray-200 pb-7">
              <div className="flex items-center gap-2">
                <ShieldAlert className="size-4 text-blue-600" aria-hidden="true" />
                <h2 className="text-xl font-bold text-gray-900">
                  주장 검수
                </h2>
              </div>
              <div className="mt-4 divide-y divide-gray-100 border-t border-gray-200">
                {detail.claims.length > 0 ? (
                  detail.claims.map((claim) => (
                  <div
                    key={claim.id ?? claim.text}
                    className="grid gap-4 py-5 xl:grid-cols-[120px_minmax(0,1fr)_132px_120px]"
                  >
                    <span className="text-sm font-semibold text-gray-500">
                      {claim.type}
                    </span>
                    <div>
                      <p className="font-bold leading-7 text-gray-900">
                        {claim.text}
                      </p>
                      <p className="mt-1 text-sm leading-6 text-gray-500">
                        근거: {claim.evidence}
                      </p>
                      <p className="mt-1 text-sm leading-6 text-gray-500">
                        처리: {formatStatus(claim.status)}
                      </p>
                    </div>
                    <StatusBadge tone={claim.tone}>{claim.verdict}</StatusBadge>
                    <span className="text-sm font-semibold text-gray-600">
                      {formatCredibility(claim.confidence)}
                    </span>
                  </div>
                  ))
                ) : (
                  <p className="py-4 text-sm leading-7 text-gray-500">
                    검수할 주장이 없습니다.
                  </p>
                )}
              </div>
            </section>

            <section className="border-b border-gray-200 py-7">
              <div className="flex items-center gap-2">
                <GitCompareArrows
                  className="size-4 text-blue-600"
                  aria-hidden="true"
                />
                <h2 className="text-xl font-bold text-gray-900">
                  기사 비교
                </h2>
              </div>
              <div className="mt-4 divide-y divide-gray-100 border-t border-gray-200">
                {detail.articles.length > 0 ? (
                  detail.articles.map((article) => (
                  <a
                    key={article.id}
                    href={article.url}
                    target="_blank"
                    rel="noreferrer"
                    className="grid gap-4 py-5 lg:grid-cols-[minmax(0,1fr)_120px_120px]"
                  >
                    <div>
                      <h3 className="font-bold text-gray-900">{article.title}</h3>
                      <p className="mt-1 text-sm leading-6 text-gray-500">
                        {article.outlet} · {formatDateTime(article.publishedAt)}
                      </p>
                      <p className="mt-2 text-sm leading-6 text-gray-600">
                        {article.note}
                      </p>
                    </div>
                    <span className="text-sm text-gray-600">
                      공식근거 {article.officialSourceCount}
                    </span>
                    <StatusBadge tone={article.tone}>{article.verdict}</StatusBadge>
                  </a>
                  ))
                ) : (
                  <p className="py-4 text-sm leading-7 text-gray-500">
                    비교할 기사가 없습니다.
                  </p>
                )}
              </div>
            </section>

            <section className="py-7">
              <div className="flex items-center gap-2">
                <FileText className="size-4 text-blue-600" aria-hidden="true" />
                <h2 className="text-xl font-bold text-gray-900">
                  신고 표현
                </h2>
              </div>
              <div className="mt-4 divide-y divide-gray-100 border-t border-gray-200">
                {detail.reports.length > 0 ? (
                  detail.reports.map((report) => (
                  <div
                    key={report.id}
                    className="grid gap-4 py-5 lg:grid-cols-[minmax(0,1fr)_160px]"
                  >
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <StatusBadge tone={statusTone(report.priority)}>
                          {formatStatus(report.priority)}
                        </StatusBadge>
                        <StatusBadge tone={statusTone(report.status)}>
                          {formatStatus(report.status)}
                        </StatusBadge>
                        <span className="text-xs font-semibold text-amber-600">
                          {report.reason}
                        </span>
                      </div>
                      <h3 className="mt-2 font-bold text-gray-900">
                        {report.excerpt}
                      </h3>
                      <p className="mt-1 text-sm leading-6 text-gray-500">
                      {formatTargetType(report.targetType)} · 접수{" "}
                      {formatDateTime(report.submittedAt)}
                      </p>
                    </div>
                    <AdminReportResolveButtons reportId={report.id} />
                  </div>
                  ))
                ) : (
                  <p className="py-4 text-sm leading-7 text-gray-500">
                    신고 표현이 없습니다.
                  </p>
                )}
              </div>
            </section>
          </article>

          <aside className="xl:sticky xl:top-8 xl:self-start">
            <section className="border-y border-gray-200 py-6">
              <h2 className="text-base font-bold text-gray-900">출고 승인</h2>
              <div className="mt-4">
                <AdminIssueActionButtons
                  issueId={detail.issue.id}
                  showOpenLink={false}
                />
              </div>
            </section>
            <section className="border-b border-gray-200 py-6">
              <h2 className="text-base font-bold text-gray-900">재검증</h2>
              <AdminReverificationForm issueId={detail.issue.id} />
            </section>
            <section className="border-b border-gray-200 py-6">
              <h2 className="text-base font-bold text-gray-900">
                팟캐스트 생성
              </h2>
              <p className="mt-2 text-xs leading-5 text-gray-500">
                이 이슈만 대상으로 스크립트를 만들고 운영 화면에서 TTS를
                렌더링합니다.
              </p>
              <div className="mt-4">
                <AdminIssuePodcastGenerateButton
                  issueId={detail.issue.id}
                  topic={detail.issue.topic}
                />
              </div>
            </section>
            <section className="py-6">
              <h2 className="text-base font-bold text-gray-900">
                다른 검토 이슈
              </h2>
              <div className="mt-4 divide-y divide-gray-100 border-t border-gray-200">
                {detail.queue.length > 0 ? (
                  detail.queue.map((item) => (
                  <Link
                    key={item.id}
                    href={`/admin/issues/${item.id}`}
                    className="block py-4"
                  >
                    <p className="text-sm font-bold leading-6 text-gray-900">
                      {item.title}
                    </p>
                    <p className="mt-1 text-xs font-semibold text-gray-500">
                      {formatStatus(item.priority)} · {formatStatus(item.status)}
                    </p>
                  </Link>
                  ))
                ) : (
                  <p className="py-4 text-sm leading-7 text-gray-500">
                    다른 검토 이슈가 없습니다.
                  </p>
                )}
              </div>
            </section>
          </aside>
        </section>
    </div>
  );
}

function ReviewWorkflow() {
  const steps = [
    ["수집", "기사와 자료 수집 확인"],
    ["AI 초안", "자동 추출 오류 점검"],
    ["출처 확인", "공식 자료와 기준 시점 대조"],
    ["주장 검토", "사실/해석/요구/반박 분류"],
    ["표현 정제", "낙인과 단정 표현 제거"],
    ["게시 승인", "체크리스트와 승인 메모 기록"],
  ];

  return (
    <section className="border-b border-gray-200 pb-7">
      <h2 className="text-xl font-bold text-gray-900">검토 진행 상태</h2>
      <ol className="mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-6">
        {steps.map(([title, description], index) => (
          <li
            key={title}
            className={`min-h-24 border px-3 py-3 ${
              index < 3
                ? "border-gray-200 bg-gray-50"
                : "border-gray-200 bg-white"
            }`}
          >
            <p className="text-sm font-bold text-gray-900">{title}</p>
            <p className="mt-2 text-xs leading-5 text-gray-600">
              {description}
            </p>
          </li>
        ))}
      </ol>
    </section>
  );
}
