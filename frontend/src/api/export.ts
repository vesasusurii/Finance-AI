const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

export async function downloadPurchaseInvoicesExcel(
  filters: Record<string, string> = {},
): Promise<void> {
  const params = new URLSearchParams(filters);
  const qs = params.toString();
  const res = await fetch(
    `${API_BASE}/api/export/purchase-invoices-excel${qs ? `?${qs}` : ""}`,
    { credentials: "include" },
  );
  if (!res.ok) {
    throw new Error("Export failed");
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download =
    res.headers
      .get("Content-Disposition")
      ?.match(/filename="(.+)"/)?.[1] ?? "purchase_invoices_export.xlsx";
  a.click();
  URL.revokeObjectURL(url);
}
