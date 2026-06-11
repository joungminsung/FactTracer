"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  ArrowLeft,
  FileClock,
  Flag,
  Headphones,
  ListChecks,
  RadioTower,
  ShieldAlert,
  SlidersHorizontal,
} from "lucide-react";

const navItems = [
  {
    href: "/admin",
    icon: ListChecks,
    label: "검토 목록",
    note: "민감 이슈 큐",
  },
  {
    href: "/admin/reports",
    icon: Flag,
    label: "신고 표현",
    note: "낙인/단정 정제",
  },
  {
    href: "/admin/podcasts",
    icon: Headphones,
    label: "팟캐스트",
    note: "생성/TTS 관리",
  },
  {
    href: "/admin/sources",
    icon: ShieldAlert,
    label: "출처 관리",
    note: "공식성/신뢰도",
  },
  {
    href: "/admin/agents",
    icon: RadioTower,
    label: "자동 처리 기록",
    note: "수집/추출/매칭",
  },
  {
    href: "/admin/settings",
    icon: SlidersHorizontal,
    label: "운영 설정",
    note: "판정 기준",
  },
];

function isActiveRoute(pathname: string, href: string, label: string, active?: string) {
  if (active === href || active === label) return true;
  if (href === "/admin") {
    return pathname === "/admin" || pathname.startsWith("/admin/issues");
  }
  return pathname.startsWith(href);
}

export function AdminWorkspaceNav({ active }: { active?: string }) {
  const pathname = usePathname();

  const nav = (
    <nav aria-label="관리자 메뉴" className="grid gap-1">
      {navItems.map((item) => {
        const Icon = item.icon;
        const isActive = isActiveRoute(pathname, item.href, item.label, active);

        return (
          <Link
            key={item.href}
            href={item.href}
            className={`group flex min-h-12 items-center gap-3 border-l-2 px-3 py-2 transition-colors ${
              isActive
                ? "border-blue-600 bg-gray-50 text-gray-900"
                : "border-transparent text-gray-500 hover:bg-gray-50 hover:text-gray-900"
            }`}
          >
            <Icon
              className={`size-4 ${isActive ? "text-blue-600" : "text-gray-400 group-hover:text-gray-500"}`}
              aria-hidden="true"
            />
            <span className="min-w-0">
              <span className="block text-sm font-medium">{item.label}</span>
              <span
                className={`mt-0.5 block text-xs ${
                  isActive ? "text-gray-500" : "text-gray-400"
                }`}
              >
                {item.note}
              </span>
            </span>
          </Link>
        );
      })}
    </nav>
  );

  return (
    <>
      <aside className="hidden border-r border-gray-200 bg-white lg:fixed lg:inset-y-0 lg:left-0 lg:z-40 lg:flex lg:w-64 lg:flex-col">
        <div className="border-b border-gray-200 px-5 py-5">
          <Link
            href="/admin"
            className="flex items-center gap-3"
            aria-label="FactTracer 운영 콘솔 홈"
          >
            <span className="grid size-9 place-items-center rounded-md border border-gray-200 text-blue-600">
              <FileClock className="size-5" aria-hidden="true" />
            </span>
            <span>
              <span className="block text-xs font-medium uppercase tracking-wide text-gray-500">
                FactTracer
              </span>
              <span className="block text-lg font-semibold tracking-tight text-gray-900">
                운영 콘솔
              </span>
            </span>
          </Link>
        </div>

        <div className="flex-1 overflow-y-auto px-4 py-5">
          <div className="mb-4 px-1 text-xs font-medium uppercase tracking-wide text-gray-500">
            운영 메뉴
          </div>
          {nav}
        </div>

        <div className="border-t border-gray-200 px-5 py-4">
          <Link
            href="/"
            className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-md border border-gray-300 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            <ArrowLeft className="size-4" aria-hidden="true" />
            공개 화면으로
          </Link>
        </div>
      </aside>

      <header className="sticky top-0 z-40 border-b border-gray-200 bg-white lg:hidden">
        <div className="flex items-center justify-between gap-3 px-4 py-3">
          <Link href="/admin" className="flex items-center gap-2 font-semibold text-gray-900">
            <FileClock className="size-5 text-blue-600" aria-hidden="true" />
            운영 콘솔
          </Link>
          <Link href="/" className="text-xs font-medium text-gray-500">
            공개 화면
          </Link>
        </div>
        <nav
          aria-label="관리자 모바일 메뉴"
          className="flex gap-2 overflow-x-auto px-4 pb-3"
        >
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = isActiveRoute(
              pathname,
              item.href,
              item.label,
              active,
            );

            return (
              <Link
                key={item.href}
                href={item.href}
                className={`inline-flex h-9 shrink-0 items-center gap-2 rounded-md border px-3 text-xs font-medium ${
                  isActive
                    ? "border-blue-600 text-blue-600"
                    : "border-gray-200 text-gray-500"
                }`}
              >
                <Icon className="size-4" aria-hidden="true" />
                {item.label}
              </Link>
            );
          })}
        </nav>
      </header>
    </>
  );
}
