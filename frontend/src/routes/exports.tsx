import { useState } from "react";
import { Download, Loader2 } from "lucide-react";
import { ExportFiltersPanel } from "@/components/invoices/ExportFiltersPanel";
import { PageHeader } from "@/components/ui-finance/PageHeader";
import { Button } from "@/components/ui-finance/Button";
import { downloadPurchaseInvoicesExcel } from "@/api/export";
import {
  EMPTY_EXPORT_FILTERS,
  exportFiltersToParams,
  hasActiveExportFilters,
  type PurchaseInvoiceExportFilters,
} from "@/types/export";

export function ExportsPage() {
  const [filters, setFilters] =
    useState<PurchaseInvoiceExportFilters>(EMPTY_EXPORT_FILTERS);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleExport() {
    setExporting(true);
    setError(null);
    try {
      await downloadPurchaseInvoicesExcel(exportFiltersToParams(filters));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Export failed");
    } finally {
      setExporting(false);
    }
  }

  return (
    <div>
      <PageHeader
        eyebrow="Workflow · Step 4"
        title="Export centre"
        description="Download purchase invoices as Excel for accounting. Apply filters to export a subset."
        actions={
          <Button
            icon={
              exporting ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Download className="h-3.5 w-3.5" />
              )
            }
            disabled={exporting}
            onClick={() => void handleExport()}
          >
            {exporting ? "Exporting…" : "Export purchase invoices"}
          </Button>
        }
      />

      {error && (
        <p className="mb-4 text-[13px] text-destructive">{error}</p>
      )}

      <ExportFiltersPanel
        filters={filters}
        onChange={setFilters}
        onClear={() => setFilters(EMPTY_EXPORT_FILTERS)}
      />

      <p className="mt-4 text-[12px] text-muted-foreground">
        {hasActiveExportFilters(filters)
          ? "Export will include only invoices matching the filters above."
          : "No filters selected — all of your invoices will be exported."}
      </p>
    </div>
  );
}
