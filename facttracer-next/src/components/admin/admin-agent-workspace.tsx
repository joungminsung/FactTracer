"use client";

import { useMemo, useState } from "react";
import { AdminAgentRunButton } from "@/components/admin/admin-actions";
import { AdminFilterControls } from "@/components/admin/admin-filter-controls";
import {
  matchesSearch,
  statusTone,
  uniqueOptions,
} from "@/components/admin/admin-workspace-utils";
import { EmptyState } from "@/components/common/empty-state";
import { StatusBadge } from "@/components/status-badge";
import type { AgentRun, IssueTimelineEvent } from "@/lib/api/types";
import {
  formatDateTime,
  formatProcessingName,
} from "@/lib/display";

function formatAgentStatus(value?: string | null) {
  if (value === "completed") return "완료";
  if (value === "running") return "실행 중";
  if (value === "needs_review") return "검토 필요";
  if (value === "failed") return "실패";
  return value || "";
}

function getEmptyState({
  hasActiveFilters,
  loadFailed,
}: {
  hasActiveFilters: boolean;
  loadFailed: boolean;
}) {
  if (loadFailed) {
    return {
      description: "연결 상태를 확인한 뒤 다시 시도해 주세요.",
      title: "자동 처리 정보를 불러오지 못했습니다",
    };
  }

  if (hasActiveFilters) {
    return {
      description: "필터를 초기화하거나 검색어를 조정해 주세요.",
      title: "조건에 맞는 자동 처리 기록이 없습니다",
    };
  }

  return {
    description: "자동 처리 결과가 생기면 이 목록에 표시됩니다.",
    title: "자동 처리 기록이 없습니다",
  };
}

export function AdminAgentWorkspace({
  agentRuns,
  loadFailed = false,
  recentEvents,
}: {
  agentRuns: AgentRun[];
  loadFailed?: boolean;
  recentEvents: IssueTimelineEvent[];
}) {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");

  const statusOptions = useMemo(
    () => uniqueOptions(agentRuns.map((run) => run.status), formatAgentStatus),
    [agentRuns],
  );
  const effectiveStatus = statusOptions.some((option) => option.value === status)
    ? status
    : "";

  const filteredRuns = useMemo(
    () =>
      agentRuns.filter(
        (run) =>
          matchesSearch(query, [
            run.agent,
            formatProcessingName(run.agent),
            run.target,
            run.status,
            formatAgentStatus(run.status),
            run.failureReason,
            run.finishedAt,
            formatDateTime(run.finishedAt),
          ]) &&
          (!effectiveStatus || run.status === effectiveStatus),
      ),
    [agentRuns, effectiveStatus, query],
  );
  const hasActiveFilters = Boolean(query.trim() || effectiveStatus);
  const emptyState = getEmptyState({ hasActiveFilters, loadFailed });

  function clearFilters() {
    setQuery("");
    setStatus("");
  }

  return (
    <section className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_340px]">
      <div className="min-w-0">
        <AdminFilterControls
          count={filteredRuns.length}
          onClear={clearFilters}
          onQueryChange={setQuery}
          query={query}
          resultLabel="자동 처리"
          selects={[
            {
              label: "상태",
              onChange: setStatus,
              options: statusOptions,
              value: effectiveStatus,
            },
          ]}
        />

        <div className="border-b border-gray-200">
          {filteredRuns.length > 0 ? (
            <>
              <div className="hidden border-b border-gray-200 py-2 text-xs font-medium text-gray-500 lg:grid lg:grid-cols-[minmax(0,1fr)_120px_150px_80px] lg:gap-4">
                <span>자동 처리</span>
                <span>상태</span>
                <span>시점</span>
                <span className="text-right">실행</span>
              </div>
              <div className="divide-y divide-gray-100">
                {filteredRuns.map((run) => {
                  const processingName = formatProcessingName(run.agent);
                  const finishedAt = formatDateTime(run.finishedAt);

                  return (
                    <div
                      key={`${run.agent}-${run.target}-${run.finishedAt}`}
                      className="grid gap-3 py-4 lg:grid-cols-[minmax(0,1fr)_120px_150px_80px] lg:items-center lg:gap-4"
                    >
                      <div className="min-w-0">
                        <h2 className="font-semibold text-gray-900">
                          {processingName}
                        </h2>
                        <p className="mt-1 break-words text-sm leading-6 text-gray-500">
                          대상 {run.target || "-"}
                          {run.agent !== processingName
                            ? ` · 원본 ${run.agent}`
                            : ""}
                        </p>
                        {run.failureReason ? (
                          <p className="mt-1 text-sm font-semibold leading-6 text-red-600">
                            실패 사유: {run.failureReason}
                          </p>
                        ) : null}
                      </div>
                      <StatusBadge tone={statusTone(run.status)}>
                        {formatAgentStatus(run.status)}
                      </StatusBadge>
                      <p className="text-sm leading-6 text-gray-500">
                        <span className="lg:hidden">시점 </span>
                        {finishedAt}
                      </p>
                      <div className="lg:justify-self-end">
                        <AdminAgentRunButton agent={run.agent} />
                      </div>
                    </div>
                  );
                })}
              </div>
            </>
          ) : (
            <EmptyState
              title={emptyState.title}
              description={emptyState.description}
              action={
                hasActiveFilters ? (
                  <button
                    type="button"
                    onClick={clearFilters}
                    className="inline-flex h-10 items-center rounded-md border border-gray-300 px-4 text-sm font-medium text-gray-700 hover:bg-gray-50"
                  >
                    필터 초기화
                  </button>
                ) : null
              }
            />
          )}
        </div>
      </div>

      <aside className="border-b border-gray-200 pb-6 lg:sticky lg:top-8 lg:self-start">
        <div className="border-y border-gray-200 py-4">
          <h2 className="text-base font-bold text-gray-900">최근 이벤트</h2>
          <div className="mt-4 divide-y divide-gray-100 border-t border-gray-200">
            {recentEvents.length > 0 ? (
              recentEvents.map((event) => (
                <div key={event.id} className="py-4">
                  <p className="text-xs font-medium text-blue-600">
                    {formatProcessingName(event.type)} · 발생{" "}
                    {formatDateTime(event.occurredAt)}
                  </p>
                  <h3 className="mt-2 text-sm font-bold text-gray-900">
                    {event.title}
                  </h3>
                  <p className="mt-1 text-sm leading-6 text-gray-500">
                    {event.description}
                  </p>
                </div>
              ))
            ) : (
              <p className="py-4 text-sm leading-7 text-gray-500">
                최근 이벤트가 없습니다.
              </p>
            )}
          </div>
        </div>
      </aside>
    </section>
  );
}
