"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { FileSearch, UserRound } from "lucide-react";
import { ProfileForm, UserRowAction } from "@/components/account/account-actions";
import { useAuth } from "@/components/auth/auth-provider";
import { PageIntro, WorkSurface } from "@/components/common/design-system";
import { PreferenceForm } from "@/components/notifications/preference-form";
import { fetchUserDashboard } from "@/lib/api/auth";
import { getUserActionMessage } from "@/lib/api/messages";
import type { UserDashboardResponse } from "@/lib/api/types";
import { formatDateTime, formatStatus, formatUpdatedAt } from "@/lib/display";

export function AccountDashboard() {
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
      .catch((dashboardError) => {
        if (!isMounted) return;
        setError(
          getUserActionMessage(
            dashboardError,
            "계정 정보를 불러오지 못했습니다.",
          ),
        );
      });

    return () => {
      isMounted = false;
    };
  }, [token, user]);

  if (isLoading) {
    return <AccountShell title="로그인 상태를 확인하고 있습니다" />;
  }

  if (!isAuthenticated) {
    return (
      <AccountShell title="로그인이 필요합니다">
        <p className="mt-3 max-w-2xl text-base leading-8 text-gray-600">
          계정별 저장 이슈, 검증 요청, 제출 주장은 로그인 이후 확인할 수
          있습니다.
        </p>
        <Link
          href="/login"
          className="mt-6 inline-flex h-11 items-center rounded-md bg-blue-600 px-4 text-sm font-medium text-white"
        >
          로그인으로 이동
        </Link>
      </AccountShell>
    );
  }

  if (error) {
    return (
      <AccountShell title="계정 정보를 불러오지 못했습니다">
        <p className="mt-3 text-sm font-semibold text-red-600">{error}</p>
      </AccountShell>
    );
  }

  if (!dashboard) {
    return <AccountShell title="계정 정보를 불러오는 중입니다" />;
  }

  return (
    <main className="mx-auto max-w-[1180px] px-4 py-6 sm:px-6 sm:py-8">
      <PageIntro
        eyebrow={
          <span className="flex items-center gap-2">
            <UserRound className="size-5" aria-hidden="true" />
            {dashboard.user.role}
          </span>
        }
        title={`${dashboard.user.name}님의 FactTracer`}
        description={`${dashboard.user.email} 계정 기준으로 저장 이슈, 제출 주장, 기사 검증 요청을 관리합니다.`}
      />

      <section className="mt-5 grid gap-5 lg:grid-cols-3">
        <WorkSurface className="px-5 py-5 sm:px-6">
          <div className="flex items-center gap-2">
            <UserRound className="size-4 text-blue-600" aria-hidden="true" />
            <h2 className="text-xl font-bold text-gray-900">프로필</h2>
          </div>
          <div className="mt-4">
            <ProfileForm initialName={dashboard.user.name} />
          </div>
        </WorkSurface>
        <AccountList
          title="저장 이슈"
          type="savedIssue"
          rows={dashboard.savedIssues.map((issue) => ({
            href: `/issues/${issue.id}`,
            id: issue.id,
            title: issue.title,
            meta: `${formatStatus(issue.status)} · ${formatUpdatedAt(issue.updatedAt)}`,
          }))}
        />
        <AccountList
          title="제출 주장"
          type="submittedClaim"
          rows={dashboard.submittedClaims.map((claim) => ({
            href: `/account?claimId=${claim.id}`,
            id: claim.id,
            title: claim.text,
            meta: `${claim.issueTitle} · ${formatStatus(claim.status)} · ${formatDateTime(claim.submittedAt)}`,
          }))}
        />
      </section>

      <section className="mt-5">
        <AccountList
          title="검증 요청"
          type="verificationRequest"
          rows={dashboard.verificationRequests.map((request) => ({
            href: request.articleUrl,
            id: request.id,
            title: request.articleUrl,
            meta: `${formatStatus(request.status)} · ${formatDateTime(request.requestedAt)}`,
          }))}
        />
      </section>

      <WorkSurface className="mt-5 px-5 py-5 sm:px-6">
        <PreferenceForm />
      </WorkSurface>
    </main>
  );
}

function AccountShell({
  children,
  title,
}: {
  children?: React.ReactNode;
  title: string;
}) {
  return (
    <main className="mx-auto max-w-[1180px] px-4 py-6 sm:px-6 sm:py-8">
      <section className="border border-gray-300 bg-white px-5 py-6 sm:px-7">
        <p className="text-sm font-bold text-blue-600">내 계정</p>
        <h1 className="mt-2 text-3xl font-bold leading-tight text-gray-900 sm:text-4xl">
          {title}
        </h1>
        {children}
      </section>
    </main>
  );
}

function AccountList({
  rows,
  title,
  type,
}: {
  rows: { href: string; id: string; meta: string; title: string }[];
  title: string;
  type: "savedIssue" | "submittedClaim" | "verificationRequest";
}) {
  return (
    <WorkSurface className="px-5 py-5 sm:px-6">
      <div className="flex items-center gap-2">
        <FileSearch className="size-4 text-blue-600" aria-hidden="true" />
        <h2 className="text-xl font-bold text-gray-900">{title}</h2>
      </div>
      <div className="mt-4 divide-y divide-gray-100 border-y border-gray-200">
        {rows.length > 0 ? (
          rows.map((row) => (
            <div key={row.id} className="py-4">
              <Link
                href={row.href}
                className="text-sm font-bold leading-6 text-gray-900"
              >
                {row.title}
              </Link>
              <p className="mt-1 text-xs font-semibold text-gray-500">
                {row.meta}
              </p>
              <UserRowAction id={row.id} type={type} />
            </div>
          ))
        ) : (
          <p className="py-4 text-sm leading-7 text-gray-500">
            아직 표시할 항목이 없습니다.
          </p>
        )}
      </div>
    </WorkSurface>
  );
}
