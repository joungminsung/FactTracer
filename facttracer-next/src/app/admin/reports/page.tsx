import { AdminReportWorkspace } from "@/components/admin/admin-report-workspace";
import { AdminPageHeader } from "@/components/common/design-system";
import { getAdminReports } from "@/lib/api/facttracer";
import { getServerAccessToken } from "@/lib/auth/server-session";

export default async function AdminReportsPage() {
  const token = await getServerAccessToken();
  let reports: Awaited<ReturnType<typeof getAdminReports>>["reports"] = [];
  let loadFailed = false;

  try {
    const response = await getAdminReports(token);
    reports = response.reports;
  } catch {
    loadFailed = true;
  }

  return (
    <div className="space-y-8">
      <AdminPageHeader
        title="신고 표현 처리"
        description="낙인 표현, 근거 없는 고의성 단정, 출처 신뢰도 신고를 이슈와 연결해 처리합니다."
      />
      <AdminReportWorkspace reports={reports} loadFailed={loadFailed} />
    </div>
  );
}
