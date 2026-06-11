import { SavedIssuesDashboard } from "@/components/account/saved-issues-dashboard";
import { PageShell } from "@/components/common/design-system";
import { SiteHeader } from "@/components/site-header";

export default function SavedIssuesPage() {
  return (
    <PageShell tone="dossier">
      <SiteHeader />
      <SavedIssuesDashboard />
    </PageShell>
  );
}
