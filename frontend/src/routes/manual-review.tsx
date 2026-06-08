import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ChevronLeft, ChevronRight, ExternalLink } from "lucide-react";
import {
  LoadingSpinner,
  SectionLoadingSpinner,
} from "@/components/LoadingSpinner";
import { PageHeader } from "@/components/ui-finance/PageHeader";
import { Button } from "@/components/ui-finance/Button";
import { StatusBadge } from "@/components/ui-finance/StatusBadge";
import { EmptyState } from "@/components/EmptyState";
import { InvoiceAmountDisplay } from "@/components/invoices/InvoiceAmountDisplay";
import { InvoiceDocumentPreview } from "@/components/invoices/InvoiceDocumentPreview";
import { BankTransactionCandidatesPanel } from "@/components/review/BankTransactionCandidatesPanel";
import { approveReviewTask, rejectReviewTask } from "@/api/review";
import {
  useManualReviewQueue,
  type ManualReviewEntry,
  type ReviewQueueFilter,
} from "@/hooks/useManualReviewQueue";
import {
  formatDate,
  reviewReasonLabel,
  reviewStatusLabel,
} from "@/lib/labels";
import { useAppDialog } from "@/components/dialogs/AppDialogProvider";
import { cn } from "@/lib/utils";

const FILTERS: { id: ReviewQueueFilter; label: string }[] = [
  { id: "all", label: "All" },
  { id: "bank_match", label: "Bank match" },
  { id: "extraction", label: "Extraction" },
];

function entryIndex(
  entries: ManualReviewEntry[],
  taskId: string | null,
  invoiceId: string | null,
): number {
  if (taskId) {
    const id = parseInt(taskId, 10);
    const found = entries.findIndex((e) => e.task?.id === id);
    if (found >= 0) return found;
  }
  if (invoiceId) {
    const id = parseInt(invoiceId, 10);
    const found = entries.findIndex((e) => e.invoice.id === id);
    if (found >= 0) return found;
  }
  return 0;
}

function TaskDismissActions({
  taskId,
  onDone,
  showApprove,
}: {
  taskId: number;
  onDone: () => void;
  showApprove: boolean;
}) {
  const { prompt } = useAppDialog();
  const [busy, setBusy] = useState<"approve" | "reject" | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleApprove = async () => {
    setBusy("approve");
    setError(null);
    try {
      await approveReviewTask(taskId);
      onDone();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Approve failed");
      setBusy(null);
    }
  };

  const handleReject = async () => {
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
      await rejectReviewTask(taskId, reason.trim() || undefined);
      onDone();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Reject failed");
      setBusy(null);
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-2">
      {error && (
        <p className="w-full text-[12px] text-destructive">{error}</p>
      )}
      <Button
        variant="secondary"
        size="sm"
        disabled={busy !== null}
        onClick={() => void handleReject()}
      >
        {busy === "reject" ? (
          <LoadingSpinner size="sm" />
        ) : (
          "Reject"
        )}
      </Button>
      {showApprove && (
        <Button
          variant="success"
          size="sm"
          disabled={busy !== null}
          onClick={() => void handleApprove()}
        >
          {busy === "approve" ? (
            <LoadingSpinner size="sm" />
          ) : (
            "Approve"
          )}
        </Button>
      )}
    </div>
  );
}

function BankMatchView({
  entry,
  onResolved,
}: {
  entry: ManualReviewEntry;
  onResolved: () => void;
}) {
  const { invoice, task } = entry;
  return (
    <div className="grid min-h-[calc(100vh-14rem)] grid-cols-1 items-stretch gap-4 lg:grid-cols-2">
      <div className="flex h-full min-h-[960px] flex-col lg:min-h-0">
        <InvoiceDocumentPreview
          key={invoice.id}
          invoiceId={invoice.id}
          invoice={invoice}
        />
      </div>
      <BankTransactionCandidatesPanel
        key={`${invoice.id}-${task?.id ?? "none"}`}
        invoice={invoice}
        task={task}
        onResolved={onResolved}
      />
    </div>
  );
}

function ExtractionView({
  entry,
  onResolved,
}: {
  entry: ManualReviewEntry;
  onResolved: () => void;
}) {
  const { invoice, task } = entry;
  if (!task) return null;

  return (
    <div className="grid min-h-[calc(100vh-14rem)] grid-cols-1 items-stretch gap-4 lg:grid-cols-2">
      <div className="flex h-full min-h-[960px] flex-col lg:min-h-0">
        <InvoiceDocumentPreview
          key={invoice.id}
          invoiceId={invoice.id}
          invoice={invoice}
        />
      </div>
      <div className="flex h-full min-h-[960px] flex-col rounded-lg border border-border bg-card lg:min-h-0">
        <div className="border-b border-border px-4 py-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[13px] font-semibold text-foreground">
              Extraction review
            </span>
            <StatusBadge
              value={reviewReasonLabel(task.reason)}
              tone="warning"
            />
          </div>
          <p className="mt-2 text-[13px] text-muted-foreground">
            Preview is read-only here. Edit fields on Purchase invoices, or
            approve/reject this queue item when extraction is acceptable.
          </p>
        </div>
        <div className="flex flex-1 flex-col justify-between gap-4 p-4">
          <dl className="grid gap-3 text-[13px] sm:grid-cols-2">
            <div>
              <dt className="text-muted-foreground">Invoice date</dt>
              <dd className="tabular-nums text-foreground">
                {formatDate(invoice.invoice_date)}
              </dd>
            </div>
            {invoice.extraction_confidence != null && (
              <div>
                <dt className="text-muted-foreground">AI confidence</dt>
                <dd className="tabular-nums text-foreground">
                  {Math.round(Number(invoice.extraction_confidence) * 100)}%
                </dd>
              </div>
            )}
            <div>
              <dt className="text-muted-foreground">Review status</dt>
              <dd>{reviewStatusLabel(invoice.review_status)}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Bill amount (EUR)</dt>
              <dd>
                <InvoiceAmountDisplay invoice={invoice} />
              </dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Original currency</dt>
              <dd className="text-foreground">
                {invoice.original_currency ?? invoice.currency ?? "EUR"}
              </dd>
            </div>
          </dl>
          <div className="flex flex-wrap items-center gap-2 border-t border-border pt-4">
            <Link to="/documents">
              <Button
                variant="secondary"
                size="sm"
                icon={<ExternalLink className="h-3.5 w-3.5" />}
              >
                Edit on Purchase invoices
              </Button>
            </Link>
            <TaskDismissActions
              taskId={task.id}
              onDone={onResolved}
              showApprove
            />
          </div>
        </div>
      </div>
    </div>
  );
}

export function ManualReviewPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [filter, setFilter] = useState<ReviewQueueFilter>("bank_match");
  const { items, total, loading, error, reload } = useManualReviewQueue(filter);
  const [idx, setIdx] = useState(0);

  const taskIdParam = searchParams.get("task");
  const invoiceIdParam = searchParams.get("invoice");

  const initialIdx = useMemo(
    () => entryIndex(items, taskIdParam, invoiceIdParam),
    [items, taskIdParam, invoiceIdParam],
  );

  useEffect(() => {
    if (items.length === 0) {
      setIdx(0);
      return;
    }
    setIdx(Math.min(initialIdx, items.length - 1));
  }, [items.length, initialIdx, filter]);

  const entry = items[idx] ?? null;

  const syncUrl = useCallback(
    (e: ManualReviewEntry) => {
      if (e.mode === "extraction" && e.task) {
        setSearchParams({ task: String(e.task.id) }, { replace: true });
      } else {
        setSearchParams({ invoice: String(e.invoice.id) }, { replace: true });
      }
    },
    [setSearchParams],
  );

  const goTo = useCallback(
    (next: number) => {
      if (items.length === 0) return;
      const clamped = Math.max(0, Math.min(next, items.length - 1));
      setIdx(clamped);
      const e = items[clamped];
      if (e) syncUrl(e);
    },
    [items, syncUrl],
  );

  const onResolved = useCallback(async () => {
    const currentIdx = idx;
    const nextItems = await reload();
    const nextIdx = Math.min(
      currentIdx,
      Math.max(0, nextItems.length - 1),
    );
    setIdx(nextIdx);
    const next = nextItems[nextIdx];
    if (next) {
      syncUrl(next);
    } else {
      setSearchParams({}, { replace: true });
    }
  }, [reload, idx, setSearchParams, syncUrl]);

  if (!loading && items.length === 0) {
    return (
      <div>
        <PageHeader
          eyebrow="Workflow"
          title="Manual review"
          description="Match purchase invoices to bank lines, or resolve extraction review items."
        />
        <FilterBar filter={filter} onFilter={setFilter} />
        <EmptyState
          title="Manual review queue is empty"
          description={
            filter === "extraction"
              ? "No open extraction review tasks."
              : "No unmatched invoices waiting for a bank match. Run matching after uploading bank data."
          }
        />
      </div>
    );
  }

  return (
    <div className="flex flex-col">
      <PageHeader
        eyebrow={
          entry
            ? `Workflow · Invoice ${idx + 1} of ${total}`
            : "Workflow"
        }
        title="Manual review"
        actions={
          items.length > 1 ? (
            <div className="flex items-center gap-1.5">
              <Button
                variant="secondary"
                size="sm"
                disabled={idx === 0}
                onClick={() => goTo(idx - 1)}
                icon={<ChevronLeft className="h-3.5 w-3.5" />}
              >
                Prev
              </Button>
              <Button
                variant="secondary"
                size="sm"
                disabled={idx >= items.length - 1}
                onClick={() => goTo(idx + 1)}
              >
                Next <ChevronRight className="h-3.5 w-3.5" />
              </Button>
            </div>
          ) : undefined
        }
      />

      <FilterBar filter={filter} onFilter={setFilter} />

      {error && <p className="mb-4 text-[13px] text-destructive">{error}</p>}

      {loading || !entry ? (
        <SectionLoadingSpinner label="Loading review queue…" />
      ) : (
        <>
          <div className="mb-3 flex flex-wrap items-center gap-2 text-[12px] text-muted-foreground">
            <StatusBadge
              value={
                entry.mode === "extraction" ? "Extraction" : "Bank match"
              }
              tone="info"
            />
            {entry.task && (
              <StatusBadge
                value={reviewReasonLabel(entry.task.reason)}
                tone="warning"
              />
            )}
            <StatusBadge
              value={reviewStatusLabel(entry.invoice.review_status)}
              tone={
                entry.invoice.review_status === "approved"
                  ? "success"
                  : "warning"
              }
            />
            <span className="tabular-nums">
              {formatDate(entry.invoice.invoice_date)}
            </span>
            <InvoiceAmountDisplay
              invoice={entry.invoice}
              className="text-[12px] font-medium text-muted-foreground"
              subtitleClassName="text-[10px] text-muted-foreground/80"
            />
          </div>
          {entry.mode === "extraction" ? (
            <ExtractionView
              key={entry.key}
              entry={entry}
              onResolved={() => void onResolved()}
            />
          ) : (
            <BankMatchView
              key={entry.key}
              entry={entry}
              onResolved={() => void onResolved()}
            />
          )}
        </>
      )}
    </div>
  );
}

function FilterBar({
  filter,
  onFilter,
}: {
  filter: ReviewQueueFilter;
  onFilter: (f: ReviewQueueFilter) => void;
}) {
  return (
    <div className="mb-4 flex flex-wrap gap-2">
      {FILTERS.map((f) => (
        <FilterTab
          key={f.id}
          active={filter === f.id}
          label={f.label}
          onClick={() => onFilter(f.id)}
        />
      ))}
    </div>
  );
}

function FilterTab({
  active,
  label,
  onClick,
}: {
  active: boolean;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "rounded-md px-3 py-1.5 text-[12px] font-medium transition-colors",
        active
          ? "bg-primary text-primary-foreground"
          : "bg-secondary text-muted-foreground hover:text-foreground",
      )}
    >
      {label}
    </button>
  );
}
