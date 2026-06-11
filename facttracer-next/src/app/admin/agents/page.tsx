import { AdminAgentWorkspace } from "@/components/admin/admin-agent-workspace";
import { AdminPageHeader } from "@/components/common/design-system";
import { getAdminAgents } from "@/lib/api/facttracer";
import { getServerAccessToken } from "@/lib/auth/server-session";

export default async function AdminAgentsPage() {
  const token = await getServerAccessToken();
  let agentRuns: Awaited<ReturnType<typeof getAdminAgents>>["agentRuns"] = [];
  let recentEvents: Awaited<ReturnType<typeof getAdminAgents>>["recentEvents"] =
    [];
  let loadFailed = false;

  try {
    const response = await getAdminAgents(token);
    agentRuns = response.agentRuns;
    recentEvents = response.recentEvents;
  } catch {
    loadFailed = true;
  }

  return (
    <div className="space-y-8">
      <AdminPageHeader
        title="자동 처리 기록"
        description="자동 수집, 주장 추출, 근거 매칭, 낙인 필터링 상태를 확인하고 수동 실행합니다."
      />
      <AdminAgentWorkspace
        agentRuns={agentRuns}
        loadFailed={loadFailed}
        recentEvents={recentEvents}
      />
    </div>
  );
}
