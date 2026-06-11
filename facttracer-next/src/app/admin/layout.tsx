import type { ReactNode } from "react";
import { AdminWorkspaceNav } from "@/components/admin/admin-workspace-nav";

export default function AdminLayout({ children }: { children: ReactNode }) {
  return (
    <div className="admin-console-shell min-h-screen bg-white text-gray-900">
      <AdminWorkspaceNav />
      <div className="min-w-0 lg:pl-64">
        <main className="mx-auto min-h-screen w-full max-w-screen-xl px-4 py-6 sm:px-6 lg:px-8 lg:py-10">
          {children}
        </main>
      </div>
    </div>
  );
}
