import { BankStatementInvoicesExportPanel } from "@/components/reports/BankStatementInvoicesExportPanel";
import { PageHeader } from "@/components/ui-finance/PageHeader";

export function ExportsPage() {
  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Workflow · Step 4"
        title="Reports"
        description="Download purchase invoice exports scoped to a bank statement."
      />

      <BankStatementInvoicesExportPanel />
    </div>
  );
}
