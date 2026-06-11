"use client";

import Link from "next/link";
import { LogOut, UserRound } from "lucide-react";
import { useAuth } from "@/components/auth/auth-provider";

export function AuthStatus() {
  const { isAuthenticated, isLoading, logout, user } = useAuth();

  if (isLoading) {
    return (
      <span className="px-1 py-2 text-sm font-semibold text-gray-400">
        로그인 확인
      </span>
    );
  }

  if (!isAuthenticated) {
    return (
      <>
        <Link href="/login" className="px-1 py-2 hover:text-blue-700">
          로그인
        </Link>
        <Link
          href="/signup"
          className="whitespace-nowrap px-1 py-2 hover:text-blue-700"
        >
          회원가입
        </Link>
      </>
    );
  }

  return (
    <>
      <Link
        href="/account"
        className="inline-flex min-w-0 items-center gap-2 px-1 py-2 hover:text-blue-700"
      >
        <UserRound className="size-4" aria-hidden="true" />
        <span className="max-w-24 truncate">{user?.name ?? "내 계정"}</span>
      </Link>
      <button
        type="button"
        onClick={logout}
        className="inline-flex items-center gap-2 whitespace-nowrap px-1 py-2 hover:text-blue-700"
      >
        <LogOut className="size-4" aria-hidden="true" />
        로그아웃
      </button>
    </>
  );
}
