import { useEffect, useMemo, useState } from "react";
import { Search, X } from "lucide-react";
import { LoadingSpinner } from "@/components/LoadingSpinner";
import {
  hintsFromInvoice,
  hintsLabel,
  matchesHints,
  matchesFreeText,
  scoreHints,
  getHighlightTerms,
  type AutoSearchHints,
} from "@/lib/bankTransactionSearch";
import { Button } from "@/components/ui-finance/Button";
import { StatusBadge } from "@/components/ui-finance/StatusBadge";
import {
  BankTransactionMatchCard,
  transactionDisplayValue,
} from "@/components/review/BankTransactionMatchCard";
import { ApiError } from "@/api/client";
import { listBankTransactions } from "@/api/bankStatements";
import { manualMatch } from "@/api/reconciliation";
import { rejectReviewTask } from "@/api/review";
import { useAppDialog } from "@/components/dialogs/AppDialogProvider";
import { InvoiceAmountDisplay } from "@/components/invoices/InvoiceAmountDisplay";
import { formatDate, reviewReasonLabel } from "@/lib/labels";
import type { ReviewTask } from "@/types/review";
import type { BankTransaction } from "@/types/bank";
import type { Invoice } from "@/types/invoice";

const RECONCILABLE_STATUSES = new Set([
  "needs_review",
  "pending",
  "partial",
  "unmatched",
]);

export function mergeTransactionCandidates(
  items: BankTransaction[],
  preferred: BankTransaction | null | undefined,
): BankTransaction[] {
  const byId = new Map<number, BankTransaction>();
  for (const t of items) {
    if (RECONCILABLE_STATUSES.has(t.reconciliation_status)) {
      byId.set(t.id, t);
    }
  }
  if (preferred) {
    byId.set(preferred.id, preferred);
  }
  return [...byId.values()];
}

function rankForInvoice(
  transactions: BankTransaction[],
  invoice: Invoice,
): BankTransaction[] {
  const num = (
    invoice.invoice_number_normalized ?? invoice.invoice_number
  )
    ?.trim()
    .toLowerCase();
  return [...transactions].sort((a, b) => {
    const da = a.transaction_date ?? "";
    const db = b.transaction_date ?? "";
    if (num) {
      const aHit = a.detected_invoice_numbers.some(
        (n) => n.trim().toLowerCase() === num,
      );
      const bHit = b.detected_invoice_numbers.some(
        (n) => n.trim().toLowerCase() === num,
      );
      if (aHit !== bHit) return aHit ? -1 : 1;
    }
    return db.localeCompare(da);
  });
}

export function BankTransactionCandidatesPanel({
  invoice,
  task,
  onResolved,
}: {
  invoice: Invoice;
  task?: ReviewTask | null;
  onResolved: () => void;
}) {
  const [transactions, setTransactions] = useState<BankTransaction[]>([]);
  const [loadingTxns, setLoadingTxns] = useState(true);
  const [expandedTxnId, setExpandedTxnId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<"match" | "reject" | null>(null);
  const [matchingTxnId, setMatchingTxnId] = useState<number | null>(null);
  const [autoHints, setAutoHints] = useState<AutoSearchHints>(() => hintsFromInvoice(invoice));
  const [searchInput, setSearchInput] = useState(() => hintsLabel(hintsFromInvoice(invoice)));
  const { confirm, prompt } = useAppDialog();

  useEffect(() => {
    setExpandedTxnId(null);
  }, [invoice.id, task?.id]);

  useEffect(() => {
    const hints = hintsFromInvoice(invoice);
    setAutoHints(hints);
    setSearchInput(hintsLabel(hints));
  }, [invoice.id]);

  useEffect(() => {
    let cancelled = false;
    setLoadingTxns(true);
    setError(null);
    const statementId = task?.bank_transaction?.bank_statement_id;
    const load = async () => {
      try {
        const res = await listBankTransactions({
          ...(statementId != null ? { bank_statement_id: statementId } : {}),
          limit: 200,
        });
        if (cancelled) return;
        const merged = mergeTransactionCandidates(
          res.items,
          task?.bank_transaction,
        );
        setTransactions(rankForInvoice(merged, invoice));
      } catch (e) {
        if (!cancelled) {
          setError(
            e instanceof Error ? e.message : "Could not load bank transactions",
          );
        }
      } finally {
        if (!cancelled) setLoadingTxns(false);
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, [task?.bank_transaction, task?.id, invoice]);

  const handleReject = async () => {
    if (!task) return;
    const reason = await prompt({
      title: "Reject task",
      description: "Reason for rejection (optional):",
      defaultValue: "",
      confirmLabel: "Reject",
    });
    if (reason === null) return;
    setBusy("reject");
    setError(null);
    try {
      await rejectReviewTask(task.id, reason.trim() || undefined);
      onResolved();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Reject failed");
      setBusy(null);
    }
  };

  const handleMatch = async (bankTransactionId: number) => {
    const ok = await confirm({
      title: "Match invoice",
      description:
        "Match this invoice to the selected bank line? Paid date will be set from the transaction date.",
      confirmLabel: "Match",
    });
    if (!ok) return;
    setBusy("match");
    setMatchingTxnId(bankTransactionId);
    setError(null);
    try {
      await manualMatch({
        invoice_id: invoice.id,
        bank_transaction_id: bankTransactionId,
        review_task_id: task?.id,
      });
      onResolved();
    } catch (e) {
      if (e instanceof ApiError) {
        setError(e.message);
      } else {
        setError(e instanceof Error ? e.message : "Match failed");
      }
      setBusy(null);
      setMatchingTxnId(null);
    }
  };

  const isAutoSearch = searchInput === hintsLabel(autoHints);

  const visibleTransactions = useMemo(() => {
    if (!searchInput.trim()) return transactions;
    if (isAutoSearch) {
      return transactions
        .filter((t) => matchesHints(t, autoHints))
        .sort((a, b) => scoreHints(b, autoHints) - scoreHints(a, autoHints));
    }
    return transactions.filter((t) => matchesFreeText(t, searchInput));
  }, [transactions, searchInput, isAutoSearch, autoHints]);

  const highlightTerms = useMemo(() => {
    if (!searchInput.trim()) return [];
    if (isAutoSearch) return getHighlightTerms(autoHints);
    return [searchInput.trim().toLowerCase()];
  }, [searchInput, isAutoSearch, autoHints]);

  return (
    <div className="flex h-full min-h-[960px] flex-col overflow-hidden rounded-lg border border-border bg-card lg:min-h-0">
      <div className="shrink-0 border-b border-border px-4 py-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[13px] font-semibold text-foreground">
              Bank transactions
            </span>
            {task && (
              <StatusBadge
                value={reviewReasonLabel(task.reason)}
                tone="warning"
              />
            )}
          </div>
          {task && (
            <Button
              variant="secondary"
              size="sm"
              disabled={busy !== null}
              onClick={() => void handleReject()}
              icon={
                busy === "reject" ? (
                  <LoadingSpinner size="sm" />
                ) : (
                  <X className="h-3.5 w-3.5" />
                )
              }
            >
              Reject task
            </Button>
          )}
        </div>
        <p className="mt-1 text-[11px] text-muted-foreground">
          Open a transaction to see full details, then match it to the invoice on
          the left. Lines matching this invoice number are listed first.
        </p>
        <div className="mt-3 rounded-md border border-border bg-surface-muted/40 px-3 py-2">
          <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
            Invoice amount
          </p>
          <div className="mt-1">
            <InvoiceAmountDisplay invoice={invoice} />
          </div>
        </div>
        {task?.bank_transaction && (
          <div className="mt-3 rounded-md border border-border bg-surface-muted/40 px-3 py-2">
            <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
              Linked bank line
            </p>
            <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-[12px] text-foreground">
              <span className="tabular-nums">
                {formatDate(task.bank_transaction.transaction_date)}
              </span>
              <span className="tabular-nums font-medium">
                {transactionDisplayValue(task.bank_transaction)}
              </span>
              {task.bank_transaction.detected_invoice_numbers.length > 0 && (
                <span className="font-mono text-[11px] text-muted-foreground">
                  {task.bank_transaction.detected_invoice_numbers.join(", ")}
                </span>
              )}
            </div>
          </div>
        )}
        <div className="relative mt-2">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            placeholder="Search comment, amount, invoice #, date (dd/mm/yyyy)…"
            className="h-8 w-full rounded-md border border-input bg-background pl-8 pr-7 text-[12px] text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
          />
          {searchInput && (
            <button
              type="button"
              onClick={() => setSearchInput("")}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-3">
        {error && (
          <p className="mb-3 text-[12px] text-destructive">{error}</p>
        )}
        {loadingTxns ? (
          <LoadingSpinner
            centered
            size="md"
            className="text-muted-foreground"
            label="Loading transactions…"
            containerClassName="py-12"
          />
        ) : transactions.length === 0 ? (
          <p className="text-[13px] text-muted-foreground">
            No candidate bank lines found. Upload a bank statement and run
            matching, or open the matching screen.
          </p>
        ) : visibleTransactions.length === 0 ? (
          <p className="text-[13px] text-muted-foreground">
            No transactions match the search.{" "}
            <button
              type="button"
              className="underline hover:text-foreground"
              onClick={() => setSearchInput("")}
            >
              Clear search
            </button>
          </p>
        ) : (
          <div className="space-y-2">
            {visibleTransactions.map((t) => (
              <BankTransactionMatchCard
                key={t.id}
                transaction={t}
                expanded={expandedTxnId === t.id}
                matching={busy === "match" && matchingTxnId === t.id}
                highlightTerms={highlightTerms}
                onExpand={() => {
                  setExpandedTxnId(t.id);
                  setError(null);
                }}
                onClose={() => setExpandedTxnId(null)}
                onMatch={() => void handleMatch(t.id)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
