import { AuthForm } from "@/components/auth/auth-form";
import { PageShell } from "@/components/common/design-system";
import { SiteHeader } from "@/components/site-header";

export default function SignupPage() {
  return (
    <PageShell tone="dossier">
      <SiteHeader />
      <AuthForm mode="signup" />
    </PageShell>
  );
}
