import { useCallback, useEffect, useState } from "react";
import { listManualReviewQueue } from "@/api/review";
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

const QUEUE_LIMIT = 200;

export function useManualReviewQueue(taskTypeFilter: ReviewQueueFilter) {
  const [items, setItems] = useState<ManualReviewEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async (): Promise<ManualReviewEntry[]> => {
    setLoading(true);
    setError(null);
    try {
      const res = await listManualReviewQueue({
        filter: taskTypeFilter,
        limit: QUEUE_LIMIT,
      });
      const entries: ManualReviewEntry[] = res.items.map((item) => ({
        key: item.key,
        invoice: item.invoice,
        task: item.task,
        mode: item.mode,
      }));
      setItems(entries);
      setTotal(res.total);
      return entries;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load review queue");
      setItems([]);
      setTotal(0);
      return [];
    } finally {
      setLoading(false);
    }
  }, [taskTypeFilter]);

  useEffect(() => {
    setItems([]);
    setTotal(0);
  }, [taskTypeFilter]);

  useEffect(() => {
    void reload();
  }, [reload]);

  return { items, total, loading, error, reload };
}
