import { useCallback, useEffect, useState } from "react";
import { listReviewTasks } from "@/api/review";
import type { ReviewTask } from "@/types/review";

export type ReviewQueueFilter = "all" | "extraction" | "bank_match";

export function useReviewQueue(
  taskTypeFilter: ReviewQueueFilter,
  page = 1,
  limit = 50,
) {
  const [items, setItems] = useState<ReviewTask[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const task_type =
        taskTypeFilter === "all" ? undefined : taskTypeFilter;
      const res = await listReviewTasks({ task_type, page, limit });
      setItems(res.items);
      setTotal(res.total);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load review queue");
      setItems([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [taskTypeFilter, page, limit]);

  useEffect(() => {
    void reload();
  }, [reload]);

  return { items, total, loading, error, reload };
}
