import { PageHeader } from "@/components/ui-finance/PageHeader";
import { EmptyState } from "@/components/EmptyState";

export function UsersPage() {
  return (
    <div>
      <PageHeader eyebrow="Site admin" title="Users" description="Manage platform users and roles." />
      <EmptyState
        title="User management not available in this build"
        description="Seed users via scripts/seed_admin.py. Admin APIs are planned for a later phase."
      />
    </div>
  );
}
