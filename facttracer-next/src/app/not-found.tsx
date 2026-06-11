import Link from "next/link";
import { PageIntro, PageShell } from "@/components/common/design-system";
import { EmptyState } from "@/components/common/empty-state";
import { SiteHeader } from "@/components/site-header";

export default function NotFound() {
  return (
    <PageShell tone="dossier">
      <SiteHeader />
      <main className="mx-auto max-w-[1180px] px-4 py-6 sm:px-6 sm:py-8">
        <PageIntro
          eyebrow="탐색"
          title="페이지를 찾을 수 없습니다"
          description="주소가 바뀌었거나 아직 공개되지 않은 화면입니다."
        />
        <EmptyState
          title="표시할 화면 없음"
          description="최근 이슈를 확인하거나 보도 분석 자료를 보내 주세요."
          action={
            <div className="flex flex-wrap gap-2">
              <Link
                href="/"
                className="inline-flex h-10 items-center rounded-md bg-blue-600 px-4 text-sm font-medium text-white"
              >
                이슈 모니터 보기
              </Link>
              <Link
                href="/verify"
                className="inline-flex h-10 items-center rounded-md border border-gray-200 px-4 text-sm font-bold text-gray-700"
              >
                제보/검증
              </Link>
            </div>
          }
        />
      </main>
    </PageShell>
  );
}
