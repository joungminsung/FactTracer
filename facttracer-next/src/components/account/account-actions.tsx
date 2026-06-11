"use client";

import { FormEvent, useState } from "react";
import { useAuth } from "@/components/auth/auth-provider";
import {
  cancelVerificationRequest,
  removeSavedIssue,
  withdrawSubmittedClaim,
} from "@/lib/api/facttracer";
import { updateCurrentUserProfile } from "@/lib/api/auth";
import { getUserActionMessage } from "@/lib/api/messages";

export function ProfileForm({ initialName }: { initialName: string }) {
  const { refreshUser, token } = useAuth();
  const [name, setName] = useState(initialName);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token) {
      setErrorMessage("로그인이 필요합니다.");
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);
    try {
      await updateCurrentUserProfile({ name }, token);
      await refreshUser();
    } catch (error) {
      setErrorMessage(
        getUserActionMessage(error, "프로필 저장에 실패했습니다."),
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="border-t border-gray-200 pt-5">
      <label className="block text-sm font-semibold text-gray-700">
        표시 이름
        <input
          value={name}
          onChange={(event) => setName(event.target.value)}
          required
          className="mt-2 h-10 w-full rounded-md border border-gray-200 px-3 text-sm outline-none"
        />
      </label>
      <button
        type="submit"
        disabled={isSubmitting}
        className="mt-3 h-10 rounded-md bg-blue-600 px-4 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
      >
        {isSubmitting ? "저장 중" : "프로필 저장"}
      </button>
      {errorMessage ? (
        <p className="mt-2 text-xs font-semibold text-red-600">
          {errorMessage}
        </p>
      ) : null}
    </form>
  );
}

export function UserRowAction({
  id,
  type,
}: {
  id: string;
  type: "savedIssue" | "submittedClaim" | "verificationRequest";
}) {
  const { token } = useAuth();
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const label =
    type === "savedIssue"
      ? "저장 해제"
      : type === "submittedClaim"
        ? "철회"
        : "취소";

  async function handleClick() {
    setIsSubmitting(true);
    setErrorMessage(null);
    try {
      await (
        type === "savedIssue"
          ? removeSavedIssue(id, token)
          : type === "submittedClaim"
            ? withdrawSubmittedClaim(id, token)
            : cancelVerificationRequest(id, token)
      );
    } catch (error) {
      setErrorMessage(getUserActionMessage(error, "요청 처리에 실패했습니다."));
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
        className="mt-2 text-xs font-bold text-gray-500 hover:text-red-600 disabled:cursor-not-allowed"
      >
        {isSubmitting ? "처리 중" : label}
      </button>
      {errorMessage ? (
        <p className="mt-1 text-xs font-semibold text-red-600">
          {errorMessage}
        </p>
      ) : null}
    </div>
  );
}
