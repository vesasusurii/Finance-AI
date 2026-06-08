import { useMemo } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { LoadingSpinner } from "@/components/LoadingSpinner";
import { PageHeader } from "@/components/ui-finance/PageHeader";
import { DataTable, type Column } from "@/components/ui-finance/DataTable";
import { StatusBadge } from "@/components/ui-finance/StatusBadge";
import { useBankTransactions } from "@/hooks/useBankTransactions";
import type { BankTransaction } from "@/types/bank";
import {
  formatCurrency,
  formatDate,
  reconciliationStatusLabel,
} from "@/lib/labels";

export function BankTransactionsPage() {
  const [searchParams] = useSearchParams();
  const statementIdParam = searchParams.get("bank_statement_id");
  const bankStatementId = statementIdParam
    ? parseInt(statementIdParam, 10)
    : undefined;

  const filters = useMemo(
    () => ({
      bank_statement_id: Number.isFinite(bankStatementId)
        ? bankStatementId
        : undefined,
      limit: 200,
    }),
    [bankStatementId],
  );

  const { items, total, loading, error } = useBankTransactions(filters);

  const columns: Column<BankTransaction>[] = [
    {
      key: "date",
      header: "Date",
      cell: (r) => (
        <span className="tabular-nums">{formatDate(r.transaction_date)}</span>
      ),
    },
    {
      key: "debited",
      header: "Debited",
      cell: (r) => (
        <span className="tabular-nums">
          {formatCurrency(r.debited_amount, "EUR")}
        </span>
      ),
    },
    {
      key: "credited",
      header: "Credited",
      cell: (r) => (
        <span className="tabular-nums">
          {formatCurrency(r.credited_amount, "EUR")}
        </span>
      ),
    },
    {
      key: "type",
      header: "Type",
      cell: (r) => (
        <span className="max-w-[160px] truncate block">
          {r.transaction_type ?? "—"}
        </span>
      ),
    },
    {
      key: "comment",
      header: "Comment",
      cell: (r) => (
        <span className="max-w-[240px] truncate block" title={r.comment ?? ""}>
          {r.comment ?? "—"}
        </span>
      ),
    },
    {
      key: "numbers",
      header: "Detected #",
      cell: (r) =>
        r.detected_invoice_numbers.length ? (
          <div className="flex flex-wrap gap-1">
            {r.detected_invoice_numbers.map((n) => (
              <span
                key={n}
                className="rounded border border-border bg-surface-muted px-1.5 py-0.5 text-[11px] font-medium"
              >
                {n}
              </span>
            ))}
          </div>
        ) : (
          <span className="text-muted-foreground">—</span>
        ),
    },
    {
      key: "status",
      header: "Reconciliation",
      cell: (r) => (
        <StatusBadge
          value={reconciliationStatusLabel(r.reconciliation_status)}
        />
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Bank data"
        title="Bank transactions"
        description={
          bankStatementId
            ? `Transactions for statement #${bankStatementId}. Matching runs in Phase 3.`
            : "All parsed bank rows. Upload statements from Bank Statements."
        }
        actions={
          <Link
            to="/bank-statements"
            className="text-[13px] font-medium text-primary hover:underline"
          >
            Upload statement
          </Link>
        }
      />

      {error && (
        <p className="text-[13px] text-destructive" role="alert">
          {error}
        </p>
      )}

      {loading ? (
        <LoadingSpinner centered className="text-muted-foreground" />
      ) : (
        <>
          <p className="text-[12px] text-muted-foreground">
            {total} transaction{total === 1 ? "" : "s"}
          </p>
          <DataTable
            columns={columns}
            rows={items}
            empty="No transactions. Upload a bank statement first."
          />
        </>
      )}
    </div>
  );
}
