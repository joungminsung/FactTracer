import Link from "next/link";
import { AuthStatus } from "@/components/auth/auth-status";
import { HeaderSearchForm } from "@/components/search/header-search-form";

const primaryNav = [
  { href: "/?topic=정치", label: "정치" },
  { href: "/?topic=사회", label: "사회" },
  { href: "/?topic=경제", label: "경제" },
  { href: "/?topic=국제", label: "국제" },
  { href: "/?topic=재난", label: "재난/환경" },
  { href: "/?topic=과학", label: "과학/기술" },
  { href: "/?topic=라이프", label: "라이프" },
  { href: "/podcasts", label: "팟캐스트" },
  { href: "/verify", label: "제보/검증" },
];

export function SiteHeader() {
  return (
    <header className="border-b border-gray-200 bg-white">
      <div className="mx-auto max-w-[1520px] overflow-hidden px-5 sm:px-7 lg:px-9">
        <div className="flex h-[66px] items-center justify-between gap-6">
          <Link href="/" className="flex min-w-0 items-baseline gap-5">
            <span className="shrink-0 font-serif text-[38px] font-bold leading-none tracking-[-0.02em] text-gray-950">
              FactTracer
            </span>
            <span className="hidden text-[13px] font-medium text-gray-500 md:inline">
              사건 흐름을 정리하고, 정확한 보도를 돕습니다
            </span>
          </Link>

          <div className="ml-auto hidden items-center gap-6 text-[13px] font-bold text-gray-950 md:flex">
            <HeaderSearchForm />
            <AuthStatus />
          </div>
        </div>

        <nav
          aria-label="주요 분야"
          className="flex h-11 max-w-full items-center gap-7 overflow-x-auto text-[14px] font-bold text-gray-950"
        >
          {primaryNav.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="shrink-0 whitespace-nowrap hover:text-blue-700"
            >
              {item.label}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  );
}
