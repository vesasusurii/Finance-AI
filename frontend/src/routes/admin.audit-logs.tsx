import { PageHeader } from "@/components/ui-finance/PageHeader";
import { EmptyState } from "@/components/EmptyState";

export function AuditPage() {
  return (
    <div>
      <PageHeader eyebrow="Site admin" title="Audit logs" description="Platform activity and extraction events." />
      <EmptyState
        title="Audit log UI not available in this build"
        description="Events are stored in the database. A read-only audit viewer is planned for a later phase."
      />
    </div>
  );
}
