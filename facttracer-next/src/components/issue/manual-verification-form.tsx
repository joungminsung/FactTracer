"use client";

import { ChangeEvent, FormEvent, useState } from "react";
import { FileUp, Link as LinkIcon, Send, TextCursorInput, Video } from "lucide-react";
import { useAuth } from "@/components/auth/auth-provider";
import {
  registerVerificationFile,
  submitManualCheck,
} from "@/lib/api/facttracer";
import { getUserActionMessage } from "@/lib/api/messages";
import type { ManualCheckRequest } from "@/lib/api/types";

type ManualInputMode = "url" | "text" | "youtube" | "file";

const modeOptions: Array<{
  description: string;
  icon: typeof LinkIcon;
  label: string;
  value: ManualInputMode;
}> = [
  {
    description: "기사, 보도자료, 공개 문서를 기존 이슈와 연결합니다.",
    icon: LinkIcon,
    label: "링크",
    value: "url",
  },
  {
    description: "기사 본문, 제보 문장, 발표문 일부를 바로 검증합니다.",
    icon: TextCursorInput,
    label: "텍스트",
    value: "text",
  },
  {
    description: "영상 링크와 가능한 자막을 검증 입력으로 처리합니다.",
    icon: Video,
    label: "YouTube",
    value: "youtube",
  },
  {
    description: "PDF, 이미지, 텍스트 파일에서 근거 문장을 추출합니다.",
    icon: FileUp,
    label: "파일",
    value: "file",
  },
];

function readFileAsBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("파일을 읽지 못했습니다."));
    reader.onload = () => {
      const result = String(reader.result ?? "");
      resolve(result.includes(",") ? result.split(",")[1] : result);
    };
    reader.readAsDataURL(file);
  });
}

export function ManualVerificationForm({ issueId }: { issueId?: string }) {
  const { token } = useAuth();
  const [mode, setMode] = useState<ManualInputMode>("url");
  const [content, setContent] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  function handleModeChange(nextMode: ManualInputMode) {
    setMode(nextMode);
    setContent("");
    setFile(null);
    setErrorMessage(null);
    setSuccessMessage(null);
  }

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    setFile(event.target.files?.[0] ?? null);
    setSuccessMessage(null);
  }

  function handleContentChange(value: string) {
    setContent(value);
    setSuccessMessage(null);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErrorMessage(null);
    setSuccessMessage(null);
    setIsSubmitting(true);

    try {
      let payload: ManualCheckRequest;

      if (mode === "file") {
        if (!file) {
          throw new Error("검증할 파일을 선택해 주세요.");
        }
        const contentBase64 = await readFileAsBase64(file);
        const registered = await registerVerificationFile(
          {
            contentBase64,
            contentType: file.type || "text/plain",
            filename: file.name,
            sizeBytes: file.size,
          },
          token,
        );
        payload = {
          content: registered.id,
          inputType: "file",
          issueId,
        };
      } else {
        payload = {
          content,
          inputType: mode,
          issueId,
        };
      }

      const response = await submitManualCheck(payload, token);
      if (response.status === "rejected") {
        setErrorMessage(response.message || "입력한 내용을 다시 확인해 주세요.");
      } else {
        setContent("");
        setFile(null);
        setSuccessMessage(response.message || "분석 요청이 접수되었습니다.");
      }
    } catch (error) {
      setErrorMessage(
        getUserActionMessage(error, "분석 요청을 처리하지 못했습니다."),
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form id="manual-verification" onSubmit={handleSubmit}>
      <div className="flex items-center justify-between gap-4">
        <h2 className="text-base font-bold text-gray-900">직접 검증 입력</h2>
        <span className="text-xs font-medium text-gray-500">이슈 매칭 또는 단독 결과</span>
      </div>

      <div className="mt-4 grid gap-2 sm:grid-cols-4">
        {modeOptions.map((option) => {
          const Icon = option.icon;
          const isSelected = mode === option.value;

          return (
            <button
              key={option.value}
              type="button"
              onClick={() => handleModeChange(option.value)}
              className={`min-h-24 rounded-md border px-3 py-3 text-left ${
                isSelected
                  ? "border-blue-300 bg-gray-50 text-blue-600"
                  : "border-gray-200 text-gray-700 hover:border-gray-300"
              }`}
            >
              <span className="flex items-center gap-2 text-sm font-bold">
                <Icon className="size-4" aria-hidden="true" />
                {option.label}
              </span>
              <span className="mt-2 block text-xs font-medium leading-5 text-gray-500">
                {option.description}
              </span>
            </button>
          );
        })}
      </div>

      {mode === "text" ? (
        <label className="mt-4 block text-sm font-semibold text-gray-700">
          검증할 텍스트
          <textarea
            value={content}
            onChange={(event) => handleContentChange(event.target.value)}
            required
            className="mt-2 min-h-36 w-full resize-y rounded-md border border-gray-200 px-3 py-2 text-sm leading-6 outline-none"
            placeholder="검증할 기사 본문, 발표문, 제보 내용을 붙여 넣으세요."
          />
        </label>
      ) : mode === "file" ? (
        <label className="mt-4 flex min-h-28 cursor-pointer items-center gap-3 rounded-md border border-dashed border-gray-300 px-4 py-4 text-sm font-semibold text-gray-700">
          <FileUp className="size-5 text-blue-600" aria-hidden="true" />
          <span className="min-w-0">
            <span className="block">{file ? file.name : "PDF, 이미지, 텍스트 파일 선택"}</span>
            <span className="mt-1 block text-xs font-medium text-gray-500">
              문자 인식 또는 텍스트 추출 후 주장 검증 흐름으로 보냅니다.
            </span>
          </span>
          <input
            type="file"
            accept="application/pdf,image/*,text/plain"
            onChange={handleFileChange}
            required
            className="sr-only"
          />
        </label>
      ) : (
        <label className="mt-4 flex h-11 items-center gap-2 rounded-md border border-gray-200 px-3 text-gray-500">
          {mode === "youtube" ? (
            <Video className="size-4" aria-hidden="true" />
          ) : (
            <LinkIcon className="size-4" aria-hidden="true" />
          )}
          <input
            type="url"
            value={content}
            onChange={(event) => handleContentChange(event.target.value)}
            required
            className="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-gray-400"
            placeholder={mode === "youtube" ? "YouTube 링크" : "뉴스, 보도자료, 원문 링크"}
          />
        </label>
      )}

      <button
        type="submit"
        disabled={isSubmitting}
        className="mt-4 flex h-11 w-full items-center justify-center gap-2 rounded-md bg-blue-600 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
      >
        <Send className="size-4" aria-hidden="true" />
        {isSubmitting ? "요청 중" : "분석 요청"}
      </button>

      {errorMessage ? (
        <p className="mt-3 text-sm font-semibold leading-6 text-red-600">
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
