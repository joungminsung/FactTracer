import { AccountDashboard } from "@/components/account/account-dashboard";
import { PageShell } from "@/components/common/design-system";
import { SiteHeader } from "@/components/site-header";

export default function AccountPage() {
  return (
    <PageShell tone="dossier">
      <SiteHeader />
      <AccountDashboard />
    </PageShell>
  );
}
