"use client";

import { useState } from "react";
import Link from "next/link";
import { Bookmark, Download } from "lucide-react";
import { useAuth } from "@/components/auth/auth-provider";
import { API_BASE_URL } from "@/lib/api/config";
import { createIssueReport, saveIssue } from "@/lib/api/facttracer";
import { getUserActionMessage } from "@/lib/api/messages";
import type { IssueReportResponse } from "@/lib/api/types";

export function SaveIssueButton({
  buttonClassName,
  issueId,
  label = "이슈 저장",
}: {
  buttonClassName?: string;
  issueId: string;
  label?: string;
}) {
  const { token } = useAuth();
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleClick() {
    setIsSubmitting(true);
    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      const response = await saveIssue(issueId, token);
      setSuccessMessage(response.message || "이슈를 저장했습니다.");
    } catch (error) {
      setErrorMessage(getUserActionMessage(error, "이슈 저장에 실패했습니다."));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div>
      <button
        type="button"
        onClick={handleClick}
        disabled={isSubmitting}
        className={
          buttonClassName ??
          "inline-flex h-10 items-center gap-2 rounded-md border border-gray-200 px-4 text-sm font-bold text-gray-700 disabled:cursor-not-allowed disabled:text-gray-400"
        }
      >
        <Bookmark className="size-4" aria-hidden="true" />
        {isSubmitting ? "저장 중" : successMessage ? "저장됨" : label}
      </button>
      {successMessage ? (
        <p className="mt-2 text-xs font-semibold text-blue-700" role="status">
          {successMessage}
        </p>
      ) : null}
      {errorMessage ? (
        <p className="mt-2 text-xs font-semibold text-red-600">
          {errorMessage}
        </p>
      ) : null}
    </div>
  );
}

export function CreateIssueReportButton({
  buttonClassName,
  issueId,
  label = "출처 포함 리포트",
}: {
  buttonClassName?: string;
  issueId: string;
  label?: string;
}) {
  const { token } = useAuth();
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [report, setReport] = useState<IssueReportResponse | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleClick() {
    setIsSubmitting(true);
    setErrorMessage(null);
    setReport(null);
    try {
      const response = await createIssueReport(issueId, token);
      setReport(response);
    } catch (error) {
      setErrorMessage(getUserActionMessage(error, "리포트 저장에 실패했습니다."));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div>
      <button
        type="button"
        onClick={handleClick}
        disabled={isSubmitting}
        className={
          buttonClassName ??
          "inline-flex h-10 items-center gap-2 rounded-md bg-blue-600 px-4 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
        }
      >
        <Download className="size-4" aria-hidden="true" />
        {isSubmitting ? "생성 중" : label}
      </button>
      {report ? (
        <div className="mt-2 flex flex-wrap gap-2 text-xs font-semibold leading-5" role="status">
          <Link href={report.shareUrl || `/reports/${issueId}`} className="text-gray-700 hover:text-blue-600">
            공유 리포트 열기
          </Link>
          {report.markdownUrl ? (
            <a
              href={`${API_BASE_URL}${report.markdownUrl}`}
              target="_blank"
              rel="noreferrer"
              className="text-gray-700 hover:text-blue-600"
            >
              마크다운 다운로드
            </a>
          ) : null}
        </div>
      ) : null}
      {errorMessage ? (
        <p className="mt-2 text-xs font-semibold text-red-600">
          {errorMessage}
        </p>
      ) : null}
    </div>
  );
}
