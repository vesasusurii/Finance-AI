import { useCallback, useEffect, useState } from "react";
import { Download, RefreshCw } from "lucide-react";
import { LoadingSpinner } from "@/components/LoadingSpinner";
import { Button } from "@/components/ui-finance/Button";
import { DataTable, type Column } from "@/components/ui-finance/DataTable";
import { DateTextInput } from "@/components/ui-finance/DateTextInput";
import { fetchPeriodReport, downloadPeriodReportExcel } from "@/api/export";
import type { CategorySummary, PeriodReport, ReportPeriod } from "@/types/report";
import { REPORT_PERIOD_OPTIONS } from "@/types/report";
import { formatCurrency, formatDate, isoDateFromInput } from "@/lib/labels";

function todayDisplay(): string {
  return formatDate(new Date().toISOString().slice(0, 10));
}

export function PeriodReportPanel() {
  const [period, setPeriod] = useState<ReportPeriod>("month");
  const [anchorDateInput, setAnchorDateInput] = useState(todayDisplay);
  const [report, setReport] = useState<PeriodReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const anchorDateIso = isoDateFromInput(anchorDateInput);

  const loadReport = useCallback(async () => {
    if (!anchorDateIso) {
      setError("Reference date must be dd/mm/yyyy");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await fetchPeriodReport({
        period,
        anchor_date: anchorDateIso,
      });
      setReport(data);
    } catch (e) {
      setReport(null);
      setError(e instanceof Error ? e.message : "Could not load report");
    } finally {
      setLoading(false);
    }
  }, [period, anchorDateIso]);

  useEffect(() => {
    if (!anchorDateIso) return;
    void loadReport();
  }, [loadReport, anchorDateIso]);

  async function handleDownload() {
    if (!anchorDateIso) {
      setError("Reference date must be dd/mm/yyyy");
      return;
    }
    setDownloading(true);
    setError(null);
    try {
      await downloadPeriodReportExcel({ period, anchor_date: anchorDateIso });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Download failed");
    } finally {
      setDownloading(false);
    }
  }

  const categoryColumns: Column<CategorySummary>[] = [
    {
      key: "category",
      header: "Category",
      cell: (r) => r.category,
    },
    {
      key: "count",
      header: "Invoices",
      cell: (r) => <span className="tabular-nums">{r.count}</span>,
    },
    {
      key: "amount",
      header: "Total amount",
      cell: (r) => (
        <span className="tabular-nums">
          {formatCurrency(r.total_amount, "EUR")}
        </span>
      ),
    },
  ];

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <label className="space-y-1">
          <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
            Period
          </span>
          <select
            value={period}
            onChange={(e) => setPeriod(e.target.value as ReportPeriod)}
            className="block h-9 min-w-[140px] rounded-md border border-input bg-background px-2 text-[13px]"
          >
            {REPORT_PERIOD_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </label>

        <label className="space-y-1">
          <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
            Reference date
          </span>
          <DateTextInput
            value={anchorDateInput}
            onChange={setAnchorDateInput}
          />
        </label>

        <Button
          variant="ghost"
          size="sm"
          icon={
            loading ? (
              <LoadingSpinner size="sm" />
            ) : (
              <RefreshCw className="h-3.5 w-3.5" />
            )
          }
          disabled={loading}
          onClick={() => void loadReport()}
        >
          Refresh
        </Button>

        <Button
          variant="primary"
          size="sm"
          icon={
            downloading ? (
              <LoadingSpinner size="sm" />
            ) : (
              <Download className="h-3.5 w-3.5" />
            )
          }
          disabled={downloading || loading}
          onClick={() => void handleDownload()}
        >
          Download report Excel
        </Button>
      </div>

      {error && (
        <p className="text-[13px] text-destructive" role="alert">
          {error}
        </p>
      )}

      {report && (
        <>
          <div className="rounded-lg border border-border bg-surface-muted/40 px-4 py-3">
            <p className="text-[14px] font-semibold text-foreground">
              {report.period_label}
            </p>
            <p className="mt-1 text-[12px] text-muted-foreground">
              <span className="tabular-nums">
                {formatDate(report.start_date)} – {formatDate(report.end_date)}
              </span>
              {" · "}
              Invoice date basis
            </p>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <MetricCard
              label="Total invoices"
              value={String(report.total_invoices)}
              detail={formatCurrency(report.total_amount, "EUR")}
            />
            <MetricCard
              label="Paid"
              value={String(report.paid_invoices)}
              detail={formatCurrency(report.total_paid_amount, "EUR")}
            />
            <MetricCard
              label="Matched"
              value={String(report.matched_invoices)}
              detail={`${report.unmatched_invoices} unmatched`}
            />
            <MetricCard
              label="Needs review"
              value={String(report.needs_review)}
              detail={`${report.bank_needs_review} bank lines`}
            />
          </div>

          <div className="grid gap-3 sm:grid-cols-3">
            <MetricCard
              label="Unpaid invoices"
              value={String(report.unpaid_invoices)}
            />
            <MetricCard
              label="Bank transactions"
              value={String(report.bank_transactions)}
              detail={`${report.bank_matched} matched`}
            />
            <MetricCard
              label="Bank needs review"
              value={String(report.bank_needs_review)}
            />
          </div>

          <div className="space-y-2">
            <h3 className="text-[13px] font-semibold text-foreground">
              By category
            </h3>
            <DataTable
              columns={categoryColumns}
              rows={report.by_category.map((row, i) => ({
                ...row,
                id: `${row.category}-${i}`,
              }))}
              empty="No invoices in this period."
            />
          </div>
        </>
      )}
    </section>
  );
}

function MetricCard({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail?: string;
}) {
  return (
    <div className="rounded-lg border border-border px-4 py-3">
      <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
        {label}
      </p>
      <p className="mt-1 text-[20px] font-semibold tabular-nums text-foreground">
        {value}
      </p>
      {detail ? (
        <p className="mt-0.5 text-[12px] text-muted-foreground">{detail}</p>
      ) : null}
    </div>
  );
}
