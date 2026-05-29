export type ReportPeriod = "day" | "week" | "month" | "year";

export interface CategorySummary {
  category: string;
  count: number;
  total_amount: number;
}

export interface PeriodReport {
  period: ReportPeriod;
  period_label: string;
  start_date: string;
  end_date: string;
  total_invoices: number;
  total_amount: number;
  paid_invoices: number;
  unpaid_invoices: number;
  total_paid_amount: number;
  matched_invoices: number;
  unmatched_invoices: number;
  needs_review: number;
  bank_transactions: number;
  bank_matched: number;
  bank_needs_review: number;
  by_category: CategorySummary[];
}

export interface PeriodReportParams {
  period: ReportPeriod;
  anchor_date?: string;
}

export const REPORT_PERIOD_OPTIONS: { value: ReportPeriod; label: string }[] = [
  { value: "day", label: "Daily" },
  { value: "week", label: "Weekly" },
  { value: "month", label: "Monthly" },
  { value: "year", label: "Yearly" },
];
