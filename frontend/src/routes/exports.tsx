import { PeriodReportPanel } from "@/components/reports/PeriodReportPanel";
import { PurchaseInvoicesExportPanel } from "@/components/reports/PurchaseInvoicesExportPanel";
import { PageHeader } from "@/components/ui-finance/PageHeader";

export function ExportsPage() {
  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Workflow · Step 4"
        title="Reports"
        description="Period summaries and filtered purchase invoice exports."
      />

      <PurchaseInvoicesExportPanel />

      <section className="space-y-4">
        <h2 className="text-[14px] font-semibold text-foreground">
          Period summary
        </h2>
        <p className="text-[12px] text-muted-foreground">
          Totals are based on invoice date within the selected period.
        </p>
        <PeriodReportPanel />
      </section>
    </div>
  );
}
