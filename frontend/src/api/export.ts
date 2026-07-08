const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

export type PurchaseInvoicesExportParams = {
  paid_date_from?: string;
  paid_date_to?: string;
  match_status?: string;
  review_status?: string;
  category?: string;
  company?: string;
  bank_statement_id?: number;
  sort?:
    | "paid_at_date_desc"
    | "paid_at_date_asc"
    | "invoice_date_desc"
    | "invoice_date_asc";
};

export async function downloadPurchaseInvoicesExcel(
  params: PurchaseInvoicesExportParams = {},
): Promise<void> {
  const qs = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value) qs.set(key, value);
  }
  const query = qs.toString();
  const res = await fetch(
    `${API_BASE}/api/export/purchase-invoices-excel${query ? `?${query}` : ""}`,
    { credentials: "include" },
  );
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { message?: string };
    throw new Error(body.message ?? "Excel download failed");
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download =
    res.headers
      .get("Content-Disposition")
      ?.match(/filename="(.+)"/)?.[1] ??
    `purchase_invoices_export_${new Date().toISOString().slice(0, 10)}.xlsx`;
  a.click();
  URL.revokeObjectURL(url);
}
