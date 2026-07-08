import { useEffect, useState } from "react";
import { Download } from "lucide-react";
import { LoadingSpinner } from "@/components/LoadingSpinner";
import { Button } from "@/components/ui-finance/Button";
import { listBankStatements } from "@/api/bankStatements";
import { downloadPurchaseInvoicesExcel } from "@/api/export";
import { formatDate } from "@/lib/labels";
import type { BankStatement } from "@/types/bank";

function formatStatementOptionLabel(statement: BankStatement): string {
  const dateLabel = statement.statement_date
    ? formatDate(statement.statement_date)
    : `#${statement.id}`;
  return `${dateLabel} — ${statement.original_filename}`;
}

export function BankStatementInvoicesExportPanel() {
  const [statements, setStatements] = useState<BankStatement[]>([]);
  const [statementId, setStatementId] = useState("");
  const [loadingStatements, setLoadingStatements] = useState(true);
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void listBankStatements(1, 100)
      .then((res) => setStatements(res.items))
      .catch(() => setStatements([]))
      .finally(() => setLoadingStatements(false));
  }, []);

  async function handleDownload() {
    if (!statementId) return;

    setDownloading(true);
    setError(null);

    try {
      await downloadPurchaseInvoicesExcel({
        bank_statement_id: Number(statementId),
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Export failed");
    } finally {
      setDownloading(false);
    }
  }

  return (
    <section className="card space-y-4 p-5">
      <div>
        <h2 className="text-[14px] font-semibold text-foreground">
          Bank statement export
        </h2>
        <p className="mt-1 text-[12px] text-muted-foreground">
          Download the purchase invoices Excel export for invoices with
          confirmed matches to transactions on the selected bank statement.
        </p>
      </div>

      <label className="block space-y-1">
        <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
          Bank statement
        </span>
        <select
          value={statementId}
          onChange={(e) => setStatementId(e.target.value)}
          disabled={loadingStatements}
          className="block h-9 w-full max-w-md rounded-md border border-input bg-background px-2 text-[13px]"
        >
          <option value="">
            {loadingStatements ? "Loading statements…" : "Select a statement"}
          </option>
          {statements.map((statement) => (
            <option key={statement.id} value={String(statement.id)}>
              {formatStatementOptionLabel(statement)}
            </option>
          ))}
        </select>
      </label>

      {error ? (
        <p className="text-[13px] text-destructive" role="alert">
          {error}
        </p>
      ) : null}

      <Button
        variant="primary"
        size="sm"
        icon={
          downloading ? (
            <LoadingSpinner size="sm" />
          ) : (
            <Download className="h-3.5 w-3.5" />
          )
        }
        disabled={downloading || !statementId}
        onClick={() => void handleDownload()}
      >
        {downloading ? "Preparing export…" : "Download statement Excel"}
      </Button>
    </section>
  );
}
