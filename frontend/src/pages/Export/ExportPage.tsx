import { useState } from "react";
import { downloadPurchaseInvoicesExcel } from "../../api/export";
import { PageHeader } from "../../components/PageHeader";

export function ExportPage() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleDownload() {
    setLoading(true);
    setError(null);
    try {
      await downloadPurchaseInvoicesExcel();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Export failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="section">
      <div className="container stack-5">
        <PageHeader title="Export" />
        <section className="card stack-4">
          <p className="text-fg2">
            Download the Purchase Invoices Database as Excel with the official
            12-column layout.
          </p>
          <button
            type="button"
            className="btn btn-accent"
            onClick={handleDownload}
            disabled={loading}
          >
            {loading ? "Generating…" : "Download Excel"}
          </button>
          {error && <p className="text-accent">{error}</p>}
        </section>
      </div>
    </div>
  );
}
