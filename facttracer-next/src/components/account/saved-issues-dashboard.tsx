"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Bookmark, FileSearch } from "lucide-react";
import { useAuth } from "@/components/auth/auth-provider";
import { PageIntro, WorkSurface } from "@/components/common/design-system";
import { EmptyState } from "@/components/common/empty-state";
import { UserRowAction } from "@/components/account/account-actions";
import { fetchUserDashboard } from "@/lib/api/auth";
import { getUserActionMessage } from "@/lib/api/messages";
import type { UserDashboardResponse } from "@/lib/api/types";
import { formatStatus, formatUpdatedAt } from "@/lib/display";

export function SavedIssuesDashboard() {
  const { isAuthenticated, isLoading, token, user } = useAuth();
  const [dashboard, setDashboard] = useState<UserDashboardResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token || !user) return;

    let isMounted = true;

    fetchUserDashboard(token, user)
      .then((response) => {
        if (!isMounted) return;
        setDashboard({ ...response, user });
      })
      .catch((savedError) => {
        if (!isMounted) return;
        setError(
          getUserActionMessage(savedError, "저장 이슈를 불러오지 못했습니다."),
        );
      });

    return () => {
      isMounted = false;
    };
  }, [token, user]);

  if (isLoading) {
    return <SavedShell title="저장 이슈를 확인하고 있습니다" />;
  }

  if (!isAuthenticated) {
    return (
      <SavedShell title="로그인이 필요합니다">
        <p className="mt-3 max-w-2xl text-base leading-8 text-gray-600">
          관심 이슈와 팔로우한 이슈는 로그인 이후 확인할 수 있습니다.
        </p>
        <Link
          href="/login"
          className="mt-6 inline-flex h-11 items-center rounded-md bg-blue-600 px-4 text-sm font-medium text-white"
        >
          로그인으로 이동
        </Link>
      </SavedShell>
    );
  }

  if (error) {
    return (
      <SavedShell title="저장 이슈를 불러오지 못했습니다">
        <p className="mt-3 text-sm font-semibold text-red-600">{error}</p>
      </SavedShell>
    );
  }

  if (!dashboard) {
    return <SavedShell title="저장 이슈를 불러오는 중입니다" />;
  }

  return (
    <main className="mx-auto max-w-[1180px] px-4 py-6 sm:px-6 sm:py-8">
      <PageIntro
        eyebrow={
          <span className="flex items-center gap-2">
            <Bookmark className="size-5" aria-hidden="true" />
            관심 이슈
          </span>
        }
        title="저장한 이슈"
        description="다시 확인해야 할 사건과 업데이트 흐름을 한곳에서 봅니다."
      />

      <section className="mt-5 grid gap-5 lg:grid-cols-[minmax(0,1fr)_320px]">
        <WorkSurface className="min-w-0 px-5 sm:px-6">
          <article className="divide-y divide-gray-100">
          {dashboard.savedIssues.length > 0 ? (
            dashboard.savedIssues.map((issue) => (
              <div
                key={issue.id}
                className="grid gap-4 py-5 md:grid-cols-[minmax(0,1fr)_140px]"
              >
                <div>
                  <Link
                    href={`/issues/${issue.id}`}
                    className="font-bold leading-7 text-gray-900"
                  >
                    {issue.title}
                  </Link>
                  <p className="mt-1 text-sm font-semibold text-gray-500">
                    {formatStatus(issue.status)} · {formatUpdatedAt(issue.updatedAt)}
                  </p>
                </div>
                <UserRowAction id={issue.id} type="savedIssue" />
              </div>
            ))
          ) : (
            <EmptyState
              title="저장한 이슈 없음"
              description="관심 있는 이슈를 저장하면 이 목록에 표시됩니다."
              action={
                <Link
                  href="/"
                  className="inline-flex h-10 items-center rounded-md bg-blue-600 px-4 text-sm font-medium text-white"
                >
                  이슈 모니터 보기
                </Link>
              }
            />
          )}
          </article>
        </WorkSurface>

        <WorkSurface className="px-5 py-5 sm:px-6">
          <div className="flex items-center gap-2">
            <FileSearch className="size-4 text-blue-600" aria-hidden="true" />
            <h2 className="text-base font-bold text-gray-900">다음 행동</h2>
          </div>
          <div className="mt-4 divide-y divide-gray-100 border-y border-gray-200">
            <Link
              href="/verify"
              className="block py-4 text-sm font-semibold text-gray-700"
            >
              기사 검증 요청
            </Link>
            <Link
              href="/notifications"
              className="block py-4 text-sm font-semibold text-gray-700"
            >
              알림 설정 확인
            </Link>
          </div>
        </WorkSurface>
      </section>
    </main>
  );
}

function SavedShell({
  children,
  title,
}: {
  children?: React.ReactNode;
  title: string;
}) {
  return (
    <main className="mx-auto max-w-[1180px] px-4 py-6 sm:px-6 sm:py-8">
      <section className="border border-gray-300 bg-white px-5 py-6 sm:px-7">
        <p className="text-sm font-bold text-blue-600">저장 이슈</p>
        <h1 className="mt-2 text-3xl font-bold leading-tight text-gray-900 sm:text-4xl">
          {title}
        </h1>
        {children}
      </section>
    </main>
  );
}
