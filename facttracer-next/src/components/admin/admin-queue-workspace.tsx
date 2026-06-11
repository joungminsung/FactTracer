"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import {
  Bot,
  CheckCircle2,
  FileText,
  Gauge,
  SlidersHorizontal,
  TriangleAlert,
} from "lucide-react";
import {
  AdminIssueActionButtons,
  AdminQueueSyncButton,
  AdminReverificationForm,
} from "@/components/admin/admin-actions";
import { AdminFilterControls } from "@/components/admin/admin-filter-controls";
import {
  matchesSearch,
  statusTone,
  uniqueOptions,
} from "@/components/admin/admin-workspace-utils";
import { EmptyState } from "@/components/common/empty-state";
import { StatusBadge } from "@/components/status-badge";
import type {
  AgentRun,
  AdminDashboardResponse,
  AdminQueueItem,
  Claim,
  ClaimCluster,
  Evidence,
} from "@/lib/api/types";
import {
  formatCredibility,
  formatDateTime,
  formatProcessingName,
  formatStatus,
} from "@/lib/display";

const reviewSteps = [
  ["수집", "기사와 자료 수집 상태 확인"],
  ["AI 초안", "자동 주장 추출 결과 점검"],
  ["출처 확인", "공식 자료와 기준 시점 대조"],
  ["주장 검토", "반론, 공통분모, 보류 사유 확인"],
  ["표현 정제", "낙인/단정 표현 제거"],
  ["게시 승인", "체크리스트와 판단 메모 기록"],
];

function formatQueueDetectedAt(value?: string | null) {
  if (!value) return "시점 확인 전";

  const trimmed = value.trim();
  if (/^\d{2}[-.]\d{2}(\s+\d{2}:\d{2})?$/.test(trimmed)) {
    return trimmed;
  }

  return formatDateTime(value);
}

export function AdminQueueWorkspace({
  dashboard,
  needsAuthForRealApi,
}: {
  dashboard: AdminDashboardResponse;
  needsAuthForRealApi: boolean;
}) {
  const [query, setQuery] = useState("");
  const [priority, setPriority] = useState("");
  const [status, setStatus] = useState("");
  const [topic, setTopic] = useState("");

  const priorityOptions = useMemo(
    () => uniqueOptions(dashboard.queue.map((item) => item.priority), formatStatus),
    [dashboard.queue],
  );
  const statusOptions = useMemo(
    () => uniqueOptions(dashboard.queue.map((item) => item.status), formatStatus),
    [dashboard.queue],
  );
  const topicOptions = useMemo(
    () => uniqueOptions(dashboard.queue.map((item) => item.topic)),
    [dashboard.queue],
  );
  const filteredQueue = useMemo(
    () =>
      dashboard.queue.filter(
        (item) =>
          matchesSearch(query, [
            item.id,
            item.title,
            item.reason,
            item.topic,
            item.priority,
            formatStatus(item.priority),
            item.status,
            formatStatus(item.status),
          ]) &&
          (!priority || item.priority === priority) &&
          (!status || item.status === status) &&
          (!topic || item.topic === topic),
      ),
    [dashboard.queue, priority, query, status, topic],
  );

  const hasActiveFilters = Boolean(query.trim() || priority || status || topic);
  const selectedIssue = hasActiveFilters
    ? filteredQueue.find((item) => item.id === dashboard.selectedIssue?.id) ??
      filteredQueue[0] ??
      null
    : dashboard.selectedIssue ?? dashboard.queue[0] ?? null;
  const selectedIssueHasDashboardDetails =
    selectedIssue?.id === dashboard.selectedIssue?.id;

  return (
    <div className="space-y-8">
      {needsAuthForRealApi ? (
        <section className="rounded-md border border-gray-200 bg-amber-50 px-4 py-3 text-sm font-medium text-amber-700">
          운영 화면을 보려면 로그인이 필요합니다.
        </section>
      ) : null}

      <section className="grid gap-8 xl:grid-cols-[minmax(0,1fr)_360px]">
        <article className="min-w-0">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h2 className="text-lg font-semibold text-gray-900">
                검토 우선순위 목록
              </h2>
              <p className="mt-1 text-sm text-gray-500">
                고영향 이슈, 공식 자료 갱신, 수치 충돌, 신고 증가를 먼저 확인합니다.
              </p>
            </div>
            <AdminQueueSyncButton />
          </div>

          <AdminFilterControls
            count={filteredQueue.length}
            onClear={() => {
              setQuery("");
              setPriority("");
              setStatus("");
              setTopic("");
            }}
            onQueryChange={setQuery}
            query={query}
            resultLabel="검토 항목"
            selects={[
              { label: "우선순위", onChange: setPriority, options: priorityOptions, value: priority },
              { label: "상태", onChange: setStatus, options: statusOptions, value: status },
              { label: "분야", onChange: setTopic, options: topicOptions, value: topic },
            ]}
          />

          <QueueList items={filteredQueue} selectedIssueId={selectedIssue?.id ?? null} />
          <SelectedIssueReview
            claims={selectedIssueHasDashboardDetails ? dashboard.claims : []}
            clusters={
              selectedIssueHasDashboardDetails ? dashboard.claimClusters : []
            }
            evidences={
              selectedIssueHasDashboardDetails ? dashboard.evidences : []
            }
            issue={selectedIssue}
          />
        </article>

        <AdminQueueRail
          agentRuns={dashboard.agentRuns}
          selectedIssue={selectedIssue}
        />
      </section>
    </div>
  );
}

function QueueList({
  items,
  selectedIssueId,
}: {
  items: AdminQueueItem[];
  selectedIssueId: string | null;
}) {
  if (items.length === 0) {
    return (
      <div className="mt-6">
        <EmptyState
          title="검토할 이슈가 없습니다"
          description="목록이 비어 있으면 새 기사 수집 상태, 신고 표현, 출처 기준, 자동 처리 실패 기록을 먼저 확인합니다."
          action={
            <div className="flex flex-wrap gap-2">
              {[
                ["출처 관리", "/admin/sources"],
                ["신고 표현 처리", "/admin/reports"],
                ["자동 처리 기록", "/admin/agents"],
              ].map(([label, href]) => (
                <Link
                  key={href}
                  href={href}
                  className="inline-flex h-9 items-center rounded-md border border-gray-200 px-3 text-xs font-bold text-gray-700 hover:border-gray-300 hover:bg-gray-50"
                >
                  {label}
                </Link>
              ))}
            </div>
          }
        />
      </div>
    );
  }

  return (
    <div className="mt-6 border-y border-gray-200">
      {items.map((item) => {
        const isSelected = item.id === selectedIssueId;

        return (
          <Link
            key={item.id}
            href={`/admin/issues/${item.id}`}
            aria-current={isSelected ? "page" : undefined}
            className={`grid w-full gap-4 border-b border-gray-200 py-5 pr-4 text-left last:border-b-0 lg:grid-cols-[120px_minmax(0,1fr)_112px_112px_112px] ${
              isSelected
                ? "border-l-2 border-blue-600 bg-gray-50 pl-4"
                : "pl-0 hover:bg-gray-50"
            }`}
          >
            <div>
              <p className="text-xs font-semibold text-gray-500">{item.id}</p>
              <p className="mt-1 text-xs text-gray-500">
                {formatQueueDetectedAt(item.firstDetectedAt)}
              </p>
            </div>
            <div>
              <h3 className="font-bold leading-6 text-gray-900">
                {item.title}
              </h3>
              <p className="mt-1 text-sm leading-6 text-gray-500">
                {item.reason}
              </p>
            </div>
            <div className="text-sm font-semibold text-gray-600">
              {item.topic}
              <p className="mt-1 text-xs font-semibold text-gray-500">
                기사 {item.articleCount}
              </p>
            </div>
            <StatusBadge tone={statusTone(item.priority)}>
              {formatStatus(item.priority)}
            </StatusBadge>
            <StatusBadge tone={statusTone(item.status)}>
              {formatStatus(item.status)}
            </StatusBadge>
          </Link>
        );
      })}
    </div>
  );
}

function SelectedIssueReview({
  claims,
  clusters,
  evidences,
  issue,
}: {
  claims: Claim[];
  clusters: ClaimCluster[];
  evidences: Evidence[];
  issue: AdminQueueItem | null;
}) {
  if (!issue) {
    return (
      <section className="mt-8 border-y border-gray-200 py-6">
        <h2 className="text-xl font-bold text-gray-900">
          검토 항목을 선택하면 상세 판정이 열립니다
        </h2>
        <p className="mt-2 max-w-2xl text-sm leading-7 text-gray-500">
          큐의 이슈를 열면 주장 검수, 쟁점 판정, 출처 기준, 게시 전 체크리스트가 한 화면에 연결됩니다.
        </p>
      </section>
    );
  }

  return (
    <section className="mt-8 border-b border-gray-200 pb-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex flex-wrap items-center gap-2 text-sm font-semibold text-gray-600">
            <span>{issue.topic}</span>
            <StatusBadge tone={statusTone(issue.status)}>
              {formatStatus(issue.status)}
            </StatusBadge>
          </div>
          <h2 className="mt-2 text-2xl font-bold text-gray-900">
            {issue.title}
          </h2>
          <p className="mt-2 max-w-2xl text-sm leading-7 text-gray-600">
            {issue.reason}
          </p>
        </div>
        <AdminIssueActionButtons issueId={issue.id} />
      </div>

      <ReviewWorkflow />
      <ReviewSectionIndex
        claims={claims}
        clusters={clusters}
        evidences={evidences}
      />
    </section>
  );
}

function ReviewWorkflow() {
  return (
    <div className="mt-6 border-y border-gray-200 py-4">
      <p className="text-xs font-bold text-gray-500">검토 단계</p>
      <ol className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-6">
        {reviewSteps.map(([title, description], index) => (
          <li
            key={title}
            className={`min-h-24 border border-gray-200 px-3 py-3 ${
              index < 2 ? "bg-gray-50" : "bg-white"
            }`}
          >
            <p className="text-sm font-bold text-gray-900">{title}</p>
            <p className="mt-2 text-xs leading-5 text-gray-600">
              {description}
            </p>
          </li>
        ))}
      </ol>
    </div>
  );
}

function ReviewSectionIndex({
  claims,
  clusters,
  evidences,
}: {
  claims: Claim[];
  clusters: ClaimCluster[];
  evidences: Evidence[];
}) {
  const visibleClaims = claims.slice(0, 4);
  const visibleClusters = clusters.slice(0, 4);
  const visibleEvidences = evidences.slice(0, 4);

  return (
    <div className="mt-8 grid gap-8 xl:grid-cols-3">
      <section>
        <div className="flex items-center gap-2">
          <CheckCircle2 className="size-4 text-blue-600" aria-hidden="true" />
          <h3 className="text-base font-bold text-gray-900">주장 검수</h3>
        </div>
        <div className="mt-4 divide-y divide-gray-100 border-y border-gray-200">
          {visibleClaims.length > 0 ? (
            visibleClaims.map((claim) => (
              <div key={claim.id ?? claim.text} className="py-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <p className="text-xs font-bold text-gray-500">
                    {claim.type}
                  </p>
                  <StatusBadge tone={claim.tone}>{claim.verdict}</StatusBadge>
                </div>
                <p className="mt-2 text-sm font-bold leading-6 text-gray-900">
                  {claim.text}
                </p>
                <p className="mt-2 text-sm leading-6 text-gray-500">
                  근거: {claim.evidence}
                </p>
                <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs font-semibold text-gray-500">
                  <span>처리: {formatStatus(claim.status)}</span>
                  <span>{formatCredibility(claim.confidence)}</span>
                </div>
              </div>
            ))
          ) : (
            <p className="py-4 text-sm leading-7 text-gray-500">
              검수할 주장이 없습니다.
            </p>
          )}
        </div>
      </section>

      <section>
        <div className="flex items-center gap-2">
          <SlidersHorizontal
            className="size-4 text-blue-600"
            aria-hidden="true"
          />
          <h3 className="text-base font-bold text-gray-900">쟁점 판정</h3>
        </div>
        <div className="mt-4 divide-y divide-gray-100 border-y border-gray-200">
          {visibleClusters.length > 0 ? (
            visibleClusters.map((cluster) => (
              <div key={cluster.title} className="py-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <h4 className="font-bold text-gray-900">{cluster.title}</h4>
                  <StatusBadge tone={cluster.tone}>
                    {cluster.verdict}
                  </StatusBadge>
                </div>
                <p className="mt-2 text-sm leading-6 text-gray-600">
                  {cluster.conflict}
                </p>
                <p className="mt-2 text-sm leading-6 text-gray-500">
                  공통분모: {cluster.commonGround}
                </p>
              </div>
            ))
          ) : (
            <p className="py-4 text-sm leading-7 text-gray-500">
              쟁점 판정 항목이 없습니다.
            </p>
          )}
        </div>
      </section>

      <section>
        <div className="flex items-center gap-2">
          <FileText className="size-4 text-blue-600" aria-hidden="true" />
          <h3 className="text-base font-bold text-gray-900">출처 기준</h3>
        </div>
        <div className="mt-4 divide-y divide-gray-100 border-y border-gray-200">
          {visibleEvidences.length > 0 ? (
            visibleEvidences.map((evidence) => (
              <div key={evidence.id ?? evidence.label} className="py-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <h4 className="font-bold text-gray-900">{evidence.label}</h4>
                  <span className="text-sm font-semibold text-gray-500">
                    {formatCredibility(evidence.credibility)}
                  </span>
                </div>
                <p className="mt-2 text-xs font-semibold text-gray-500">
                  {evidence.source} · {formatDateTime(evidence.date)}
                </p>
                <p className="mt-2 text-sm leading-6 text-gray-600">
                  {evidence.summary}
                </p>
              </div>
            ))
          ) : (
            <p className="py-4 text-sm leading-7 text-gray-500">
              출처 기준 항목이 없습니다.
            </p>
          )}
        </div>
      </section>
    </div>
  );
}

function AdminQueueRail({
  agentRuns,
  selectedIssue,
}: {
  agentRuns: AgentRun[];
  selectedIssue: AdminQueueItem | null;
}) {
  return (
    <aside className="xl:sticky xl:top-8 xl:self-start">
      <section className="border-b border-gray-200 py-6">
        <div className="flex items-center gap-2">
          <Bot className="size-4 text-blue-600" aria-hidden="true" />
          <h2 className="text-base font-bold text-gray-900">
            자동 처리 상태
          </h2>
        </div>
        <div className="mt-4 divide-y divide-gray-100 border-t border-gray-200">
          {agentRuns.length > 0 ? (
            agentRuns.map((run) => (
              <div key={`${run.agent}-${run.target}`} className="py-4">
                <div className="flex items-center justify-between gap-3">
                  <h3 className="text-sm font-bold text-gray-900">
                    {formatProcessingName(run.agent)}
                  </h3>
                  <StatusBadge tone={statusTone(run.status)}>
                    {formatStatus(run.status)}
                  </StatusBadge>
                </div>
                <p className="mt-2 text-sm leading-6 text-gray-500">
                  {run.target} · {formatDateTime(run.finishedAt)}
                </p>
                {run.failureReason ? (
                  <p className="mt-2 text-sm font-semibold leading-6 text-red-600">
                    실패 사유: {run.failureReason}
                  </p>
                ) : null}
              </div>
            ))
          ) : (
            <p className="py-4 text-sm leading-7 text-gray-500">
              자동 처리 기록이 없습니다.
            </p>
          )}
        </div>
      </section>

      <section className="border-b border-gray-200 py-6">
        <div className="flex items-center gap-2">
          <Gauge className="size-4 text-blue-600" aria-hidden="true" />
          <h2 className="text-base font-bold text-gray-900">재검증 실행</h2>
        </div>
        {selectedIssue ? (
          <AdminReverificationForm issueId={selectedIssue.id} />
        ) : (
          <p className="mt-4 text-sm leading-7 text-gray-500">
            재검증할 이슈가 없습니다.
          </p>
        )}
      </section>

      <section className="py-6">
        <div className="flex items-center gap-2">
          <TriangleAlert className="size-4 text-amber-600" aria-hidden="true" />
          <h2 className="text-base font-bold text-gray-900">출고 전 확인</h2>
        </div>
        <ul className="mt-4 space-y-3 text-sm leading-6 text-gray-600">
          {[
            "기사 전체를 가짜뉴스로 단정하지 않았는지 확인",
            "초기 보도와 후속 자료 기준이 분리됐는지 확인",
            "낙인 표현이 주장 유형으로 정제됐는지 확인",
          ].map((label) => (
            <li key={label} className="flex gap-2">
              <CheckCircle2
                className="mt-0.5 size-4 shrink-0 text-emerald-600"
                aria-hidden="true"
              />
              {label}
            </li>
          ))}
        </ul>
      </section>
    </aside>
  );
}
