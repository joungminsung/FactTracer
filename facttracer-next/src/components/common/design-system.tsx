import Link from "next/link";
import type { ReactNode } from "react";

export function PageShell({
  children,
}: {
  children: ReactNode;
  tone?: "default" | "dossier";
}) {
  return (
    <div className="min-h-screen bg-white text-gray-900">
      {children}
    </div>
  );
}

export function WorkSurface({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`bg-white ${className}`}>
      {children}
    </section>
  );
}

export function PageIntro({
  children,
  description,
  eyebrow,
  title,
}: {
  children?: ReactNode;
  description?: string;
  eyebrow: ReactNode;
  title: string;
}) {
  return (
    <section className="bg-white py-10">
      <div className="text-xs font-medium uppercase tracking-wide text-gray-500">{eyebrow}</div>
      <h1 className="mt-2 max-w-4xl text-2xl font-bold tracking-tight text-gray-900">
        {title}
      </h1>
      {description ? (
        <p className="mt-4 max-w-[680px] text-[15px] leading-7 text-gray-700">
          {description}
        </p>
      ) : null}
      {children}
    </section>
  );
}

export function AdminSurface({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return <section className={`bg-white ${className}`}>{children}</section>;
}

export function AdminPageHeader({
  backHref = "/admin",
  backLabel = "운영 콘솔",
  children,
  description,
  eyebrow,
  title,
}: {
  backHref?: string;
  backLabel?: string;
  children?: ReactNode;
  description: string;
  eyebrow?: ReactNode;
  title: string;
}) {
  return (
    <AdminSurface className="py-10">
      <Link href={backHref} className="text-sm font-medium text-blue-600 hover:underline">
        {backLabel}
      </Link>
      {eyebrow ? (
        <div className="mt-5 text-xs font-medium uppercase tracking-wide text-gray-500">
          {eyebrow}
        </div>
      ) : null}
      <h1 className="mt-2 max-w-4xl text-2xl font-bold tracking-tight text-gray-900 sm:text-3xl">
        {title}
      </h1>
      <p className="mt-3 max-w-[680px] text-[15px] leading-7 text-gray-700">
        {description}
      </p>
      {children ? <div className="mt-6">{children}</div> : null}
    </AdminSurface>
  );
}

export function AdminMetricStrip({
  metrics,
}: {
  metrics: Array<{ label: string; value: string | number }>;
}) {
  if (metrics.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-x-8 gap-y-4 border-y border-gray-200 py-4">
      {metrics.map((metric) => (
        <div key={metric.label} className="min-w-24">
          <p className="text-2xl font-semibold tabular-nums text-gray-900">
            {metric.value}
          </p>
          <p className="mt-1 text-xs font-medium text-gray-500">
            {metric.label}
          </p>
        </div>
      ))}
    </div>
  );
}
