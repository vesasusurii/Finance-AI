import { useCallback, useEffect, useState } from "react";
import { listInvoices } from "@/api/invoices";
import { listReviewTasks } from "@/api/review";

export type NotificationItem = {
  id: string;
  title: string;
  description: string;
  href: string;
};

export function useNotificationSummary(enabled: boolean) {
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [loading, setLoading] = useState(false);

  const reload = useCallback(async () => {
    if (!enabled) {
      setItems([]);
      return;
    }
    setLoading(true);
    try {
      const [needsReview, unmatched, reviewTasks] = await Promise.all([
        listInvoices({ review_status: "needs_review", limit: 1 }),
        listInvoices({ match_status: "unmatched", limit: 1 }),
        listReviewTasks({ limit: 1, slim: true }),
      ]);

      const next: NotificationItem[] = [];
      if (needsReview.total > 0) {
        next.push({
          id: "invoices-needs-review",
          title: `${needsReview.total} invoice${needsReview.total === 1 ? "" : "s"} need review`,
          description: "Extraction or validation issues",
          href: "/documents?tab=needs-review",
        });
      }
      if (unmatched.total > 0) {
        next.push({
          id: "invoices-unmatched",
          title: `${unmatched.total} unmatched invoice${unmatched.total === 1 ? "" : "s"}`,
          description: "Awaiting bank reconciliation",
          href: "/matching?tab=unmatched-invoices",
        });
      }
      if (reviewTasks.total > 0) {
        next.push({
          id: "review-tasks",
          title: `${reviewTasks.total} open review task${reviewTasks.total === 1 ? "" : "s"}`,
          description: "Bank match or extraction queue",
          href: "/manual-review",
        });
      }
      setItems(next);
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [enabled]);

  useEffect(() => {
    void reload();
  }, [reload]);

  return { items, total: items.length, loading, reload };
}
