import { Check, Loader2, X } from "lucide-react";
import { Button } from "@/components/ui-finance/Button";
import { StatusBadge } from "@/components/ui-finance/StatusBadge";
import {
  formatCurrency,
  formatDate,
  reconciliationStatusLabel,
} from "@/lib/labels";
import { cn } from "@/lib/utils";
import type { BankTransaction } from "@/types/bank";

export function transactionCompanyLabel(transaction: BankTransaction): string {
  const comment = transaction.comment?.trim();
  if (comment) {
    const firstLine = comment.split(/\r?\n/)[0]?.trim() ?? "";
    if (firstLine) {
      return firstLine.length > 96 ? `${firstLine.slice(0, 96)}…` : firstLine;
    }
  }
  return transaction.transaction_type?.trim() || "—";
}

export function transactionDisplayValue(transaction: BankTransaction): string {
  if (transaction.debited_amount != null) {
    return formatCurrency(transaction.debited_amount, null);
  }
  if (transaction.credited_amount != null) {
    return formatCurrency(transaction.credited_amount, null);
  }
  return "—";
}

export function BankTransactionMatchCard({
  transaction,
  expanded,
  matching,
  matchEnabled = true,
  onExpand,
  onClose,
  onMatch,
}: {
  transaction: BankTransaction;
  expanded: boolean;
  matching: boolean;
  /** When false, cards expand for inspection only (no Match action). */
  matchEnabled?: boolean;
  onExpand: () => void;
  onClose: () => void;
  onMatch: () => void;
}) {
  const company = transactionCompanyLabel(transaction);
  const value = transactionDisplayValue(transaction);
  const numbers = transaction.detected_invoice_numbers;

  if (!expanded) {
    return (
      <button
        type="button"
        onClick={onExpand}
        className="w-full rounded-lg border border-border bg-card px-3 py-3 text-left transition-colors hover:border-primary/40 hover:bg-secondary/30"
      >
        <div className="grid gap-2 sm:grid-cols-3 sm:items-start">
          <div className="min-w-0 sm:col-span-1">
            <span className="text-[11px] text-muted-foreground">Company</span>
            <p className="truncate text-[13px] font-medium text-foreground">
              {company}
            </p>
          </div>
          <div>
            <span className="text-[11px] text-muted-foreground">Value</span>
            <p className="tabular-nums text-[13px] font-medium text-foreground">
              {value}
            </p>
          </div>
          <div className="min-w-0">
            <span className="text-[11px] text-muted-foreground">
              Detected invoice #
            </span>
            <p className="font-mono text-[12px] text-foreground">
              {numbers.length > 0 ? numbers.join(", ") : "—"}
            </p>
          </div>
        </div>
      </button>
    );
  }

  return (
    <div
      className={cn(
        "rounded-lg border border-primary/40 bg-card ring-1 ring-primary/20",
      )}
    >
      <div className="border-b border-border px-3 py-3">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <span className="text-[13px] font-semibold text-foreground">
            {company}
          </span>
          <StatusBadge
            value={reconciliationStatusLabel(transaction.reconciliation_status)}
            tone="neutral"
          />
        </div>
        <dl className="grid gap-2 text-[13px] sm:grid-cols-2">
          <div>
            <dt className="text-muted-foreground">Date</dt>
            <dd className="tabular-nums text-foreground">
              {formatDate(transaction.transaction_date)}
            </dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Type</dt>
            <dd className="text-foreground">
              {transaction.transaction_type ?? "—"}
            </dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Debited</dt>
            <dd className="tabular-nums text-foreground">
              {formatCurrency(transaction.debited_amount, null)}
            </dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Credited</dt>
            <dd className="tabular-nums text-foreground">
              {formatCurrency(transaction.credited_amount, null)}
            </dd>
          </div>
          <div className="sm:col-span-2">
            <dt className="text-muted-foreground">Detected invoice numbers</dt>
            <dd className="font-mono text-foreground">
              {numbers.length > 0 ? numbers.join(", ") : "—"}
            </dd>
          </div>
          <div className="sm:col-span-2">
            <dt className="text-muted-foreground">Comment</dt>
            <dd className="whitespace-pre-wrap text-foreground">
              {transaction.comment?.trim() || "—"}
            </dd>
          </div>
        </dl>
      </div>

      <div className="flex flex-wrap justify-end gap-2 px-3 py-3">
        <Button
          variant="secondary"
          size="sm"
          disabled={matching}
          onClick={onClose}
          icon={<X className="h-3.5 w-3.5" />}
        >
          Close
        </Button>
        {matchEnabled && (
          <Button
            variant="success"
            size="sm"
            disabled={matching}
            onClick={onMatch}
            icon={
              matching ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Check className="h-3.5 w-3.5" />
              )
            }
          >
            Match
          </Button>
        )}
      </div>
    </div>
  );
}
