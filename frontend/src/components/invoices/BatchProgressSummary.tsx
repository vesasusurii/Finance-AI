import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";
import type { BatchProgressStats } from "@/types/uploadQueue";

function StatCard({
  label,
  value,
  tone = "default",
}: {
  label: string;
  value: number;
  tone?: "default" | "success" | "warning" | "danger";
}) {
  const valueClass =
    tone === "success"
      ? "text-success"
      : tone === "warning"
        ? "text-[oklch(0.45_0.13_60)]"
        : tone === "danger"
          ? "text-destructive"
          : "text-foreground";

  return (
    <div className="rounded-lg border border-border bg-card px-4 py-3">
      <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <p className={cn("mt-1 text-[22px] font-semibold tabular-nums", valueClass)}>
        {value}
      </p>
    </div>
  );
}

export function BatchProgressSummary({
  stats,
  isRunning,
}: {
  stats: BatchProgressStats;
  isRunning: boolean;
}) {
  if (stats.total === 0) return null;

  const done = stats.completed + stats.failed + stats.requiresReview;

  return (
    <section className="mb-6 rounded-lg border border-border bg-card p-5">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-[0.08em] text-muted-foreground">
            Batch progress
          </p>
          <h2 className="mt-1 text-[15px] font-semibold text-foreground">
            {isRunning
              ? `${stats.processing} of ${stats.total} invoices are currently processing`
              : `${done} of ${stats.total} invoices finished`}
          </h2>
        </div>
        <p className="text-[13px] tabular-nums text-muted-foreground">
          Overall {stats.overallProgress}%
        </p>
      </div>

      <Progress value={stats.overallProgress} className="mb-4 h-2" />

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <StatCard label="Total uploaded" value={stats.total} />
        <StatCard label="Processing" value={stats.processing} />
        <StatCard label="Completed" value={stats.completed} tone="success" />
        <StatCard
          label="Requires review"
          value={stats.requiresReview}
          tone="warning"
        />
        <StatCard label="Failed" value={stats.failed} tone="danger" />
      </div>
    </section>
  );
}
