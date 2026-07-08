import { apiFetch } from "./client";
import { inspectPdfBlob, logPdfByteReport } from "@/lib/pdfBytes";
import type {
  Invoice,
  InvoiceFilters,
  InvoiceListResponse,
  InvoiceTabCounts,
  UploadResponse,
} from "../types/invoice";
import type { MatchListResponse } from "../types/match";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

export type InvoiceFileFetchMeta = {
  invoiceId: number;
  status: number;
  contentType: string | null;
  contentDisposition: string | null;
  blobSize: number;
  blobType: string;
};

function logInvoiceFileFetch(meta: InvoiceFileFetchMeta): void {
  console.info("[invoice-file] loaded", meta);
}

function logInvoiceFileError(
  invoiceId: number,
  message: string,
  meta?: Partial<InvoiceFileFetchMeta>,
): void {
  console.error("[invoice-file] failed", { invoiceId, message, ...meta });
}

function blobFromResponse(res: Response): Promise<Blob> {
  const contentType = res.headers.get("content-type");
  return res.blob().then((blob) => {
    if (blob.type || !contentType) {
      return blob;
    }
    const baseType = contentType.split(";")[0]?.trim();
    if (!baseType) {
      return blob;
    }
    return new Blob([blob], { type: baseType });
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
export async function fetchInvoiceFile(
  invoiceId: number,
): Promise<Blob> {
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

  const headerMeta = {
    invoiceId,
    status: res.status,
    contentType: res.headers.get("content-type"),
    contentDisposition: res.headers.get("content-disposition"),
  };

  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as {
      message?: string;
    };
    logInvoiceFileError(invoiceId, body.message ?? "Could not load invoice file", {
      ...headerMeta,
      blobSize: 0,
      blobType: "",
    });
    throw new Error(body.message ?? "Could not load invoice file");
  }

  const blob = await blobFromResponse(res);
  const meta: InvoiceFileFetchMeta = {
    ...headerMeta,
    blobSize: blob.size,
    blobType: blob.type,
  };
  logInvoiceFileFetch(meta);

  if (blob.size === 0) {
    logInvoiceFileError(invoiceId, "Invoice file response was empty", meta);
    throw new Error("Invoice file is empty");
  }

  if (
    (meta.contentType ?? "").includes("pdf") ||
    blob.type.includes("pdf")
  ) {
    const report = await inspectPdfBlob(blob);
    logPdfByteReport("fetch", invoiceId, report, {
      contentType: meta.contentType,
      contentDisposition: meta.contentDisposition,
    });
    if (!report.startsWithPdf) {
      logInvoiceFileError(
        invoiceId,
        "Response is not a valid PDF (missing %PDF header)",
        meta,
      );
      throw new Error("Invoice file is not a valid PDF");
    }
  }

  return blob;
}

/** Direct URL — only works when the browser sends session cookies (e.g. Open link). */
export function invoiceFileUrl(invoiceId: number): string {
  return `${API_BASE}/api/invoices/${invoiceId}/file`;
}

/** Server-rendered JPEG for one PDF page (pypdfium2). */
export function invoiceFilePreviewPageUrl(
  invoiceId: number,
  pageNumber: number,
): string {
  return `${API_BASE}/api/invoices/${invoiceId}/file/preview/${pageNumber}`;
}

const MAX_PREVIEW_PAGES = 50;

/**
 * Fetch server-rendered JPEG pages until the API returns 404 (no more pages).
 */
export async function fetchInvoicePreviewPages(
  invoiceId: number,
): Promise<Blob[]> {
  const pages: Blob[] = [];
  for (let page = 1; page <= MAX_PREVIEW_PAGES; page++) {
    const res = await fetch(invoiceFilePreviewPageUrl(invoiceId, page), {
      credentials: "include",
    });
    if (res.status === 404) {
      break;
    }
    if (!res.ok) {
      const body = (await res.json().catch(() => ({}))) as { message?: string };
      if (page === 1) {
        throw new Error(body.message ?? "Could not render PDF preview");
      }
      break;
    }
    pages.push(await res.blob());
  }
  return pages;
}
