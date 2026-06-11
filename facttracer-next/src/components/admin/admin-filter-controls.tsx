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
        <label className="grid gap-1 text-xs font-medium text-gray-500">
          검색
          <span className="relative block">
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
          </span>
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
