"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Bell, Clock3 } from "lucide-react";
import { useAuth } from "@/components/auth/auth-provider";
import { PageIntro, WorkSurface } from "@/components/common/design-system";
import { EmptyState } from "@/components/common/empty-state";
import { PreferenceForm } from "@/components/notifications/preference-form";
import { fetchUserNotifications } from "@/lib/api/auth";
import { getUserActionMessage } from "@/lib/api/messages";
import type { UserNotificationsResponse } from "@/lib/api/types";
import { formatDateTime, formatStatus, formatUpdatedAt } from "@/lib/display";

export function NotificationsDashboard() {
  const { isAuthenticated, isLoading, token } = useAuth();
  const [response, setResponse] = useState<UserNotificationsResponse | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;

    let isMounted = true;

    fetchUserNotifications(token)
      .then((nextResponse) => {
        if (!isMounted) return;
        setResponse(nextResponse);
      })
      .catch((notificationError) => {
        if (!isMounted) return;
        setError(
          getUserActionMessage(
            notificationError,
            "알림을 불러오지 못했습니다.",
          ),
        );
      });

    return () => {
      isMounted = false;
    };
  }, [token]);

  if (isLoading) {
    return <NotificationShell title="알림을 확인하고 있습니다" />;
  }

  if (!isAuthenticated) {
    return (
      <NotificationShell title="로그인이 필요합니다">
        <p className="mt-3 max-w-2xl text-base leading-8 text-gray-600">
          공식 자료 변경, 수치 변경, 검토 완료 알림은 로그인 이후 받을 수
          있습니다.
        </p>
        <Link
          href="/login"
          className="mt-6 inline-flex h-11 items-center rounded-md bg-blue-600 px-4 text-sm font-medium text-white"
        >
          로그인으로 이동
        </Link>
      </NotificationShell>
    );
  }

  if (error) {
    return (
      <NotificationShell title="알림을 불러오지 못했습니다">
        <p className="mt-3 text-sm font-semibold text-red-600">{error}</p>
      </NotificationShell>
    );
  }

  if (!response) {
    return <NotificationShell title="알림을 불러오는 중입니다" />;
  }

  return (
    <main className="mx-auto max-w-[1180px] px-4 py-6 sm:px-6 sm:py-8">
      <PageIntro
        eyebrow={
          <span className="flex items-center gap-2">
            <Bell className="size-5" aria-hidden="true" />
            알림
          </span>
        }
        title="변경 알림"
        description="공식 자료, 수치 변경, 검토 완료처럼 다시 확인해야 할 변화만 모읍니다."
      />

      <section className="mt-5 grid gap-5 lg:grid-cols-[minmax(0,1fr)_360px]">
        <WorkSurface className="min-w-0 px-5 sm:px-6">
          <article className="divide-y divide-gray-100">
          {response.notifications.length > 0 ? (
            response.notifications.map((notification) => (
              <Link
                key={notification.id}
                href={notification.href ?? "/"}
                className="grid gap-4 py-5 md:grid-cols-[120px_minmax(0,1fr)_92px]"
              >
                <div className="text-xs font-semibold text-blue-600">
                  {formatStatus(notification.type)}
                </div>
                <div>
                  <h2 className="font-bold leading-7 text-gray-900">
                    {notification.title}
                  </h2>
                  {notification.issueTitle ? (
                    <p className="mt-1 text-sm leading-6 text-gray-500">
                      {notification.issueTitle}
                    </p>
                  ) : null}
                </div>
                <span className="text-xs font-semibold text-gray-500">
                  {formatDateTime(notification.occurredAt)}
                </span>
              </Link>
            ))
          ) : (
            <EmptyState
              title="새 알림 없음"
              description="공식 자료나 수치가 바뀌면 이 목록에 표시됩니다."
              action={
                <Link
                  href="/saved"
                  className="inline-flex h-10 items-center rounded-md bg-blue-600 px-4 text-sm font-medium text-white"
                >
                  저장 이슈 확인
                </Link>
              }
            />
          )}
          </article>
        </WorkSurface>

        <WorkSurface className="px-5 py-5 sm:px-6">
          <PreferenceForm initialSettings={response.settings} />
          <section className="mt-8 border-t border-gray-200 pt-6">
            <div className="flex items-center gap-2">
              <Clock3 className="size-4 text-blue-600" aria-hidden="true" />
              <h2 className="text-base font-bold text-gray-900">
                팔로우한 이슈
              </h2>
            </div>
            <div className="mt-4 divide-y divide-gray-100 border-y border-gray-200">
              {response.followedIssues.length > 0 ? (
                response.followedIssues.map((issue) => (
                  <Link
                    key={issue.id}
                    href={`/issues/${issue.id}`}
                    className="block py-4"
                  >
                    <p className="text-sm font-bold leading-6 text-gray-900">
                      {issue.title}
                    </p>
                    <p className="mt-1 text-xs font-semibold text-gray-500">
                      {formatStatus(issue.status)} · {formatUpdatedAt(issue.updatedAt)}
                    </p>
                  </Link>
                ))
              ) : (
                <p className="py-4 text-sm leading-7 text-gray-500">
                  팔로우한 이슈가 없습니다.
                </p>
              )}
            </div>
          </section>
        </WorkSurface>
      </section>
    </main>
  );
}

function NotificationShell({
  children,
  title,
}: {
  children?: React.ReactNode;
  title: string;
}) {
  return (
    <main className="mx-auto max-w-[1180px] px-4 py-6 sm:px-6 sm:py-8">
      <section className="border border-gray-300 bg-white px-5 py-6 sm:px-7">
        <p className="text-sm font-bold text-blue-600">알림</p>
        <h1 className="mt-2 text-3xl font-bold leading-tight text-gray-900 sm:text-4xl">
          {title}
        </h1>
        {children}
      </section>
    </main>
  );
}
