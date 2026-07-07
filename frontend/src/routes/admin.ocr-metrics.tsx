import { useCallback, useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { getWorkerMetrics } from "@/api/metrics";
import { LoadingSpinner } from "@/components/LoadingSpinner";
import { PageHeader } from "@/components/ui-finance/PageHeader";
import { Button } from "@/components/ui-finance/Button";
import { DataTable, type Column } from "@/components/ui-finance/DataTable";
import { StatusBadge } from "@/components/ui-finance/StatusBadge";
import type { OcrAnalytics, SlowJobEntry, WorkerMetricsResponse } from "@/types/metrics";

function formatMs(value: number | null | undefined): string {
  if (value == null) return "—";
  return `${Math.round(value).toLocaleString()} ms`;
}

function formatPct(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function DistributionCard({
  title,
  data,
}: {
  title: string;
  data: Record<string, number>;
}) {
  const entries = Object.entries(data).sort((a, b) => b[1] - a[1]);
  if (entries.length === 0) {
    return (
      <div className="card p-4">
        <h3 className="text-[13px] font-semibold text-foreground">{title}</h3>
        <p className="mt-2 text-[12px] text-muted-foreground">No samples yet</p>
      </div>
    );
  }
  const total = entries.reduce((sum, [, count]) => sum + count, 0);
  return (
    <div className="card p-4">
      <h3 className="text-[13px] font-semibold text-foreground">{title}</h3>
      <ul className="mt-3 space-y-2">
        {entries.map(([key, count]) => (
          <li key={key} className="flex items-center justify-between gap-3 text-[12px]">
            <span className="truncate text-muted-foreground">{key}</span>
            <span className="shrink-0 tabular-nums text-foreground">
              {count} ({formatPct(count / total)})
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function PercentileGrid({
  analytics,
}: {
  analytics: OcrAnalytics;
}) {
  const rows = [
    { label: "Total", key: "total_ms" as const },
    { label: "OpenAI", key: "openai_total_ms" as const },
    { label: "Queue wait", key: "queue_wait_ms" as const },
    { label: "Render", key: "render_ms" as const },
  ];
  return (
    <div className="overflow-hidden rounded-lg border border-border">
      <table className="data-table w-full text-[13px]">
        <thead>
          <tr>
            <th className="text-left">Metric</th>
            <th className="text-right">p50</th>
            <th className="text-right">p90</th>
            <th className="text-right">p95</th>
            <th className="text-right">p99</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const values = analytics.percentiles[row.key];
            return (
              <tr key={row.key}>
                <td>{row.label}</td>
                <td className="text-right tabular-nums">{formatMs(values.p50)}</td>
                <td className="text-right tabular-nums">{formatMs(values.p90)}</td>
                <td className="text-right tabular-nums">{formatMs(values.p95)}</td>
                <td className="text-right tabular-nums">{formatMs(values.p99)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

const slowJobColumns: Column<SlowJobEntry & { id: number }>[] = [
  {
    key: "document",
    header: "Document",
    cell: (row) => (
      <span className="font-mono text-[12px]">#{row.document_id ?? "—"}</span>
    ),
  },
  {
    key: "mode",
    header: "Mode",
    cell: (row) => (
      <span className="text-[12px] text-muted-foreground">
        {row.extraction_mode ?? "—"}
      </span>
    ),
  },
  {
    key: "total",
    header: "Total",
    cell: (row) => (
      <span className="tabular-nums text-[12px]">{formatMs(row.total_ms)}</span>
    ),
  },
  {
    key: "openai",
    header: "OpenAI",
    cell: (row) => (
      <span className="tabular-nums text-[12px]">{formatMs(row.openai_total_ms)}</span>
    ),
  },
  {
    key: "queue",
    header: "Queue",
    cell: (row) => (
      <span className="tabular-nums text-[12px]">{formatMs(row.queue_wait_ms)}</span>
    ),
  },
  {
    key: "reason",
    header: "Slowness",
    cell: (row) => <StatusBadge value={row.slowness_reason.replace(/_/g, " ")} />,
  },
  {
    key: "slo",
    header: "SLO",
    cell: (row) =>
      row.slo_violations.length > 0 ? (
        <span className="text-[12px] text-destructive">
          {row.slo_violations.join(", ")}
        </span>
      ) : (
        <span className="text-[12px] text-muted-foreground">OK</span>
      ),
  },
];

export function OcrMetricsPage() {
  const [metrics, setMetrics] = useState<WorkerMetricsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getWorkerMetrics();
      setMetrics(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load OCR metrics");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const analytics = metrics?.ocr_analytics;
  const slowRows =
    analytics?.slow_jobs.map((row, index) => ({ ...row, id: index })) ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Site admin"
        title="OCR monitoring"
        description="Production extraction latency, queue health, routing breakdown, and SLO status."
        actions={
          <Button
            variant="secondary"
            icon={<RefreshCw className="h-3.5 w-3.5" />}
            disabled={loading}
            onClick={() => void load()}
          >
            Refresh
          </Button>
        }
      />

      {error ? (
        <p className="text-[13px] text-destructive" role="alert">
          {error}
        </p>
      ) : null}

      {loading ? (
        <LoadingSpinner centered className="text-muted-foreground" />
      ) : metrics && analytics ? (
        <>
          <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <div className="card p-4">
              <p className="eyebrow">Queue</p>
              <p className="mt-2 text-[24px] font-bold tabular-nums text-foreground">
                {metrics.ocr_queue_size}
              </p>
              <p className="mt-1 text-[12px] text-muted-foreground">
                High {metrics.ocr_high_priority_queue_size} · Normal{" "}
                {metrics.ocr_normal_queue_size}
              </p>
            </div>
            <div className="card p-4">
              <p className="eyebrow">Sample size</p>
              <p className="mt-2 text-[24px] font-bold tabular-nums text-foreground">
                {analytics.sample_size}
              </p>
              <p className="mt-1 text-[12px] text-muted-foreground">
                Recent production extractions
              </p>
            </div>
            <div className="card p-4">
              <p className="eyebrow">Avg OpenAI calls</p>
              <p className="mt-2 text-[24px] font-bold tabular-nums text-foreground">
                {analytics.averages.openai_call_count.toFixed(1)}
              </p>
              <p className="mt-1 text-[12px] text-muted-foreground">
                SLO max {analytics.slo_config.max_openai_calls}
              </p>
            </div>
            <div className="card p-4">
              <p className="eyebrow">Overlap saved</p>
              <p className="mt-2 text-[24px] font-bold tabular-nums text-foreground">
                {formatMs(metrics.avg_pipeline_overlap_saved_ms)}
              </p>
              <p className="mt-1 text-[12px] text-muted-foreground">
                Avg pipeline overlap savings
              </p>
            </div>
          </section>

          <section className="space-y-3">
            <h2 className="text-[14px] font-semibold text-foreground">Latency percentiles</h2>
            <PercentileGrid analytics={analytics} />
          </section>

          <section className="grid gap-4 lg:grid-cols-2">
            <DistributionCard
              title="Extraction mode"
              data={analytics.distributions.extraction_mode ?? {}}
            />
            <DistributionCard
              title="Queue class"
              data={analytics.distributions.queue_class ?? {}}
            />
            <DistributionCard
              title="Preclassification"
              data={analytics.distributions.preclassification_type ?? {}}
            />
            <DistributionCard
              title="Model strategy"
              data={analytics.distributions.model_strategy ?? {}}
            />
          </section>

          <section className="grid gap-4 sm:grid-cols-2">
            <div className="card p-4">
              <p className="eyebrow">Usage rates</p>
              <dl className="mt-3 space-y-2 text-[13px]">
                <div className="flex justify-between gap-4">
                  <dt className="text-muted-foreground">Targeted recovery</dt>
                  <dd className="tabular-nums text-foreground">
                    {formatPct(analytics.rates.targeted_recovery_usage)}
                  </dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-muted-foreground">Fallback routing</dt>
                  <dd className="tabular-nums text-foreground">
                    {formatPct(analytics.rates.fallback_usage)}
                  </dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-muted-foreground">Failure rate (5m)</dt>
                  <dd className="tabular-nums text-foreground">
                    {formatPct(metrics.failure_rate_5m)}
                  </dd>
                </div>
              </dl>
            </div>
            <div className="card p-4">
              <p className="eyebrow">SLO thresholds</p>
              <dl className="mt-3 space-y-2 text-[13px]">
                <div className="flex justify-between gap-4">
                  <dt className="text-muted-foreground">Total</dt>
                  <dd className="tabular-nums text-foreground">
                    {formatMs(analytics.slo_config.total_ms)}
                  </dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-muted-foreground">OpenAI</dt>
                  <dd className="tabular-nums text-foreground">
                    {formatMs(analytics.slo_config.openai_ms)}
                  </dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-muted-foreground">Queue wait</dt>
                  <dd className="tabular-nums text-foreground">
                    {formatMs(analytics.slo_config.queue_wait_ms)}
                  </dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-muted-foreground">Max fallback rate</dt>
                  <dd className="tabular-nums text-foreground">
                    {formatPct(analytics.slo_config.max_fallback_rate)}
                  </dd>
                </div>
              </dl>
            </div>
          </section>

          <section className="space-y-3">
            <h2 className="text-[14px] font-semibold text-foreground">Slowest recent jobs</h2>
            {slowRows.length === 0 ? (
              <p className="text-[13px] text-muted-foreground">No recent OCR timings recorded.</p>
            ) : (
              <DataTable columns={slowJobColumns} rows={slowRows} />
            )}
          </section>

          {analytics.slo_violations.length > 0 ? (
            <section className="space-y-3">
              <h2 className="text-[14px] font-semibold text-foreground">SLO violations</h2>
              <p className="text-[12px] text-muted-foreground">
                {analytics.slo_violations.length} recent job(s) exceeded configured thresholds.
              </p>
              <DataTable
                columns={slowJobColumns}
                rows={analytics.slo_violations.map((row, index) => ({
                  ...row,
                  id: index,
                }))}
              />
            </section>
          ) : null}
        </>
      ) : null}
    </div>
  );
}
