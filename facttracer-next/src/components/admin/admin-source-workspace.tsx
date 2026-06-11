"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { AdminSourceConfigForm } from "@/components/admin/admin-actions";
import { AdminFilterControls } from "@/components/admin/admin-filter-controls";
import {
  matchesSearch,
  statusTone,
  uniqueOptions,
} from "@/components/admin/admin-workspace-utils";
import { EmptyState } from "@/components/common/empty-state";
import { StatusBadge } from "@/components/status-badge";
import type { SourceDomain } from "@/lib/api/types";
import {
  formatCredibility,
  formatSourceType,
  formatStatus,
} from "@/lib/display";

const activeOptions = [
  { label: "수집 활성", value: "active" },
  { label: "수집 중지", value: "inactive" },
];

function formatActiveState(isActive: boolean) {
  return isActive ? "수집 활성" : "수집 중지";
}

function formatSourceStatus(value?: string | null) {
  if (value === "trusted") return "신뢰";
  if (value === "watch") return "감시";
  if (value === "blocked") return "차단";
  return formatStatus(value);
}

export function AdminSourceWorkspace({
  loadFailed = false,
  sources,
}: {
  loadFailed?: boolean;
  sources: SourceDomain[];
}) {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const [activeState, setActiveState] = useState("");

  const statusOptions = useMemo(
    () =>
      uniqueOptions(sources.map((source) => source.status), formatSourceStatus),
    [sources],
  );
  const filteredSources = useMemo(
    () =>
      sources.filter(
        (source) =>
          matchesSearch(query, [
            source.name,
            source.domain,
            source.sourceType,
            formatSourceType(source.sourceType),
            source.note,
            source.collectionUrl,
            source.status,
            formatSourceStatus(source.status),
            source.lastCollectionStatus,
          ]) &&
          (!status || source.status === status) &&
          (activeState === "active"
            ? source.isActive
            : activeState === "inactive"
              ? !source.isActive
              : true),
      ),
    [activeState, query, sources, status],
  );
  const hasActiveFilters = Boolean(query.trim() || status || activeState);
  const isLoadFailure = loadFailed && sources.length === 0;
  const isTrueEmpty = !loadFailed && sources.length === 0 && !hasActiveFilters;

  return (
    <section className="space-y-6">
      <section className="border-y border-gray-200 py-5">
        <div className="mb-4">
          <h2 className="text-base font-bold text-gray-900">새 출처 등록</h2>
          <p className="mt-1 text-sm leading-6 text-gray-600">
            공식자료, 언론, SNS 후보의 수집 대상과 신뢰도 기준을 등록합니다.
          </p>
        </div>
        <AdminSourceConfigForm />
      </section>

      <section>
        <AdminFilterControls
          count={filteredSources.length}
          onClear={() => {
            setQuery("");
            setStatus("");
            setActiveState("");
          }}
          onQueryChange={setQuery}
          query={query}
          resultLabel="출처"
          selects={[
            {
              label: "상태",
              onChange: setStatus,
              options: statusOptions,
              value: status,
            },
            {
              label: "수집",
              onChange: setActiveState,
              options: activeOptions,
              value: activeState,
            },
          ]}
        />

        <div className="divide-y divide-gray-100 border-b border-gray-200">
          {filteredSources.length > 0 ? (
            filteredSources.map((source) => (
              <div
                key={source.id}
                className="grid gap-5 py-5 2xl:grid-cols-[minmax(0,0.8fr)_minmax(560px,1.2fr)]"
              >
                <div>
                  <div className="flex flex-wrap gap-3">
                    <StatusBadge tone={statusTone(source.status)}>
                      {formatSourceStatus(source.status)}
                    </StatusBadge>
                    <StatusBadge
                      tone={source.isActive ? "positive" : "neutral"}
                    >
                      {formatActiveState(source.isActive)}
                    </StatusBadge>
                    <StatusBadge tone={statusTone(source.lastCollectionStatus)}>
                      최근 {formatStatus(source.lastCollectionStatus) || "idle"}
                    </StatusBadge>
                  </div>
                  <h2 className="mt-3 font-bold text-gray-900">
                    {source.name}
                  </h2>
                  <p className="mt-1 text-sm leading-6 text-gray-500">
                    식별자 {source.domain}
                  </p>
                  {source.collectionUrl ? (
                    <p className="mt-1 break-all text-sm leading-6 text-gray-600">
                      수집 링크{" "}
                      <a
                        href={source.collectionUrl}
                        target="_blank"
                        rel="noreferrer"
                        className="font-medium text-blue-600 hover:underline"
                      >
                        {source.collectionUrl}
                      </a>
                    </p>
                  ) : null}
                  <p className="mt-1 text-sm leading-6 text-gray-600">
                    메모: {source.note || "없음"}
                  </p>
                  <div className="mt-3 grid grid-cols-2 gap-2 text-sm leading-6 text-gray-600 sm:grid-cols-3">
                    <p>유형 {formatSourceType(source.sourceType)}</p>
                    <p>{formatCredibility(source.credibility)}</p>
                    <p>
                      주기{" "}
                      {source.collectionIntervalMinutes
                        ? `${source.collectionIntervalMinutes}분`
                        : "-"}
                    </p>
                    <p>수집 {formatActiveState(source.isActive)}</p>
                    <p>
                      최근 수집{" "}
                      {formatStatus(source.lastCollectionStatus) || "idle"}
                    </p>
                    <p>상태 {formatSourceStatus(source.status)}</p>
                  </div>
                </div>
                <AdminSourceConfigForm source={source} />
              </div>
            ))
          ) : (
            <EmptyState
              title={
                isLoadFailure
                  ? "출처 목록을 불러오지 못했습니다"
                  : isTrueEmpty
                  ? "관리할 출처가 없습니다"
                  : "조건에 맞는 출처가 없습니다"
              }
              description={
                isLoadFailure
                  ? "연결 상태를 확인한 뒤 다시 시도해 주세요."
                  : isTrueEmpty
                  ? "관리 대상 출처가 생기면 신뢰도와 상태가 표시됩니다."
                  : "필터를 초기화하거나 새 출처를 등록해 수집 기준을 보강하세요."
              }
              action={
                <Link
                  href="/admin"
                  className="inline-flex h-10 items-center rounded-md bg-blue-600 px-4 text-sm font-medium text-white"
                >
                  운영 콘솔 보기
                </Link>
              }
            />
          )}
        </div>
      </section>
    </section>
  );
}
