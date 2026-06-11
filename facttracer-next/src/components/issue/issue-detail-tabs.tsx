"use client";

import { Children, ReactNode, useEffect, useMemo, useState } from "react";

export type IssueDetailTab = {
  id: string;
  label: string;
};

function activeFromHash(tabs: IssueDetailTab[]) {
  if (typeof window === "undefined") return tabs[0]?.id ?? "";

  const hashId = window.location.hash.replace("#", "");
  return tabs.some((tab) => tab.id === hashId) ? hashId : (tabs[0]?.id ?? "");
}

export function IssueDetailTabs({
  children,
  tabs,
}: {
  children: ReactNode;
  tabs: IssueDetailTab[];
}) {
  const [activeId, setActiveId] = useState(() => activeFromHash(tabs));
  const panels = useMemo(() => Children.toArray(children), [children]);

  useEffect(() => {
    function syncHash() {
      const nextId = activeFromHash(tabs);
      setActiveId(nextId);
      window.requestAnimationFrame(() => {
        document.getElementById(nextId)?.scrollIntoView({ block: "start" });
      });
    }

    window.addEventListener("hashchange", syncHash);
    return () => window.removeEventListener("hashchange", syncHash);
  }, [tabs]);

  function selectTab(id: string) {
    setActiveId(id);
    window.history.replaceState(null, "", `${window.location.pathname}#${id}`);
    window.requestAnimationFrame(() => {
      document.getElementById(id)?.scrollIntoView({ block: "start" });
    });
  }

  return (
    <div>
      <nav
        aria-label="이슈 상세 탭"
        className="sticky top-16 z-20 -mx-6 border-b border-gray-200 bg-white px-6 py-2"
      >
        <div role="tablist" className="flex flex-wrap items-center gap-1">
          {tabs.map((tab) => {
            const isActive = activeId === tab.id;

            return (
              <button
                key={tab.id}
                id={`tab-${tab.id}`}
                type="button"
                role="tab"
                aria-selected={isActive}
                aria-controls={`panel-${tab.id}`}
                onClick={() => selectTab(tab.id)}
                className={`inline-flex h-9 items-center border-b-2 px-3 text-sm font-bold ${
                  isActive
                    ? "border-blue-700 text-blue-600"
                    : "border-transparent text-gray-600 hover:border-blue-700 hover:text-blue-600"
                }`}
              >
                {tab.label}
              </button>
            );
          })}
        </div>
      </nav>

      <div>
        {tabs.map((tab, index) => (
          <div
            key={tab.id}
            id={`panel-${tab.id}`}
            role="tabpanel"
            aria-labelledby={`tab-${tab.id}`}
            hidden={activeId !== tab.id}
          >
            {panels[index]}
          </div>
        ))}
      </div>
    </div>
  );
}
