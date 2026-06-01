import { useCallback, useEffect, useState, type ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Play, Check, X } from "lucide-react";
import { PageHeader } from "@/components/ui-finance/PageHeader";
import { Button } from "@/components/ui-finance/Button";
import { DataTable, type Column } from "@/components/ui-finance/DataTable";
import { StatusBadge } from "@/components/ui-finance/StatusBadge";
import {
  approveMatch,
  getReconciliationResults,
  rejectMatch,
  runReconciliation,
} from "@/api/reconciliation";
import { ApiError, apiFetch } from "@/api/client";
import { refreshSession } from "@/api/auth";
import { listReviewTasks } from "@/api/review";
import { listBankStatements, listBankTransactions } from "@/api/bankStatements";
import { useInvoices } from "@/hooks/useInvoices";
import type { InvoicePaymentMatch, ReconciliationSummary } from "@/types/match";
import type { BankStatement, BankTransaction } from "@/types/bank";
import type { ReviewTask } from "@/types/review";
import type { Invoice } from "@/types/invoice";
import {
  formatDate,
  formatStatementId,
  matchStatusLabel,
  reconciliationStatusLabel,
  reviewReasonLabel,
} from "@/lib/labels";

export function MatchingPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [statementId, setStatementId] = useState(
    () => searchParams.get("bank_statement_id") ?? "",
  );
  const [statements, setStatements] = useState<BankStatement[]>([]);

  useEffect(() => {
    const sid = searchParams.get("bank_statement_id");
    if (sid) setStatementId(sid);
  }, [searchParams]);

  useEffect(() => {
    void listBankStatements(1, 100)
      .then((res) => setStatements(res.items))
      .catch(() => setStatements([]));
  }, []);
  const [running, setRunning] = useState(false);
  const [summary, setSummary] = useState<ReconciliationSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [matches, setMatches] = useState<InvoicePaymentMatch[]>([]);
  const [reviewTasks, setReviewTasks] = useState<ReviewTask[]>([]);
  const [unmatchedTxns, setUnmatchedTxns] = useState<BankTransaction[]>([]);
  const [multiTxns, setMultiTxns] = useState<BankTransaction[]>([]);
  const [busyMatchId, setBusyMatchId] = useState<number | null>(null);

  const { items: unmatchedInvoices, reload: reloadInvoices } = useInvoices({
    match_status: "unmatched",
    limit: 100,
  });

  const refresh = useCallback(async () => {
    const sid = statementId ? parseInt(statementId, 10) : undefined;
    const filters = Number.isFinite(sid) ? { bank_statement_id: sid } : {};

    const [matchRes, reviewRes, txnRes, allTxnRes] = await Promise.all([
      getReconciliationResults({ ...filters, limit: 100 }),
      listReviewTasks({ task_type: "bank_match", limit: 100 }),
      listBankTransactions({
        ...filters,
        reconciliation_status: "needs_review",
        limit: 200,
      }),
      listBankTransactions({ ...filters, limit: 200 }),
    ]);

    setMatches(matchRes.items);
    setReviewTasks(
      reviewRes.items.filter((t) =>
        [
          "no_invoice_in_db",
          "duplicate_invoice_in_db",
          "internal_error",
          "no_invoice_numbers_detected",
          "invoice_numbers_not_visible",
          "batch_payment_incomplete",
          "batch_amount_suggested",
          "missing_transaction_date",
        ].includes(t.reason),
      ),
    );
    setUnmatchedTxns(txnRes.items);
    setMultiTxns(
      allTxnRes.items.filter((t) => t.detected_invoice_numbers.length > 1),
    );
    await reloadInvoices();
  }, [statementId, reloadInvoices]);

  useEffect(() => {
    void refresh().catch((e) => {
      setError(e instanceof Error ? e.message : "Could not load matching data");
    });
  }, [refresh]);

  const onRun = async () => {
    setRunning(true);
    setError(null);
    try {
      await refreshSession();
      const sid = statementId ? parseInt(statementId, 10) : undefined;
      const res = await runReconciliation(
        Number.isFinite(sid) ? sid : undefined,
      );
      setSummary(res);
      await refreshSession();
      await refresh();
    } catch (e) {
      if (e instanceof ApiError && e.code === "session_expired") {
        setError("Session expired. Please sign in again.");
      } else {
        setError(e instanceof Error ? e.message : "Matching failed");
      }
    } finally {
      setRunning(false);
    }
  };

  const onApprove = async (matchId: number) => {
    if (busyMatchId != null) return;
    setBusyMatchId(matchId);
    setError(null);
    try {
      await approveMatch(matchId);
    } catch (e) {
      if (e instanceof ApiError && e.code === "match_already_resolved") {
        // Idempotent — row was already approved/rejected; refresh UI.
      } else {
        setError(e instanceof Error ? e.message : "Could not approve match");
        return;
      }
    } finally {
      setBusyMatchId(null);
    }
    await refresh();
  };

  const onReject = async (matchId: number) => {
    if (busyMatchId != null) return;
    const reason = window.prompt("Reason for rejecting this match (optional):");
    if (reason === null) return;
    setBusyMatchId(matchId);
    setError(null);
    try {
      await rejectMatch(matchId, reason || undefined);
    } catch (e) {
      if (e instanceof ApiError && e.code === "match_already_resolved") {
        // Idempotent — refresh to sync state.
      } else {
        setError(e instanceof Error ? e.message : "Could not reject match");
        return;
      }
    } finally {
      setBusyMatchId(null);
    }
    await refresh();
  };

  const onStatementChange = (value: string) => {
    setStatementId(value);
    if (value) {
      setSearchParams({ bank_statement_id: value });
    } else {
      setSearchParams({});
    }
  };

  const selectedStatement = statements.find(
    (s) => String(s.id) === statementId,
  );
  const staleStatementFilter =
    statementId !== "" &&
    !selectedStatement &&
    statements.length > 0 &&
    Number.isFinite(parseInt(statementId, 10));

  const matchColumns: Column<InvoicePaymentMatch>[] = [
    {
      key: "inv",
      header: "Invoice #",
      cell: (r) => <span className="font-mono text-[12px]">{r.invoice_number}</span>,
    },
    {
      key: "paid",
      header: "Paid at",
      cell: (r) => (
        <span className="tabular-nums">{formatDate(r.paid_at_date)}</span>
      ),
    },
    {
      key: "type",
      header: "Type",
      cell: (r) => (
        <span className="text-[12px] text-muted-foreground">
          {r.match_type === "batch_amount"
            ? "Batch amount"
            : r.match_type === "batch_invoice_number"
              ? "Batch invoice #"
              : "Invoice #"}
        </span>
      ),
    },
    {
      key: "status",
      header: "Status",
      cell: (r) => <StatusBadge value={r.status} />,
    },
    {
      key: "actions",
      header: "",
      cell: (r) =>
        r.status === "matched" || r.status === "suggested" ? (
          <div className="flex gap-1">
            <Button
              variant="success"
              size="sm"
              icon={<Check className="h-3 w-3" />}
              disabled={busyMatchId === r.id}
              onClick={(e) => {
                e.stopPropagation();
                void onApprove(r.id);
              }}
            >
              Approve
            </Button>
            <Button
              variant="danger"
              size="sm"
              icon={<X className="h-3 w-3" />}
              disabled={busyMatchId === r.id}
              onClick={(e) => {
                e.stopPropagation();
                void onReject(r.id);
              }}
            >
              Reject
            </Button>
          </div>
        ) : null,
    },
  ];

  const invoiceColumns: Column<Invoice>[] = [
    {
      key: "num",
      header: "Invoice #",
      cell: (r) => r.invoice_number ?? "—",
    },
    {
      key: "company",
      header: "Company",
      cell: (r) => r.name_of_company ?? "—",
    },
    {
      key: "paid",
      header: "Paid at",
      cell: (r) => formatDate(r.paid_at_date),
    },
    {
      key: "status",
      header: "Match",
      cell: (r) => <StatusBadge value={matchStatusLabel(r.match_status)} />,
    },
  ];

  const txnColumns: Column<BankTransaction>[] = [
    {
      key: "date",
      header: "Date",
      cell: (r) => formatDate(r.transaction_date),
    },
    {
      key: "comment",
      header: "Comment",
      cell: (r) => (
        <span className="max-w-[200px] truncate block" title={r.comment ?? ""}>
          {r.comment ?? "—"}
        </span>
      ),
    },
    {
      key: "nums",
      header: "Detected #",
      cell: (r) => r.detected_invoice_numbers.join(", ") || "—",
    },
    {
      key: "status",
      header: "Status",
      cell: (r) => (
        <StatusBadge value={reconciliationStatusLabel(r.reconciliation_status)} />
      ),
    },
  ];

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Workflow · Step 3"
        title="Matching"
        description="Match bank transactions to invoices using comment extraction (regex + LLM). One payment can cover multiple invoices. Amount-combination suggestions require approval when numbers are absent."
        actions={
          <div className="flex items-center gap-2">
            <select
              value={statementId}
              onChange={(e) => onStatementChange(e.target.value)}
              className="h-9 max-w-[220px] rounded-md border border-input bg-background px-2 text-[13px]"
            >
              <option value="">All statements</option>
              {statements.map((s) => (
                <option key={s.id} value={String(s.id)}>
                  {formatStatementId(s)} — {s.original_filename}
                </option>
              ))}
            </select>
            <Button
              variant="primary"
              icon={<Play className="h-3.5 w-3.5" />}
              disabled={running}
              onClick={() => void onRun()}
            >
              {running ? "Running…" : "Run Matching"}
            </Button>
          </div>
        }
      />

      {staleStatementFilter && (
        <p className="text-[13px] text-muted-foreground" role="status">
          Statement ID {statementId} is no longer available. Choose a statement
          from the list or clear the filter.
        </p>
      )}

      {error && (
        <p className="text-[13px] text-destructive" role="alert">
          {error}
        </p>
      )}

      {summary && (
        <div className="rounded-lg border border-border bg-surface-muted/50 px-4 py-3 text-[13px] text-foreground">
          Last run: <strong>{summary.matched}</strong> matched,{" "}
          <strong>{summary.unmatched_transactions}</strong> unmatched transactions,{" "}
          <strong>{summary.review_tasks_created}</strong> review tasks,{" "}
          <strong>{summary.unmatched_invoices}</strong> unmatched invoices in DB
        </div>
      )}

      <Section title="Matched" count={matches.length}>
        <DataTable
          columns={matchColumns}
          rows={matches.map((m) => ({ ...m, id: m.id }))}
          empty="No matches yet. Upload bank data and run matching."
        />
      </Section>

      <Section title="Unmatched invoices" count={unmatchedInvoices.length}>
        <DataTable
          columns={invoiceColumns}
          rows={unmatchedInvoices}
          empty="No unmatched invoices."
        />
      </Section>

      <Section title="Unmatched transactions" count={unmatchedTxns.length}>
        <DataTable
          columns={txnColumns}
          rows={unmatchedTxns}
          empty="No transactions needing review."
        />
      </Section>

      <Section
        title="Needs review"
        count={reviewTasks.length}
        action={
          reviewTasks.length > 0 ? (
            <Link
              to="/manual-review"
              className="text-[12px] font-medium text-primary hover:underline"
            >
              Open in Manual Review
            </Link>
          ) : undefined
        }
      >
        {reviewTasks.length === 0 ? (
          <p className="text-[13px] text-muted-foreground">No open review tasks.</p>
        ) : (
          <ul className="space-y-2 text-[13px]">
            {reviewTasks.map((t) => (
              <li
                key={t.id}
                className="rounded-md border border-border px-3 py-2"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium text-foreground">
                    Task #{t.id}
                  </span>
                  <span className="text-muted-foreground">
                    · txn #{t.bank_transaction_id}
                  </span>
                  <StatusBadge value={reviewReasonLabel(t.reason)} />
                  {t.payload?.invoice_number ? (
                    <span className="font-mono text-foreground">
                      {t.payload.invoice_number as string}
                    </span>
                  ) : null}
                  {t.reason === "batch_amount_suggested" &&
                  Array.isArray(t.payload?.invoices) ? (
                    <span className="text-muted-foreground">
                      ·{" "}
                      {(t.payload.invoices as { invoice_number?: string }[])
                        .map((i) => i.invoice_number)
                        .filter(Boolean)
                        .join(", ")}
                    </span>
                  ) : null}
                  <Link
                    to={`/manual-review?task=${t.id}`}
                    className="ml-auto text-[12px] text-primary hover:underline"
                  >
                    Review
                  </Link>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section title="Multi-invoice comments" count={multiTxns.length}>
        <DataTable
          columns={txnColumns}
          rows={multiTxns}
          empty="No multi-invoice bank lines."
        />
      </Section>
    </div>
  );
}

function Section({
  title,
  count,
  action,
  children,
}: {
  title: string;
  count: number;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-[14px] font-semibold text-foreground">
          {title}{" "}
          <span className="font-normal text-muted-foreground">({count})</span>
        </h2>
        {action}
      </div>
      {children}
    </section>
  );
}
