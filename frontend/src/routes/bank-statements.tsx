import { PageHeader } from "@/components/ui-finance/PageHeader";
import { EmptyState } from "@/components/EmptyState";

export function BankPage() {
  return (
    <div>
      <PageHeader
        eyebrow="Workflow · Step 2"
        title="Bank statements"
        description="Upload ProCredit-style Excel exports for transaction matching."
      />
      <EmptyState
        title="Bank ingest not available in this build"
        description="Statement upload and parsing are defined in the roadmap. Use purchase invoices and export until bank APIs are implemented."
      />
    </div>
  );
}
