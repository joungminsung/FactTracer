"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { RefreshCw } from "lucide-react";
import { useAuth } from "@/components/auth/auth-provider";
import {
  approveAdminIssue,
  createSourceDomain,
  resolveAdminReport,
  runIssueReverification,
  syncAdminQueue,
  triggerAdminAgent,
  updateSourceDomainConfig,
  updateSourceDomainPolicy,
  updateSourceDomainStatus,
} from "@/lib/api/facttracer";
import type { SourceDomain } from "@/lib/api/types";
import { getUserActionMessage } from "@/lib/api/messages";
import { formatProcessingName } from "@/lib/display";

type ActionState = {
  errorMessage: string | null;
  isSubmitting: boolean;
};

export function AdminQueueSyncButton() {
  const { token } = useAuth();
  const [state, setState] = useState<ActionState>({
    errorMessage: null,
    isSubmitting: false,
  });

  async function handleClick() {
    setState({ errorMessage: null, isSubmitting: true });
    try {
      await syncAdminQueue(token);
      setState({ errorMessage: null, isSubmitting: false });
    } catch (error) {
      setState({
        errorMessage: getUserActionMessage(error, "목록 갱신에 실패했습니다."),
        isSubmitting: false,
      });
    }
  }

  return (
    <div>
      <button
        type="button"
        onClick={handleClick}
        disabled={state.isSubmitting}
        className="inline-flex h-10 items-center gap-2 rounded-md bg-blue-600 px-4 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
      >
        <RefreshCw className="size-4" aria-hidden="true" />
        {state.isSubmitting ? "갱신 중" : "목록 갱신"}
      </button>
      {state.errorMessage ? (
        <p className="mt-2 text-xs font-semibold text-red-600">
          {state.errorMessage}
        </p>
      ) : null}
    </div>
  );
}

export function AdminIssueActionButtons({
  issueId,
  showOpenLink = true,
}: {
  issueId: string;
  showOpenLink?: boolean;
}) {
  const { token } = useAuth();
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [approvalMemo, setApprovalMemo] = useState("");
  const [checks, setChecks] = useState({
    counterClaims: false,
    noPendingHold: false,
    officialSources: false,
    refinedLanguage: false,
  });
  const canApprove =
    approvalMemo.trim().length >= 6 && Object.values(checks).every(Boolean);

  async function handleApprove() {
    if (!canApprove) {
      setErrorMessage("공식 출처, 반론, 표현 정제, 보류 사유를 확인하고 승인 메모를 남겨 주세요.");
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);
    try {
      await approveAdminIssue(issueId, token);
    } catch (error) {
      setErrorMessage(getUserActionMessage(error, "출고 승인에 실패했습니다."));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div>
      <div className="flex gap-2">
        {showOpenLink ? (
          <Link
            href={`/admin/issues/${issueId}`}
            className="inline-flex h-10 items-center rounded-md border border-gray-200 px-4 text-sm font-bold text-gray-700"
          >
            검토 열기
          </Link>
        ) : null}
        <button
          type="button"
          onClick={handleApprove}
          disabled={isSubmitting || !canApprove}
          className="h-10 rounded-md bg-blue-600 px-4 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
        >
          {isSubmitting ? "승인 중" : "승인 게시"}
        </button>
      </div>
      <div className="mt-3 border-t border-gray-200 pt-3">
        <p className="text-xs font-bold text-gray-500">게시 전 체크리스트</p>
        <div className="mt-2 grid gap-2 text-xs font-semibold text-gray-700">
          {[
            ["officialSources", "공식 출처와 기준 시점을 확인함"],
            ["counterClaims", "반론과 공통분모를 확인함"],
            ["refinedLanguage", "낙인/단정 표현을 정제함"],
            ["noPendingHold", "남은 보류 사유가 없음"],
          ].map(([key, label]) => (
            <label key={key} className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={checks[key as keyof typeof checks]}
                onChange={(event) =>
                  setChecks((current) => ({
                    ...current,
                    [key]: event.target.checked,
                  }))
                }
                className="size-4 accent-blue-700"
              />
              {label}
            </label>
          ))}
        </div>
        <label className="mt-3 block text-xs font-bold text-gray-600">
          승인 메모
          <textarea
            value={approvalMemo}
            onChange={(event) => setApprovalMemo(event.target.value)}
            className="mt-1 min-h-20 w-full resize-none rounded-md border border-gray-200 px-3 py-2 text-sm leading-6 font-medium text-gray-900 outline-none"
            placeholder="게시 판단 사유를 남겨 주세요."
          />
        </label>
      </div>
      {errorMessage ? (
        <p className="mt-2 text-xs font-semibold text-red-600">
          {errorMessage}
        </p>
      ) : null}
    </div>
  );
}

export function AdminReportResolveButtons({ reportId }: { reportId: string }) {
  const router = useRouter();
  const { token } = useAuth();
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [replacement, setReplacement] = useState("");
  const [reasonMemo, setReasonMemo] = useState("");

  async function handleResolve(status: "resolved" | "dismissed") {
    if (status === "resolved" && replacement.trim().length < 2) {
      setErrorMessage("처리할 때는 대체 표현을 남겨 주세요.");
      return;
    }
    if (reasonMemo.trim().length < 4) {
      setErrorMessage("처리 사유를 남겨 주세요.");
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);
    try {
      await resolveAdminReport(reportId, status, token);
      router.refresh();
    } catch (error) {
      setErrorMessage(getUserActionMessage(error, "신고 처리에 실패했습니다."));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div>
      <label className="block text-xs font-bold text-gray-600">
        대체 표현
        <input
          value={replacement}
          onChange={(event) => setReplacement(event.target.value)}
          className="mt-1 h-9 w-full rounded-md border border-gray-200 px-2 text-sm font-medium text-gray-900 outline-none"
          placeholder="낙인 없이 바꿀 표현"
        />
      </label>
      <label className="mt-2 block text-xs font-bold text-gray-600">
        처리 사유
        <textarea
          value={reasonMemo}
          onChange={(event) => setReasonMemo(event.target.value)}
          className="mt-1 min-h-16 w-full resize-none rounded-md border border-gray-200 px-2 py-2 text-sm font-medium leading-5 text-gray-900 outline-none"
          placeholder="근거 부족, 표현 정제, 기각 사유 등"
        />
      </label>
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          disabled={isSubmitting}
          onClick={() => handleResolve("resolved")}
          className="h-9 rounded-md bg-blue-600 px-3 text-xs font-medium text-white disabled:opacity-50"
        >
          표현 정제 처리
        </button>
        <button
          type="button"
          disabled={isSubmitting}
          onClick={() => handleResolve("dismissed")}
          className="h-9 rounded-md border border-gray-200 px-3 text-xs font-bold text-gray-700 disabled:text-gray-400"
        >
          기각
        </button>
      </div>
      {errorMessage ? (
        <p className="mt-2 text-xs font-semibold text-red-600">
          {errorMessage}
        </p>
      ) : null}
    </div>
  );
}

export function AdminSourceStatusButtons({ domainId }: { domainId: string }) {
  const { token } = useAuth();
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleStatus(status: "trusted" | "watch" | "blocked") {
    setIsSubmitting(true);
    setErrorMessage(null);
    try {
      await updateSourceDomainStatus(domainId, status, token);
    } catch (error) {
      setErrorMessage(
        getUserActionMessage(error, "출처 상태 변경에 실패했습니다."),
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div>
      <div className="flex flex-wrap gap-2">
        {[
          ["trusted", "신뢰"],
          ["watch", "감시"],
          ["blocked", "차단"],
        ].map(([status, label]) => (
          <button
            key={status}
            type="button"
            disabled={isSubmitting}
            onClick={() =>
              handleStatus(status as "trusted" | "watch" | "blocked")
            }
            className="h-9 rounded-md border border-gray-200 px-3 text-xs font-bold text-gray-700 disabled:text-gray-400"
          >
            {label}
          </button>
        ))}
      </div>
      {errorMessage ? (
        <p className="mt-2 text-xs font-semibold text-red-600">
          {errorMessage}
        </p>
      ) : null}
    </div>
  );
}

export function AdminSourcePolicyForm({
  credibility,
  domainId,
  intervalMinutes,
  status,
}: {
  credibility: number;
  domainId: string;
  intervalMinutes?: number | null;
  status: string;
}) {
  const { token } = useAuth();
  const [nextStatus, setNextStatus] = useState(status);
  const [nextCredibility, setNextCredibility] = useState(
    Math.round(credibility * 100),
  );
  const [nextInterval, setNextInterval] = useState(intervalMinutes ?? 30);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setErrorMessage(null);
    try {
      await updateSourceDomainPolicy(
        domainId,
        {
          collectionIntervalMinutes: nextInterval,
          credibility: nextCredibility / 100,
          status: nextStatus,
        },
        token,
      );
    } catch (error) {
      setErrorMessage(
        getUserActionMessage(error, "출처 정책 저장에 실패했습니다."),
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="grid gap-3">
      <div className="grid gap-2 sm:grid-cols-3">
        <label className="grid gap-1 text-xs font-bold text-gray-600">
          상태
          <select
            value={nextStatus}
            onChange={(event) => setNextStatus(event.target.value)}
            className="h-9 rounded-md border border-gray-300 bg-white px-2 text-sm font-semibold text-gray-900 outline-none focus:border-blue-700 focus:ring-2 focus:ring-blue-100"
          >
            <option value="trusted">신뢰</option>
            <option value="watch">감시</option>
            <option value="blocked">차단</option>
          </select>
        </label>
        <label className="grid gap-1 text-xs font-bold text-gray-600">
          신뢰도
          <input
            type="number"
            min={0}
            max={100}
            value={nextCredibility}
            onChange={(event) =>
              setNextCredibility(Number.parseInt(event.target.value || "0", 10))
            }
            className="h-9 rounded-md border border-gray-300 px-2 text-sm font-semibold text-gray-900 outline-none focus:border-blue-700 focus:ring-2 focus:ring-blue-100"
          />
        </label>
        <label className="grid gap-1 text-xs font-bold text-gray-600">
          수집 주기
          <input
            type="number"
            min={1}
            value={nextInterval}
            onChange={(event) =>
              setNextInterval(Number.parseInt(event.target.value || "1", 10))
            }
            className="h-9 rounded-md border border-gray-300 px-2 text-sm font-semibold text-gray-900 outline-none focus:border-blue-700 focus:ring-2 focus:ring-blue-100"
          />
        </label>
      </div>
      <div className="flex items-center gap-3">
        <button
          type="submit"
          disabled={isSubmitting}
          className="h-9 rounded-md bg-blue-600 px-3 text-xs font-medium text-white disabled:opacity-50"
        >
          {isSubmitting ? "저장 중" : "정책 저장"}
        </button>
        {errorMessage ? (
          <p className="text-xs font-semibold text-red-600">
            {errorMessage}
          </p>
        ) : null}
      </div>
    </form>
  );
}

const sourceTypes = [
  ["rss", "RSS"],
  ["official", "공식자료"],
  ["public", "공공자료"],
  ["news", "뉴스"],
  ["social", "SNS"],
  ["youtube", "YouTube"],
] as const;

export function AdminSourceConfigForm({
  source,
}: {
  source?: SourceDomain;
}) {
  const router = useRouter();
  const { token } = useAuth();
  const [domain, setDomain] = useState(source?.domain ?? "");
  const [name, setName] = useState(source?.name ?? "");
  const [sourceType, setSourceType] = useState(source?.sourceType ?? "rss");
  const [collectionUrl, setCollectionUrl] = useState(
    source?.collectionUrl ?? "",
  );
  const [status, setStatus] = useState(source?.status ?? "watch");
  const [credibility, setCredibility] = useState(
    Math.round((source?.credibility ?? 0.5) * 100),
  );
  const [intervalMinutes, setIntervalMinutes] = useState(
    source?.collectionIntervalMinutes ?? 30,
  );
  const [isActive, setIsActive] = useState(source?.isActive ?? true);
  const [note, setNote] = useState(source?.note ?? "");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setErrorMessage(null);
    const payload = {
      collectionIntervalMinutes: intervalMinutes,
      collectionUrl: collectionUrl || null,
      credibility: credibility / 100,
      domain,
      isActive,
      name,
      note,
      sourceType,
      status,
    };
    try {
      if (source) {
        await updateSourceDomainConfig(
          source.id,
          payload,
          token,
        );
      } else {
        await createSourceDomain(payload, token);
        setDomain("");
        setName("");
        setCollectionUrl("");
        setNote("");
      }
      router.refresh();
    } catch (error) {
      setErrorMessage(
        getUserActionMessage(error, "출처 설정 저장에 실패했습니다."),
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="grid gap-3">
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <label className="grid gap-1 text-xs font-bold text-gray-600">
          식별자
          <input
            required
            value={domain}
            onChange={(event) => setDomain(event.target.value)}
            className="h-9 rounded-md border border-gray-300 px-2 text-sm font-semibold text-gray-900 outline-none focus:border-blue-700 focus:ring-2 focus:ring-blue-100"
            placeholder="example.com"
          />
        </label>
        <label className="grid gap-1 text-xs font-bold text-gray-600">
          이름
          <input
            required
            value={name}
            onChange={(event) => setName(event.target.value)}
            className="h-9 rounded-md border border-gray-300 px-2 text-sm font-semibold text-gray-900 outline-none focus:border-blue-700 focus:ring-2 focus:ring-blue-100"
            placeholder="출처명"
          />
        </label>
        <label className="grid gap-1 text-xs font-bold text-gray-600">
          타입
          <select
            value={sourceType}
            onChange={(event) => setSourceType(event.target.value)}
            className="h-9 rounded-md border border-gray-300 bg-white px-2 text-sm font-semibold text-gray-900 outline-none focus:border-blue-700 focus:ring-2 focus:ring-blue-100"
          >
            {sourceTypes.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label className="grid gap-1 text-xs font-bold text-gray-600">
          상태
          <select
            value={status}
            onChange={(event) => setStatus(event.target.value)}
            className="h-9 rounded-md border border-gray-300 bg-white px-2 text-sm font-semibold text-gray-900 outline-none focus:border-blue-700 focus:ring-2 focus:ring-blue-100"
          >
            <option value="trusted">신뢰</option>
            <option value="watch">감시</option>
            <option value="blocked">차단</option>
          </select>
        </label>
      </div>

      <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_120px_120px_120px]">
        <label className="grid gap-1 text-xs font-bold text-gray-600">
          수집 링크
          <input
            value={collectionUrl}
            onChange={(event) => setCollectionUrl(event.target.value)}
            className="h-9 rounded-md border border-gray-300 px-2 text-sm font-semibold text-gray-900 outline-none focus:border-blue-700 focus:ring-2 focus:ring-blue-100"
            placeholder="https://..."
          />
        </label>
        <label className="grid gap-1 text-xs font-bold text-gray-600">
          신뢰도
          <input
            type="number"
            min={0}
            max={100}
            value={credibility}
            onChange={(event) =>
              setCredibility(Number.parseInt(event.target.value || "0", 10))
            }
            className="h-9 rounded-md border border-gray-300 px-2 text-sm font-semibold text-gray-900 outline-none focus:border-blue-700 focus:ring-2 focus:ring-blue-100"
          />
        </label>
        <label className="grid gap-1 text-xs font-bold text-gray-600">
          수집 주기
          <input
            type="number"
            min={1}
            value={intervalMinutes}
            onChange={(event) =>
              setIntervalMinutes(Number.parseInt(event.target.value || "1", 10))
            }
            className="h-9 rounded-md border border-gray-300 px-2 text-sm font-semibold text-gray-900 outline-none focus:border-blue-700 focus:ring-2 focus:ring-blue-100"
          />
        </label>
        <label className="flex items-end gap-2 text-xs font-bold text-gray-600">
          <input
            type="checkbox"
            checked={isActive}
            onChange={(event) => setIsActive(event.target.checked)}
            className="mb-2 size-4 rounded border-gray-300 text-blue-600"
          />
          <span className="pb-2">수집 활성</span>
        </label>
      </div>

      <label className="grid gap-1 text-xs font-bold text-gray-600">
        메모
        <textarea
          value={note}
          onChange={(event) => setNote(event.target.value)}
          rows={2}
          className="min-h-16 rounded-md border border-gray-300 px-2 py-2 text-sm font-semibold leading-6 text-gray-900 outline-none focus:border-blue-700 focus:ring-2 focus:ring-blue-100"
        />
      </label>

      <div className="flex flex-wrap items-center gap-3">
        <button
          type="submit"
          disabled={isSubmitting}
          className="h-9 rounded-md bg-blue-600 px-3 text-xs font-medium text-white disabled:opacity-50"
        >
          {isSubmitting ? "저장 중" : source ? "설정 저장" : "출처 등록"}
        </button>
        {errorMessage ? (
          <p className="text-xs font-semibold text-red-600">
            {errorMessage}
          </p>
        ) : null}
      </div>
    </form>
  );
}

export function AdminAgentRunButton({ agent }: { agent: string }) {
  const router = useRouter();
  const { token } = useAuth();
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const processingName = formatProcessingName(agent);

  async function handleClick() {
    setIsSubmitting(true);
    setErrorMessage(null);
    try {
      await triggerAdminAgent(agent, token);
      router.refresh();
    } catch (error) {
      setErrorMessage(getUserActionMessage(error, "작업 실행에 실패했습니다."));
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
        aria-label={`${processingName} 실행`}
        className="h-9 rounded-md bg-blue-600 px-3 text-xs font-medium text-white disabled:opacity-50"
      >
        {isSubmitting ? "실행 중" : "실행"}
      </button>
      {errorMessage ? (
        <p className="mt-2 text-xs font-semibold text-red-600">
          {errorMessage}
        </p>
      ) : null}
    </div>
  );
}

export function AdminReverificationForm({ issueId }: { issueId: string }) {
  const { token } = useAuth();
  const [priority, setPriority] = useState<"high" | "medium" | "low">("high");
  const [memo, setMemo] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      await runIssueReverification(
        issueId,
        { memo, priority },
        token,
      );
    } catch (error) {
      setErrorMessage(
        getUserActionMessage(error, "재검증 실행에 실패했습니다."),
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      <label className="mt-4 block text-sm font-semibold text-gray-700">
        우선순위
        <select
          value={priority}
          onChange={(event) =>
            setPriority(event.target.value as "high" | "medium" | "low")
          }
          className="mt-2 h-10 w-full rounded-md border border-gray-200 bg-white px-3 text-sm outline-none"
        >
          <option value="high">높음</option>
          <option value="medium">중간</option>
          <option value="low">낮음</option>
        </select>
      </label>
      <label className="mt-4 block text-sm font-semibold text-gray-700">
        검토 메모
        <textarea
          value={memo}
          onChange={(event) => setMemo(event.target.value)}
          className="mt-2 min-h-28 w-full resize-none rounded-md border border-gray-200 px-3 py-2 text-sm leading-6 outline-none"
          placeholder="판정 변경 사유, 출처 보강 지시, 낙인 표현 정제 기준을 남기세요."
        />
      </label>
      <button
        type="submit"
        disabled={isSubmitting}
        className="mt-4 inline-flex h-10 w-full items-center justify-center gap-2 rounded-md bg-blue-600 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
      >
        <RefreshCw className="size-4" aria-hidden="true" />
        {isSubmitting ? "실행 중" : "재검증 실행"}
      </button>
      {errorMessage ? (
        <p className="mt-3 text-sm font-semibold leading-6 text-red-600">
          {errorMessage}
        </p>
      ) : null}
    </form>
  );
}
