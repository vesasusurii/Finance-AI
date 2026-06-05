import { useState } from "react";
import { Check, X, ChevronDown, ChevronUp } from "lucide-react";
import { Button } from "@/components/ui-finance/Button";
import { StatusBadge } from "@/components/ui-finance/StatusBadge";
import { InvoiceAmountDisplay } from "@/components/invoices/InvoiceAmountDisplay";
import { formatCurrency, formatDate } from "@/lib/labels";
import { cn } from "@/lib/utils";
import type { InvoicePaymentMatch } from "@/types/match";

function matchTypeLabel(type: string): string {
  if (type === "batch_amount") return "Batch amount";
  if (type === "batch_invoice_number") return "Batch invoice #";
  return "Invoice #";
}

/** A single labeled value with clear label/value hierarchy. */
function DataPoint({
  label,
  children,
  mono = false,
  prominent = false,
}: {
  label: string;
  children: React.ReactNode;
  mono?: boolean;
  prominent?: boolean;
}) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/70">
        {label}
      </span>
      <span
        className={cn(
          "text-[13px] leading-snug text-foreground",
          mono && "font-mono",
          prominent && "text-[15px] font-semibold tracking-tight",
        )}
      >
        {children}
      </span>
    </div>
  );
}

/** Thin vertical rule between the two panels. */
function Divider() {
  return <div className="hidden w-px self-stretch bg-border/60 md:block" />;
}

export function MatchConfirmationRow({
  match,
  busy,
  onApprove,
  onReject,
}: {
  match: InvoicePaymentMatch;
  busy: boolean;
  onApprove: () => void;
  onReject: () => void;
}) {
  const [commentOpen, setCommentOpen] = useState(false);
  const { invoice, bank_transaction: txn } = match;
  const isPending = match.status === "matched" || match.status === "suggested";

  const txnAmount =
    txn?.debited_amount != null
      ? formatCurrency(txn.debited_amount, null)
      : txn?.credited_amount != null
        ? formatCurrency(txn.credited_amount, null)
        : "—";

  const hasComment = Boolean(txn?.comment?.trim());

  return (
    <div
      className={cn(
        "overflow-hidden rounded-xl border bg-card transition-shadow",
        isPending
          ? "border-border shadow-sm hover:shadow-md"
          : "border-border/60 opacity-80",
      )}
    >
      {/* Main row */}
      <div className="grid grid-cols-1 md:grid-cols-[1fr_1px_auto_1px_1fr]">
        {/* ── Left: Invoice ── */}
        <div className="flex flex-col gap-5 px-6 py-5">
          {/* Section label + match type pill */}
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground/60">
              Invoice
            </span>
            <span className="rounded-full bg-accent px-2 py-0.5 text-[10px] font-semibold text-primary/70">
              {matchTypeLabel(match.match_type)}
            </span>
          </div>

          {/* Primary info: company name large, amount prominent */}
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0 flex-1">
              <p className="truncate text-[15px] font-semibold leading-tight text-foreground">
                {invoice?.name_of_company?.trim() || "—"}
              </p>
            </div>
            <div className="shrink-0 text-right">
              {invoice ? (
                <InvoiceAmountDisplay
                  invoice={invoice}
                  className="text-[17px] font-bold tracking-tight text-foreground"
                />
              ) : (
                <p className="text-[17px] font-bold text-foreground">—</p>
              )}
            </div>
          </div>

          {/* Secondary info row */}
          <div className="flex items-center gap-6">
            <DataPoint label="Invoice #" mono>
              {invoice?.invoice_number?.trim() || match.invoice_number}
            </DataPoint>
            <DataPoint label="Paid">
              <span className="tabular-nums">
                {formatDate(match.paid_at_date)}
              </span>
            </DataPoint>
          </div>
        </div>

        {/* Vertical divider */}
        <Divider />

        {/* ── Center: Actions ── */}
        <div className="flex flex-row items-center justify-center gap-2 border-t border-border/60 px-6 py-5 md:flex-col md:border-t-0">
          {isPending ? (
            <div className="flex flex-col gap-2">
              <Button
                variant="success"
                size="sm"
                icon={<Check className="h-3.5 w-3.5" />}
                disabled={busy}
                onClick={(e) => {
                  e.stopPropagation();
                  onApprove();
                }}
                className="w-full justify-center"
              >
                Approve
              </Button>
              <Button
                variant="danger"
                size="sm"
                icon={<X className="h-3.5 w-3.5" />}
                disabled={busy}
                onClick={(e) => {
                  e.stopPropagation();
                  onReject();
                }}
                className="w-full justify-center"
              >
                Reject
              </Button>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-1.5">
              <StatusBadge value={match.status} />
              <span className="text-[10px] tabular-nums text-muted-foreground/60">
                {formatDate(match.paid_at_date)}
              </span>
            </div>
          )}
        </div>

        {/* Vertical divider */}
        <Divider />

        {/* ── Right: Bank transaction ── */}
        <div className="flex flex-col gap-5 border-t border-border/60 px-6 py-5 md:border-t-0">
          {/* Section label + reconciliation status */}
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground/60">
              Bank transaction
            </span>
            {txn && (
              <StatusBadge value={txn.reconciliation_status} />
            )}
          </div>

          {/* Primary: amount large */}
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0 flex-1">
              <p className="text-[11px] tabular-nums text-muted-foreground">
                {formatDate(txn?.transaction_date ?? null)}
              </p>
              {txn && txn.detected_invoice_numbers.length > 0 && (
                <p className="mt-1 font-mono text-[12px] text-foreground/70">
                  {txn.detected_invoice_numbers.join(", ")}
                </p>
              )}
            </div>
            <p className="shrink-0 tabular-nums text-[17px] font-bold tracking-tight text-foreground">
              {txnAmount}
            </p>
          </div>

          {/* Comment — collapsed by default */}
          {hasComment && (
            <button
              type="button"
              onClick={() => setCommentOpen((v) => !v)}
              className="flex items-center gap-1.5 text-[11px] font-medium text-muted-foreground transition-colors hover:text-foreground"
            >
              {commentOpen ? (
                <ChevronUp className="h-3.5 w-3.5" />
              ) : (
                <ChevronDown className="h-3.5 w-3.5" />
              )}
              {commentOpen ? "Hide comment" : "Show comment"}
            </button>
          )}
          {commentOpen && hasComment && (
            <p className="rounded-lg bg-surface-muted px-3 py-2.5 text-[12px] leading-relaxed text-muted-foreground">
              {txn!.comment}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
