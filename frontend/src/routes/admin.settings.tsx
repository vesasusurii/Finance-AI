import { PageHeader } from "@/components/ui-finance/PageHeader";
import { EmptyState } from "@/components/EmptyState";

export function SettingsPage() {
  return (
    <div>
      <PageHeader eyebrow="Site admin" title="Settings" description="System configuration." />
      <EmptyState
        title="Settings UI not available in this build"
        description="Configure the application via .env and Docker Compose. A settings screen is planned for a later phase."
      />
    </div>
  );
}
