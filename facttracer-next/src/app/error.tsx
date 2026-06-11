"use client";

import Link from "next/link";
import { useEffect } from "react";
import { PageIntro, PageShell, WorkSurface } from "@/components/common/design-system";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <PageShell tone="dossier">
      <header className="border-b border-gray-200 bg-white">
        <div className="mx-auto flex min-h-16 max-w-[1440px] items-center justify-between gap-4 px-6">
          <Link href="/" className="text-2xl font-bold tracking-tight">
            FactTracer
          </Link>
          <Link href="/login" className="text-sm font-semibold text-gray-600">
            로그인
          </Link>
        </div>
      </header>
      <main className="mx-auto max-w-[1180px] px-4 py-6 sm:px-6 sm:py-8">
        <PageIntro
          eyebrow="일시 실패"
          title="내용을 불러오지 못했습니다"
          description="다시 시도하거나 이슈 모니터에서 다른 항목을 선택해 주세요."
        />
        <section className="mt-5 grid gap-5 lg:grid-cols-[minmax(0,1fr)_320px]">
          <WorkSurface className="min-w-0 px-5 py-8 sm:px-6">
              <h2 className="text-xl font-bold tracking-tight text-gray-900">
                다시 확인할 수 있습니다
              </h2>
              <p className="mt-3 max-w-2xl text-sm leading-7 text-gray-600">
                잠시 뒤 다시 시도하거나 이슈 모니터로 이동해 주세요.
              </p>
              <div className="mt-5 flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={reset}
                  className="inline-flex h-10 items-center rounded-md bg-blue-600 px-4 text-sm font-medium text-white"
                >
                  다시 시도
                </button>
                <Link
                  href="/"
                  className="inline-flex h-10 items-center rounded-md border border-gray-200 px-4 text-sm font-bold text-gray-700"
                >
                  이슈 모니터 보기
                </Link>
              </div>
          </WorkSurface>
          <WorkSurface className="px-5 py-5 sm:px-6">
            <h2 className="text-base font-bold text-gray-900">다음 행동</h2>
            <div className="mt-4 divide-y divide-gray-100 border-y border-gray-200">
              <Link
                href="/verify"
                className="block py-4 text-sm font-semibold text-gray-700"
              >
                제보/검증
              </Link>
              <Link
                href="/saved"
                className="block py-4 text-sm font-semibold text-gray-700"
              >
                저장 이슈 확인
              </Link>
            </div>
          </WorkSurface>
        </section>
      </main>
    </PageShell>
  );
}
