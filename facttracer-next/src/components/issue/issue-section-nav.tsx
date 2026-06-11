"use client";

import { useEffect, useState } from "react";

const sections = [
  { href: "#facts", label: "핵심 팩트" },
  { href: "#map", label: "쟁점 지도" },
  { href: "#perspectives", label: "관점별 주장" },
  { href: "#articles", label: "기사 비교" },
  { href: "#sources", label: "원문 자료" },
  { href: "#timeline", label: "타임라인" },
  { href: "#numbers", label: "수치 변경" },
  { href: "#report-actions", label: "리포트/활용" },
  { href: "#claim-submit", label: "주장 제출" },
  { href: "#content-report", label: "정정 요청" },
];

export function IssueSectionNav() {
  const [activeId, setActiveId] = useState(sections[0].href.slice(1));

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];

        if (visible?.target.id) setActiveId(visible.target.id);
      },
      { rootMargin: "-120px 0px -55% 0px", threshold: [0.1, 0.25, 0.5] },
    );

    sections.forEach((section) => {
      const element = document.getElementById(section.href.slice(1));
      if (element) observer.observe(element);
    });

    return () => observer.disconnect();
  }, []);

  return (
    <nav
      aria-label="이슈 상세 섹션"
      className="sticky top-16 z-20 -mx-6 border-b border-gray-200 bg-white px-6 py-2"
    >
      <div className="flex flex-wrap items-center gap-1">
        {sections.map((section) => (
          <a
            key={section.href}
            href={section.href}
            className={`inline-flex h-9 items-center border-b-2 px-3 text-sm font-bold ${
              activeId === section.href.slice(1)
                ? "border-blue-700 text-blue-600"
                : "border-transparent text-gray-600 hover:border-blue-700 hover:text-blue-600"
            }`}
          >
            {section.label}
          </a>
        ))}
      </div>
    </nav>
  );
}
