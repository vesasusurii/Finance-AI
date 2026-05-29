import { apiFetch } from "./client";
import type { PeriodReport, PeriodReportParams } from "../types/report";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

export async function fetchPeriodReport(
  params: PeriodReportParams,
): Promise<PeriodReport> {
  const qs = new URLSearchParams({ period: params.period });
  if (params.anchor_date) {
    qs.set("anchor_date", params.anchor_date);
  }
  return apiFetch<PeriodReport>(`/api/export/period-report?${qs}`);
}

export async function downloadPeriodReportExcel(
  params: PeriodReportParams,
): Promise<void> {
  const qs = new URLSearchParams({ period: params.period });
  if (params.anchor_date) {
    qs.set("anchor_date", params.anchor_date);
  }
  const res = await fetch(
    `${API_BASE}/api/export/period-report-excel?${qs}`,
    { credentials: "include" },
  );
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { message?: string };
    throw new Error(body.message ?? "Report download failed");
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download =
    res.headers
      .get("Content-Disposition")
      ?.match(/filename="(.+)"/)?.[1] ?? `finance_report_${params.period}.xlsx`;
  a.click();
  URL.revokeObjectURL(url);
}
