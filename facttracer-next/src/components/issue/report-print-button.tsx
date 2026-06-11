"use client";

import { Printer } from "lucide-react";

export function ReportPrintButton() {
  return (
    <button
      type="button"
      onClick={() => window.print()}
      className="inline-flex h-10 items-center gap-2 rounded-md bg-blue-600 px-4 text-sm font-medium text-white print:hidden"
    >
      <Printer className="size-4" aria-hidden="true" />
      인쇄/파일 저장
    </button>
  );
}
