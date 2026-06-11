"use client";

import { Children, ReactNode, useEffect, useMemo, useState } from "react";

export type IssueSectionIndexItem = {
  id: string;
  label: string;
};

function getHashSection(items: IssueSectionIndexItem[]) {
  if (typeof window === "undefined") return items[0]?.id ?? "";

  const hashId = window.location.hash.replace("#", "");
  return items.some((item) => item.id === hashId) ? hashId : (items[0]?.id ?? "");
}

export function IssueSectionWorkspace({
  children,
  items,
}: {
  children: ReactNode;
  items: IssueSectionIndexItem[];
}) {
  const [activeId, setActiveId] = useState(() => getHashSection(items));
  const panels = useMemo(() => Children.toArray(children), [children]);
  const activeIndex = Math.max(
    0,
    items.findIndex((item) => item.id === activeId),
  );

  useEffect(() => {
    function syncHash() {
      setActiveId(getHashSection(items));
    }

    syncHash();
    window.addEventListener("hashchange", syncHash);
    return () => window.removeEventListener("hashchange", syncHash);
  }, [items]);

  function selectSection(id: string) {
    setActiveId(id);
    window.history.replaceState(null, "", `${window.location.pathname}#${id}`);
  }

  return (
    <div className="grid gap-5 py-7 lg:grid-cols-[152px_minmax(0,1fr)]">
      <nav
        aria-label="이슈 상세 섹션"
        role="tablist"
        className="-mx-4 flex gap-1 overflow-x-auto border-b border-gray-200 px-4 pb-2 lg:hidden"
      >
        {items.map((item) => {
          const isActive = activeId === item.id;

          return (
            <button
              key={item.id}
              type="button"
              role="tab"
              aria-controls={`issue-section-panel-${item.id}`}
              aria-selected={isActive}
              onClick={() => selectSection(item.id)}
              className={`h-9 shrink-0 border-b-2 px-2 text-sm font-medium ${
                isActive
                  ? "border-blue-600 text-blue-600"
                  : "border-transparent text-gray-600"
              }`}
            >
              {item.label}
            </button>
          );
        })}
      </nav>

      <aside className="hidden lg:block">
        <nav aria-label="이슈 상세 섹션" role="tablist" className="sticky top-24">
          <p className="text-sm font-semibold text-gray-950">섹션</p>
          <div className="mt-4 grid">
            {items.map((item) => {
              const isActive = activeId === item.id;

              return (
                <button
                  key={item.id}
                  type="button"
                  role="tab"
                  aria-controls={`issue-section-panel-${item.id}`}
                  aria-selected={isActive}
                  onClick={() => selectSection(item.id)}
                  className={`border-l py-2.5 pl-4 text-left text-sm font-medium transition-colors ${
                    isActive
                      ? "border-blue-600 text-blue-600"
                      : "border-gray-200 text-gray-700 hover:border-gray-400 hover:text-blue-600"
                  }`}
                >
                  {item.label}
                </button>
              );
            })}
          </div>
        </nav>
      </aside>

      <div className="min-w-0">
        <div className="min-h-[560px]">
          {items.map((item, index) => (
            <div
              key={item.id}
              id={`issue-section-panel-${item.id}`}
              role="tabpanel"
              aria-label={item.label}
              hidden={activeIndex !== index}
              className="min-w-0"
            >
              {panels[index]}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
