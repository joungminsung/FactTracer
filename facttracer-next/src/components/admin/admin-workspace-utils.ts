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

export function matchesSearch(
  query: string,
  values: Array<string | number | null | undefined>,
) {
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
  const normalizedValue = value?.trim();

  switch (normalizedValue) {
    case "completed":
    case "resolved":
    case "trusted":
    case "verified":
    case "완료":
    case "신뢰":
    case "확인됨":
      return "positive";
    case "high":
    case "medium":
    case "open":
    case "queued":
    case "received":
    case "running":
    case "updated":
    case "watch":
    case "검토 대기":
    case "검토 중":
    case "높음":
    case "접수":
    case "접수됨":
    case "주의":
    case "중간":
    case "최신화 필요":
      return "warning";
    case "blocked":
    case "dead_letter":
    case "dismissed":
    case "failed":
    case "needs_review":
    case "긴급":
    case "기각":
    case "보류":
    case "실패":
    case "위험":
    case "차단":
      return "danger";
    default:
      return "neutral";
  }
}
