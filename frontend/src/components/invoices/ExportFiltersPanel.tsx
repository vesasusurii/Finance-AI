import { Button } from "@/components/ui-finance/Button";
import {
  EMPTY_EXPORT_FILTERS,
  type PurchaseInvoiceExportFilters,
} from "@/types/export";

const REVIEW_OPTIONS = [
  { value: "", label: "Any review status" },
  { value: "pending", label: "Pending" },
  { value: "approved", label: "Approved" },
  { value: "needs_review", label: "Requires review" },
];

const MATCH_OPTIONS = [
  { value: "", label: "Any match status" },
  { value: "unmatched", label: "Unmatched" },
  { value: "matched", label: "Matched" },
  { value: "needs_review", label: "Needs review" },
];

const CATEGORY_OPTIONS = [
  "",
  "Professional services",
  "Utilities",
  "Software",
  "IT / Hardware",
  "Office",
  "Travel",
  "Other",
];

const fieldClass =
  "h-9 w-full rounded-md border border-input bg-background px-3 text-[13px] text-foreground focus:border-ring focus:outline-none";

export function ExportFiltersPanel({
  filters,
  onChange,
  onClear,
}: {
  filters: PurchaseInvoiceExportFilters;
  onChange: (filters: PurchaseInvoiceExportFilters) => void;
  onClear?: () => void;
}) {
  const set = (key: keyof PurchaseInvoiceExportFilters, value: string) => {
    onChange({ ...filters, [key]: value });
  };

  return (
    <div className="rounded-lg border border-border bg-card p-5">
      <div className="mb-4 flex items-start justify-between gap-4">
        <div>
          <h3 className="text-[15px] font-semibold text-foreground">
            Export filters
          </h3>
          <p className="mt-1 text-[13px] text-muted-foreground">
            Leave fields empty to include all values. Only your invoices are
            exported.
          </p>
        </div>
        {onClear && (
          <Button type="button" variant="ghost" size="sm" onClick={onClear}>
            Clear filters
          </Button>
        )}
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <label className="block">
          <span className="mb-1.5 block text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
            Invoice date from
          </span>
          <input
            type="date"
            value={filters.invoice_date_from}
            onChange={(e) => set("invoice_date_from", e.target.value)}
            className={fieldClass}
          />
        </label>
        <label className="block">
          <span className="mb-1.5 block text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
            Invoice date to
          </span>
          <input
            type="date"
            value={filters.invoice_date_to}
            onChange={(e) => set("invoice_date_to", e.target.value)}
            className={fieldClass}
          />
        </label>
        <label className="block">
          <span className="mb-1.5 block text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
            Review status
          </span>
          <select
            value={filters.review_status}
            onChange={(e) => set("review_status", e.target.value)}
            className={fieldClass}
          >
            {REVIEW_OPTIONS.map((o) => (
              <option key={o.value || "any"} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="mb-1.5 block text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
            Match status
          </span>
          <select
            value={filters.match_status}
            onChange={(e) => set("match_status", e.target.value)}
            className={fieldClass}
          >
            {MATCH_OPTIONS.map((o) => (
              <option key={o.value || "any"} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </label>
        <label className="block md:col-span-2 lg:col-span-1">
          <span className="mb-1.5 block text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
            Category
          </span>
          <select
            value={filters.category}
            onChange={(e) => set("category", e.target.value)}
            className={fieldClass}
          >
            <option value="">Any category</option>
            {CATEGORY_OPTIONS.filter(Boolean).map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </label>
      </div>
    </div>
  );
}

export { EMPTY_EXPORT_FILTERS };
