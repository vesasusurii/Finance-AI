import { useCallback, useEffect, useState } from "react";
import { listInvoices } from "@/api/invoices";
import { listReviewTasks } from "@/api/review";
import type { Invoice } from "@/types/invoice";
import type { ReviewTask } from "@/types/review";

export type ReviewQueueFilter = "all" | "extraction" | "bank_match";

export type ManualReviewEntry = {
  /** Stable key for React lists and deep links (`inv-12` or `task-34`). */
  key: string;
  invoice: Invoice;
  task: ReviewTask | null;
  mode: "bank_match" | "extraction";
};

function dedupeInvoices(items: Invoice[]): Invoice[] {
  const byId = new Map<number, Invoice>();
  for (const inv of items) {
    byId.set(inv.id, inv);
  }
  return [...byId.values()].sort(
    (a, b) => b.updated_at.localeCompare(a.updated_at),
  );
}

function findTaskForInvoice(
  tasks: ReviewTask[],
  invoiceId: number,
): ReviewTask | null {
  return (
    tasks.find(
      (t) =>
        t.invoice_id === invoiceId ||
        t.invoice?.id === invoiceId,
    ) ?? null
  );
}

async function loadBankMatchInvoices(): Promise<Invoice[]> {
  const [unmatched, needsReview] = await Promise.all([
    listInvoices({ match_status: "unmatched", limit: 200 }),
    listInvoices({ match_status: "needs_review", limit: 200 }),
  ]);
  return dedupeInvoices([...unmatched.items, ...needsReview.items]);
}

async function loadExtractionEntries(): Promise<ManualReviewEntry[]> {
  const res = await listReviewTasks({ task_type: "extraction", limit: 200 });
  const entries: ManualReviewEntry[] = [];
  for (const task of res.items) {
    const invoice = task.invoice;
    if (!invoice) continue;
    entries.push({
      key: `task-${task.id}`,
      invoice,
      task,
      mode: "extraction",
    });
  }
  return entries;
}

async function loadBankMatchEntries(): Promise<ManualReviewEntry[]> {
  const [invoices, taskRes] = await Promise.all([
    loadBankMatchInvoices(),
    listReviewTasks({ task_type: "bank_match", limit: 200 }),
  ]);
  return invoices.map((invoice) => ({
    key: `inv-${invoice.id}`,
    invoice,
    task: findTaskForInvoice(taskRes.items, invoice.id),
    mode: "bank_match" as const,
  }));
}

export function useManualReviewQueue(taskTypeFilter: ReviewQueueFilter) {
  const [items, setItems] = useState<ManualReviewEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async (): Promise<ManualReviewEntry[]> => {
    setLoading(true);
    setError(null);
    try {
      let entries: ManualReviewEntry[] = [];
      if (taskTypeFilter === "extraction") {
        entries = await loadExtractionEntries();
      } else if (taskTypeFilter === "bank_match") {
        entries = await loadBankMatchEntries();
      } else {
        const [bank, extraction] = await Promise.all([
          loadBankMatchEntries(),
          loadExtractionEntries(),
        ]);
        const seen = new Set<number>();
        for (const e of [...extraction, ...bank]) {
          if (seen.has(e.invoice.id)) continue;
          seen.add(e.invoice.id);
          entries.push(e);
        }
      }
      setItems(entries);
      return entries;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load review queue");
      setItems([]);
      return [];
    } finally {
      setLoading(false);
    }
  }, [taskTypeFilter]);

  useEffect(() => {
    void reload();
  }, [reload]);

  return { items, total: items.length, loading, error, reload };
}
