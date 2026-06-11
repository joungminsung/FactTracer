"use client";

import { FormEvent, useState } from "react";
import { SlidersHorizontal } from "lucide-react";
import { useAuth } from "@/components/auth/auth-provider";
import { updateUserPreferences } from "@/lib/api/auth";
import { getUserActionMessage } from "@/lib/api/messages";
import type { NotificationSettings } from "@/lib/api/types";

const defaultSettings: NotificationSettings = {
  dailyDigest: false,
  numberChanges: true,
  officialSourceChanges: true,
  preferredPerspective: "균형",
  reviewCompleted: true,
  timelineUpdates: true,
};

const settingLabels: Array<{
  key: keyof Omit<NotificationSettings, "preferredPerspective">;
  label: string;
}> = [
  { key: "officialSourceChanges", label: "공식 자료 변경" },
  { key: "numberChanges", label: "수치 변경" },
  { key: "reviewCompleted", label: "검토 완료" },
  { key: "timelineUpdates", label: "타임라인 업데이트" },
  { key: "dailyDigest", label: "하루 요약" },
];

export function PreferenceForm({
  initialSettings = defaultSettings,
}: {
  initialSettings?: NotificationSettings;
}) {
  const { token } = useAuth();
  const [settings, setSettings] = useState(initialSettings);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  function toggleSetting(
    key: keyof Omit<NotificationSettings, "preferredPerspective">,
  ) {
    setSettings((current) => ({ ...current, [key]: !current[key] }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!token) {
      setErrorMessage("로그인이 필요합니다.");
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      await updateUserPreferences(settings, token);
    } catch (error) {
      setErrorMessage(
        getUserActionMessage(error, "설정을 저장하지 못했습니다."),
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      <div className="flex items-center gap-2">
        <SlidersHorizontal className="size-4 text-blue-600" aria-hidden="true" />
        <h2 className="text-xl font-bold text-gray-900">알림/관심 설정</h2>
      </div>

      <div className="mt-4 divide-y divide-gray-100 border-y border-gray-200">
        {settingLabels.map((item) => (
          <label
            key={item.key}
            className="flex min-h-12 items-center justify-between gap-4 py-3 text-sm font-semibold text-gray-700"
          >
            <span>{item.label}</span>
            <input
              checked={settings[item.key]}
              onChange={() => toggleSetting(item.key)}
              type="checkbox"
              className="size-4 accent-blue-700"
            />
          </label>
        ))}
      </div>

      <label className="mt-4 block text-sm font-semibold text-gray-700">
        관심 관점
        <select
          value={settings.preferredPerspective}
          onChange={(event) =>
            setSettings((current) => ({
              ...current,
              preferredPerspective: event.target.value,
            }))
          }
          className="mt-2 h-10 w-full rounded-md border border-gray-200 bg-white px-3 text-sm outline-none"
        >
          <option>균형</option>
          <option>공식 자료 우선</option>
          <option>수치 변화 우선</option>
          <option>반박 근거 우선</option>
        </select>
      </label>

      <button
        type="submit"
        disabled={isSubmitting}
        className="mt-4 h-10 rounded-md bg-blue-600 px-4 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
      >
        {isSubmitting ? "저장 중" : "설정 저장"}
      </button>
      {errorMessage ? (
        <p className="mt-2 text-xs font-semibold text-red-600">
          {errorMessage}
        </p>
      ) : null}
    </form>
  );
}
