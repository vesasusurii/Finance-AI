import { formatCurrency } from "@/lib/labels";
import type { Invoice } from "@/types/invoice";

export function formatInvoiceDetailSummary(
  invoice: Invoice | null | undefined,
): string | null {
  if (!invoice) return null;

  const parts: string[] = [];
  if (invoice.name_of_company?.trim()) {
    parts.push(invoice.name_of_company.trim());
  }
  if (invoice.invoice_number?.trim()) {
    parts.push(invoice.invoice_number.trim());
  }
  if (invoice.amount != null) {
    parts.push(
      formatCurrency(Number(invoice.amount), invoice.currency ?? null),
    );
  }
  return parts.length > 0 ? parts.join(" · ") : null;
}
