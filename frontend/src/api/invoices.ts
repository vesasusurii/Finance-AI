import { apiFetch } from "./client";
import type {
  Invoice,
  InvoiceFilters,
  InvoiceListResponse,
  UploadResponse,
} from "../types/invoice";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

export async function uploadInvoices(files: File[]): Promise<UploadResponse> {
  const form = new FormData();
  files.forEach((f) => form.append("files", f));
  return apiFetch<UploadResponse>("/api/invoices/upload", {
    method: "POST",
    body: form,
  });
}

export async function listInvoices(
  filters: InvoiceFilters = {},
): Promise<InvoiceListResponse> {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== "") {
      params.set(key, String(value));
    }
  });
  const qs = params.toString();
  return apiFetch<InvoiceListResponse>(
    `/api/invoices${qs ? `?${qs}` : ""}`,
  );
}

export async function updateInvoice(
  id: number,
  data: Partial<Invoice>,
): Promise<Invoice> {
  const {
    paid_at_date: _paidAtDate, // system-only — bank matching sets this later
    extraction_confidence: _c,
    match_status: _m,
    review_status: _r,
    id: _id,
    source_file_id: _s,
    source_filename: _sf,
    source_mime_type: _sm,
    created_at: _ca,
    updated_at: _ua,
    ...writable
  } = data;
  return apiFetch<Invoice>(`/api/invoices/${id}`, {
    method: "PUT",
    body: JSON.stringify(writable),
  });
}

export async function approveInvoice(
  id: number,
): Promise<{ id: number; review_status: string }> {
  return apiFetch(`/api/invoices/${id}/approve`, { method: "POST" });
}

export async function deleteInvoice(id: number): Promise<void> {
  return apiFetch(`/api/invoices/${id}`, { method: "DELETE" });
}

/**
 * Authenticated URL for inline document preview (PDF / JPEG / PNG).
 * Uses GET only — do not probe with HEAD (not supported by the dev proxy).
 */
export function invoiceFileUrl(invoiceId: number): string {
  return `${API_BASE}/api/invoices/${invoiceId}/file`;
}
