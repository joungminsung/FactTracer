# Admin Console Enhancement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade FactTracer's existing `/admin` route set into a coherent operator review workspace with consistent page structure, local filters, stronger review context, and preserved API behavior.

**Architecture:** Keep data fetching in server route components, pass typed data into focused client workspace components, and reuse the existing admin action components for mutations. Shared layout primitives and filter controls provide consistent visual grammar across queue, reports, sources, agents, and settings.

**Tech Stack:** Next.js 16 App Router, React 19, TypeScript, Tailwind CSS 4, lucide-react, existing FactTracer API client.

---

## File Structure

Create:

- `src/components/admin/admin-workspace-utils.ts`
  Pure helper functions for text normalization, option extraction, local filtering, and status tone mapping.

- `src/components/admin/admin-filter-controls.tsx`
  Shared client filter bar for search, select filters, clear action, and result count copy.

- `src/components/admin/admin-queue-workspace.tsx`
  Client workspace for `/admin`: queue filters, queue rows, selected issue preview, claims/clusters/evidence, agent rail, re-verification, and publishing readiness.

- `src/components/admin/admin-report-workspace.tsx`
  Client workspace for `/admin/reports`: report search/status/priority filters and rows with existing resolve controls.

- `src/components/admin/admin-source-workspace.tsx`
  Client workspace for `/admin/sources`: source search/status/active filters, new source form, and source rows with existing config form.

- `src/components/admin/admin-agent-workspace.tsx`
  Client workspace for `/admin/agents`: agent search/status filters, agent rows, manual run controls, and recent events rail.

Modify:

- `src/components/common/design-system.tsx`
  Normalize `AdminPageHeader`, `AdminSurface`, and add small metric/header helpers only if needed.

- `src/app/admin/page.tsx`
  Fetch data server-side and delegate rendering to `AdminQueueWorkspace`.

- `src/app/admin/issues/[issueId]/page.tsx`
  Keep server fetch/error behavior, align header/surface style, improve detail/right rail hierarchy.

- `src/app/admin/reports/page.tsx`
  Fetch reports and delegate rendering to `AdminReportWorkspace`.

- `src/app/admin/sources/page.tsx`
  Fetch sources and delegate rendering to `AdminSourceWorkspace`.

- `src/app/admin/agents/page.tsx`
  Fetch agents/events and delegate rendering to `AdminAgentWorkspace`.

- `src/app/admin/settings/page.tsx`
  Use shared admin header/surface and improve failure copy.

Do not modify:

- Backend API contracts.
- Auth/session code.
- Existing public routes.
- Existing admin mutation functions except for class name polish if a task explicitly touches the owning component.

## Verification Baseline

- [ ] **Step 1: Record current verification baseline**

Run:

```bash
npm run lint
npm run build
```

Expected:

- If both pass, continue and use the output as the clean baseline.
- If either fails before edits, record the exact failure in the implementation notes and continue only if it is unrelated to admin code. Do not fix unrelated failures in this plan.

---

### Task 1: Shared Admin Layout And Filter Primitives

**Files:**
- Modify: `src/components/common/design-system.tsx`
- Create: `src/components/admin/admin-workspace-utils.ts`
- Create: `src/components/admin/admin-filter-controls.tsx`

- [ ] **Step 1: Update `design-system.tsx` shared admin primitives**

Replace the current `AdminSurface` and `AdminPageHeader` implementations with this contract. Keep existing exports `PageShell`, `WorkSurface`, and `PageIntro` unchanged unless TypeScript requires import sorting.

```tsx
export function AdminSurface({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return <section className={`bg-white ${className}`}>{children}</section>;
}

export function AdminPageHeader({
  backHref = "/admin",
  backLabel = "운영 콘솔",
  children,
  description,
  eyebrow,
  title,
}: {
  backHref?: string;
  backLabel?: string;
  children?: ReactNode;
  description: string;
  eyebrow?: ReactNode;
  title: string;
}) {
  return (
    <AdminSurface className="py-10">
      <Link href={backHref} className="text-sm font-medium text-blue-600 hover:underline">
        {backLabel}
      </Link>
      {eyebrow ? (
        <div className="mt-5 text-xs font-medium uppercase tracking-wide text-gray-500">
          {eyebrow}
        </div>
      ) : null}
      <h1 className="mt-2 max-w-4xl text-2xl font-bold tracking-tight text-gray-900 sm:text-3xl">
        {title}
      </h1>
      <p className="mt-3 max-w-[680px] text-[15px] leading-7 text-gray-700">
        {description}
      </p>
      {children ? <div className="mt-6">{children}</div> : null}
    </AdminSurface>
  );
}

export function AdminMetricStrip({
  metrics,
}: {
  metrics: Array<{ label: string; value: string | number }>;
}) {
  if (metrics.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-x-8 gap-y-4 border-y border-gray-200 py-4">
      {metrics.map((metric) => (
        <div key={metric.label} className="min-w-24">
          <p className="text-2xl font-semibold tabular-nums text-gray-900">
            {metric.value}
          </p>
          <p className="mt-1 text-xs font-medium text-gray-500">
            {metric.label}
          </p>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Create `admin-workspace-utils.ts`**

Add this file:

```ts
import type { VerdictTone } from "@/lib/api/types";

export type FilterOption = {
  label: string;
  value: string;
};

export function normalizeSearchValue(value?: string | number | null) {
  return String(value ?? "")
    .trim()
    .toLocaleLowerCase("ko-KR");
}

export function matchesSearch(query: string, values: Array<string | number | null | undefined>) {
  const normalizedQuery = normalizeSearchValue(query);
  if (!normalizedQuery) return true;

  return values.some((value) =>
    normalizeSearchValue(value).includes(normalizedQuery),
  );
}

export function uniqueOptions(
  values: Array<string | null | undefined>,
  formatter: (value: string) => string = (value) => value,
) {
  return Array.from(
    new Set(values.map((value) => value?.trim()).filter(Boolean) as string[]),
  )
    .sort((a, b) => formatter(a).localeCompare(formatter(b), "ko-KR"))
    .map((value) => ({ label: formatter(value), value }));
}

export function statusTone(value?: string | null): VerdictTone {
  switch (value) {
    case "completed":
    case "resolved":
    case "trusted":
    case "verified":
      return "positive";
    case "high":
    case "needs_review":
    case "open":
    case "running":
    case "watch":
      return "warning";
    case "blocked":
    case "dismissed":
    case "failed":
    case "dead_letter":
      return "danger";
    default:
      return "neutral";
  }
}
```

- [ ] **Step 3: Create `admin-filter-controls.tsx`**

Add this client component:

```tsx
"use client";

import { Search, X } from "lucide-react";
import type { FilterOption } from "@/components/admin/admin-workspace-utils";

export type AdminSelectFilter = {
  label: string;
  onChange: (value: string) => void;
  options: FilterOption[];
  value: string;
};

export function AdminFilterControls({
  count,
  onClear,
  onQueryChange,
  query,
  resultLabel,
  selects,
}: {
  count: number;
  onClear: () => void;
  onQueryChange: (value: string) => void;
  query: string;
  resultLabel: string;
  selects: AdminSelectFilter[];
}) {
  const hasFilters = Boolean(query) || selects.some((filter) => filter.value);

  return (
    <div className="border-y border-gray-200 py-4">
      <div className="grid gap-3 lg:grid-cols-[minmax(220px,1fr)_auto]">
        <label className="relative block">
          <span className="sr-only">검색</span>
          <Search
            className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-gray-400"
            aria-hidden="true"
          />
          <input
            value={query}
            onChange={(event) => onQueryChange(event.target.value)}
            className="h-10 w-full rounded-md border border-gray-300 bg-white pr-3 pl-9 text-sm font-medium text-gray-900 outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-600/20"
            placeholder="제목, 사유, 상태로 검색"
          />
        </label>
        <div className="flex flex-wrap gap-2">
          {selects.map((filter) => (
            <label
              key={filter.label}
              className="grid min-w-36 gap-1 text-xs font-medium text-gray-500"
            >
              {filter.label}
              <select
                value={filter.value}
                onChange={(event) => filter.onChange(event.target.value)}
                className="h-10 rounded-md border border-gray-300 bg-white px-3 text-sm font-medium text-gray-900 outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-600/20"
              >
                <option value="">전체</option>
                {filter.options.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
          ))}
          <button
            type="button"
            onClick={onClear}
            disabled={!hasFilters}
            className="mt-auto inline-flex h-10 items-center gap-2 rounded-md border border-gray-300 px-3 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <X className="size-4" aria-hidden="true" />
            초기화
          </button>
        </div>
      </div>
      <p className="mt-3 text-sm text-gray-500">
        {resultLabel} {count.toLocaleString("ko-KR")}건
      </p>
    </div>
  );
}
```

- [ ] **Step 4: Run focused verification**

Run:

```bash
npm run lint
```

Expected: PASS. If it fails, fix only issues introduced in the three files above.

- [ ] **Step 5: Commit**

```bash
git add src/components/common/design-system.tsx src/components/admin/admin-workspace-utils.ts src/components/admin/admin-filter-controls.tsx
git commit -m "feat: add admin workspace primitives"
```

---

### Task 2: Admin Queue Workspace

**Files:**
- Create: `src/components/admin/admin-queue-workspace.tsx`
- Modify: `src/app/admin/page.tsx`

- [ ] **Step 1: Create `admin-queue-workspace.tsx` imports and helpers**

Start the file with these imports and local constants:

```tsx
"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { Bot, CheckCircle2, FileText, Gauge, SlidersHorizontal, TriangleAlert } from "lucide-react";
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
import type { AgentRun, AdminDashboardResponse, AdminQueueItem, Claim, ClaimCluster, Evidence } from "@/lib/api/types";
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
```

- [ ] **Step 2: Add filtered workspace shell**

Implement this top-level component contract. Keep rendering functions below it in the same file.

```tsx
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
            item.status,
          ]) &&
          (!priority || item.priority === priority) &&
          (!status || item.status === status) &&
          (!topic || item.topic === topic),
      ),
    [dashboard.queue, priority, query, status, topic],
  );

  const selectedIssue =
    dashboard.selectedIssue ??
    filteredQueue[0] ??
    dashboard.queue[0] ??
    null;

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
            claims={dashboard.claims}
            clusters={dashboard.claimClusters}
            evidences={dashboard.evidences}
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
```

- [ ] **Step 3: Add queue, selected issue, and rail render helpers**

Implement these functions in the same file:

```tsx
function QueueList({
  items,
  selectedIssueId,
}: {
  items: AdminQueueItem[];
  selectedIssueId: string | null;
}) {
  if (items.length === 0) {
    return (
      <EmptyState
        title="조건에 맞는 검토 항목이 없습니다"
        description="필터를 초기화하거나 출처 관리, 신고 표현, 자동 처리 기록을 확인해 주세요."
        action={
          <div className="flex flex-wrap gap-2">
            <Link href="/admin/sources" className="inline-flex h-10 items-center rounded-md border border-gray-300 px-4 text-sm font-medium text-gray-700 hover:bg-gray-50">
              출처 관리
            </Link>
            <Link href="/admin/reports" className="inline-flex h-10 items-center rounded-md border border-gray-300 px-4 text-sm font-medium text-gray-700 hover:bg-gray-50">
              신고 표현
            </Link>
            <Link href="/admin/agents" className="inline-flex h-10 items-center rounded-md bg-blue-600 px-4 text-sm font-medium text-white">
              자동 처리 기록
            </Link>
          </div>
        }
      />
    );
  }

  return (
    <div className="divide-y divide-gray-100 border-b border-gray-200">
      {items.map((item) => {
        const selected = item.id === selectedIssueId;
        return (
          <Link
            key={item.id}
            href={`/admin/issues/${item.id}`}
            className={`grid gap-4 py-5 transition-colors lg:grid-cols-[120px_minmax(0,1fr)_120px_110px] ${
              selected ? "border-l-2 border-blue-600 bg-gray-50 pl-4" : "hover:bg-gray-50"
            }`}
          >
            <div>
              <p className="text-xs font-medium text-gray-500">{item.id}</p>
              <p className="mt-1 text-xs text-gray-500">
                감지 {formatDateTime(item.firstDetectedAt)}
              </p>
            </div>
            <div>
              <h3 className="font-semibold leading-6 text-gray-900">
                {item.title}
              </h3>
              <p className="mt-1 text-sm leading-6 text-gray-500">
                {item.reason}
              </p>
            </div>
            <div className="text-sm text-gray-600">
              <p className="font-medium text-gray-900">{item.topic}</p>
              <p className="mt-1 text-xs text-gray-500">기사 {item.articleCount}</p>
            </div>
            <div className="space-y-2">
              <StatusBadge tone={statusTone(item.priority)}>
                {formatStatus(item.priority)}
              </StatusBadge>
              <StatusBadge tone={statusTone(item.status)}>
                {formatStatus(item.status)}
              </StatusBadge>
            </div>
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
      <section className="py-8">
        <h2 className="text-lg font-semibold text-gray-900">
          검토 항목을 선택하면 상세 판정이 열립니다
        </h2>
        <p className="mt-2 max-w-2xl text-sm leading-7 text-gray-500">
          주장 검수, 쟁점 판정, 출처 기준, 게시 전 체크리스트가 한 화면에 연결됩니다.
        </p>
      </section>
    );
  }

  return (
    <section className="py-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <StatusBadge tone={statusTone(issue.status)}>
            {issue.topic} · {formatStatus(issue.status)}
          </StatusBadge>
          <h2 className="mt-2 text-2xl font-bold tracking-tight text-gray-900">
            {issue.title}
          </h2>
          <p className="mt-2 max-w-2xl text-sm leading-7 text-gray-600">
            {issue.reason}
          </p>
        </div>
        <AdminIssueActionButtons issueId={issue.id} />
      </div>

      <ReviewWorkflow />
      <ReviewSectionIndex claims={claims} clusters={clusters} evidences={evidences} />
    </section>
  );
}

function ReviewWorkflow() {
  return (
    <div className="mt-6 border-y border-gray-200 py-4">
      <p className="text-xs font-medium uppercase tracking-wide text-gray-500">
        검토 단계
      </p>
      <ol className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-6">
        {reviewSteps.map(([title, description], index) => (
          <li
            key={title}
            className={`min-h-24 border px-3 py-3 ${
              index < 2 ? "border-gray-200 bg-gray-50" : "border-gray-200 bg-white"
            }`}
          >
            <p className="text-sm font-semibold text-gray-900">{title}</p>
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
  return (
    <div className="grid gap-8 py-7 xl:grid-cols-3">
      <section>
        <div className="flex items-center gap-2">
          <SlidersHorizontal className="size-4 text-blue-600" aria-hidden="true" />
          <h3 className="text-base font-semibold text-gray-900">주장 검수</h3>
        </div>
        <div className="mt-4 divide-y divide-gray-100 border-t border-gray-200">
          {claims.slice(0, 4).map((claim) => (
            <div key={claim.id ?? claim.text} className="py-4">
              <StatusBadge tone={claim.tone}>{claim.verdict}</StatusBadge>
              <p className="mt-2 text-sm font-medium leading-6 text-gray-900">
                {claim.text}
              </p>
              <p className="mt-1 text-xs leading-5 text-gray-500">
                {claim.type} · {formatCredibility(claim.confidence)}
              </p>
            </div>
          ))}
          {claims.length === 0 ? (
            <p className="py-4 text-sm leading-7 text-gray-500">
              검수할 주장이 없습니다.
            </p>
          ) : null}
        </div>
      </section>

      <section>
        <div className="flex items-center gap-2">
          <FileText className="size-4 text-blue-600" aria-hidden="true" />
          <h3 className="text-base font-semibold text-gray-900">쟁점 판정</h3>
        </div>
        <div className="mt-4 divide-y divide-gray-100 border-t border-gray-200">
          {clusters.slice(0, 4).map((cluster) => (
            <div key={cluster.title} className="py-4">
              <StatusBadge tone={cluster.tone}>{cluster.verdict}</StatusBadge>
              <p className="mt-2 text-sm font-medium leading-6 text-gray-900">
                {cluster.title}
              </p>
              <p className="mt-1 text-xs leading-5 text-gray-500">
                {cluster.conflict || cluster.commonGround}
              </p>
            </div>
          ))}
          {clusters.length === 0 ? (
            <p className="py-4 text-sm leading-7 text-gray-500">
              쟁점 판정 항목이 없습니다.
            </p>
          ) : null}
        </div>
      </section>

      <section>
        <div className="flex items-center gap-2">
          <Gauge className="size-4 text-blue-600" aria-hidden="true" />
          <h3 className="text-base font-semibold text-gray-900">출처 기준</h3>
        </div>
        <div className="mt-4 divide-y divide-gray-100 border-t border-gray-200">
          {evidences.slice(0, 4).map((evidence) => (
            <div key={evidence.id ?? evidence.label} className="py-4">
              <p className="text-sm font-medium leading-6 text-gray-900">
                {evidence.label}
              </p>
              <p className="mt-1 text-xs leading-5 text-gray-500">
                {evidence.source} · {formatCredibility(evidence.credibility)}
              </p>
            </div>
          ))}
          {evidences.length === 0 ? (
            <p className="py-4 text-sm leading-7 text-gray-500">
              출처 기준 항목이 없습니다.
            </p>
          ) : null}
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
    <aside className="lg:sticky lg:top-8 lg:self-start">
      <section className="border-b border-gray-200 py-6">
        <div className="flex items-center gap-2">
          <Bot className="size-4 text-blue-600" aria-hidden="true" />
          <h2 className="text-base font-semibold text-gray-900">
            자동 처리 상태
          </h2>
        </div>
        <div className="mt-4 divide-y divide-gray-100">
          {agentRuns.length > 0 ? (
            agentRuns.map((run) => (
              <div key={run.agent} className="py-4">
                <div className="flex items-center justify-between gap-3">
                  <h3 className="text-sm font-semibold text-gray-900">
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
                  <p className="mt-2 text-sm font-medium leading-6 text-red-600">
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
          <h2 className="text-base font-semibold text-gray-900">재검증 실행</h2>
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
          <h2 className="text-base font-semibold text-gray-900">출고 전 확인</h2>
        </div>
        <ul className="mt-4 space-y-3 text-sm leading-6 text-gray-600">
          {[
            "기사 전체를 가짜뉴스로 단정하지 않았는지 확인",
            "초기 보도와 후속 자료 기준이 분리됐는지 확인",
            "낙인 표현이 주장 유형으로 정제됐는지 확인",
          ].map((item) => (
            <li key={item} className="flex gap-2">
              <CheckCircle2
                className="mt-0.5 size-4 shrink-0 text-emerald-600"
                aria-hidden="true"
              />
              {item}
            </li>
          ))}
        </ul>
      </section>
    </aside>
  );
}
```

- [ ] **Step 4: Replace `/admin` page rendering**

Modify `src/app/admin/page.tsx` so it only imports server dependencies, shared header/metric strip, and `AdminQueueWorkspace`.

Final shape:

```tsx
import { AdminQueueWorkspace } from "@/components/admin/admin-queue-workspace";
import { AdminMetricStrip, AdminPageHeader } from "@/components/common/design-system";
import { isApiConfigured } from "@/lib/api/config";
import { getAdminDashboard } from "@/lib/api/facttracer";
import { getServerAccessToken } from "@/lib/auth/server-session";

export default async function AdminPage() {
  const accessToken = await getServerAccessToken();
  const needsAuthForRealApi = isApiConfigured() && !accessToken;
  const dashboard = await getAdminDashboard(accessToken, {
    fallbackToEmpty: needsAuthForRealApi,
  });

  return (
    <div className="space-y-8">
      <AdminPageHeader
        backHref="/admin"
        backLabel="FactTracer"
        eyebrow="운영 콘솔"
        title="검토 목록에서 민감 이슈를 확인하고 안전하게 게시합니다"
        description="고위험 이슈, 신고 표현, 공식 출처 갱신, 자동 처리 실패를 우선순위대로 확인하고 판단 사유를 남깁니다."
      >
        <AdminMetricStrip metrics={dashboard.metrics} />
      </AdminPageHeader>
      <AdminQueueWorkspace
        dashboard={dashboard}
        needsAuthForRealApi={needsAuthForRealApi}
      />
    </div>
  );
}
```

- [ ] **Step 5: Verify**

Run:

```bash
npm run lint
npm run build
```

Expected: PASS. If build fails because a helper function was omitted from `admin-queue-workspace.tsx`, add the missing local helper before continuing.

- [ ] **Step 6: Commit**

```bash
git add src/app/admin/page.tsx src/components/admin/admin-queue-workspace.tsx
git commit -m "feat: upgrade admin review queue workspace"
```

---

### Task 3: Reports Workspace

**Files:**
- Create: `src/components/admin/admin-report-workspace.tsx`
- Modify: `src/app/admin/reports/page.tsx`

- [ ] **Step 1: Create report workspace**

Add a client component that:

- Tracks `query`, `priority`, and `status`.
- Filters `ModerationReport[]` with `matchesSearch`.
- Uses `uniqueOptions` for priority/status options.
- Renders `AdminReportResolveButtons` in each row.
- Uses `EmptyState` when filtered rows are empty.

Use this component contract:

```tsx
"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { AdminReportResolveButtons } from "@/components/admin/admin-actions";
import { AdminFilterControls } from "@/components/admin/admin-filter-controls";
import { matchesSearch, statusTone, uniqueOptions } from "@/components/admin/admin-workspace-utils";
import { EmptyState } from "@/components/common/empty-state";
import { StatusBadge } from "@/components/status-badge";
import type { ModerationReport } from "@/lib/api/types";
import { formatDateTime, formatStatus, formatTargetType } from "@/lib/display";

export function AdminReportWorkspace({ reports }: { reports: ModerationReport[] }) {
  const [query, setQuery] = useState("");
  const [priority, setPriority] = useState("");
  const [status, setStatus] = useState("");

  const priorityOptions = useMemo(
    () => uniqueOptions(reports.map((report) => report.priority), formatStatus),
    [reports],
  );
  const statusOptions = useMemo(
    () => uniqueOptions(reports.map((report) => report.status), formatStatus),
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
            report.status,
          ]) &&
          (!priority || report.priority === priority) &&
          (!status || report.status === status),
      ),
    [priority, query, reports, status],
  );

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
          { label: "우선순위", onChange: setPriority, options: priorityOptions, value: priority },
          { label: "상태", onChange: setStatus, options: statusOptions, value: status },
        ]}
      />
      <div className="divide-y divide-gray-100 border-b border-gray-200">
        {filteredReports.length > 0 ? (
          filteredReports.map((report) => (
            <div key={report.id} className="grid gap-5 py-5 lg:grid-cols-[minmax(0,1fr)_220px]">
              <div>
                <div className="flex flex-wrap gap-3">
                  <StatusBadge tone={statusTone(report.priority)}>
                    {formatStatus(report.priority)}
                  </StatusBadge>
                  <StatusBadge tone={statusTone(report.status)}>
                    {formatStatus(report.status)}
                  </StatusBadge>
                  <span className="text-sm text-gray-500">{report.reason}</span>
                </div>
                <Link href={`/admin/issues/${report.issueId}`} className="mt-2 block font-semibold leading-7 text-gray-900 hover:text-blue-600">
                  {report.issueTitle}
                </Link>
                <p className="mt-1 text-sm leading-6 text-gray-600">{report.excerpt}</p>
                <p className="mt-1 text-xs font-medium text-gray-500">
                  대상 {formatTargetType(report.targetType)} · 접수 {formatDateTime(report.submittedAt)}
                </p>
              </div>
              <AdminReportResolveButtons reportId={report.id} />
            </div>
          ))
        ) : (
          <EmptyState
            title="조건에 맞는 신고 표현이 없습니다"
            description="필터를 초기화하거나 검토 목록에서 민감 이슈를 확인해 주세요."
            action={<Link href="/admin" className="inline-flex h-10 items-center rounded-md bg-blue-600 px-4 text-sm font-medium text-white">검토 목록 보기</Link>}
          />
        )}
      </div>
    </section>
  );
}
```

- [ ] **Step 2: Simplify reports page**

Modify `src/app/admin/reports/page.tsx`:

```tsx
import { AdminReportWorkspace } from "@/components/admin/admin-report-workspace";
import { AdminPageHeader } from "@/components/common/design-system";
import { getAdminReports } from "@/lib/api/facttracer";
import { getServerAccessToken } from "@/lib/auth/server-session";

export default async function AdminReportsPage() {
  const token = await getServerAccessToken();
  const reports = await getAdminReports(token)
    .then((response) => response.reports)
    .catch(() => []);

  return (
    <div className="space-y-8">
      <AdminPageHeader
        title="신고 표현 처리"
        description="낙인 표현, 근거 없는 고의성 단정, 출처 신뢰도 신고를 이슈와 연결해 처리합니다."
      />
      <AdminReportWorkspace reports={reports} />
    </div>
  );
}
```

- [ ] **Step 3: Verify and commit**

Run:

```bash
npm run lint
npm run build
```

Expected: PASS.

Commit:

```bash
git add src/app/admin/reports/page.tsx src/components/admin/admin-report-workspace.tsx
git commit -m "feat: add admin report filters"
```

---

### Task 4: Sources Workspace

**Files:**
- Create: `src/components/admin/admin-source-workspace.tsx`
- Modify: `src/app/admin/sources/page.tsx`

- [ ] **Step 1: Create source workspace**

Create a client component with:

- `query`, `status`, `activeState`.
- Search across name, domain, source type, note, collection URL, status, and last collection status.
- Status filter from unique source statuses.
- Active filter values: `active`, `inactive`.
- New source registration section at top.
- Filtered source rows below.

Use this component contract:

```tsx
"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { AdminSourceConfigForm } from "@/components/admin/admin-actions";
import { AdminFilterControls } from "@/components/admin/admin-filter-controls";
import { matchesSearch, statusTone, uniqueOptions } from "@/components/admin/admin-workspace-utils";
import { EmptyState } from "@/components/common/empty-state";
import { StatusBadge } from "@/components/status-badge";
import type { SourceDomain } from "@/lib/api/types";
import { formatCredibility, formatSourceType, formatStatus } from "@/lib/display";

const activeOptions = [
  { label: "수집 활성", value: "active" },
  { label: "수집 중지", value: "inactive" },
];

export function AdminSourceWorkspace({ sources }: { sources: SourceDomain[] }) {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const [activeState, setActiveState] = useState("");

  const statusOptions = useMemo(
    () => uniqueOptions(sources.map((source) => source.status), formatStatus),
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
            source.note,
            source.collectionUrl,
            source.status,
            source.lastCollectionStatus,
          ]) &&
          (!status || source.status === status) &&
          (!activeState ||
            (activeState === "active" ? source.isActive : !source.isActive)),
      ),
    [activeState, query, sources, status],
  );

  return (
    <div className="space-y-8">
      <section className="border-y border-gray-200 py-6">
        <h2 className="text-lg font-semibold text-gray-900">새 출처 등록</h2>
        <p className="mt-1 text-sm leading-6 text-gray-600">
          수집 대상과 신뢰도 기준을 등록합니다.
        </p>
        <div className="mt-5">
          <AdminSourceConfigForm />
        </div>
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
            { label: "상태", onChange: setStatus, options: statusOptions, value: status },
            { label: "수집", onChange: setActiveState, options: activeOptions, value: activeState },
          ]}
        />
        <div className="divide-y divide-gray-100 border-b border-gray-200">
          {filteredSources.length > 0 ? (
            filteredSources.map((source) => (
              <div key={source.id} className="grid gap-6 py-6 2xl:grid-cols-[minmax(0,0.8fr)_minmax(560px,1.2fr)]">
                <div>
                  <h2 className="font-semibold text-gray-900">{source.name}</h2>
                  <p className="mt-1 text-sm leading-6 text-gray-500">식별자 {source.domain}</p>
                  {source.collectionUrl ? (
                    <p className="mt-1 break-all text-sm leading-6 text-gray-600">수집 링크 {source.collectionUrl}</p>
                  ) : null}
                  <p className="mt-1 text-sm leading-6 text-gray-600">메모: {source.note || "없음"}</p>
                  <div className="mt-3 flex flex-wrap gap-x-5 gap-y-2 text-sm leading-6 text-gray-600">
                    <span>{formatSourceType(source.sourceType)}</span>
                    <span>{formatCredibility(source.credibility)}</span>
                    <StatusBadge tone={statusTone(source.status)}>{formatStatus(source.status)}</StatusBadge>
                    <span>주기 {source.collectionIntervalMinutes ?? "-"}분</span>
                    <span>수집 {source.isActive ? "활성" : "중지"}</span>
                    <span>최근 {source.lastCollectionStatus ?? "idle"}</span>
                  </div>
                </div>
                <AdminSourceConfigForm source={source} />
              </div>
            ))
          ) : (
            <EmptyState
              title="조건에 맞는 출처가 없습니다"
              description="필터를 초기화하거나 새 출처를 등록해 수집 기준을 보강하세요."
              action={<Link href="/admin" className="inline-flex h-10 items-center rounded-md bg-blue-600 px-4 text-sm font-medium text-white">운영 콘솔 보기</Link>}
            />
          )}
        </div>
      </section>
    </div>
  );
}
```

- [ ] **Step 2: Simplify sources page**

Modify `src/app/admin/sources/page.tsx`:

```tsx
import { AdminSourceWorkspace } from "@/components/admin/admin-source-workspace";
import { AdminPageHeader } from "@/components/common/design-system";
import { getAdminSources } from "@/lib/api/facttracer";
import { getServerAccessToken } from "@/lib/auth/server-session";

export default async function AdminSourcesPage() {
  const token = await getServerAccessToken();
  const sources = await getAdminSources(token)
    .then((response) => response.sources)
    .catch(() => []);

  return (
    <div className="space-y-8">
      <AdminPageHeader
        title="출처 관리"
        description="공식자료, 언론, SNS 후보의 신뢰도와 상태를 관리해 주장 검증 우선순위에 반영합니다."
      />
      <AdminSourceWorkspace sources={sources} />
    </div>
  );
}
```

- [ ] **Step 3: Verify and commit**

Run:

```bash
npm run lint
npm run build
```

Expected: PASS.

Commit:

```bash
git add src/app/admin/sources/page.tsx src/components/admin/admin-source-workspace.tsx
git commit -m "feat: add admin source filters"
```

---

### Task 5: Agents Workspace

**Files:**
- Create: `src/components/admin/admin-agent-workspace.tsx`
- Modify: `src/app/admin/agents/page.tsx`

- [ ] **Step 1: Create agent workspace**

Create a client component that:

- Tracks `query` and `status`.
- Filters `AgentRun[]`.
- Renders `AdminAgentRunButton`.
- Keeps recent events in an aside.
- Uses `StatusBadge` and `statusTone`.

Use this component contract:

```tsx
"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { AdminAgentRunButton } from "@/components/admin/admin-actions";
import { AdminFilterControls } from "@/components/admin/admin-filter-controls";
import { matchesSearch, statusTone, uniqueOptions } from "@/components/admin/admin-workspace-utils";
import { EmptyState } from "@/components/common/empty-state";
import { StatusBadge } from "@/components/status-badge";
import type { AgentRun, IssueTimelineEvent } from "@/lib/api/types";
import { formatDateTime, formatProcessingName, formatStatus } from "@/lib/display";

export function AdminAgentWorkspace({
  agentRuns,
  recentEvents,
}: {
  agentRuns: AgentRun[];
  recentEvents: IssueTimelineEvent[];
}) {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const statusOptions = useMemo(
    () => uniqueOptions(agentRuns.map((run) => run.status), formatStatus),
    [agentRuns],
  );
  const filteredRuns = useMemo(
    () =>
      agentRuns.filter(
        (run) =>
          matchesSearch(query, [
            run.agent,
            formatProcessingName(run.agent),
            run.target,
            run.status,
            run.failureReason,
          ]) &&
          (!status || run.status === status),
      ),
    [agentRuns, query, status],
  );

  return (
    <section className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_360px]">
      <article className="min-w-0">
        <AdminFilterControls
          count={filteredRuns.length}
          onClear={() => {
            setQuery("");
            setStatus("");
          }}
          onQueryChange={setQuery}
          query={query}
          resultLabel="자동 처리"
          selects={[
            { label: "상태", onChange: setStatus, options: statusOptions, value: status },
          ]}
        />
        <div className="divide-y divide-gray-100 border-b border-gray-200">
          {filteredRuns.length > 0 ? (
            filteredRuns.map((run) => (
              <div key={run.agent} className="grid gap-4 py-5 lg:grid-cols-[minmax(0,1fr)_130px_100px]">
                <div>
                  <h2 className="font-semibold text-gray-900">{formatProcessingName(run.agent)}</h2>
                  <p className="mt-1 text-sm leading-6 text-gray-500">
                    {run.target} · {formatDateTime(run.finishedAt)}
                  </p>
                  {run.failureReason ? (
                    <p className="mt-2 text-sm font-medium leading-6 text-red-600">
                      실패 사유: {run.failureReason}
                    </p>
                  ) : null}
                </div>
                <StatusBadge tone={statusTone(run.status)}>
                  {formatStatus(run.status)}
                </StatusBadge>
                <AdminAgentRunButton agent={run.agent} />
              </div>
            ))
          ) : (
            <EmptyState
              title="조건에 맞는 자동 처리 기록이 없습니다"
              description="필터를 초기화하거나 검토 목록에서 재검증할 이슈를 선택해 주세요."
              action={<Link href="/admin" className="inline-flex h-10 items-center rounded-md bg-blue-600 px-4 text-sm font-medium text-white">운영 콘솔 보기</Link>}
            />
          )}
        </div>
      </article>

      <aside className="lg:sticky lg:top-8 lg:self-start">
        <h2 className="text-base font-semibold text-gray-900">최근 이벤트</h2>
        <div className="mt-4 divide-y divide-gray-100 border-t border-gray-200">
          {recentEvents.length > 0 ? (
            recentEvents.map((event) => (
              <div key={event.id} className="py-4">
                <p className="text-xs font-medium text-blue-600">
                  {formatProcessingName(event.type)} · {formatDateTime(event.occurredAt)}
                </p>
                <h3 className="mt-2 text-sm font-semibold text-gray-900">{event.title}</h3>
                <p className="mt-1 text-sm leading-6 text-gray-500">{event.description}</p>
              </div>
            ))
          ) : (
            <p className="py-4 text-sm leading-7 text-gray-500">최근 이벤트가 없습니다.</p>
          )}
        </div>
      </aside>
    </section>
  );
}
```

- [ ] **Step 2: Simplify agents page**

Modify `src/app/admin/agents/page.tsx`:

```tsx
import { AdminAgentWorkspace } from "@/components/admin/admin-agent-workspace";
import { AdminPageHeader } from "@/components/common/design-system";
import { getAdminAgents } from "@/lib/api/facttracer";
import { getServerAccessToken } from "@/lib/auth/server-session";

export default async function AdminAgentsPage() {
  const token = await getServerAccessToken();
  const response = await getAdminAgents(token).catch(() => ({
    agentRuns: [],
    recentEvents: [],
  }));

  return (
    <div className="space-y-8">
      <AdminPageHeader
        title="자동 처리 기록"
        description="자동 수집, 주장 추출, 근거 매칭, 낙인 필터링 상태를 확인하고 수동 실행합니다."
      />
      <AdminAgentWorkspace
        agentRuns={response.agentRuns}
        recentEvents={response.recentEvents}
      />
    </div>
  );
}
```

- [ ] **Step 3: Verify and commit**

Run:

```bash
npm run lint
npm run build
```

Expected: PASS.

Commit:

```bash
git add src/app/admin/agents/page.tsx src/components/admin/admin-agent-workspace.tsx
git commit -m "feat: add admin agent filters"
```

---

### Task 6: Issue Detail And Settings Alignment

**Files:**
- Modify: `src/app/admin/issues/[issueId]/page.tsx`
- Modify: `src/app/admin/settings/page.tsx`

- [ ] **Step 1: Align issue detail imports**

In `src/app/admin/issues/[issueId]/page.tsx`, add:

```tsx
import { AdminMetricStrip, AdminPageHeader } from "@/components/common/design-system";
import { statusTone } from "@/components/admin/admin-workspace-utils";
```

Use `AdminPageHeader` for both the error state and loaded state header.

- [ ] **Step 2: Improve loaded issue header**

Replace the loaded header section with:

```tsx
<AdminPageHeader
  backLabel="검토 목록으로 돌아가기"
  description={detail.issue.reason}
  eyebrow={
    <>
      {detail.issue.topic} · {formatStatus(detail.issue.status)} ·{" "}
      {formatStatus(detail.issue.priority)}
    </>
  }
  title={detail.issue.title}
>
  <AdminMetricStrip
    metrics={[
      { label: "수집 기사", value: detail.issue.articleCount },
      { label: "주장", value: detail.claims.length },
      { label: "신고", value: detail.reports.length },
      { label: "비교 기사", value: detail.articles.length },
    ]}
  />
</AdminPageHeader>
```

Move `AdminIssueActionButtons issueId={detail.issue.id}` into the right rail under a heading `출고 승인` so publishing readiness is near re-verification and podcast controls.

- [ ] **Step 3: Improve missing issue header**

Replace the missing detail header with:

```tsx
<AdminPageHeader
  backLabel="검토 목록으로 돌아가기"
  description={copy.description}
  eyebrow={`검토 상세 · ${issueId}`}
  title={copy.title}
/>
```

Keep the existing empty recovery body and next-action aside, but remove heavy `border border-gray-300` outer boxes in favor of `border-y border-gray-200 py-5`.

- [ ] **Step 4: Normalize status tones in detail lists**

In detail page rows, replace direct `StatusBadge tone={article.tone}` and `StatusBadge tone={claim.tone}` only when the row has a raw status field:

```tsx
<StatusBadge tone={statusTone(report.priority)}>
  {formatStatus(report.priority)}
</StatusBadge>
```

Keep API-provided `tone` for verdicts because verdict tone is domain data.

- [ ] **Step 5: Align settings page**

Modify `src/app/admin/settings/page.tsx` to use:

```tsx
import { AdminPageHeader } from "@/components/common/design-system";
```

Final page shape:

```tsx
return (
  <div className="space-y-8">
    <AdminPageHeader
      title="운영 설정"
      description="자동 수집, 판정 기준, AI 연결, 입력 제한을 조정합니다."
    />
    <section className="border-y border-gray-200 py-5">
      {settings.groups.length > 0 ? (
        <AdminSettingsConsole initialSettings={settings} />
      ) : (
        <EmptyState
          title="설정 항목을 불러오지 못했습니다"
          description="현재 운영 기본값은 유지됩니다. 연결 상태를 확인한 뒤 다시 시도해 주세요."
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
    </section>
  </div>
);
```

- [ ] **Step 6: Verify and commit**

Run:

```bash
npm run lint
npm run build
```

Expected: PASS.

Commit:

```bash
git add 'src/app/admin/issues/[issueId]/page.tsx' src/app/admin/settings/page.tsx
git commit -m "feat: align admin detail and settings pages"
```

---

### Task 7: Final Verification And Browser QA

**Files:**
- No planned code changes unless verification reveals admin-specific issues.

- [ ] **Step 1: Run final static verification**

Run:

```bash
npm run lint
npm run build
```

Expected: PASS.

- [ ] **Step 2: Start dev server**

Run:

```bash
npm run dev -- --port 3002
```

Expected: local server starts at `http://localhost:3002`.

- [ ] **Step 3: Browser QA routes**

Open these routes in the in-app Browser:

```text
http://localhost:3002/admin
http://localhost:3002/admin/reports
http://localhost:3002/admin/sources
http://localhost:3002/admin/agents
http://localhost:3002/admin/settings
http://localhost:3002/admin/issues/sample
```

Expected:

- Admin shell navigation is visible.
- Header style is consistent.
- Empty fallback states preserve layout.
- Filter bars render without overflow at desktop width.
- Mobile width keeps nav and filter controls usable.
- Buttons and inputs do not overlap.
- There are no dark admin panels, colored tint card grids, or pill status badges.

- [ ] **Step 4: Stop dev server**

Stop the dev server session cleanly after QA.

- [ ] **Step 5: Commit verification fixes only if needed**

If QA reveals admin-specific issues, fix them and commit:

```bash
git add src/app/admin src/components/admin src/components/common/design-system.tsx
git commit -m "fix: polish admin console responsive states"
```

If no fixes are needed, do not create an empty commit.

---

## Self-Review

- Spec coverage: core console/detail, reports, sources, agents, and settings are each represented by a task.
- Backend contract changes are excluded.
- Page components remain server-side for data fetching.
- Client components own only local filtering and rendering.
- Existing mutation components are reused.
- Verification uses the scripts available in `package.json`.
- No new dark theme, heavy tint cards, or nested cards are introduced.
