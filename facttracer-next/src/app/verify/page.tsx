import Link from "next/link";
import { FileSearch, Link2, ListChecks } from "lucide-react";
import { PageIntro, PageShell, WorkSurface } from "@/components/common/design-system";
import { ManualVerificationForm } from "@/components/issue/manual-verification-form";
import { SiteHeader } from "@/components/site-header";

export default function VerifyPage() {
  return (
    <PageShell tone="dossier">
      <SiteHeader />
      <main className="mx-auto max-w-[1180px] px-4 py-6 sm:px-6 sm:py-8">
        <section className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_380px]">
          <PageIntro
            eyebrow={
              <span className="flex items-center gap-2">
                <FileSearch className="size-5" aria-hidden="true" />
                제보/검증
              </span>
            }
            title="기사, 문서, 텍스트를 보도 분석에 보냅니다"
            description="공유받은 기사 링크, 공식자료 PDF, 이미지, 영상, 직접 입력한 문장을 기존 사건 흐름에 연결하거나 단독 분석 결과로 저장합니다."
          />
          <WorkSurface className="px-5 py-5 sm:px-6">
            <ManualVerificationForm />
          </WorkSurface>
        </section>

        <section className="mt-5 grid gap-5 lg:grid-cols-2">
          <WorkSurface className="px-5 py-5 sm:px-6">
            <div className="flex items-center gap-2">
              <Link2 className="size-4 text-blue-600" aria-hidden="true" />
              <h2 className="text-xl font-bold text-gray-900">접수 기준</h2>
            </div>
            <div className="mt-4 divide-y divide-gray-100 border-y border-gray-200">
              {[
                "기사 링크, 텍스트, 영상, PDF/이미지를 같은 분석 흐름으로 보냅니다.",
                "기존 사건이 있으면 해당 기록에 연결하고, 없으면 단독 결과로 저장합니다.",
                "파일은 형식과 크기를 확인한 뒤 텍스트 추출 또는 문자 인식 대기 상태로 처리합니다.",
              ].map((item) => (
                <p key={item} className="py-4 text-sm font-semibold text-gray-700">
                  {item}
                </p>
              ))}
            </div>
          </WorkSurface>
          <WorkSurface className="px-5 py-5 sm:px-6">
            <div className="flex items-center gap-2">
              <ListChecks className="size-4 text-blue-600" aria-hidden="true" />
              <h2 className="text-xl font-bold text-gray-900">다음 행동</h2>
            </div>
            <div className="mt-4 divide-y divide-gray-100 border-y border-gray-200">
              <Link
                href="/"
                className="block py-4 text-sm font-semibold text-gray-700"
              >
                이슈 모니터 보기
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
