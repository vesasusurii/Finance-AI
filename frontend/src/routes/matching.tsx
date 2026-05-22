import { PageHeader } from "@/components/ui-finance/PageHeader";
import { EmptyState } from "@/components/EmptyState";

export function MatchingPage() {
  return (
    <div>
      <PageHeader
        eyebrow="Workflow · Step 3"
        title="Matching"
        description="Match bank transactions to purchase invoices."
      />
      <EmptyState
        title="Matching not available in this build"
        description="Automatic matching requires bank statement data. This screen will activate once bank ingest is implemented."
      />
    </div>
  );
}
