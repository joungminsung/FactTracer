"use client";

import { useMemo, useState } from "react";
import {
  CheckCircle2,
  EyeOff,
  RotateCcw,
  Save,
  ToggleLeft,
  ToggleRight,
} from "lucide-react";
import { useAuth } from "@/components/auth/auth-provider";
import { updateAdminSettings } from "@/lib/api/facttracer";
import { getUserActionMessage } from "@/lib/api/messages";
import type {
  AdminSettingItem,
  AdminSettingValue,
  AdminSettingsResponse,
} from "@/lib/api/types";

type DraftValue = string | number | boolean;

function draftFromItem(item: AdminSettingItem): DraftValue {
  if (item.isSecret) return "";
  if (item.valueType === "boolean") return Boolean(item.value);
  if (item.valueType === "list") {
    return Array.isArray(item.value) ? item.value.join("\n") : "";
  }
  return item.value === null || item.value === undefined
    ? ""
    : String(item.value);
}

function payloadValue(
  item: AdminSettingItem,
  value: DraftValue,
): AdminSettingValue {
  if (item.valueType === "boolean") return Boolean(value);
  if (item.valueType === "integer") {
    return value === "" ? null : Number.parseInt(String(value), 10);
  }
  if (item.valueType === "float") {
    return value === "" ? null : Number.parseFloat(String(value));
  }
  if (item.valueType === "list") {
    return String(value)
      .split(/\n|,/)
      .map((entry) => entry.trim())
      .filter(Boolean);
  }
  return String(value);
}

function sourceLabel(source: string) {
  if (source === "admin") return "관리자값";
  if (source === "env") return "환경값";
  return "기본값";
}

function settingDomId(key: string, suffix: string) {
  return `setting-${key.replace(/[^a-zA-Z0-9_-]/g, "-")}-${suffix}`;
}

function isBlankConfiguredSecret(item: AdminSettingItem, value: DraftValue) {
  return item.isSecret && item.configured && String(value).trim() === "";
}

function buildDrafts(response: AdminSettingsResponse) {
  return Object.fromEntries(
    response.groups.flatMap((group) =>
      group.items.map((item) => [item.key, draftFromItem(item)]),
    ),
  ) as Record<string, DraftValue>;
}

export function AdminSettingsConsole({
  initialSettings,
}: {
  initialSettings: AdminSettingsResponse;
}) {
  const { token } = useAuth();
  const [settings, setSettings] = useState(initialSettings);
  const [drafts, setDrafts] = useState<Record<string, DraftValue>>(
    buildDrafts(initialSettings),
  );
  const [activeGroup, setActiveGroup] = useState(
    initialSettings.groups[0]?.id ?? "",
  );
  const [pendingKey, setPendingKey] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const flatItems = useMemo(
    () => settings.groups.flatMap((group) => group.items),
    [settings.groups],
  );
  const activeItems = useMemo(
    () =>
      settings.groups.find((group) => group.id === activeGroup)?.items ??
      flatItems,
    [activeGroup, flatItems, settings.groups],
  );
  const summary = useMemo(() => {
    const adminOverrides = flatItems.filter(
      (item) => item.source === "admin",
    ).length;
    const configuredSecrets = flatItems.filter(
      (item) => item.isSecret && item.configured,
    ).length;
    const restartRequired = flatItems.filter(
      (item) => !item.isRuntimeMutable,
    ).length;
    return {
      adminOverrides,
      configuredSecrets,
      restartRequired,
      total: flatItems.length,
    };
  }, [flatItems]);
  const summaryRows: Array<[string, number]> = [
    ["전체", summary.total],
    ["관리자값", summary.adminOverrides],
    ["연결키", summary.configuredSecrets],
    ["재시작 후", summary.restartRequired],
  ];

  function updateDraft(key: string, value: DraftValue) {
    setDrafts((current) => ({ ...current, [key]: value }));
  }

  function syncResponse(next: AdminSettingsResponse) {
    setSettings(next);
    setDrafts(buildDrafts(next));
  }

  async function saveItem(item: AdminSettingItem) {
    const draftValue = drafts[item.key] ?? "";
    if (isBlankConfiguredSecret(item, draftValue)) {
      setErrorMessage(
        "보안 값은 새 값을 입력한 경우에만 저장할 수 있습니다. 기존 값을 지우려면 초기화를 사용해 주세요.",
      );
      return;
    }

    setPendingKey(item.key);
    setErrorMessage(null);
    try {
      const value = payloadValue(item, draftValue);
      const next = await updateAdminSettings([{ key: item.key, value }], token);
      syncResponse(next);
    } catch (error) {
      setErrorMessage(getUserActionMessage(error, "설정 저장에 실패했습니다."));
    } finally {
      setPendingKey(null);
    }
  }

  async function resetItem(item: AdminSettingItem) {
    setPendingKey(item.key);
    setErrorMessage(null);
    try {
      const next = await updateAdminSettings(
        [{ key: item.key, reset: true }],
        token,
      );
      syncResponse(next);
    } catch (error) {
      setErrorMessage(
        getUserActionMessage(error, "설정 초기화에 실패했습니다."),
      );
    } finally {
      setPendingKey(null);
    }
  }

  function renderControl(
    item: AdminSettingItem,
    {
      descriptionId,
      labelId,
    }: {
      descriptionId: string;
      labelId: string;
    },
  ) {
    const value = drafts[item.key] ?? "";
    const baseClass =
      "w-full border border-gray-300 bg-white px-3 text-sm font-semibold text-gray-900 outline-none transition focus:border-blue-700 focus:ring-2 focus:ring-blue-100";

    if (item.valueType === "boolean") {
      const checked = Boolean(value);
      return (
        <button
          type="button"
          aria-pressed={checked}
          aria-labelledby={labelId}
          aria-describedby={descriptionId}
          onClick={() => updateDraft(item.key, !checked)}
          className={`inline-flex h-10 min-w-28 items-center justify-between gap-3 rounded-md border px-3 text-sm font-bold ${
            checked
              ? "border-blue-700 bg-blue-600 text-white"
              : "border-gray-300 bg-white text-gray-700"
          }`}
        >
          {checked ? "켜짐" : "꺼짐"}
          {checked ? (
            <ToggleRight className="size-4" aria-hidden="true" />
          ) : (
            <ToggleLeft className="size-4" aria-hidden="true" />
          )}
        </button>
      );
    }

    if (item.valueType === "select") {
      return (
        <select
          value={String(value)}
          aria-labelledby={labelId}
          aria-describedby={descriptionId}
          onChange={(event) => updateDraft(item.key, event.target.value)}
          className={`${baseClass} h-10 rounded-md`}
        >
          {item.options.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      );
    }

    if (item.valueType === "list") {
      return (
        <textarea
          value={String(value)}
          aria-labelledby={labelId}
          aria-describedby={descriptionId}
          onChange={(event) => updateDraft(item.key, event.target.value)}
          rows={4}
          className={`${baseClass} min-h-24 resize-y rounded-md py-2 leading-6`}
        />
      );
    }

    return (
      <div className="relative">
        {item.isSecret ? (
          <EyeOff
            className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-gray-400"
            aria-hidden="true"
          />
        ) : null}
        <input
          type={
            item.isSecret
              ? "password"
              : item.valueType === "string"
                ? "text"
                : "number"
          }
          min={item.min ?? undefined}
          max={item.max ?? undefined}
          step={item.step ?? (item.valueType === "float" ? 0.01 : undefined)}
          value={String(value)}
          placeholder={item.isSecret && item.configured ? "설정됨" : undefined}
          aria-labelledby={labelId}
          aria-describedby={descriptionId}
          onChange={(event) => updateDraft(item.key, event.target.value)}
          className={`${baseClass} h-10 rounded-md ${
            item.isSecret ? "pl-9" : ""
          }`}
        />
      </div>
    );
  }

  return (
    <div className="min-w-0">
      <div className="grid border-y border-gray-200 text-sm sm:grid-cols-4">
        {summaryRows.map(([label, value]) => (
          <div
            key={label}
            className="flex items-center justify-between border-b border-gray-100 px-4 py-3 last:border-b-0 sm:border-r sm:border-b-0 sm:last:border-r-0"
          >
            <span className="font-semibold text-gray-500">{label}</span>
            <span className="font-bold text-gray-900">{value}</span>
          </div>
        ))}
      </div>

      <div className="grid min-w-0 gap-6 pt-6 xl:grid-cols-[190px_minmax(0,1fr)]">
        <nav className="flex gap-2 overflow-x-auto border-b border-gray-200 pb-3 xl:block xl:overflow-visible xl:border-r xl:border-b-0 xl:pr-4">
          {settings.groups.map((group) => {
            const isActive = group.id === activeGroup;
            return (
              <button
                type="button"
                key={group.id}
                onClick={() => setActiveGroup(group.id)}
                className={`shrink-0 border-b-2 px-2 py-3 text-left text-sm font-bold xl:block xl:w-full xl:border-b xl:border-l-2 xl:px-4 ${
                  isActive
                    ? "border-blue-700 text-blue-600"
                    : "border-transparent text-gray-600 hover:text-gray-900"
                }`}
              >
                {group.label}
              </button>
            );
          })}
        </nav>

        <div className="min-w-0 divide-y divide-gray-200 border-t border-gray-200">
          {activeItems.map((item) => {
            const labelId = settingDomId(item.key, "label");
            const descriptionId = settingDomId(item.key, "description");

            return (
              <div
                key={item.key}
                className="grid min-w-0 gap-4 py-5 lg:grid-cols-[minmax(220px,0.8fr)_minmax(260px,1fr)_170px_150px]"
              >
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <h2
                      id={labelId}
                      className="text-sm font-bold text-gray-900"
                    >
                      {item.label}
                    </h2>
                    {item.configured ? (
                      <CheckCircle2
                        className="size-4 text-blue-600"
                        aria-hidden="true"
                      />
                    ) : null}
                  </div>
                  <p
                    id={descriptionId}
                    className="mt-1 text-sm leading-6 text-gray-600"
                  >
                    {item.description}
                  </p>
                </div>

                <div className="min-w-0">
                  {renderControl(item, { descriptionId, labelId })}
                </div>

                <div className="text-sm leading-6 text-gray-600">
                  <p className="font-bold text-gray-900">
                    {sourceLabel(item.source)}
                  </p>
                  <p>{item.isRuntimeMutable ? "즉시 반영" : "재시작 후 반영"}</p>
                  {item.unit ? <p>단위 {item.unit}</p> : null}
                </div>

                <div className="flex items-start gap-2">
                  <button
                    type="button"
                    onClick={() => saveItem(item)}
                    disabled={pendingKey === item.key}
                    className="inline-flex h-10 items-center gap-2 rounded-md bg-blue-600 px-3 text-sm font-medium text-white disabled:opacity-50"
                  >
                    <Save className="size-4" aria-hidden="true" />
                    저장
                  </button>
                  <button
                    type="button"
                    onClick={() => resetItem(item)}
                    disabled={pendingKey === item.key}
                    className="inline-flex h-10 items-center gap-2 rounded-md border border-gray-300 px-3 text-sm font-bold text-gray-700 disabled:text-gray-400"
                  >
                    <RotateCcw className="size-4" aria-hidden="true" />
                    초기화
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {errorMessage ? (
        <p className="mt-5 border-t border-gray-200 pt-4 text-sm font-semibold text-red-600">
          {errorMessage}
        </p>
      ) : null}
    </div>
  );
}
