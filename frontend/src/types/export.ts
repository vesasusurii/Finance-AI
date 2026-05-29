export interface PurchaseInvoiceExportFilters {
  invoice_date_from: string;
  invoice_date_to: string;
  match_status: string;
  review_status: string;
  category: string;
}

export const EMPTY_EXPORT_FILTERS: PurchaseInvoiceExportFilters = {
  invoice_date_from: "",
  invoice_date_to: "",
  match_status: "",
  review_status: "",
  category: "",
};

export function exportFiltersToParams(
  filters: PurchaseInvoiceExportFilters,
): Record<string, string> {
  const params: Record<string, string> = {};
  if (filters.invoice_date_from) {
    params.invoice_date_from = filters.invoice_date_from;
  }
  if (filters.invoice_date_to) {
    params.invoice_date_to = filters.invoice_date_to;
  }
  if (filters.match_status) {
    params.match_status = filters.match_status;
  }
  if (filters.review_status) {
    params.review_status = filters.review_status;
  }
  if (filters.category.trim()) {
    params.category = filters.category.trim();
  }
  return params;
}

export function hasActiveExportFilters(
  filters: PurchaseInvoiceExportFilters,
): boolean {
  return Object.values(filters).some((v) => v.trim() !== "");
}
