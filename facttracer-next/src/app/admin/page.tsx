import { AdminQueueWorkspace } from "@/components/admin/admin-queue-workspace";
import {
  AdminMetricStrip,
  AdminPageHeader,
} from "@/components/common/design-system";
import { isApiConfigured } from "@/lib/api/config";
import { getAdminDashboard } from "@/lib/api/facttracer";
import { getServerAccessToken } from "@/lib/auth/server-session";

export default async function AdminPage() {
  const accessToken = await getServerAccessToken();
  const needsAuthForRealApi = isApiConfigured() && !accessToken;
  const dashboard = await getAdminDashboard(accessToken, {
    fallbackToEmpty: needsAuthForRealApi,
  });

  return (
    <div className="space-y-8">
      <AdminPageHeader
        backHref="/admin"
        backLabel="FactTracer"
        eyebrow="운영 콘솔"
        title="검토 목록에서 민감 이슈를 확인하고 안전하게 게시합니다"
        description="고위험 이슈, 신고 표현, 공식 출처 갱신, 자동 처리 실패를 우선순위대로 확인하고 판단 사유를 남깁니다."
      >
        <AdminMetricStrip metrics={dashboard.metrics} />
      </AdminPageHeader>
      <AdminQueueWorkspace
        dashboard={dashboard}
        needsAuthForRealApi={needsAuthForRealApi}
      />
    </div>
  );
}
