import { useState } from "react";
import { Download, Loader2 } from "lucide-react";
import { PageHeader } from "@/components/ui-finance/PageHeader";
import { Button } from "@/components/ui-finance/Button";
import { downloadPurchaseInvoicesExcel } from "@/api/export";

export function ExportsPage() {
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleExport() {
    setExporting(true);
    setError(null);
    try {
      await downloadPurchaseInvoicesExcel();
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
        description="Download purchase invoices as Excel for accounting. Export history will be added in a later phase."
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
        <p className="text-[13px] text-destructive">{error}</p>
      )}

      <div className="mt-6 rounded-lg border border-border bg-card p-6">
        <h3 className="text-[15px] font-semibold text-foreground">
          Purchase invoices export
        </h3>
        <p className="mt-2 max-w-xl text-[13px] text-muted-foreground">
          Exports all invoices in the database to an Excel workbook matching the
          purchase invoices column layout. Filtered export and audit history are
          planned for a later release.
        </p>
      </div>
    </div>
  );
}
