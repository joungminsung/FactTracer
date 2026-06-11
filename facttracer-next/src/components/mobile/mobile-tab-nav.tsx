"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Bell, FileSearch, Home, Newspaper, Radio, UserRound } from "lucide-react";

const tabs = [
  { href: "/", icon: Home, label: "홈" },
  { href: "/podcasts", icon: Radio, label: "팟캐스트" },
  { href: "/saved", icon: Newspaper, label: "저장" },
  { href: "/verify", icon: FileSearch, label: "제보/검증" },
  { href: "/notifications", icon: Bell, label: "알림" },
  { href: "/account", icon: UserRound, label: "내 정보" },
];

export function MobileTabNav() {
  const pathname = usePathname();

  if (pathname.startsWith("/admin")) return null;

  return (
    <nav className="fixed inset-x-0 bottom-0 z-40 border-t border-gray-200 bg-white/95 px-2 pb-[max(env(safe-area-inset-bottom),0.5rem)] pt-2 backdrop-blur sm:hidden">
      <div className="mx-auto grid max-w-lg grid-cols-6">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive =
            tab.href === "/" ? pathname === "/" : pathname.startsWith(tab.href);

          return (
            <Link
              key={tab.href}
              href={tab.href}
              className={`flex min-w-0 flex-col items-center gap-1 px-1 py-1 text-[11px] font-medium ${
                isActive ? "text-blue-600" : "text-gray-500"
              }`}
            >
              <Icon className="size-5" aria-hidden="true" />
              <span className="truncate">{tab.label}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
