import type { VerdictTone } from "@/lib/api/types";
import type { ReactNode } from "react";

const toneClassName: Record<VerdictTone, string> = {
  positive: "bg-emerald-600",
  warning: "bg-amber-600",
  danger: "bg-red-600",
  negative: "bg-red-600",
  neutral: "bg-gray-400",
};

export function StatusBadge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: VerdictTone;
}) {
  return (
    <span className="inline-flex items-center gap-1.5 whitespace-nowrap text-sm font-medium text-gray-700">
      <span className={`h-1.5 w-1.5 rounded-full ${toneClassName[tone]}`} />
      {children}
    </span>
  );
}
