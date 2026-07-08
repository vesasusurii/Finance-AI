import { apiFetch } from "./client";
import type {
  Invoice,
  InvoiceFilters,
  InvoiceListResponse,
  InvoiceTabCounts,
  UploadResponse,
} from "../types/invoice";
import type { MatchListResponse } from "../types/match";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

async function refreshSessionIfNeeded(
  res: Response,
  retry: () => Promise<Response>,
): Promise<Response> {
  if (res.status !== 401) {
    return res;
  }

  const body = (await res.clone().json().catch(() => ({}))) as {
    error?: string;
  };
  if (body.error !== "token_expired" && body.error !== "invalid_token") {
    return res;
  }

  const refresh = await fetch(`${API_BASE}/api/auth/refresh`, {
    method: "POST",
    credentials: "include",
  });
  return refresh.ok ? retry() : res;
}

function blobFromResponse(res: Response): Promise<Blob> {
  const contentType = res.headers.get("content-type");
  return res.blob().then((blob) => {
    if (blob.type || !contentType) {
      return blob;
    }
    const baseType = contentType.split(";")[0]?.trim();
    return baseType ? new Blob([blob], { type: baseType }) : blob;
  });
}

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

export async function getInvoiceTabCounts(
  search?: string,
): Promise<InvoiceTabCounts> {
  const params = new URLSearchParams();
  if (search) {
    params.set("search", search);
  }
  const qs = params.toString();
  return apiFetch<InvoiceTabCounts>(
    `/api/invoices/tab-counts${qs ? `?${qs}` : ""}`,
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

  const res = await refreshSessionIfNeeded(await doFetch(), doFetch);

  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as {
      message?: string;
    };
    throw new Error(body.message ?? "Could not load invoice file");
  }

  return blobFromResponse(res);
}

/** Direct URL — only works when the browser sends session cookies (e.g. Open link). */
export function invoiceFileUrl(invoiceId: number): string {
  return `${API_BASE}/api/invoices/${invoiceId}/file`;
}

export type InvoicePdfPreviewPage = {
  blob: Blob;
  pageCount: number;
  pageNumber: number;
};

export type InvoicePdfPreviewBatchPage = {
  pageNumber: number;
  contentType: "image/jpeg";
  dataBase64: string;
};

export type InvoicePdfPreviewBatch = {
  pageCount: number;
  pages: InvoicePdfPreviewBatchPage[];
};

export async function fetchInvoicePdfPreview(
  invoiceId: number,
): Promise<InvoicePdfPreviewBatch> {
  const path = `/api/invoices/${invoiceId}/file/preview`;
  const doFetch = () =>
    fetch(`${API_BASE}${path}`, { credentials: "include" });

  const res = await refreshSessionIfNeeded(await doFetch(), doFetch);
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as {
      message?: string;
    };
    throw new Error(body.message ?? "Could not render PDF preview");
  }

  return res.json() as Promise<InvoicePdfPreviewBatch>;
}

export async function fetchInvoicePdfPreviewPage(
  invoiceId: number,
  pageNumber: number,
): Promise<InvoicePdfPreviewPage> {
  const path = `/api/invoices/${invoiceId}/file/preview/${pageNumber}`;
  const doFetch = () =>
    fetch(`${API_BASE}${path}`, { credentials: "include" });

  const res = await refreshSessionIfNeeded(await doFetch(), doFetch);
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as {
      message?: string;
    };
    throw new Error(body.message ?? "Could not render PDF preview");
  }

  const blob = await blobFromResponse(res);
  const headerPageCount = Number(res.headers.get("x-pdf-page-count"));
  const headerPageNumber = Number(res.headers.get("x-pdf-page-number"));

  return {
    blob: blob.type ? blob : new Blob([blob], { type: "image/jpeg" }),
    pageCount:
      Number.isFinite(headerPageCount) && headerPageCount > 0
        ? headerPageCount
        : pageNumber,
    pageNumber:
      Number.isFinite(headerPageNumber) && headerPageNumber > 0
        ? headerPageNumber
        : pageNumber,
  };
}
