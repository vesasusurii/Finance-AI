import { PageHeader } from "@/components/ui-finance/PageHeader";
import { EmptyState } from "@/components/EmptyState";

export function PermissionsPage() {
  return (
    <div>
      <PageHeader eyebrow="Site admin" title="Permissions" description="Role-based access control." />
      <EmptyState
        title="Permissions UI not available in this build"
        description="Roles are enforced on the API. Permission matrix editing is planned for a later phase."
      />
    </div>
  );
}
