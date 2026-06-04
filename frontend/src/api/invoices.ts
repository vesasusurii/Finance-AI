import { apiFetch } from "./client";
import type {
  Invoice,
  InvoiceFilters,
  InvoiceListResponse,
  UploadResponse,
} from "../types/invoice";
import type { MatchListResponse } from "../types/match";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

export async function uploadInvoices(files: File[]): Promise<UploadResponse> {
  const form = new FormData();
  files.forEach((f) => form.append("files", f));
  return apiFetch<UploadResponse>("/api/invoices/upload", {
    method: "POST",
    body: form,
  });
}

export async function getInvoice(id: number): Promise<Invoice> {
  return apiFetch<Invoice>(`/api/invoices/${id}`);
}

export async function getInvoiceMatches(
  invoiceId: number,
): Promise<MatchListResponse> {
  return apiFetch<MatchListResponse>(`/api/invoices/${invoiceId}/matches`);
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
 * Fetch invoice source file with session cookies (for preview blob URLs).
 */
export async function fetchInvoiceFile(invoiceId: number): Promise<Blob> {
  const path = `/api/invoices/${invoiceId}/file`;
  const doFetch = () =>
    fetch(`${API_BASE}${path}`, { credentials: "include" });

  let res = await doFetch();

  if (res.status === 401) {
    const body = (await res.clone().json().catch(() => ({}))) as {
      error?: string;
    };
    if (body.error === "token_expired" || body.error === "invalid_token") {
      const refresh = await fetch(`${API_BASE}/api/auth/refresh`, {
        method: "POST",
        credentials: "include",
      });
      if (refresh.ok) {
        res = await doFetch();
      }
    }
  }

  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as {
      message?: string;
    };
    throw new Error(body.message ?? "Could not load invoice file");
  }

  return res.blob();
}

/** Direct URL — only works when the browser sends session cookies (e.g. Open link). */
export function invoiceFileUrl(invoiceId: number): string {
  return `${API_BASE}/api/invoices/${invoiceId}/file`;
}
