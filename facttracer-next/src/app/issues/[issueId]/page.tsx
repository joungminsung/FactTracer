import Link from "next/link";
import {
  Bell,
  Building2,
  CalendarDays,
  CheckCircle2,
  FileText,
  Globe2,
  LinkIcon,
  MessageSquareText,
  Newspaper,
  Scale,
  UserRound,
} from "lucide-react";
import type { ReactNode } from "react";
import { ArticleVerificationForm } from "@/components/issue/article-verification-form";
import { ClaimSubmissionForm } from "@/components/issue/claim-submission-form";
import { ContentReportForm } from "@/components/issue/content-report-form";
import {
  CreateIssueReportButton,
  SaveIssueButton,
} from "@/components/issue/issue-actions";
import { IssueSectionWorkspace } from "@/components/issue/issue-section-index";
import {
  ArticleComparisonTable,
  ClaimVerificationList,
  ConfirmedFactList,
  IssueDebateMap,
  NumberChangeList,
  PerspectiveClaims,
  SourceDocumentList,
  TimelineList,
} from "@/components/issue/issue-structure";
import { SiteHeader } from "@/components/site-header";
import { StatusBadge } from "@/components/status-badge";
import { getIssueDetail } from "@/lib/api/facttracer";
import { ApiError } from "@/lib/api/http";
import type {
  ArticleComparison,
  ClaimCluster,
  ConfirmedFact,
  Issue,
  IssueDetail,
  SourceDocument,
  VerdictTone,
} from "@/lib/api/types";
import {
  formatDateTime,
  formatSourceType,
  formatStatus,
  formatUpdatedAt,
} from "@/lib/display";

type IssueDetailState = "not_found" | "unauthorized" | "failed";

const issueDetailStateCopy: Record<
  IssueDetailState,
  { title: string; description: string }
> = {
  failed: {
    description: "잠시 후 다시 시도하거나 최근 이슈에서 다시 선택해 주세요.",
    title: "이슈를 찾을 수 없습니다",
  },
  not_found: {
    description: "아직 공개되지 않았거나 처리 이력이 정리되지 않았습니다.",
    title: "이슈를 찾을 수 없습니다",
  },
  unauthorized: {
    description: "로그인 상태를 확인하거나 공개된 이슈를 선택해 주세요.",
    title: "이 화면을 볼 권한이 없습니다",
  },
};

const detailNavItems = [
  { id: "summary", label: "핵심 요약" },
  { id: "facts", label: "확인된 사실" },
  { id: "map", label: "쟁점 지도" },
  { id: "claims", label: "주장 검증" },
  { id: "articles", label: "기사 비교" },
  { id: "perspectives", label: "관점별 주장" },
  { id: "timeline", label: "타임라인" },
  { id: "numbers", label: "수치 변경" },
  { id: "sources", label: "원문 자료" },
  { id: "user-feedback", label: "참여/제보" },
];

export default async function IssueDetailPage({
  params,
}: {
  params: Promise<{ issueId: string }>;
}) {
  const { issueId } = await params;
  let detailState: IssueDetailState = "not_found";
  let issueResponse: Awaited<ReturnType<typeof getIssueDetail>> | null = null;

  try {
    issueResponse = await getIssueDetail(issueId);
  } catch (error) {
    if (error instanceof ApiError) {
      detailState =
        error.status === 401 || error.status === 403
          ? "unauthorized"
          : error.status === 404
            ? "not_found"
            : "failed";
    } else {
      detailState = "failed";
    }
  }

  const issue = issueResponse?.issue ?? null;
  const relatedIssues = issueResponse?.relatedIssues ?? [];

  if (!issue) {
    const copy = issueDetailStateCopy[detailState];

    return (
      <div className="min-h-screen bg-white text-gray-900">
        <SiteHeader />
        <main className="mx-auto max-w-screen-xl px-4 py-10 sm:px-6 lg:px-8">
          <Link href="/" className="text-sm font-medium text-blue-600 hover:underline">
            이슈 모니터로 돌아가기
          </Link>
          <section className="py-10">
            <p className="text-xs font-medium uppercase tracking-wide text-gray-500">
              이슈 상세
            </p>
            <h1 className="mt-2 max-w-4xl text-3xl font-bold tracking-tight text-gray-900 sm:text-4xl">
              {copy.title}
            </h1>
            <p className="mt-4 max-w-[680px] text-lg leading-8 text-gray-600">
              {copy.description}
            </p>
            <div className="mt-7 flex flex-wrap gap-8">
              <Metric label="수집 기사" value={0} />
              <Metric label="쟁점 묶음" value={0} />
              <Metric label="검증 완료" value={0} />
              <Metric label="추가 확인" value={0} />
            </div>
          </section>

          <section className="grid gap-10 py-10 lg:grid-cols-[minmax(0,1fr)_360px]">
            <IssueNotFoundRecovery />
            <ArticleVerificationForm />
          </section>
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-white text-gray-900">
      <SiteHeader />

      <main className="mx-auto max-w-[1600px] px-4 py-6 sm:px-6 lg:px-8 xl:px-10">
        <section className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_288px]">
          <div className="min-w-0">
            <IssueArticleHeader issue={issue} />

            <IssueSectionWorkspace items={detailNavItems}>
              <IssueSummaryPanel issue={issue} />
              <ConfirmedFactList
                facts={issue.confirmedFacts}
                sources={issue.sourceDocuments ?? []}
                title="확인된 사실"
              />
              <IssueDebateMap
                clusters={issue.claimClusters}
                facts={issue.confirmedFacts}
              />
              <ClaimVerificationList claims={issue.claims} />
              <ArticleComparisonTable articles={issue.articles ?? []} />
              <PerspectiveClaims perspectives={issue.perspectives} />
              <TimelineList events={issue.timeline ?? []} />
              <NumberChangeList changes={issue.numberChanges ?? []} />
              <SourceDocumentList sources={issue.sourceDocuments ?? []} />
              <IssueParticipationPanel issueId={issue.id} />
            </IssueSectionWorkspace>
          </div>

          <IssueContextRail issue={issue} relatedIssues={relatedIssues} />
        </section>
      </main>
    </div>
  );
}

function IssueArticleHeader({ issue }: { issue: IssueDetail }) {
  return (
    <header className="pb-6">
      <nav
        aria-label="경로"
        className="flex flex-wrap items-center gap-2 text-xs text-gray-500"
      >
        <Link href="/" className="hover:text-blue-600">
          홈
        </Link>
        <span aria-hidden="true">›</span>
        <span>{issue.topic}</span>
        <span aria-hidden="true">›</span>
        <span>사건 상세</span>
      </nav>

      <div className="mt-5 flex flex-wrap items-center gap-2 text-sm font-medium">
        <span className="text-blue-600">{issue.topic}</span>
        <span className="text-gray-300" aria-hidden="true">
          |
        </span>
        <StatusBadge tone={issueStatusTone(issue.status)}>
          {formatStatus(issue.status)}
        </StatusBadge>
      </div>

      <h1 className="mt-3 max-w-4xl text-[32px] font-bold leading-tight tracking-normal text-gray-950 sm:text-[40px]">
        {issue.title}
      </h1>
      <p className="mt-4 max-w-[760px] text-[16px] leading-7 text-gray-700">
        {issue.summary}
      </p>

      <div className="mt-7 flex flex-wrap items-center justify-between gap-4 border-b border-gray-200 pb-5">
        <p className="text-sm text-gray-500">
          FactTracer 취재팀
          <span className="mx-2 text-gray-300" aria-hidden="true">
            |
          </span>
          {formatDateTime(issue.updatedAt)}
        </p>
        <IssueUtilityActions issueId={issue.id} />
      </div>
    </header>
  );
}

function IssueSummaryPanel({ issue }: { issue: IssueDetail }) {
  const facts = issue.confirmedFacts.slice(0, 5);
  const clusters = issue.claimClusters.slice(0, 2);
  const articles = (issue.articles ?? []).slice(0, 4);

  return (
    <section id="summary" className="min-w-0 py-7">
      <div className="grid min-w-0 gap-6 2xl:grid-cols-[minmax(0,1fr)_minmax(320px,0.72fr)]">
        <SummaryFactsTable facts={facts} />
        <EvidenceReliabilityPanel sources={issue.sourceDocuments ?? []} />
      </div>

      <div className="mt-6 grid min-w-0 gap-6 2xl:grid-cols-[minmax(0,1fr)_minmax(320px,0.72fr)]">
        <SummaryDebateMap clusters={clusters} facts={facts} />
        <SummaryArticleTable articles={articles} />
      </div>
    </section>
  );
}

function SummaryPanelFrame({ children }: { children: ReactNode }) {
  return (
    <section className="min-w-0 overflow-hidden rounded-[3px] border border-gray-200 bg-white">
      {children}
    </section>
  );
}

function SummarySectionHeader({
  action,
  subtitle,
  title,
}: {
  action?: string;
  subtitle?: string;
  title: string;
}) {
  return (
    <div className="flex min-h-14 items-center justify-between gap-4 border-b border-gray-200 bg-white px-4 py-3">
      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
        <h2 className="text-[19px] font-bold tracking-normal text-gray-950">{title}</h2>
        {subtitle ? (
          <p className="text-sm text-gray-500">({subtitle})</p>
        ) : null}
      </div>
      {action ? (
        <span className="shrink-0 text-sm font-medium text-gray-500">
          {action} <span aria-hidden="true">›</span>
        </span>
      ) : null}
    </div>
  );
}

function SummaryFactsTable({ facts }: { facts: ConfirmedFact[] }) {
  return (
    <SummaryPanelFrame>
      <SummarySectionHeader
        action="전체 보기"
        subtitle="확인된 사실 요약"
        title="핵심 팩트"
      />
      <div className="max-w-full overflow-x-auto">
        <table className="w-full border-collapse text-left text-sm">
          <thead className="bg-gray-50 text-xs font-semibold text-gray-700">
            <tr>
              <th className="w-28 border-b border-r border-gray-200 px-4 py-3">항목</th>
              <th className="border-b border-r border-gray-200 px-4 py-3">확인된 내용</th>
              <th className="w-20 border-b border-gray-200 px-4 py-3">판정</th>
            </tr>
          </thead>
          <tbody>
            {facts.length > 0 ? (
              facts.map((fact, index) => (
                <tr key={`${fact.label}-${index}`} className="align-top">
                  <td className="border-b border-r border-gray-100 px-4 py-3 font-medium text-gray-900">
                    {fact.label}
                  </td>
                  <td className="border-b border-r border-gray-100 px-4 py-3 leading-6 text-gray-700">
                    {fact.text}
                  </td>
                  <td className="border-b border-gray-100 px-4 py-3">
                    <StatusBadge tone={fact.tone}>{fact.verdict}</StatusBadge>
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td className="px-4 py-4 text-gray-500" colSpan={3}>
                  확인된 사실이 아직 없습니다.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </SummaryPanelFrame>
  );
}

function EvidenceReliabilityPanel({ sources }: { sources: SourceDocument[] }) {
  const rows = [
    { icon: FileText, label: "공식 문서", level: "높음", dots: 4 },
    { icon: Globe2, label: "정부/공공 발표", level: "높음", dots: 4 },
    { icon: Newspaper, label: "언론 보도", level: "중간", dots: 2 },
    { icon: UserRound, label: "전문가 의견", level: "중간", dots: 2 },
    { icon: MessageSquareText, label: "SNS/커뮤니티", level: "낮음", dots: 1 },
  ];

  return (
    <SummaryPanelFrame>
      <SummarySectionHeader
        action="전체 보기"
        subtitle={`${sources.length}개 원문 자료 기준`}
        title="근거 신뢰도 평가"
      />
      <div className="p-4">
        <div className="overflow-hidden rounded-[2px] border border-gray-200">
        {rows.map((row) => (
            <div
              key={row.label}
              className="grid grid-cols-[minmax(0,1fr)_56px_88px] items-center gap-3 border-b border-gray-100 px-4 py-3 text-sm last:border-b-0"
            >
              <span className="flex min-w-0 items-center gap-3 font-medium text-gray-800">
                <row.icon className="size-4 shrink-0 text-gray-700" aria-hidden="true" />
                <span>{row.label}</span>
              </span>
              <span className="text-gray-600">{row.level}</span>
              <span className="flex justify-end gap-1.5">
                {Array.from({ length: 4 }).map((_, index) => (
                  <span
                    key={`${row.label}-${index}`}
                    className={`h-2.5 w-2.5 rounded-full ${
                      index < row.dots ? "bg-blue-600" : "bg-gray-300"
                    }`}
                  />
                ))}
              </span>
            </div>
        ))}
        </div>
        <p className="mt-3 text-xs leading-5 text-gray-500">
          * 신뢰도는 FactTracer 자체 기준입니다.
        </p>
      </div>
    </SummaryPanelFrame>
  );
}

function SummaryDebateMap({
  clusters,
  facts,
}: {
  clusters: ClaimCluster[];
  facts: ConfirmedFact[];
}) {
  const primaryCluster = clusters[0];
  const primaryClaims = primaryCluster?.claims.slice(0, 2) ?? [];

  return (
    <SummaryPanelFrame>
      <SummarySectionHeader subtitle="핵심 쟁점 비교" title="쟁점 지도" />
      <div className="p-4">
        {primaryCluster ? (
          <div className="overflow-hidden rounded-[2px] border border-gray-200">
            <div className="grid grid-cols-[minmax(0,1fr)_48px_minmax(0,1fr)]">
              <div className="bg-blue-700 px-4 py-2 text-center text-sm font-bold text-white">
                주장 A
              </div>
              <div className="z-10 flex items-center justify-center bg-white">
                <span className="-my-2 inline-flex size-10 items-center justify-center rounded-full border border-gray-200 bg-white text-sm font-bold text-gray-700">
                  VS
                </span>
              </div>
              <div className="bg-red-700 px-4 py-2 text-center text-sm font-bold text-white">
                주장 B
              </div>
            </div>

            <div className="grid md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
              <div className="border-b border-r border-gray-200 p-4 text-center text-sm leading-6 text-gray-800 md:border-b-0">
                {primaryClaims[0] ?? primaryCluster.title}
              </div>
              <div className="p-4 text-center text-sm leading-6 text-gray-800">
                {primaryClaims[1] ?? "비교할 반론이 아직 없습니다."}
              </div>
            </div>

            <div className="grid border-t border-gray-200 text-sm md:grid-cols-2">
              <div className="border-b border-r border-gray-200 p-4 md:border-b-0">
                <p className="font-semibold text-gray-950">근거</p>
                <p className="mt-2 leading-6 text-gray-600">
                  {facts[0]?.text ?? primaryCluster.commonGround}
                </p>
              </div>
              <div className="p-4">
                <p className="font-semibold text-gray-950">충돌 지점</p>
                <p className="mt-2 leading-6 text-gray-600">
                  {primaryCluster.conflict}
                </p>
              </div>
            </div>

            <div className="grid border-t border-gray-200 bg-gray-50 px-4 py-4 text-sm leading-6 text-gray-700 md:grid-cols-[32px_minmax(0,1fr)_32px] md:items-center">
              <CheckCircle2 className="hidden size-5 text-emerald-600 md:block" aria-hidden="true" />
              <p className="text-center">
                {primaryCluster.commonGround || "현재 확인된 자료 기준으로 공통분모를 정리 중입니다."}
              </p>
              <CheckCircle2 className="hidden size-5 text-emerald-600 md:block" aria-hidden="true" />
            </div>
          </div>
        ) : (
          <p className="text-sm leading-7 text-gray-500">
            쟁점 묶음이 없습니다.
          </p>
        )}
      </div>
    </SummaryPanelFrame>
  );
}

function SummaryArticleTable({ articles }: { articles: ArticleComparison[] }) {
  return (
    <SummaryPanelFrame>
      <SummarySectionHeader subtitle="주요 보도 시각 차이" title="기사 비교" />
      <div className="max-w-full overflow-x-auto">
        <table className="w-full border-collapse text-left text-sm">
          <thead className="bg-gray-50 text-xs font-semibold text-gray-700">
            <tr>
              <th className="w-28 border-b border-r border-gray-200 px-4 py-3">언론사</th>
              <th className="border-b border-r border-gray-200 px-4 py-3">핵심 관점</th>
              <th className="w-20 border-b border-gray-200 px-4 py-3">톤</th>
            </tr>
          </thead>
          <tbody>
            {articles.length > 0 ? (
              articles.map((article) => (
                <tr key={article.id} className="align-top">
                  <td className="border-b border-r border-gray-100 px-4 py-3 font-bold text-gray-900">
                    {article.outlet}
                  </td>
                  <td className="border-b border-r border-gray-100 px-4 py-3 leading-6 text-gray-700">
                    {article.note}
                  </td>
                  <td className="border-b border-gray-100 px-4 py-3">
                    <StatusBadge tone={article.tone}>{article.verdict}</StatusBadge>
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td className="px-4 py-4 text-gray-500" colSpan={3}>
                  비교할 기사가 없습니다.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </SummaryPanelFrame>
  );
}

function IssueNotFoundRecovery() {
  return (
    <section>
      <p className="text-xs font-medium uppercase tracking-wide text-gray-500">
        다음 행동
      </p>
      <h2 className="mt-2 text-lg font-semibold text-gray-900">
        이슈 기록을 다시 찾거나 새 분석을 요청할 수 있습니다
      </h2>
      <p className="mt-3 max-w-[680px] text-[15px] leading-7 text-gray-700">
        요청한 공개 기록이 없거나 아직 검토 전입니다. 최근 이슈로 이동하거나
        기사 링크로 새 분석 요청을 접수하세요.
      </p>
      <div className="mt-6 grid gap-4 sm:grid-cols-3">
        <RecoveryLink href="/" label="이슈 모니터 보기">
          최근 감지된 이슈로 돌아갑니다.
        </RecoveryLink>
        <RecoveryLink href="#article-verification" label="기사 비교 요청">
          기사 링크로 새 이슈 후보를 접수합니다.
        </RecoveryLink>
        <RecoveryLink href="/notifications" label="알림 설정">
          검토 완료와 수치 변경을 받아봅니다.
        </RecoveryLink>
      </div>
    </section>
  );
}

function RecoveryLink({
  children,
  href,
  label,
}: {
  children: ReactNode;
  href: string;
  label: string;
}) {
  return (
    <Link href={href} className="block py-3 text-sm font-medium text-gray-900 hover:text-blue-600">
      {label}
      <span className="mt-1 block text-sm font-normal leading-6 text-gray-500">
        {children}
      </span>
    </Link>
  );
}

function IssueParticipationPanel({ issueId }: { issueId: string }) {
  return (
    <section id="user-feedback" className="py-7">
      <header>
        <h2 className="text-[30px] font-bold leading-tight text-gray-950">참여/제보</h2>
        <p className="mt-2 max-w-[760px] text-[15px] leading-7 text-gray-700">
          주장, 사실, 자료에 대한 제보 또는 오류 정정 요청을 구조화해 접수합니다.
          FactTracer 취재팀 검토 후 공개 검증에 반영됩니다.
        </p>
      </header>

      <div className="mt-7 overflow-hidden rounded-[3px] border-y border-gray-200">
        <div className="grid border-b border-gray-200 text-center text-base font-bold md:grid-cols-2">
          <div className="border-b-2 border-blue-600 px-4 py-4 text-blue-600">
            검증 가능한 주장 제보
          </div>
          <div className="px-4 py-4 text-gray-900">정정 요청 / 신고</div>
        </div>
        <div className="grid divide-y divide-gray-200 md:grid-cols-2 md:divide-x md:divide-y-0">
          <div className="p-5">
            <ClaimSubmissionForm issueId={issueId} />
          </div>
          <div className="p-5">
            <ContentReportForm issueId={issueId} />
          </div>
        </div>
      </div>

      <section className="mt-8 border-t border-gray-200 pt-5">
        <h3 className="text-lg font-bold text-gray-950">
          제보 전 확인해 주세요
        </h3>
        <div className="mt-4 grid overflow-hidden rounded-[3px] border border-gray-200 text-sm leading-6 text-gray-600 md:grid-cols-4 md:divide-x md:divide-gray-200">
          <GuidanceItem
            icon={<LinkIcon className="size-6 text-blue-600" aria-hidden="true" />}
            title="원문 링크"
            value="주장·사실의 출처가 되는 원문 링크를 함께 제공해 주세요."
          />
          <GuidanceItem
            icon={<CalendarDays className="size-6 text-blue-600" aria-hidden="true" />}
            title="날짜 정보"
            value="언제, 어디서, 어떤 맥락에서 나온 주장인지 확인할 수 있어야 합니다."
          />
          <GuidanceItem
            icon={<Building2 className="size-6 text-blue-600" aria-hidden="true" />}
            title="발행처 정보"
            value="보도한 매체, 작성자, 기관 등 발행처를 확인할 수 있어야 합니다."
          />
          <GuidanceItem
            icon={<Scale className="size-6 text-blue-600" aria-hidden="true" />}
            title="반박 가능 기준"
            value="어떤 공식자료가 나오면 판단이 바뀔 수 있는지 적어 주세요."
          />
        </div>
      </section>
    </section>
  );
}

function GuidanceItem({
  icon,
  title,
  value,
}: {
  icon: ReactNode;
  title: string;
  value: string;
}) {
  return (
    <div className="p-5">
      {icon}
      <h4 className="mt-3 font-semibold text-gray-900">{title}</h4>
      <p className="mt-2">{value}</p>
    </div>
  );
}

function IssueUtilityActions({ issueId }: { issueId: string }) {
  const utilityButtonClassName =
    "inline-flex h-8 min-w-0 items-center justify-center gap-1.5 text-sm font-medium text-gray-600 transition-colors hover:text-blue-600 disabled:cursor-not-allowed disabled:opacity-50";

  return (
    <section aria-label="이슈 보조 작업">
      <div className="flex flex-wrap items-center gap-4">
        <SaveIssueButton
          buttonClassName={utilityButtonClassName}
          issueId={issueId}
          label="저장"
        />
        <Link href="/notifications" className={utilityButtonClassName}>
          <Bell className="size-4" aria-hidden="true" />
          알림
        </Link>
        <CreateIssueReportButton
          buttonClassName={utilityButtonClassName}
          issueId={issueId}
          label="리포트 생성"
        />
      </div>
    </section>
  );
}

function IssueContextRail({
  issue,
  relatedIssues,
}: {
  issue: IssueDetail;
  relatedIssues: Issue[];
}) {
  return (
    <aside className="hidden xl:block">
      <div className="sticky top-24 border-l border-gray-200 pl-8 text-sm">
        <RailSection title="관련 이슈">
          <div className="divide-y divide-gray-100">
            {relatedIssues.length > 0 ? (
              relatedIssues.map((relatedIssue) => (
                <Link
                  key={relatedIssue.id}
                  href={`/issues/${relatedIssue.id}`}
                  className="block py-4"
                >
                  <p className="font-medium leading-6 text-gray-900">
                    {relatedIssue.title}
                  </p>
                  <p className="mt-1 text-xs text-gray-500">
                    {relatedIssue.topic} · {formatUpdatedAt(relatedIssue.updatedAt)}
                  </p>
                </Link>
              ))
            ) : (
              <p className="py-4 text-sm leading-7 text-gray-500">
                관련 이슈가 없습니다.
              </p>
            )}
          </div>
        </RailSection>

        <RailSection title="주요 출처">
          <SourceLinkList sources={issue.sourceDocuments ?? []} />
        </RailSection>

        <RailSection title="검증 상태">
          <div className="flex items-center justify-between gap-4">
            <StatusBadge tone={issueStatusTone(issue.status)}>
              {formatStatus(issue.status)}
            </StatusBadge>
            <span className="text-xs text-gray-500">{formatDateTime(issue.updatedAt)}</span>
          </div>
          <p className="mt-2 text-xs leading-5 text-gray-500">
            추가 자료 확인 시 검증 내용이 업데이트될 수 있습니다.
          </p>
        </RailSection>

        <RailSection title="업데이트">
          <div className="grid gap-3">
            {(issue.timeline ?? []).slice(0, 3).map((event) => (
              <div key={event.id} className="grid grid-cols-[7px_minmax(0,1fr)] gap-3">
                <span className="mt-1.5 h-2 w-2 rounded-full bg-blue-600" aria-hidden="true" />
                <div>
                  <p className="text-xs text-gray-500">{formatDateTime(event.occurredAt)}</p>
                  <p className="mt-1 leading-6 text-gray-700">{event.title}</p>
                </div>
              </div>
            ))}
            {(issue.timeline ?? []).length === 0 ? (
              <p className="text-sm leading-7 text-gray-500">
                업데이트 이력이 없습니다.
              </p>
            ) : null}
          </div>
        </RailSection>

        <RailSection title="참여/제보">
          <p className="text-sm leading-6 text-gray-600">
            이 사건과 관련한 추가 자료나 반박 근거가 있나요?
          </p>
          <a
            href="#user-feedback"
            className="mt-3 inline-flex text-sm font-medium text-blue-600 hover:underline"
          >
            제보하기
          </a>
        </RailSection>
      </div>
    </aside>
  );
}

function RailSection({
  children,
  title,
}: {
  children: ReactNode;
  title: string;
}) {
  return (
    <section className="border-t border-gray-200 py-6 first:border-t-0 first:pt-0">
      <h2 className="text-base font-bold text-gray-950">{title}</h2>
      <div className="mt-4">{children}</div>
    </section>
  );
}

function SourceLinkList({ sources }: { sources: SourceDocument[] }) {
  if (sources.length === 0) {
    return (
      <p className="text-sm leading-7 text-gray-500">
        공개된 원문 자료가 없습니다.
      </p>
    );
  }

  return (
    <div className="divide-y divide-gray-100">
      {sources.slice(0, 4).map((source) => (
        <a
          key={source.id}
          href={source.url}
          target="_blank"
          rel="noreferrer"
          className="block py-3"
        >
          <p className="font-medium leading-6 text-gray-900 hover:text-blue-600">
            {source.title}
          </p>
          <p className="mt-1 text-xs text-gray-500">
            {source.publisher} · {formatSourceType(source.sourceType)}
          </p>
        </a>
      ))}
    </div>
  );
}

function Metric({
  label,
  value,
}: {
  label: string;
  value: number | string;
}) {
  return (
    <div>
      <p className="text-2xl font-semibold tabular-nums text-gray-900">
        {value}
      </p>
      <p className="mt-1 text-xs text-gray-500">{label}</p>
    </div>
  );
}

function issueStatusTone(status?: string): VerdictTone {
  if (status === "verified" || status === "completed" || status === "resolved") {
    return "positive";
  }
  if (status === "blocked") return "neutral";
  if (status === "high" || status === "danger") return "danger";
  if (status === "needs_review" || status === "updated" || status === "running") {
    return "warning";
  }
  return "neutral";
}
