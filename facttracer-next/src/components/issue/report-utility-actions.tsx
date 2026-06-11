"use client";

import { useState } from "react";
import { Copy, FileDown, FileText, Printer, Table2 } from "lucide-react";
import type { IssueDetail } from "@/lib/api/types";
import {
  formatCredibility,
  formatDateTime,
  formatEvidenceCount,
  formatSourceType,
  formatUpdatedAt,
} from "@/lib/display";

export function ReportUtilityActions({ issue }: { issue: IssueDetail }) {
  const [copyMessage, setCopyMessage] = useState<string | null>(null);

  async function copyText(label: string, text: string) {
    await navigator.clipboard.writeText(text);
    setCopyMessage(`${label}을 복사했습니다.`);
    window.setTimeout(() => setCopyMessage(null), 2200);
  }

  return (
    <div className="print:hidden">
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => window.print()}
          className="inline-flex h-10 items-center gap-2 rounded-md bg-blue-600 px-4 text-sm font-medium text-white"
        >
          <Printer className="size-4" aria-hidden="true" />
          PDF 저장
        </button>
        <button
          type="button"
          onClick={() => void copyText("인용", buildCitationText(issue))}
          className="inline-flex h-10 items-center gap-2 rounded-md border border-gray-200 px-3 text-sm font-bold text-gray-700 hover:border-gray-300 hover:bg-gray-50"
        >
          <Copy className="size-4" aria-hidden="true" />
          인용 복사
        </button>
        <button
          type="button"
          onClick={() => void copyText("비교표", buildArticleComparisonText(issue))}
          className="inline-flex h-10 items-center gap-2 rounded-md border border-gray-200 px-3 text-sm font-bold text-gray-700 hover:border-gray-300 hover:bg-gray-50"
        >
          <Table2 className="size-4" aria-hidden="true" />
          비교표 복사
        </button>
        <button
          type="button"
          onClick={() => void copyText("출처 목록", buildSourceText(issue))}
          className="inline-flex h-10 items-center gap-2 rounded-md border border-gray-200 px-3 text-sm font-bold text-gray-700 hover:border-gray-300 hover:bg-gray-50"
        >
          <FileText className="size-4" aria-hidden="true" />
          출처 목록 복사
        </button>
        <button
          type="button"
          onClick={() => void copyText("출처 포함 리포트", buildExportText(issue))}
          className="inline-flex h-10 items-center gap-2 rounded-md border border-gray-200 px-3 text-sm font-bold text-gray-700 hover:border-gray-300 hover:bg-gray-50"
        >
          <FileDown className="size-4" aria-hidden="true" />
          출처 포함 내보내기
        </button>
      </div>
      <p className="mt-2 min-h-5 text-xs font-semibold text-blue-700" role="status">
        {copyMessage}
      </p>
    </div>
  );
}

function buildExportText(issue: IssueDetail) {
  return [
    buildCitationText(issue),
    "",
    "기사별 검증 비교",
    buildArticleComparisonText(issue),
  ].join("\n");
}

function buildCitationText(issue: IssueDetail) {
  const facts = issue.confirmedFacts
    .map((fact) => `- ${fact.label}: ${fact.text} (${fact.verdict})`)
    .join("\n");
  const sources = buildSourceText(issue);

  return [
    `FactTracer 이슈 리포트: ${issue.title}`,
    `주제: ${issue.topic}`,
    `상태: ${issue.status} / 위험도: ${issue.risk}`,
    `업데이트: ${formatUpdatedAt(issue.updatedAt)}`,
    "",
    issue.summary,
    "",
    "핵심 팩트",
    facts || "- 확인된 팩트 없음",
    "",
    sources,
  ].join("\n");
}

function buildArticleComparisonText(issue: IssueDetail) {
  const rows = (issue.articles ?? []).map((article) =>
    [
      article.title,
      article.outlet,
      formatDateTime(article.publishedAt),
      `${article.claimCount}개`,
      formatEvidenceCount(article.officialSourceCount),
      article.outdatedClaims > 0
        ? `${article.outdatedClaims}개 최신화 필요`
        : "현재 기준 유지",
      article.verdict,
      article.note,
      article.url,
    ].join("\t"),
  );

  return [
    "기사\t매체\t발행 시각\t포함 주장\t공식 출처\t업데이트 필요\t판정\t사유\tURL",
    ...rows,
  ].join("\n");
}

function buildSourceText(issue: IssueDetail) {
  const rows = (issue.sourceDocuments ?? []).map((source, index) =>
    [
      `${index + 1}. ${source.title}`,
      `${source.publisher} / ${formatSourceType(source.sourceType)}`,
      `발행: ${formatDateTime(source.publishedAt)}`,
      `신뢰도: ${formatCredibility(source.credibility)}`,
      source.url,
    ].join("\n"),
  );

  return ["원문 자료", rows.length > 0 ? rows.join("\n\n") : "- 원문 자료 없음"].join(
    "\n",
  );
}
