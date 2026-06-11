import Link from "next/link";
import { FileText } from "lucide-react";
import { PageIntro, PageShell } from "@/components/common/design-system";
import { EmptyState } from "@/components/common/empty-state";
import { ReportUtilityActions } from "@/components/issue/report-utility-actions";
import {
  ArticleComparisonTable,
  ClaimVerificationList,
  ConfirmedFactList,
  IssueDebateMap,
  IssueMetricStrip,
  NumberChangeList,
  PerspectiveClaims,
  SourceDocumentList,
  TimelineList,
} from "@/components/issue/issue-structure";
import { SiteHeader } from "@/components/site-header";
import { getIssueDetail } from "@/lib/api/facttracer";
import { ApiError } from "@/lib/api/http";
import { formatUpdatedAt } from "@/lib/display";

type ReportState = "not_found" | "unauthorized" | "failed";

const reportStateCopy: Record<ReportState, { title: string; description: string }> = {
  failed: {
    description: "잠시 후 다시 시도하거나 다른 이슈를 선택해 주세요.",
    title: "리포트로 만들 이슈를 찾을 수 없습니다",
  },
  not_found: {
    description: "아직 공개되지 않았거나 정리된 기록이 없습니다.",
    title: "리포트로 만들 이슈를 찾을 수 없습니다",
  },
  unauthorized: {
    description: "로그인 상태를 확인하거나 다른 이슈를 선택해 주세요.",
    title: "리포트를 볼 권한이 없습니다",
  },
};

export default async function IssueReportPage({
  params,
}: {
  params: Promise<{ issueId: string }>;
}) {
  const { issueId } = await params;
  let state: ReportState = "not_found";
  let issueResponse: Awaited<ReturnType<typeof getIssueDetail>> | null = null;

  try {
    issueResponse = await getIssueDetail(issueId);
  } catch (error) {
    if (error instanceof ApiError) {
      state =
        error.status === 401 || error.status === 403
          ? "unauthorized"
          : error.status === 404
            ? "not_found"
            : "failed";
    } else {
      state = "failed";
    }
  }

  const issue = issueResponse?.issue ?? null;

  if (!issue) {
    const copy = reportStateCopy[state];

    return (
      <PageShell tone="dossier">
        <SiteHeader />
        <main className="mx-auto max-w-[960px] px-4 py-6 sm:px-6 sm:py-8">
          <PageIntro
            eyebrow={<Link href="/">이슈 모니터로 이동</Link>}
            title={copy.title}
            description={copy.description}
          />
          <EmptyState
            title="표시할 리포트 없음"
            description="이슈 기록이 준비되면 요약, 쟁점, 관점, 기사 비교, 근거가 이 화면에 정리됩니다."
            action={
              <Link
                href="/"
                className="inline-flex h-10 items-center rounded-md bg-blue-600 px-4 text-sm font-medium text-white"
              >
                최근 이슈 보기
              </Link>
            }
          />
        </main>
      </PageShell>
    );
  }

  return (
    <PageShell tone="dossier">
      <div className="print:hidden">
        <SiteHeader />
      </div>
      <main className="mx-auto max-w-[1120px] px-4 py-6 sm:px-6 sm:py-8">
        <section className="border border-gray-300 bg-white px-5 py-6 sm:px-7">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <Link
              href={`/issues/${issue.id}`}
              className="text-sm font-semibold text-blue-600 print:hidden"
            >
              이슈 상세로 돌아가기
            </Link>
            <ReportUtilityActions issue={issue} />
          </div>
          <div className="mt-6 flex items-center gap-2 text-sm font-semibold text-blue-600">
            <FileText className="size-4" aria-hidden="true" />
            발표/연구용 리포트
          </div>
          <p className="mt-3 text-sm font-semibold text-gray-500">
            {issue.topic} · {issue.risk} · {formatUpdatedAt(issue.updatedAt)}
          </p>
          <h1 className="mt-2 text-3xl font-bold leading-tight tracking-tight text-gray-900 sm:text-4xl">
            {issue.title}
          </h1>
          <p className="mt-4 text-base leading-8 text-gray-600">
            {issue.summary}
          </p>
          <IssueMetricStrip issue={issue} />
        </section>

        <article className="mt-5 border-x border-b border-gray-300 bg-white px-4 py-5 sm:px-7 sm:py-7">
          <ConfirmedFactList facts={issue.confirmedFacts} title="1. 핵심 팩트" />
          <IssueDebateMap
            clusters={issue.claimClusters}
            facts={issue.confirmedFacts}
          />
          <ClaimVerificationList claims={issue.claims} />
          <PerspectiveClaims perspectives={issue.perspectives} />
          <ArticleComparisonTable articles={issue.articles ?? []} />
          <SourceDocumentList sources={issue.sourceDocuments ?? []} />
          <TimelineList events={issue.timeline ?? []} />
          <NumberChangeList changes={issue.numberChanges ?? []} />
        </article>
      </main>
    </PageShell>
  );
}
