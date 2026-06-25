import { PurchaseInvoicesExportPanel } from "@/components/reports/PurchaseInvoicesExportPanel";
import { PageHeader } from "@/components/ui-finance/PageHeader";

export function ExportsPage() {
  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Workflow · Step 4"
        title="Reports"
        description="Filtered purchase invoice exports."
      />

      <PurchaseInvoicesExportPanel />
    </div>
  );
}
