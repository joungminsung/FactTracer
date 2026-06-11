"use client";

import { FormEvent, useState } from "react";
import { FileSearch, Link as LinkIcon } from "lucide-react";
import { useAuth } from "@/components/auth/auth-provider";
import { submitArticleVerification } from "@/lib/api/facttracer";
import { getUserActionMessage } from "@/lib/api/messages";

export function ArticleVerificationForm({
  description = "기사 링크를 보내면 기존 이슈와 연결하고, 확보된 근거와 비교합니다.",
  issueId,
  title = "기사 분석 요청",
}: {
  description?: string;
  issueId?: string;
  title?: string;
}) {
  const { token } = useAuth();
  const [articleUrl, setArticleUrl] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErrorMessage(null);
    setSuccessMessage(null);
    setIsSubmitting(true);

    try {
      const response = await submitArticleVerification(
        { articleUrl, issueId },
        token,
      );
      setArticleUrl("");
      setSuccessMessage(response.message || "기사 분석 요청이 접수되었습니다.");
    } catch (error) {
      setErrorMessage(
        getUserActionMessage(error, "분석 요청을 처리하지 못했습니다."),
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form id="article-verification" onSubmit={handleSubmit}>
      <h2 className="text-lg font-semibold text-gray-900">{title}</h2>
      {description ? (
        <p className="mt-2 text-sm leading-6 text-gray-600">
          {description}
        </p>
      ) : null}
      <label className="mt-4 block text-sm font-medium text-gray-700">
        기사 링크
        <span className="mt-2 flex h-10 items-center gap-2 rounded-md border border-gray-300 px-3 text-gray-500 focus-within:border-blue-600 focus-within:ring-2 focus-within:ring-blue-600/20">
          <LinkIcon className="size-4" aria-hidden="true" />
          <input
            type="url"
            value={articleUrl}
            onChange={(event) => {
              setArticleUrl(event.target.value);
              setSuccessMessage(null);
            }}
            required
            className="min-w-0 flex-1 bg-transparent text-[15px] text-gray-900 outline-none placeholder:text-gray-400"
            placeholder="분석할 기사 링크"
          />
        </span>
      </label>
      <button
        type="submit"
        disabled={isSubmitting}
        className="mt-3 flex h-10 w-full items-center justify-center gap-2 rounded-md bg-blue-600 px-4 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
      >
        <FileSearch className="size-4" aria-hidden="true" />
        {isSubmitting ? "요청 중" : "기사 분석 요청"}
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
