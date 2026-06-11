import { PageShell } from "@/components/common/design-system";
import { NotificationsDashboard } from "@/components/notifications/notifications-dashboard";
import { SiteHeader } from "@/components/site-header";

export default function NotificationsPage() {
  return (
    <PageShell tone="dossier">
      <SiteHeader />
      <NotificationsDashboard />
    </PageShell>
  );
}
