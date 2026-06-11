# Admin Console Enhancement Design

Date: 2026-06-11
Scope: FactTracer Next administrator pages under `/admin`.

## Goal

Upgrade the administrator experience into a coherent review workspace where operators can move from queue triage to issue review, source/report checks, re-verification, and publishing approval without losing context.

This pass includes:

- Core review queue and issue detail improvements.
- Consistent administrator page structure across reports, sources, agents, and settings.
- Frontend-only operational features where backend contracts do not yet exist.
- Preservation of the existing API client and mutation flow.

## Current Context

The current frontend already has these useful foundations:

- `src/app/admin/layout.tsx` provides a dedicated admin shell with `AdminWorkspaceNav`.
- `/admin` fetches `getAdminDashboard` and shows metrics, review queue, selected issue, claims, clusters, evidence, agent runs, re-verification, and publishing checks.
- `/admin/issues/[issueId]` fetches `getAdminIssue` and shows review detail sections for claims, article comparison, reports, re-verification, podcast generation, and other queue items.
- `/admin/reports`, `/admin/sources`, `/admin/agents`, and `/admin/settings` each use the same API layer but their page headers, list density, empty states, and action placement are inconsistent.
- `DESIGN.md` defines the required v2 design system: light UI, restrained typography, dot status indicators, limited borders, no nested cards, and admin as a review workspace.

Current gaps:

- The admin pages look related but not fully systematized.
- Queue triage lacks client-side filtering and quick narrowing by topic, status, priority, or search.
- The selected review issue preview and detail page do not expose enough operational summary before the operator starts acting.
- Publishing approval is functional but visually separated from the surrounding review evidence.
- Reports, sources, agents, and settings use bordered panels more heavily than the design system recommends.
- Empty and failure states keep the layout, but the operator's next action is not always specific enough.

## Product Position

The admin console is not a generic dashboard. It is a verification workbench for FactTracer's core principle:

```text
Facts are verified, opinions are separated, issues are structured, and stigmatizing language is refined.
```

The interface should feel like a calm editorial review desk because administrators are checking evidence and publishing risk-sensitive public information. It should emphasize scan speed, source traceability, review sequence, and explicit approval rationale.

## Design Principles

Use the existing `DESIGN.md` v2 rules as the source of truth:

- Use a white background and `gray-50` only for secondary surfaces, selected rows, and hover states.
- Use `blue-600` only for primary actions, links, selected state, and focus.
- Use semantic colors only as dots or text, not tinted cards.
- Avoid card-in-card layouts.
- Use borders for tables, inputs, dividers, and necessary row separation only.
- Keep one primary button per local action area.
- Preserve operator workflow skeletons during empty, unauthorized, and failure states.

Admin-specific interface priorities:

- The queue must make priority, reason, status, topic, article count, and age scannable.
- The selected issue or detail page must show why the item exists in the queue before showing actions.
- The publishing action must require visible source, counterclaim, language, and hold checks.
- Operational pages must share the same header, row, status, and empty-state grammar.
- Features that need backend support must not pretend to be server-side. Frontend-only filters and disabled future actions must state their scope.

## Information Architecture

### Global Admin Shell

The existing left navigation remains. It should continue to expose:

- Review queue.
- Reports.
- Podcasts.
- Sources.
- Agent runs.
- Settings.

The shell should keep the desktop left rail and mobile horizontal nav. It should avoid a second global top bar inside individual admin pages.

### Shared Page Header

Admin pages should use one shared header pattern:

- Back link or section label.
- Page title.
- Short operational description.
- Optional compact metrics or last-updated metadata.
- Optional primary local action.

This should be implemented through existing or improved shared components in `src/components/common/design-system.tsx`, especially `AdminPageHeader` and `AdminSurface`.

### Review Workspace

The `/admin` landing page should become the central review workspace:

1. Page header with compact operational metrics.
2. Queue controls for search and filtering.
3. Review queue list with selected/active row treatment.
4. Selected issue review preview.
5. Right rail with agent status, re-verification, and publishing readiness.

The queue remains useful when empty by directing operators to source checks, report handling, and agent logs.

### Issue Detail Workspace

The detail page remains the deeper review surface:

1. Header with issue topic, status, priority, reason, and actions.
2. Review progress sequence.
3. Claims review.
4. Article comparison.
5. Reported expression handling.
6. Right rail for re-verification, podcast generation, publishing readiness, and adjacent queue navigation.

The detail page should keep the operational skeleton even when the issue cannot be loaded.

### Reports

Reports should focus on expression cleanup:

- Search by issue title, excerpt, or reason.
- Filter by status and priority.
- Show target type, submitted time, reason, status, excerpt, and action controls in a consistent row.
- Empty state should guide the operator back to queue or source review.

### Sources

Sources should focus on trust and collection readiness:

- Search by name, domain, source type, or note.
- Filter by status and active state.
- Show domain, type, credibility, status, collection interval, activity, and last collection status.
- Keep create/edit controls available without turning the page into nested cards.

### Agents

Agents should focus on processing health:

- Search by agent name, target, failure reason, or status.
- Filter by status.
- Show latest target, finished time, failure reason, status, and manual run action.
- Keep recent events in a right rail.

### Settings

Settings should keep the existing console behavior but use the same header and outer surface treatment as other admin pages. When settings cannot load, the empty state should explain that operational defaults remain unchanged and provide a return path.

## Functional Requirements

### Queue Filtering

Add client-side controls for `/admin` queue data:

- Text search against title, reason, topic, priority, and status.
- Priority filter.
- Topic filter.
- Status filter.
- Clear filters action.

Filtering is frontend-only because the current `getAdminDashboard` API returns the full queue available to the page. The UI must not claim server-side search.

### Operational List Filters

Add client-side filters to these pages:

- `/admin/reports`: search, priority filter, status filter.
- `/admin/sources`: search, status filter, active-state filter.
- `/admin/agents`: search, status filter.

The filters should be implemented as client components that receive server-fetched data as props and render filtered rows. Server fetching stays in the page components.

### Publishing Readiness

The existing `AdminIssueActionButtons` checklist remains the canonical approval gate:

- Official sources checked.
- Counterclaims and common ground checked.
- Language refined.
- No pending hold reason remains.
- Approval memo has at least six characters.

Improve surrounding copy and placement so this gate reads as part of the review workflow rather than a detached action block.

### Status And Metrics

Use `StatusBadge` dot pattern for statuses. Avoid pill backgrounds.

Metrics should use number plus label without heavy card styling. Where metrics are unavailable, omit the metric row rather than showing empty decorative boxes.

### Empty, Failure, And Auth States

All admin pages must preserve their page structure when data is unavailable:

- Header remains visible.
- Primary navigation remains visible.
- The main content explains the state and suggests the next operator action.
- No page should collapse into a single isolated error panel.

## Non-Goals

This pass will not:

- Change backend API contracts.
- Add real server-side bulk actions.
- Add new authentication or role-management behavior.
- Add new admin routes beyond the existing route set.
- Redesign public pages.
- Add a dark admin theme.

## Component Plan

Create focused client components under `src/components/admin/`:

- `admin-queue-workspace.tsx`
  Receives dashboard data used on `/admin`, owns queue filters, renders filtered queue rows, selected issue preview, claims, clusters, evidence, and right rail content.

- `admin-report-workspace.tsx`
  Receives reports, owns report filters, renders report rows and existing report resolve controls.

- `admin-source-workspace.tsx`
  Receives sources, owns source filters, renders new source form and source rows with existing config form.

- `admin-agent-workspace.tsx`
  Receives agent runs and recent events, owns agent filters, renders run rows and existing run button.

Improve shared primitives:

- `src/components/common/design-system.tsx`
  Normalize `AdminPageHeader`, `AdminSurface`, and small layout helpers if needed.

Reuse existing action components:

- `AdminQueueSyncButton`.
- `AdminIssueActionButtons`.
- `AdminReverificationForm`.
- `AdminReportResolveButtons`.
- `AdminSourceConfigForm`.
- `AdminAgentRunButton`.
- `AdminIssuePodcastGenerateButton`.

## Data Flow

Server route components continue to fetch data:

```text
admin page route
  -> getServerAccessToken()
  -> getAdmin* API function
  -> pass typed response data to client workspace component
  -> client workspace filters and renders rows
  -> existing action components perform mutations with auth token from useAuth()
```

This keeps API fetching server-side while allowing local filtering without adding backend endpoints.

## Testing Strategy

Because the app currently has lint/build scripts but no dedicated unit test framework, verification will use:

- `npm run lint`.
- `npm run build`.
- Manual browser check against the local Next dev server.

The implementation should also add small pure helper functions only when they simplify filtering. If such helpers are created, they should be deterministic and easy to inspect. Do not add a test framework during this pass.

Manual browser checks should cover:

- `/admin` with empty API fallback.
- `/admin/reports`.
- `/admin/sources`.
- `/admin/agents`.
- `/admin/settings`.
- `/admin/issues/sample` or an available issue route in fallback/error state.
- Mobile-width navigation and filter wrapping.

## Acceptance Criteria

- `/admin` reads as the central review workspace, not a generic metrics dashboard.
- Queue filtering works locally and preserves empty-state guidance when no rows match.
- Issue review preview keeps claims, clusters, evidence, agent status, re-verification, and publishing readiness connected.
- `/admin/issues/[issueId]` keeps the same visual language as `/admin`.
- Reports, sources, agents, and settings use the shared admin header and surface treatment.
- Report/source/agent filters work locally.
- Existing API mutation buttons still render and keep their current validation behavior.
- No new dark theme, tint-card, nested-card, or pill-status patterns are introduced.
- `npm run lint` passes.
- `npm run build` passes.

## Risks

- Splitting page rendering into client workspaces increases client component surface area. Keep server fetching in route components and pass only typed data needed for rendering.
- The admin pages are currently untracked in Git in this local worktree. The implementation must avoid reverting unrelated user changes and should commit or stage only files intentionally modified for this enhancement.
- Backend data may include unknown statuses. Filters and status tones must gracefully fall back to neutral display.

## Design Self-Review

- No unresolved gaps remain.
- Scope is one frontend subsystem: the existing administrator route set.
- Backend contract changes are explicitly out of scope.
- UI constraints are tied to `DESIGN.md`.
- Every requested scope item is covered: core console/detail, cross-page consistency, and frontend-feasible operational functionality.
