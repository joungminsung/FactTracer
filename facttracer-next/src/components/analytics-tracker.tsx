"use client";

import { useEffect } from "react";
import { usePathname, useSearchParams } from "next/navigation";
import { useAuth } from "@/components/auth/auth-provider";
import { recordAnalyticsEvent } from "@/lib/api/facttracer";

function issueIdFromPath(pathname: string) {
  const match = pathname.match(/^\/(?:issues|reports)\/([^/?#]+)/);
  return match?.[1] ? decodeURIComponent(match[1]) : undefined;
}

export function AnalyticsTracker() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { token } = useAuth();

  useEffect(() => {
    const issueId = issueIdFromPath(pathname);
    const eventType = pathname.startsWith("/reports/")
      ? "report_view"
      : pathname === "/"
        ? "home_view"
        : "page_view";

    recordAnalyticsEvent(
      {
        eventType,
        issueId,
        metadata: {
          path: pathname,
          query: searchParams.toString(),
        },
        reportId: pathname.startsWith("/reports/") && issueId ? `report-${issueId}` : undefined,
      },
      token,
    ).catch(() => {
      // Analytics must never block reading or verification work.
    });
  }, [pathname, searchParams, token]);

  return null;
}
