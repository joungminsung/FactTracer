import type { ReactNode } from "react";

export function EmptyState({
  action,
  description,
  title,
}: {
  action?: ReactNode;
  description: string;
  title: string;
}) {
  return (
    <div className="border-y border-gray-300 bg-white px-4 py-8 sm:px-5">
      <h2 className="text-xl font-bold leading-tight text-gray-900">
        {title}
      </h2>
      <p className="mt-3 max-w-2xl text-sm leading-7 text-gray-600">
        {description}
      </p>
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  );
}
