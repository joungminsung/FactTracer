"use client";

import { FormEvent, useState } from "react";
import { Send } from "lucide-react";
import { useAuth } from "@/components/auth/auth-provider";
import { submitClaim } from "@/lib/api/facttracer";
import { getUserActionMessage } from "@/lib/api/messages";

const claimTypes = [
  "사실 주장",
  "해석/평가",
  "요구 사항",
  "운동 전략",
  "반박",
  "추가 근거 제보",
];

export function ClaimSubmissionForm({ issueId }: { issueId: string }) {
  const { token } = useAuth();
  const [claimText, setClaimText] = useState("");
  const [reason, setReason] = useState("");
  const [evidenceUrl, setEvidenceUrl] = useState("");
  const [relatedCluster, setRelatedCluster] = useState("");
  const [claimType, setClaimType] = useState(claimTypes[0]);
  const [refutablePoint, setRefutablePoint] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErrorMessage(null);
    setSuccessMessage(null);
    setIsSubmitting(true);

    try {
      const response = await submitClaim(
        {
          claimText,
          evidenceUrl: evidenceUrl || undefined,
          claimType,
          issueId,
          reason,
          refutablePoint,
          relatedCluster: relatedCluster || undefined,
        },
        token,
      );
      setClaimText("");
      setReason("");
      setEvidenceUrl("");
      setRelatedCluster("");
      setClaimType(claimTypes[0]);
      setRefutablePoint("");
      setSuccessMessage(
        response.status === "received"
          ? "주장이 접수되었습니다. 검토 후 쟁점 정리에 반영됩니다."
          : "주장을 제출했습니다.",
      );
    } catch (error) {
      setErrorMessage(
        getUserActionMessage(error, "주장 제출을 처리하지 못했습니다."),
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      <label className="block text-sm font-medium text-gray-700">
        주장
        <textarea
          value={claimText}
          onChange={(event) => setClaimText(event.target.value)}
          required
          className="mt-2 min-h-24 w-full resize-none rounded-md border border-gray-300 px-3 py-2 text-[15px] leading-6 text-gray-900 outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-600/20"
          placeholder="검증하거나 쟁점에 추가해야 할 주장을 적어 주세요."
        />
      </label>
      <label className="mt-4 block text-sm font-medium text-gray-700">
        이유
        <textarea
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          required
          className="mt-2 min-h-20 w-full resize-none rounded-md border border-gray-300 px-3 py-2 text-[15px] leading-6 text-gray-900 outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-600/20"
          placeholder="이 주장이 쟁점 이해에 왜 필요한지 적어 주세요."
        />
      </label>
      <label className="mt-4 block text-sm font-medium text-gray-700">
        근거 링크
        <input
          type="url"
          value={evidenceUrl}
          onChange={(event) => setEvidenceUrl(event.target.value)}
          className="mt-2 h-10 w-full rounded-md border border-gray-300 px-3 text-[15px] text-gray-900 outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-600/20"
          placeholder="https://"
        />
      </label>
      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <label className="block text-sm font-medium text-gray-700">
          관련 쟁점
          <input
            value={relatedCluster}
            onChange={(event) => setRelatedCluster(event.target.value)}
            className="mt-2 h-10 w-full rounded-md border border-gray-300 px-3 text-[15px] text-gray-900 outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-600/20"
            placeholder="예: 책임 소재, 최신 수치, 법적 쟁점"
          />
        </label>
        <label className="block text-sm font-medium text-gray-700">
          주장 유형
          <select
            value={claimType}
            onChange={(event) => setClaimType(event.target.value)}
            className="mt-2 h-10 w-full rounded-md border border-gray-300 bg-white px-3 text-[15px] text-gray-900 outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-600/20"
          >
            {claimTypes.map((type) => (
              <option key={type}>{type}</option>
            ))}
          </select>
        </label>
      </div>
      <label className="mt-4 block text-sm font-medium text-gray-700">
        반박 가능 지점
        <textarea
          value={refutablePoint}
          onChange={(event) => setRefutablePoint(event.target.value)}
          required
          className="mt-2 min-h-20 w-full resize-none rounded-md border border-gray-300 px-3 py-2 text-[15px] leading-6 text-gray-900 outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-600/20"
          placeholder="어떤 공식 자료나 반론이 나오면 판단이 달라질 수 있는지 적어 주세요."
        />
      </label>
      <button
        type="submit"
        disabled={isSubmitting}
        className="mt-4 inline-flex h-10 w-full items-center justify-center gap-2 rounded-md bg-blue-600 px-4 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
      >
        <Send className="size-4" aria-hidden="true" />
        {isSubmitting ? "제출 중" : "구조화된 주장 제출"}
      </button>
      {errorMessage ? (
        <p className="mt-3 text-sm leading-6 text-red-600">
          {errorMessage}
        </p>
      ) : null}
      {successMessage ? (
        <p className="mt-3 text-sm font-semibold leading-6 text-blue-700" role="status">
          {successMessage}
        </p>
      ) : null}
    </form>
  );
}
