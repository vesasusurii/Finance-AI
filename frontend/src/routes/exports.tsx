import { PeriodReportPanel } from "@/components/reports/PeriodReportPanel";
import { PageHeader } from "@/components/ui-finance/PageHeader";

export function ExportsPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Workflow · Step 4"
        title="Reports"
        description="Generate daily, weekly, monthly, and yearly finance summaries."
      />

      <section className="space-y-4">
        <p className="text-[12px] text-muted-foreground">
          Totals are based on invoice date within the selected period.
        </p>
        <PeriodReportPanel />
      </section>
    </div>
  );
}
