import { useState } from "react";
import { Download } from "lucide-react";
import { LoadingSpinner } from "@/components/LoadingSpinner";
import { Button } from "@/components/ui-finance/Button";
import { DateTextInput } from "@/components/ui-finance/DateTextInput";
import {
  downloadPurchaseInvoicesExcel,
  type PurchaseInvoicesExportParams,
} from "@/api/export";
import { isoDateFromInput } from "@/lib/labels";

const MATCH_STATUSES = [
  { value: "", label: "Any match status" },
  { value: "unmatched", label: "Unmatched" },
  { value: "partially_matched", label: "Partially paid" },
  { value: "matched", label: "Matched" },
  { value: "needs_review", label: "Needs review" },
];

const REVIEW_STATUSES = [
  { value: "", label: "Any review status" },
  { value: "pending", label: "Pending" },
  { value: "needs_review", label: "Needs review" },
  { value: "approved", label: "Approved" },
  { value: "manual_review", label: "Manual review" },
];

const CATEGORIES = [
  "",
  "Professional services",
  "Utilities",
  "Software",
  "IT / Hardware",
  "Office",
  "Travel",
  "Other",
];

export function PurchaseInvoicesExportPanel() {
  const [invoiceDateFrom, setInvoiceDateFrom] = useState("");
  const [invoiceDateTo, setInvoiceDateTo] = useState("");
  const [matchStatus, setMatchStatus] = useState("");
  const [reviewStatus, setReviewStatus] = useState("");
  const [category, setCategory] = useState("");
  const [company, setCompany] = useState("");
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleDownload() {
    setDownloading(true);
    setError(null);
    const dateFromIso = invoiceDateFrom.trim()
      ? isoDateFromInput(invoiceDateFrom)
      : null;
    const dateToIso = invoiceDateTo.trim()
      ? isoDateFromInput(invoiceDateTo)
      : null;
    if (invoiceDateFrom.trim() && !dateFromIso) {
      setError("Invoice date from must be dd/mm/yyyy");
      setDownloading(false);
      return;
    }
    if (invoiceDateTo.trim() && !dateToIso) {
      setError("Invoice date to must be dd/mm/yyyy");
      setDownloading(false);
      return;
    }
    const params: PurchaseInvoicesExportParams = {};
    if (dateFromIso) params.invoice_date_from = dateFromIso;
    if (dateToIso) params.invoice_date_to = dateToIso;
    if (matchStatus) params.match_status = matchStatus;
    if (reviewStatus) params.review_status = reviewStatus;
    if (category) params.category = category;
    if (company.trim()) params.company = company.trim();

    try {
      await downloadPurchaseInvoicesExcel(params);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Export failed");
    } finally {
      setDownloading(false);
    }
  }

  return (
    <section className="card space-y-4 p-5">
      <div>
        <h2 className="text-[14px] font-semibold text-foreground">
          Purchase invoices export
        </h2>
        <p className="mt-1 text-[12px] text-muted-foreground">
          Filter the 12-column Finance Excel export before download.
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <label className="space-y-1">
          <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
            Invoice date from
          </span>
          <DateTextInput
            value={invoiceDateFrom}
            onChange={setInvoiceDateFrom}
          />
        </label>
        <label className="space-y-1">
          <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
            Invoice date to
          </span>
          <DateTextInput
            value={invoiceDateTo}
            onChange={setInvoiceDateTo}
          />
        </label>
        <label className="space-y-1">
          <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
            Company / vendor
          </span>
          <input
            type="text"
            value={company}
            onChange={(e) => setCompany(e.target.value)}
            placeholder="Search supplier name"
            className="block h-9 w-full rounded-md border border-input bg-background px-2 text-[13px]"
          />
        </label>
        <label className="space-y-1">
          <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
            Match status
          </span>
          <select
            value={matchStatus}
            onChange={(e) => setMatchStatus(e.target.value)}
            className="block h-9 w-full rounded-md border border-input bg-background px-2 text-[13px]"
          >
            {MATCH_STATUSES.map((opt) => (
              <option key={opt.value || "any"} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </label>
        <label className="space-y-1">
          <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
            Review status
          </span>
          <select
            value={reviewStatus}
            onChange={(e) => setReviewStatus(e.target.value)}
            className="block h-9 w-full rounded-md border border-input bg-background px-2 text-[13px]"
          >
            {REVIEW_STATUSES.map((opt) => (
              <option key={opt.value || "any"} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </label>
        <label className="space-y-1">
          <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
            Category
          </span>
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="block h-9 w-full rounded-md border border-input bg-background px-2 text-[13px]"
          >
            <option value="">Any category</option>
            {CATEGORIES.filter(Boolean).map((cat) => (
              <option key={cat} value={cat}>
                {cat}
              </option>
            ))}
          </select>
        </label>
      </div>

      {error ? (
        <p className="text-[13px] text-destructive" role="alert">
          {error}
        </p>
      ) : null}

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
        disabled={downloading}
        onClick={() => void handleDownload()}
      >
        {downloading ? "Preparing export…" : "Download filtered Excel"}
      </Button>
    </section>
  );
}
