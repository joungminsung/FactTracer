import Link from "next/link";
import { AdminSettingsConsole } from "@/components/admin/admin-settings-console";
import { AdminPageHeader } from "@/components/common/design-system";
import { EmptyState } from "@/components/common/empty-state";
import { getAdminSettings } from "@/lib/api/facttracer";
import { getServerAccessToken } from "@/lib/auth/server-session";

export default async function AdminSettingsPage() {
  const token = await getServerAccessToken();
  let settings: Awaited<ReturnType<typeof getAdminSettings>> = {
    groups: [],
    updatedAt: "",
  };
  let loadFailed = false;

  try {
    settings = await getAdminSettings(token);
  } catch {
    loadFailed = true;
    settings = {
      groups: [],
      updatedAt: "",
    };
  }

  return (
    <div className="space-y-8">
      <AdminPageHeader
        title="운영 설정"
        description="자동 수집, 판정 기준, AI 연결, 입력 제한을 조정합니다."
      />

      <section className="border-y border-gray-200 py-6">
        {settings.groups.length > 0 ? (
          <AdminSettingsConsole initialSettings={settings} />
        ) : (
          <EmptyState
            title={
              loadFailed
                ? "설정 항목을 불러오지 못했습니다"
                : "설정 항목이 없습니다"
            }
            description={
              loadFailed
                ? "연결 상태를 확인한 뒤 다시 시도해 주세요."
                : "운영 설정이 등록되면 그룹별로 표시됩니다."
            }
            action={
              <Link
                href="/admin"
                className="inline-flex h-10 items-center rounded-md bg-blue-600 px-4 text-sm font-medium text-white"
              >
                운영 콘솔 보기
              </Link>
            }
          />
        )}
      </section>
    </div>
  );
}
