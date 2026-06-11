"use client";

import { FormEvent, useState } from "react";
import { Flag, Send } from "lucide-react";
import { useAuth } from "@/components/auth/auth-provider";
import { submitIssueContentReport } from "@/lib/api/facttracer";
import { getUserActionMessage } from "@/lib/api/messages";

const reportTypes = [
  { label: "이슈 정정", value: "issue" },
  { label: "주장 신고", value: "claim" },
  { label: "근거 오류", value: "source" },
  { label: "낙인 표현", value: "label" },
];

export function ContentReportForm({ issueId }: { issueId: string }) {
  const { token } = useAuth();
  const [targetType, setTargetType] = useState(reportTypes[0].value);
  const [targetId, setTargetId] = useState("");
  const [reason, setReason] = useState("");
  const [excerpt, setExcerpt] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErrorMessage(null);
    setSuccessMessage(null);
    setIsSubmitting(true);

    try {
      const response = await submitIssueContentReport(
        issueId,
        {
          excerpt,
          reason,
          targetId: targetId || undefined,
          targetType,
        },
        token,
      );
      setTargetType(reportTypes[0].value);
      setTargetId("");
      setReason("");
      setExcerpt("");
      setSuccessMessage(response.message || "검토 요청이 접수되었습니다.");
    } catch (error) {
      setErrorMessage(getUserActionMessage(error, "신고를 접수하지 못했습니다."));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form id="content-report" onSubmit={handleSubmit}>
      <div className="flex items-center gap-2">
        <Flag className="size-4 text-blue-600" aria-hidden="true" />
        <h2 className="text-xl font-bold text-gray-900">정정 요청/신고</h2>
      </div>
      <p className="mt-2 text-sm leading-6 text-gray-600">
        판정 오류, 오래된 수치, 근거 없는 단정, 낙인 표현을 검토자에게 보냅니다.
      </p>

      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <label className="block text-sm font-semibold text-gray-700">
          유형
          <select
            value={targetType}
            onChange={(event) => setTargetType(event.target.value)}
            className="mt-2 h-10 w-full rounded-md border border-gray-200 bg-white px-3 text-sm outline-none"
          >
            {reportTypes.map((type) => (
              <option key={type.value} value={type.value}>
                {type.label}
              </option>
            ))}
          </select>
        </label>
        <label className="block text-sm font-semibold text-gray-700">
          대상 ID 또는 제목
          <input
            value={targetId}
            onChange={(event) => setTargetId(event.target.value)}
            className="mt-2 h-10 w-full rounded-md border border-gray-200 px-3 text-sm outline-none"
            placeholder="선택 사항"
          />
        </label>
      </div>

      <label className="mt-4 block text-sm font-semibold text-gray-700">
        검토 요청 사유
        <textarea
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          required
          className="mt-2 min-h-20 w-full resize-none rounded-md border border-gray-200 px-3 py-2 text-sm leading-6 outline-none"
          placeholder="무엇이 잘못됐거나 추가 확인이 필요한지 적어 주세요."
        />
      </label>

      <label className="mt-4 block text-sm font-semibold text-gray-700">
        문제 표현 또는 근거 문장
        <textarea
          value={excerpt}
          onChange={(event) => setExcerpt(event.target.value)}
          className="mt-2 min-h-20 w-full resize-none rounded-md border border-gray-200 px-3 py-2 text-sm leading-6 outline-none"
          placeholder="검토자가 확인할 문장이나 링크 설명을 적어 주세요."
        />
      </label>

      <button
        type="submit"
        disabled={isSubmitting}
        className="mt-4 inline-flex h-10 w-full items-center justify-center gap-2 rounded-md border border-gray-200 text-sm font-bold text-gray-800 disabled:cursor-not-allowed disabled:text-gray-400"
      >
        <Send className="size-4" aria-hidden="true" />
        {isSubmitting ? "접수 중" : "검토 요청 보내기"}
      </button>

      {errorMessage ? (
        <p className="mt-3 text-sm font-semibold text-red-600">
          {errorMessage}
        </p>
      ) : null}
      {successMessage ? (
        <p className="mt-3 text-sm font-semibold text-blue-700" role="status">
          {successMessage}
        </p>
      ) : null}
    </form>
  );
}
