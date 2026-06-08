import { Check, X } from "lucide-react";
import { LoadingSpinner } from "@/components/LoadingSpinner";
import { Button } from "@/components/ui-finance/Button";
import { StatusBadge } from "@/components/ui-finance/StatusBadge";
import {
  formatCurrency,
  formatDate,
  reconciliationStatusLabel,
} from "@/lib/labels";
import { cn } from "@/lib/utils";
import type { BankTransaction } from "@/types/bank";

function HighlightText({
  text,
  terms,
}: {
  text: string;
  terms: string[];
}) {
  if (!terms.length || !text) return <>{text}</>;
  const escaped = terms.map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  const regex = new RegExp(`(${escaped.join("|")})`, "gi");
  const parts = text.split(regex);
  const lowerTerms = new Set(terms.map((t) => t.toLowerCase()));
  return (
    <>
      {parts.map((part, i) =>
        lowerTerms.has(part.toLowerCase()) ? (
          <mark
            key={i}
            className="rounded-sm bg-warning/30 px-0.5 text-foreground"
          >
            {part}
          </mark>
        ) : (
          <span key={i}>{part}</span>
        ),
      )}
    </>
  );
}

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
  highlightTerms = [],
  onExpand,
  onClose,
  onMatch,
}: {
  transaction: BankTransaction;
  expanded: boolean;
  matching: boolean;
  /** When false, cards expand for inspection only (no Match action). */
  matchEnabled?: boolean;
  /** Lowercase terms to highlight inside text fields. */
  highlightTerms?: string[];
  onExpand: () => void;
  onClose: () => void;
  onMatch: () => void;
}) {
  const company = transactionCompanyLabel(transaction);
  const value = transactionDisplayValue(transaction);
  const numbers = transaction.detected_invoice_numbers;
  const hl = highlightTerms;

  if (!expanded) {
    return (
      <button
        type="button"
        onClick={onExpand}
        className="w-full rounded-lg border border-border bg-card px-3 py-3 text-left transition-colors hover:border-primary/40 hover:bg-secondary/30"
      >
        <div className="grid gap-2 sm:grid-cols-4 sm:items-start">
          <div className="min-w-0 sm:col-span-1">
            <span className="text-[11px] text-muted-foreground">Company</span>
            <p className="truncate text-[13px] font-medium text-foreground">
              <HighlightText text={company} terms={hl} />
            </p>
          </div>
          <div>
            <span className="text-[11px] text-muted-foreground">Date</span>
            <p className="tabular-nums text-[13px] font-medium text-foreground">
              {formatDate(transaction.transaction_date)}
            </p>
          </div>
          <div>
            <span className="text-[11px] text-muted-foreground">Value</span>
            <p className="tabular-nums text-[13px] font-medium text-foreground">
              <HighlightText text={value} terms={hl} />
            </p>
          </div>
          <div className="min-w-0">
            <span className="text-[11px] text-muted-foreground">
              Detected invoice #
            </span>
            <p className="font-mono text-[12px] text-foreground">
              {numbers.length > 0 ? (
                <HighlightText text={numbers.join(", ")} terms={hl} />
              ) : (
                "—"
              )}
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
          <div className="min-w-0 flex-1">
            <span className="text-[13px] font-semibold text-foreground">
              <HighlightText text={company} terms={hl} />
            </span>
            <p className="mt-0.5 tabular-nums text-[11px] text-muted-foreground">
              {formatDate(transaction.transaction_date)}
            </p>
          </div>
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
              {transaction.transaction_type ? (
                <HighlightText text={transaction.transaction_type} terms={hl} />
              ) : (
                "—"
              )}
            </dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Debited</dt>
            <dd className="tabular-nums text-foreground">
              <HighlightText
                text={formatCurrency(transaction.debited_amount, null)}
                terms={hl}
              />
            </dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Credited</dt>
            <dd className="tabular-nums text-foreground">
              <HighlightText
                text={formatCurrency(transaction.credited_amount, null)}
                terms={hl}
              />
            </dd>
          </div>
          <div className="sm:col-span-2">
            <dt className="text-muted-foreground">Detected invoice numbers</dt>
            <dd className="font-mono text-foreground">
              {numbers.length > 0 ? (
                <HighlightText text={numbers.join(", ")} terms={hl} />
              ) : (
                "—"
              )}
            </dd>
          </div>
          <div className="sm:col-span-2">
            <dt className="text-muted-foreground">Comment</dt>
            <dd className="whitespace-pre-wrap text-foreground">
              {transaction.comment?.trim() ? (
                <HighlightText text={transaction.comment.trim()} terms={hl} />
              ) : (
                "—"
              )}
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
                <LoadingSpinner size="sm" />
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
