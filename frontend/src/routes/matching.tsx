import { useCallback, useEffect, useState, type ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Play } from "lucide-react";
import { SectionLoadingSpinner } from "@/components/LoadingSpinner";
import { PageHeader } from "@/components/ui-finance/PageHeader";
import { Button } from "@/components/ui-finance/Button";
import { DataTable, type Column } from "@/components/ui-finance/DataTable";
import { TablePagination } from "@/components/ui-finance/TablePagination";
import { StatusBadge } from "@/components/ui-finance/StatusBadge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { MatchedTransactionsGrid } from "@/components/matching/MatchedTransactionsGrid";
import {
  approveMatch,
  getReconciliationResults,
  rejectMatch,
  runReconciliation,
} from "@/api/reconciliation";
import { useAppDialog } from "@/components/dialogs/AppDialogProvider";
import { ApiError } from "@/api/client";
import { refreshSession } from "@/api/auth";
import { listReviewTasks } from "@/api/review";
import { listBankStatements, listBankTransactions } from "@/api/bankStatements";
import { listInvoices } from "@/api/invoices";
import type { InvoicePaymentMatch, ReconciliationSummary } from "@/types/match";
import type { BankStatement, BankTransaction } from "@/types/bank";
import type { ReviewTask } from "@/types/review";
import type { Invoice } from "@/types/invoice";
import {
  formatDate,
  formatCurrency,
  matchStatusLabel,
  reconciliationStatusLabel,
  reviewReasonLabel,
} from "@/lib/labels";
import { cn } from "@/lib/utils";

const PAGE_SIZE = 10;

const MATCHING_REVIEW_REASONS = [
  "no_invoice_in_db",
  "duplicate_invoice_in_db",
  "internal_error",
  "no_invoice_numbers_detected",
  "invoice_numbers_not_visible",
  "batch_payment_incomplete",
  "batch_amount_suggested",
  "missing_transaction_date",
] as const;

type MatchingTab =
  | "matched"
  | "partially-paid"
  | "unmatched-invoices"
  | "unmatched-transactions"
  | "needs-review"
  | "multi-invoice";

const MATCHING_TABS: { id: MatchingTab; label: string }[] = [
  { id: "matched", label: "Matched" },
  { id: "partially-paid", label: "Partially paid" },
  { id: "unmatched-invoices", label: "Unmatched invoices" },
  { id: "unmatched-transactions", label: "Unmatched transactions" },
  { id: "needs-review", label: "Needs review" },
  { id: "multi-invoice", label: "Multi-invoice comments" },
];

function isMatchingTab(value: string | null): value is MatchingTab {
  return MATCHING_TABS.some((tab) => tab.id === value);
}

function formatStatementOptionLabel(statement: BankStatement): string {
  const dateLabel = statement.statement_date
    ? formatDate(statement.statement_date)
    : `#${statement.id}`;
  return `${dateLabel} — ${statement.original_filename}`;
}

function DateCell({ value }: { value: string | null | undefined }) {
  return <span className="tabular-nums">{formatDate(value ?? null)}</span>;
}

export function MatchingPage() {
  const { prompt } = useAppDialog();
  const [searchParams, setSearchParams] = useSearchParams();
  const [activeTab, setActiveTab] = useState<MatchingTab>(() => {
    const tab = searchParams.get("tab");
    return isMatchingTab(tab) ? tab : "unmatched-invoices";
  });
  const [statementId, setStatementId] = useState(
    () => searchParams.get("bank_statement_id") ?? "",
  );
  const [statements, setStatements] = useState<BankStatement[]>([]);

  useEffect(() => {
    const sid = searchParams.get("bank_statement_id");
    if (sid) setStatementId(sid);
    const tab = searchParams.get("tab");
    if (isMatchingTab(tab)) setActiveTab(tab);
  }, [searchParams]);

  useEffect(() => {
    void listBankStatements(1, 100)
      .then((res) => setStatements(res.items))
      .catch(() => setStatements([]));
  }, []);

  const [running, setRunning] = useState(false);
  const [loadingTab, setLoadingTab] = useState(true);
  const [summary, setSummary] = useState<ReconciliationSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [matches, setMatches] = useState<InvoicePaymentMatch[]>([]);
  const [unmatchedInvoices, setUnmatchedInvoices] = useState<Invoice[]>([]);
  const [partialInvoices, setPartialInvoices] = useState<Invoice[]>([]);
  const [reviewTasks, setReviewTasks] = useState<ReviewTask[]>([]);
  const [unmatchedTxns, setUnmatchedTxns] = useState<BankTransaction[]>([]);
  const [multiTxns, setMultiTxns] = useState<BankTransaction[]>([]);
  const [busyMatchId, setBusyMatchId] = useState<number | null>(null);
  const [invoicePage, setInvoicePage] = useState(1);
  const [partialPage, setPartialPage] = useState(1);
  const [txnPage, setTxnPage] = useState(1);
  const [matchPage, setMatchPage] = useState(1);
  const [reviewPage, setReviewPage] = useState(1);
  const [multiTxnPage, setMultiTxnPage] = useState(1);
  const [matchTotal, setMatchTotal] = useState(0);
  const [unmatchedInvoiceTotal, setUnmatchedInvoiceTotal] = useState(0);
  const [partialInvoiceTotal, setPartialInvoiceTotal] = useState(0);
  const [unmatchedTxnTotal, setUnmatchedTxnTotal] = useState(0);
  const [reviewTotal, setReviewTotal] = useState(0);
  const [multiTxnTotal, setMultiTxnTotal] = useState(0);

  const statementFilters = useCallback(() => {
    const sid = statementId ? parseInt(statementId, 10) : undefined;
    return Number.isFinite(sid) ? { bank_statement_id: sid } : {};
  }, [statementId]);

  const loadTotals = useCallback(async () => {
    const filters = statementFilters();
    const [matchRes, invoiceRes, partialRes, txnRes, reviewRes, multiTxnRes] =
      await Promise.all([
        getReconciliationResults({ ...filters, page: 1, limit: 1 }),
        listInvoices({ match_status: "unmatched", page: 1, limit: 1 }),
        listInvoices({ match_status: "partially_matched", page: 1, limit: 1 }),
        listBankTransactions({
          ...filters,
          reconciliation_status: "needs_review",
          page: 1,
          limit: 1,
        }),
        listReviewTasks({
          task_type: "bank_match",
          page: 1,
          limit: 1,
          reasons: [...MATCHING_REVIEW_REASONS],
          slim: true,
        }),
        listBankTransactions({
          ...filters,
          multi_invoice: true,
          page: 1,
          limit: 1,
        }),
      ]);
    setMatchTotal(matchRes.total);
    setUnmatchedInvoiceTotal(invoiceRes.total);
    setPartialInvoiceTotal(partialRes.total);
    setUnmatchedTxnTotal(txnRes.total);
    setReviewTotal(reviewRes.total);
    setMultiTxnTotal(multiTxnRes.total);
  }, [statementFilters]);

  const loadActiveTab = useCallback(async () => {
    const filters = statementFilters();
    setLoadingTab(true);
    try {
      switch (activeTab) {
        case "matched": {
          const res = await getReconciliationResults({
            ...filters,
            page: matchPage,
            limit: PAGE_SIZE,
          });
          setMatches(res.items);
          setMatchTotal(res.total);
          break;
        }
        case "partially-paid": {
          const res = await listInvoices({
            match_status: "partially_matched",
            page: partialPage,
            limit: PAGE_SIZE,
          });
          setPartialInvoices(res.items);
          setPartialInvoiceTotal(res.total);
          break;
        }
        case "unmatched-invoices": {
          const res = await listInvoices({
            match_status: "unmatched",
            page: invoicePage,
            limit: PAGE_SIZE,
          });
          setUnmatchedInvoices(res.items);
          setUnmatchedInvoiceTotal(res.total);
          break;
        }
        case "unmatched-transactions": {
          const res = await listBankTransactions({
            ...filters,
            reconciliation_status: "needs_review",
            page: txnPage,
            limit: PAGE_SIZE,
          });
          setUnmatchedTxns(res.items);
          setUnmatchedTxnTotal(res.total);
          break;
        }
        case "needs-review": {
          const res = await listReviewTasks({
            task_type: "bank_match",
            page: reviewPage,
            limit: PAGE_SIZE,
            reasons: [...MATCHING_REVIEW_REASONS],
            slim: true,
          });
          setReviewTasks(res.items);
          setReviewTotal(res.total);
          break;
        }
        case "multi-invoice": {
          const res = await listBankTransactions({
            ...filters,
            multi_invoice: true,
            page: multiTxnPage,
            limit: PAGE_SIZE,
          });
          setMultiTxns(res.items);
          setMultiTxnTotal(res.total);
          break;
        }
      }
    } finally {
      setLoadingTab(false);
    }
  }, [
    activeTab,
    statementFilters,
    matchPage,
    partialPage,
    invoicePage,
    txnPage,
    reviewPage,
    multiTxnPage,
  ]);

  useEffect(() => {
    setInvoicePage(1);
    setPartialPage(1);
    setTxnPage(1);
    setMatchPage(1);
    setReviewPage(1);
    setMultiTxnPage(1);
  }, [statementId]);

  useEffect(() => {
    void loadTotals().catch(() => {
      /* counts are optional — tab content fetch shows errors */
    });
  }, [loadTotals]);

  useEffect(() => {
    void loadActiveTab().catch((e) => {
      setError(e instanceof Error ? e.message : "Could not load matching data");
    });
  }, [loadActiveTab]);

  const refreshAll = useCallback(async () => {
    await loadTotals();
    await loadActiveTab();
  }, [loadTotals, loadActiveTab]);

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
      await refreshAll();
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
      setMatches((prev) =>
        prev.map((m) =>
          m.id === matchId ? { ...m, status: "approved" as const } : m,
        ),
      );
    } catch (e) {
      if (e instanceof ApiError && e.code === "match_already_resolved") {
        setMatches((prev) =>
          prev.map((m) =>
            m.id === matchId ? { ...m, status: "approved" as const } : m,
          ),
        );
      } else {
        setError(e instanceof Error ? e.message : "Could not approve match");
        return;
      }
    } finally {
      setBusyMatchId(null);
    }
    await refreshAll();
  };

  const onReject = async (matchId: number) => {
    if (busyMatchId != null) return;
    const reason = await prompt({
      title: "Reject match",
      description: "Reason for rejecting this match (optional):",
      confirmLabel: "Reject",
    });
    if (reason === null) return;
    setBusyMatchId(matchId);
    setError(null);
    try {
      await rejectMatch(matchId, reason || undefined);
      setMatches((prev) =>
        prev.map((m) =>
          m.id === matchId ? { ...m, status: "rejected" as const } : m,
        ),
      );
    } catch (e) {
      if (e instanceof ApiError && e.code === "match_already_resolved") {
        setMatches((prev) =>
          prev.map((m) =>
            m.id === matchId ? { ...m, status: "rejected" as const } : m,
          ),
        );
      } else {
        setError(e instanceof Error ? e.message : "Could not reject match");
        return;
      }
    } finally {
      setBusyMatchId(null);
    }
    await refreshAll();
  };

  const onStatementChange = (value: string) => {
    setStatementId(value);
    const next = new URLSearchParams(searchParams);
    if (value) {
      next.set("bank_statement_id", value);
    } else {
      next.delete("bank_statement_id");
    }
    setSearchParams(next);
  };

  const onTabChange = (tab: string) => {
    if (!isMatchingTab(tab)) return;
    setActiveTab(tab);
    const next = new URLSearchParams(searchParams);
    next.set("tab", tab);
    setSearchParams(next);
  };

  const tabTotals: Record<MatchingTab, number> = {
    matched: matchTotal,
    "partially-paid": partialInvoiceTotal,
    "unmatched-invoices": unmatchedInvoiceTotal,
    "unmatched-transactions": unmatchedTxnTotal,
    "needs-review": reviewTotal,
    "multi-invoice": multiTxnTotal,
  };

  const selectedStatement = statements.find(
    (s) => String(s.id) === statementId,
  );
  const staleStatementFilter =
    statementId !== "" &&
    !selectedStatement &&
    statements.length > 0 &&
    Number.isFinite(parseInt(statementId, 10));

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
      cell: (r) => <DateCell value={r.paid_at_date} />,
    },
    {
      key: "status",
      header: "Match",
      cell: (r) => <StatusBadge value={matchStatusLabel(r.match_status)} />,
    },
  ];

  const partialInvoiceColumns: Column<Invoice>[] = [
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
      key: "amount",
      header: "Total",
      align: "right",
      cell: (r) => formatCurrency(r.amount != null ? Number(r.amount) : null, r.currency),
    },
    {
      key: "debt",
      header: "Remaining",
      align: "right",
      cell: (r) => (
        <span className="font-semibold tabular-nums text-primary">
          {formatCurrency(r.debt != null ? Number(r.debt) : null, r.currency)}
        </span>
      ),
    },
    {
      key: "first_paid",
      header: "First payment",
      cell: (r) => <DateCell value={r.paid_at_date} />,
    },
    {
      key: "status",
      header: "Status",
      cell: (r) => <StatusBadge value={matchStatusLabel(r.match_status)} />,
    },
  ];

  const txnColumns: Column<BankTransaction>[] = [
    {
      key: "date",
      header: "Date",
      cell: (r) => <DateCell value={r.transaction_date} />,
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
    <div className="space-y-6">
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
                  {formatStatementOptionLabel(s)}
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
          <strong>{summary.unmatched_transactions}</strong> unmatched
          transactions, <strong>{summary.review_tasks_created}</strong> review
          tasks, <strong>{summary.unmatched_invoices}</strong> unmatched invoices
          in DB
        </div>
      )}

      <Tabs value={activeTab} onValueChange={onTabChange}>
        <TabsList className="h-auto w-full flex-wrap justify-start gap-1 rounded-lg border border-border bg-card p-1">
          {MATCHING_TABS.map((tab) => (
            <TabsTrigger
              key={tab.id}
              value={tab.id}
              className={cn(
                "h-8 rounded-md px-3 text-[12px] font-medium text-muted-foreground",
                "data-[state=active]:bg-primary data-[state=active]:text-primary-foreground",
              )}
            >
              {tab.label}
              <span className="ml-1.5 rounded bg-background/20 px-1.5 py-0.5 text-[10px] tabular-nums">
                {tabTotals[tab.id]}
              </span>
            </TabsTrigger>
          ))}
        </TabsList>

        <TabPanel loading={loadingTab}>
          <TabsContent value="matched" className="mt-4">
            {matchTotal === 0 ? (
              <p className="rounded-lg border border-border bg-card px-4 py-16 text-center text-[13px] text-muted-foreground">
                No matches yet. Upload bank data and run matching.
              </p>
            ) : (
              <MatchedTransactionsGrid
                matches={matches}
                busyMatchId={busyMatchId}
                onApprove={(id) => void onApprove(id)}
                onReject={(id) => void onReject(id)}
              />
            )}
            <TablePagination
              page={matchPage}
              pageSize={PAGE_SIZE}
              total={matchTotal}
              onPageChange={setMatchPage}
            />
          </TabsContent>

          <TabsContent value="partially-paid" className="mt-4">
            <DataTable
              columns={partialInvoiceColumns}
              rows={partialInvoices}
              empty="No partially paid invoices."
            />
            <TablePagination
              page={partialPage}
              pageSize={PAGE_SIZE}
              total={partialInvoiceTotal}
              onPageChange={setPartialPage}
            />
          </TabsContent>

          <TabsContent value="unmatched-invoices" className="mt-4">
            <DataTable
              columns={invoiceColumns}
              rows={unmatchedInvoices}
              empty="No unmatched invoices."
            />
            <TablePagination
              page={invoicePage}
              pageSize={PAGE_SIZE}
              total={unmatchedInvoiceTotal}
              onPageChange={setInvoicePage}
            />
          </TabsContent>

          <TabsContent value="unmatched-transactions" className="mt-4">
            <DataTable
              columns={txnColumns}
              rows={unmatchedTxns}
              empty="No transactions needing review."
            />
            <TablePagination
              page={txnPage}
              pageSize={PAGE_SIZE}
              total={unmatchedTxnTotal}
              onPageChange={setTxnPage}
            />
          </TabsContent>

          <TabsContent value="needs-review" className="mt-4">
            <div className="mb-3 flex justify-end">
              {reviewTotal > 0 ? (
                <Link
                  to="/manual-review"
                  className="text-[12px] font-medium text-primary hover:underline"
                >
                  Open in Manual Review
                </Link>
              ) : null}
            </div>
            {reviewTotal === 0 ? (
              <p className="text-[13px] text-muted-foreground">
                No open review tasks.
              </p>
            ) : (
              <>
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
                <TablePagination
                  page={reviewPage}
                  pageSize={PAGE_SIZE}
                  total={reviewTotal}
                  onPageChange={setReviewPage}
                />
              </>
            )}
          </TabsContent>

          <TabsContent value="multi-invoice" className="mt-4">
            <DataTable
              columns={txnColumns}
              rows={multiTxns}
              empty="No multi-invoice bank lines."
            />
            <TablePagination
              page={multiTxnPage}
              pageSize={PAGE_SIZE}
              total={multiTxnTotal}
              onPageChange={setMultiTxnPage}
            />
          </TabsContent>
        </TabPanel>
      </Tabs>
    </div>
  );
}

function TabPanel({
  loading,
  children,
}: {
  loading: boolean;
  children: ReactNode;
}) {
  if (loading) {
    return (
      <div className="min-h-[200px]">
        <SectionLoadingSpinner />
      </div>
    );
  }

  return <div className="min-h-[200px]">{children}</div>;
}
