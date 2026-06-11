"use client";

import { FormEvent, useState } from "react";
import { RefreshCw, WandSparkles } from "lucide-react";
import { useAuth } from "@/components/auth/auth-provider";
import { getUserActionMessage } from "@/lib/api/messages";
import {
  generatePodcasts,
  renderPodcastAudio,
  updateAdminPodcastStatus,
} from "@/lib/api/podcasts";

export function AdminPodcastGenerateForm() {
  const { token } = useAuth();
  const [feed, setFeed] = useState("recommended");
  const [topic, setTopic] = useState("");
  const [format, setFormat] = useState("");
  const [variant, setVariant] = useState("standard");
  const [limit, setLimit] = useState(3);
  const [renderAudio, setRenderAudio] = useState(true);
  const [force, setForce] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setErrorMessage(null);
    setMessage(null);
    try {
      const result = await generatePodcasts({
        feed,
        force,
        format: format || null,
        limit,
        renderAudio,
        token,
        topic: topic || null,
        variant,
      });
      setMessage(`${result.generatedCount}개 회차 생성 요청이 완료됐습니다.`);
    } catch (error) {
      setErrorMessage(
        getUserActionMessage(error, "팟캐스트 생성 요청에 실패했습니다."),
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="grid gap-4 border-y border-gray-200 py-5"
    >
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <label className="text-xs font-bold text-gray-600">
          피드
          <select
            value={feed}
            onChange={(event) => setFeed(event.target.value)}
            className="mt-1 h-10 w-full rounded-md border border-gray-200 px-3 text-sm font-semibold text-gray-900"
          >
            <option value="recommended">추천</option>
            <option value="personalized">개인화</option>
            <option value="featured">특집</option>
            <option value="latest">최신</option>
            <option value="ranking">랭킹</option>
            <option value="category">카테고리</option>
            <option value="daily">종합</option>
            <option value="urgent">긴급</option>
          </select>
        </label>
        <label className="text-xs font-bold text-gray-600">
          카테고리
          <input
            value={topic}
            onChange={(event) => setTopic(event.target.value)}
            className="mt-1 h-10 w-full rounded-md border border-gray-200 px-3 text-sm font-semibold text-gray-900"
            placeholder="정치, 경제 등"
          />
        </label>
        <label className="text-xs font-bold text-gray-600">
          포맷
          <select
            value={format}
            onChange={(event) => setFormat(event.target.value)}
            className="mt-1 h-10 w-full rounded-md border border-gray-200 px-3 text-sm font-semibold text-gray-900"
          >
            <option value="">자동 선택</option>
            <option value="solo">1인 진행</option>
            <option value="panel_2">2인 대화</option>
            <option value="panel_3">3인 토론</option>
          </select>
        </label>
        <label className="text-xs font-bold text-gray-600">
          길이
          <select
            value={variant}
            onChange={(event) => setVariant(event.target.value)}
            className="mt-1 h-10 w-full rounded-md border border-gray-200 px-3 text-sm font-semibold text-gray-900"
          >
            <option value="standard">표준</option>
            <option value="short">짧게</option>
            <option value="deep">심층</option>
          </select>
        </label>
        <label className="text-xs font-bold text-gray-600">
          생성 수
          <input
            type="number"
            min={1}
            max={30}
            value={limit}
            onChange={(event) => setLimit(Number(event.target.value))}
            className="mt-1 h-10 w-full rounded-md border border-gray-200 px-3 text-sm font-semibold text-gray-900"
          />
        </label>
      </div>

      <div className="flex flex-wrap items-center gap-4 text-xs font-bold text-gray-700">
        <label className="inline-flex items-center gap-2">
          <input
            type="checkbox"
            checked={renderAudio}
            onChange={(event) => setRenderAudio(event.target.checked)}
            className="size-4 accent-blue-700"
          />
          생성 후 TTS 렌더링
        </label>
        <label className="inline-flex items-center gap-2">
          <input
            type="checkbox"
            checked={force}
            onChange={(event) => setForce(event.target.checked)}
            className="size-4 accent-blue-700"
          />
          기존 회차 덮어쓰기
        </label>
        <button
          type="submit"
          disabled={isSubmitting}
          className="inline-flex h-10 items-center gap-2 rounded-md bg-blue-600 px-4 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
        >
          <WandSparkles className="size-4" aria-hidden="true" />
          {isSubmitting ? "생성 중" : "팟캐스트 생성"}
        </button>
      </div>

      {message ? <p className="text-sm font-bold text-blue-700">{message}</p> : null}
      {errorMessage ? (
        <p className="text-sm font-bold text-red-600">{errorMessage}</p>
      ) : null}
    </form>
  );
}

export function AdminIssuePodcastGenerateButton({
  issueId,
  topic,
}: {
  issueId: string;
  topic?: string;
}) {
  const { token } = useAuth();
  const [variant, setVariant] = useState("standard");
  const [message, setMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleClick() {
    setIsSubmitting(true);
    setMessage(null);
    setErrorMessage(null);
    try {
      const result = await generatePodcasts({
        feed: "recommended",
        force: true,
        issueId,
        limit: 1,
        renderAudio: false,
        token,
        topic,
        variant,
      });
      setMessage(`${result.generatedCount}개 회차를 생성했습니다.`);
    } catch (error) {
      setErrorMessage(
        getUserActionMessage(error, "이슈 팟캐스트 생성에 실패했습니다."),
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div>
      <div className="grid gap-2">
        <label className="text-xs font-bold text-gray-600">
          회차 길이
          <select
            value={variant}
            onChange={(event) => setVariant(event.target.value)}
            className="mt-1 h-9 w-full rounded-md border border-gray-200 px-2 text-xs font-semibold text-gray-900"
          >
            <option value="standard">표준</option>
            <option value="short">짧게</option>
            <option value="deep">심층</option>
          </select>
        </label>
        <button
          type="button"
          onClick={handleClick}
          disabled={isSubmitting}
          className="inline-flex h-9 items-center justify-center gap-2 rounded-md bg-blue-600 px-3 text-xs font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
        >
          <WandSparkles className="size-4" aria-hidden="true" />
          {isSubmitting ? "생성 중" : "이슈 팟캐스트 생성"}
        </button>
      </div>
      {message ? <p className="mt-2 text-xs font-bold text-blue-700">{message}</p> : null}
      {errorMessage ? (
        <p className="mt-2 text-xs font-bold text-red-600">{errorMessage}</p>
      ) : null}
    </div>
  );
}

export function AdminPodcastRenderButton({ episodeId }: { episodeId: string }) {
  const { token } = useAuth();
  const [message, setMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleClick() {
    setIsSubmitting(true);
    setMessage(null);
    setErrorMessage(null);
    try {
      await renderPodcastAudio(episodeId, { force: true, token });
      setMessage("TTS 렌더링 요청이 완료됐습니다.");
    } catch (error) {
      setErrorMessage(
        getUserActionMessage(error, "TTS 렌더링 요청에 실패했습니다."),
      );
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
        className="inline-flex h-9 items-center gap-2 rounded-md border border-gray-300 px-3 text-xs font-bold text-gray-700 disabled:cursor-not-allowed disabled:opacity-50"
      >
        <RefreshCw className="size-4" aria-hidden="true" />
        {isSubmitting ? "렌더링 중" : "TTS 재렌더"}
      </button>
      {message ? <p className="mt-2 text-xs font-bold text-blue-700">{message}</p> : null}
      {errorMessage ? (
        <p className="mt-2 text-xs font-bold text-red-600">{errorMessage}</p>
      ) : null}
    </div>
  );
}

export function AdminPodcastStatusButtons({
  currentStatus,
  episodeId,
}: {
  currentStatus: string;
  episodeId: string;
}) {
  const { token } = useAuth();
  const [message, setMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleStatus(status: "archived" | "draft" | "published") {
    setIsSubmitting(true);
    setMessage(null);
    setErrorMessage(null);
    try {
      await updateAdminPodcastStatus(episodeId, status, token);
      setMessage("상태를 변경했습니다. 목록을 새로고침하면 반영됩니다.");
    } catch (error) {
      setErrorMessage(
        getUserActionMessage(error, "팟캐스트 상태 변경에 실패했습니다."),
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div>
      <div className="flex flex-wrap gap-2">
        {[
          ["published", "공개"],
          ["draft", "초안"],
          ["archived", "보관"],
        ].map(([status, label]) => (
          <button
            type="button"
            key={status}
            onClick={() =>
              handleStatus(status as "archived" | "draft" | "published")
            }
            disabled={isSubmitting || currentStatus === status}
            className="h-9 rounded-md border border-gray-300 px-3 text-xs font-bold text-gray-700 disabled:cursor-not-allowed disabled:bg-gray-50 disabled:text-gray-400"
          >
            {label}
          </button>
        ))}
      </div>
      {message ? <p className="mt-2 text-xs font-bold text-blue-700">{message}</p> : null}
      {errorMessage ? (
        <p className="mt-2 text-xs font-bold text-red-600">{errorMessage}</p>
      ) : null}
    </div>
  );
}
