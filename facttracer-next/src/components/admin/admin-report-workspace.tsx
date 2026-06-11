"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { AdminReportResolveButtons } from "@/components/admin/admin-actions";
import { AdminFilterControls } from "@/components/admin/admin-filter-controls";
import {
  matchesSearch,
  statusTone,
  uniqueOptions,
} from "@/components/admin/admin-workspace-utils";
import { EmptyState } from "@/components/common/empty-state";
import { StatusBadge } from "@/components/status-badge";
import type { ModerationReport } from "@/lib/api/types";
import { formatDateTime, formatStatus, formatTargetType } from "@/lib/display";

function formatReportStatus(value?: string | null) {
  switch (value) {
    case "open":
      return "접수";
    case "resolved":
      return "정제 완료";
    case "dismissed":
      return "기각";
    default:
      return formatStatus(value);
  }
}

function formatReportSubmittedAt(value?: string | null) {
  if (!value) return "시점 확인 전";

  const trimmed = value.trim();
  if (/^\d{2}[-.]\d{2}(\s+\d{2}:\d{2})?$/.test(trimmed)) {
    return trimmed;
  }

  return formatDateTime(value);
}

export function AdminReportWorkspace({
  loadFailed = false,
  reports,
}: {
  loadFailed?: boolean;
  reports: ModerationReport[];
}) {
  const [query, setQuery] = useState("");
  const [priority, setPriority] = useState("");
  const [status, setStatus] = useState("");

  const priorityOptions = useMemo(
    () => uniqueOptions(reports.map((report) => report.priority), formatStatus),
    [reports],
  );
  const statusOptions = useMemo(
    () =>
      uniqueOptions(reports.map((report) => report.status), formatReportStatus),
    [reports],
  );
  const filteredReports = useMemo(
    () =>
      reports.filter(
        (report) =>
          matchesSearch(query, [
            report.issueTitle,
            report.excerpt,
            report.reason,
            report.targetType,
            report.priority,
            formatStatus(report.priority),
            report.status,
            formatReportStatus(report.status),
          ]) &&
          (!priority || report.priority === priority) &&
          (!status || report.status === status),
      ),
    [priority, query, reports, status],
  );
  const hasActiveFilters = Boolean(query.trim() || priority || status);
  const isLoadFailure = loadFailed && reports.length === 0;
  const isTrueEmpty = !loadFailed && reports.length === 0 && !hasActiveFilters;

  return (
    <section>
      <AdminFilterControls
        count={filteredReports.length}
        onClear={() => {
          setQuery("");
          setPriority("");
          setStatus("");
        }}
        onQueryChange={setQuery}
        query={query}
        resultLabel="신고"
        selects={[
          {
            label: "우선순위",
            onChange: setPriority,
            options: priorityOptions,
            value: priority,
          },
          {
            label: "상태",
            onChange: setStatus,
            options: statusOptions,
            value: status,
          },
        ]}
      />
      <div className="divide-y divide-gray-100 border-b border-gray-200">
        {filteredReports.length > 0 ? (
          filteredReports.map((report) => (
            <div
              key={report.id}
              className="grid gap-5 py-5 lg:grid-cols-[minmax(0,1fr)_220px]"
            >
              <div>
                <div className="flex flex-wrap gap-3">
                  <StatusBadge tone={statusTone(report.priority)}>
                    {formatStatus(report.priority)}
                  </StatusBadge>
                  <StatusBadge tone={statusTone(report.status)}>
                    {formatReportStatus(report.status)}
                  </StatusBadge>
                  <span className="text-sm text-gray-500">
                    {report.reason}
                  </span>
                </div>
                <Link
                  href={`/admin/issues/${report.issueId}`}
                  className="mt-2 block font-semibold leading-7 text-gray-900 hover:text-blue-600"
                >
                  {report.issueTitle}
                </Link>
                <p className="mt-1 text-sm leading-6 text-gray-600">
                  {report.excerpt}
                </p>
                <p className="mt-1 text-xs font-medium text-gray-500">
                  대상 {formatTargetType(report.targetType)} · 접수{" "}
                  {formatReportSubmittedAt(report.submittedAt)}
                </p>
              </div>
              <AdminReportResolveButtons reportId={report.id} />
            </div>
          ))
        ) : (
          <EmptyState
            title={
              isLoadFailure
                ? "신고 표현을 불러오지 못했습니다"
                : isTrueEmpty
                  ? "처리할 신고 표현이 없습니다"
                : "조건에 맞는 신고 표현이 없습니다"
            }
            description={
              isLoadFailure
                ? "연결 상태를 확인한 뒤 다시 시도해 주세요."
                : isTrueEmpty
                  ? "접수된 신고가 생기면 이 목록에 표시됩니다."
                : "필터를 초기화하거나 검토 목록에서 민감 이슈를 확인해 주세요."
            }
            action={
              <Link
                href="/admin"
                className="inline-flex h-10 items-center rounded-md bg-blue-600 px-4 text-sm font-medium text-white"
              >
                검토 목록 보기
              </Link>
            }
          />
        )}
      </div>
    </section>
  );
}
