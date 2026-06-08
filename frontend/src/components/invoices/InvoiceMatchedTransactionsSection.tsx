import { useEffect, useState, type ReactNode } from "react";
import { getInvoiceMatches } from "@/api/invoices";
import { LoadingSpinner } from "@/components/LoadingSpinner";
import { StatusBadge } from "@/components/ui-finance/StatusBadge";
import {
  formatCurrency,
  formatDate,
  reconciliationStatusLabel,
} from "@/lib/labels";
import { cn } from "@/lib/utils";
import type { Invoice } from "@/types/invoice";
import type { InvoicePaymentMatch } from "@/types/match";

function matchApprovalLabel(status: string): string {
  if (status === "approved") return "Approved";
  if (status === "rejected") return "Rejected";
  return "Pending approval";
}

function matchTypeLabel(type: string): string {
  if (type === "batch_amount") return "Batch amount";
  if (type === "batch_invoice_number") return "Batch invoice #";
  return "Invoice #";
}

function DetailField({
  label,
  children,
  mono = false,
}: {
  label: string;
  children: ReactNode;
  mono?: boolean;
}) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/70">
        {label}
      </span>
      <span
        className={cn(
          "text-[13px] leading-snug text-foreground",
          mono && "font-mono text-[12px]",
        )}
      >
        {children}
      </span>
    </div>
  );
}

function MatchedTransactionCard({ match }: { match: InvoicePaymentMatch }) {
  const txn = match.bank_transaction;
  const txnAmount =
    txn?.debited_amount != null
      ? formatCurrency(Number(txn.debited_amount), null)
      : txn?.credited_amount != null
        ? formatCurrency(Number(txn.credited_amount), null)
        : "—";

  return (
    <div className="rounded-lg border border-border bg-card px-4 py-3">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
          Bank transaction
        </span>
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="rounded-full bg-accent px-2 py-0.5 text-[10px] font-semibold text-primary/70">
            {matchTypeLabel(match.match_type)}
          </span>
          <StatusBadge value={matchApprovalLabel(match.status)} />
          {txn ? (
            <StatusBadge
              value={reconciliationStatusLabel(txn.reconciliation_status)}
            />
          ) : null}
        </div>
      </div>

      <div className="flex items-start justify-between gap-4">
        <p className="text-[15px] font-semibold tabular-nums text-foreground">
          {txnAmount}
        </p>
        <p className="text-[12px] text-muted-foreground">
          {formatDate(txn?.transaction_date ?? null)}
        </p>
      </div>

      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <DetailField label="Paid on invoice">
          {formatDate(match.paid_at_date)}
        </DetailField>
        {match.paid_amount != null ? (
          <DetailField label="Allocated amount">
            {formatCurrency(Number(match.paid_amount), null)}
          </DetailField>
        ) : null}
        {txn && txn.detected_invoice_numbers.length > 0 ? (
          <DetailField label="Detected invoice #" mono>
            {txn.detected_invoice_numbers.join(", ")}
          </DetailField>
        ) : null}
      </div>

      {txn?.comment?.trim() ? (
        <p className="mt-3 rounded-md bg-surface-muted px-3 py-2 text-[12px] leading-relaxed text-muted-foreground whitespace-pre-wrap [overflow-wrap:anywhere]">
          {txn.comment.trim()}
        </p>
      ) : null}
    </div>
  );
}

function hasMatchLink(invoice: Invoice): boolean {
  return (
    invoice.match_status === "matched" ||
    invoice.match_status === "partially_matched"
  );
}

export function InvoiceMatchedTransactionsSection({
  invoice,
}: {
  invoice: Invoice;
}) {
  const [matches, setMatches] = useState<InvoicePaymentMatch[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!hasMatchLink(invoice)) {
      setMatches([]);
      setError(null);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);
    void getInvoiceMatches(invoice.id)
      .then((res) => {
        if (!cancelled) setMatches(res.items);
      })
      .catch((e) => {
        if (!cancelled) {
          setMatches([]);
          setError(e instanceof Error ? e.message : "Could not load match");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [invoice.id, invoice.match_status]);

  if (!hasMatchLink(invoice)) return null;

  return (
    <section className="mt-8 border-t border-border pt-6">
      <h3 className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
        Matched bank transaction
        {matches.length > 1 ? "s" : ""}
      </h3>

      {loading && (
        <LoadingSpinner
          centered
          size="sm"
          className="text-muted-foreground"
          label="Loading…"
          containerClassName="mt-2 py-8"
        />
      )}
      {error && (
        <p className="mt-2 text-[12px] text-destructive">{error}</p>
      )}
      {!loading && !error && matches.length === 0 && (
        <p className="mt-2 text-[12px] text-muted-foreground">
          No linked bank transaction found.
        </p>
      )}
      {!loading && matches.length > 0 && (
        <div className="mt-3 flex flex-col gap-3">
          {matches.map((match) => (
            <MatchedTransactionCard key={match.id} match={match} />
          ))}
        </div>
      )}
    </section>
  );
}
