import { AdminSourceWorkspace } from "@/components/admin/admin-source-workspace";
import { AdminPageHeader } from "@/components/common/design-system";
import { getAdminSources } from "@/lib/api/facttracer";
import { getServerAccessToken } from "@/lib/auth/server-session";

export default async function AdminSourcesPage() {
  const token = await getServerAccessToken();
  let sources: Awaited<ReturnType<typeof getAdminSources>>["sources"] = [];
  let loadFailed = false;

  try {
    const response = await getAdminSources(token);
    sources = response.sources;
  } catch {
    loadFailed = true;
  }

  return (
    <div className="space-y-8">
      <AdminPageHeader
        title="출처 관리"
        description="공식자료, 언론, SNS 후보의 신뢰도와 상태를 관리해 주장 검증 우선순위에 반영합니다."
      />
      <AdminSourceWorkspace sources={sources} loadFailed={loadFailed} />
    </div>
  );
}
