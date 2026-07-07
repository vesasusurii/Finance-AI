import { ApiError, apiFetch } from "./client";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

export interface DocumentUploadItem {
  document_id: number;
  filename: string;
  upload_status: string;
  mime_type?: string | null;
  file_size?: number | null;
  invoice_id?: number | null;
  error?: string | null;
  message?: string | null;
  original_uploader_email?: string | null;
  stage?: string | null;
  stage_label?: string | null;
  model?: string | null;
  extraction_mode?: string | null;
  pages_processed?: number | null;
  total_pdf_pages?: number | null;
  queue_wait_ms?: number | null;
  storage_download_ms?: number | null;
  download_ms?: number | null;
  text_extraction_ms?: number | null;
  document_classification_ms?: number | null;
  text_llm_ms?: number | null;
  ocr_ms?: number | null;
  render_ms?: number | null;
  rendered_image_bytes?: number | null;
  merge_ms?: number | null;
  hybrid_merge_ms?: number | null;
  field_recovery_ms?: number | null;
  validation_ms?: number | null;
  persist_ms?: number | null;
  total_ms?: number | null;
  openai_total_ms?: number | null;
  openai_call_count?: number | null;
  merge_strategy?: string | null;
  prompt_strategy?: string | null;
  image_detail_strategy?: string | null;
  render_strategy?: string | null;
  render_parallel_ms?: number | null;
  rendered_page_count?: number | null;
  estimated_prompt_tokens?: number | null;
  supplemental_text_chars?: number | null;
}

export interface DocumentUploadResponse {
  uploaded: number;
  items: DocumentUploadItem[];
}

export interface DocumentStatusResponse {
  document_id: number;
  filename: string;
  upload_status: string;
  mime_type?: string | null;
  file_size?: number | null;
  invoice_id?: number | null;
  error?: string | null;
  stage?: string | null;
  stage_label?: string | null;
  model?: string | null;
  extraction_mode?: string | null;
  pages_processed?: number | null;
  total_pdf_pages?: number | null;
  queue_wait_ms?: number | null;
  storage_download_ms?: number | null;
  download_ms?: number | null;
  text_extraction_ms?: number | null;
  document_classification_ms?: number | null;
  text_llm_ms?: number | null;
  ocr_ms?: number | null;
  render_ms?: number | null;
  rendered_image_bytes?: number | null;
  merge_ms?: number | null;
  hybrid_merge_ms?: number | null;
  field_recovery_ms?: number | null;
  validation_ms?: number | null;
  persist_ms?: number | null;
  total_ms?: number | null;
  openai_total_ms?: number | null;
  openai_call_count?: number | null;
  merge_strategy?: string | null;
  prompt_strategy?: string | null;
  image_detail_strategy?: string | null;
  render_strategy?: string | null;
  render_parallel_ms?: number | null;
  rendered_page_count?: number | null;
  estimated_prompt_tokens?: number | null;
  supplemental_text_chars?: number | null;
}

const ALLOWED_EXTENSIONS = [".pdf", ".jpg", ".jpeg", ".png", ".docx"];

const TERMINAL_UPLOAD_STATUSES = new Set([
  "processed",
  "failed",
  "linked",
  "cancelled",
]);

const POLL_TIMEOUT_MS = 5 * 60 * 1000;
const POLL_MISSING_LIMIT = 8;
const POLL_BACKOFF_MS = [2000, 4000, 8000, 15000];

export function validateClientFile(file: File): string | null {
  const name = file.name.toLowerCase();
  const ok = ALLOWED_EXTENSIONS.some((ext) => name.endsWith(ext));
  if (!ok) {
    return "Unsupported file type. Allowed: PDF, JPG, JPEG, PNG, DOCX.";
  }
  if (file.size > 20 * 1024 * 1024) {
    return "File exceeds 20 MB limit.";
  }
  return null;
}

export function isTerminalUploadStatus(status: string): boolean {
  return TERMINAL_UPLOAD_STATUSES.has(status);
}

function pollIntervalMs(pollIndex: number): number {
  return POLL_BACKOFF_MS[Math.min(pollIndex, POLL_BACKOFF_MS.length - 1)];
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

export async function getDocumentStatus(
  documentId: number,
): Promise<DocumentStatusResponse | null> {
  try {
    return await apiFetch<DocumentStatusResponse>(
      `/api/documents/${documentId}/status`,
    );
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) {
      return null;
    }
    throw e;
  }
}

export async function getDocumentStatusesBatch(
  documentIds: number[],
): Promise<DocumentStatusResponse[]> {
  if (!documentIds.length) return [];
  const uniqueIds = [...new Set(documentIds)];
  if (uniqueIds.length === 1) {
    const status = await getDocumentStatus(uniqueIds[0]);
    return status ? [status] : [];
  }
  const res = await apiFetch<{ items: DocumentStatusResponse[] }>(
    "/api/documents/batch-status",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ document_ids: uniqueIds }),
    },
  );
  return res.items;
}

function statusToUploadItem(status: DocumentStatusResponse): DocumentUploadItem {
  return {
    document_id: status.document_id,
    filename: status.filename,
    upload_status: status.upload_status,
    mime_type: status.mime_type,
    file_size: status.file_size,
    invoice_id: status.invoice_id,
    error: status.error,
    stage: status.stage,
    stage_label: status.stage_label,
    model: status.model,
    extraction_mode: status.extraction_mode,
    pages_processed: status.pages_processed,
    total_pdf_pages: status.total_pdf_pages,
    queue_wait_ms: status.queue_wait_ms,
    storage_download_ms: status.storage_download_ms,
    download_ms: status.download_ms ?? status.storage_download_ms,
    text_extraction_ms: status.text_extraction_ms,
    document_classification_ms: status.document_classification_ms,
    text_llm_ms: status.text_llm_ms,
    ocr_ms: status.ocr_ms,
    render_ms: status.render_ms,
    rendered_image_bytes: status.rendered_image_bytes,
    merge_ms: status.merge_ms,
    hybrid_merge_ms: status.hybrid_merge_ms,
    field_recovery_ms: status.field_recovery_ms,
    validation_ms: status.validation_ms,
    persist_ms: status.persist_ms,
    total_ms: status.total_ms,
    openai_total_ms: status.openai_total_ms,
    openai_call_count: status.openai_call_count,
  };
}

type WatchHandle = {
  documentId: number;
  subscriptionId: string;
  startedAt: number;
  onPoll?: (status: DocumentStatusResponse, elapsedMs: number) => void;
  resolve: (status: DocumentStatusResponse) => void;
  reject: (error: Error) => void;
  signal?: AbortSignal;
  onAbort: () => void;
};

class DocumentStatusPoller {
  private watchers = new Map<string, WatchHandle>();
  private loopPromise: Promise<void> | null = null;
  private pollIndex = 0;

  watch(
    documentId: number,
    options: {
      onPoll?: (status: DocumentStatusResponse, elapsedMs: number) => void;
      signal?: AbortSignal;
    } = {},
  ): Promise<DocumentStatusResponse> {
    return new Promise((resolve, reject) => {
      if (options.signal?.aborted) {
        reject(new Error("Extraction watch cancelled"));
        return;
      }

      const subscriptionId = `${documentId}-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
      const onAbort = () => {
        this.unsubscribe(subscriptionId);
        reject(new Error("Extraction watch cancelled"));
      };
      options.signal?.addEventListener("abort", onAbort, { once: true });

      this.watchers.set(subscriptionId, {
        documentId,
        subscriptionId,
        startedAt: Date.now(),
        onPoll: options.onPoll,
        resolve: (status) => {
          options.signal?.removeEventListener("abort", onAbort);
          resolve(status);
        },
        reject: (error) => {
          options.signal?.removeEventListener("abort", onAbort);
          reject(error);
        },
        signal: options.signal,
        onAbort,
      });
      void this.ensureLoop();
    });
  }

  private unsubscribe(subscriptionId: string) {
    const handle = this.watchers.get(subscriptionId);
    if (!handle) return;
    handle.signal?.removeEventListener("abort", handle.onAbort);
    this.watchers.delete(subscriptionId);
  }

  private ensureLoop() {
    if (!this.loopPromise) {
      this.loopPromise = this.runLoop().finally(() => {
        this.loopPromise = null;
        this.pollIndex = 0;
      });
    }
  }

  private async runLoop() {
    const missingByDoc = new Map<number, number>();

    while (this.watchers.size > 0) {
      const active = Array.from(this.watchers.values());
      for (const watcher of active) {
        if (Date.now() - watcher.startedAt >= POLL_TIMEOUT_MS) {
          this.unsubscribe(watcher.subscriptionId);
          watcher.reject(
            new Error(
              "Extraction is taking longer than expected — check Documents shortly",
            ),
          );
        }
      }
      if (this.watchers.size === 0) break;

      const documentIds = [
        ...new Set(Array.from(this.watchers.values()).map((w) => w.documentId)),
      ];

      let statuses: DocumentStatusResponse[];
      try {
        statuses = await getDocumentStatusesBatch(documentIds);
      } catch (err) {
        const error = err instanceof Error ? err : new Error(String(err));
        for (const watcher of Array.from(this.watchers.values())) {
          this.unsubscribe(watcher.subscriptionId);
          watcher.reject(error);
        }
        break;
      }

      const byId = new Map(statuses.map((status) => [status.document_id, status]));

      for (const watcher of Array.from(this.watchers.values())) {
        const status = byId.get(watcher.documentId);
        const elapsedMs = Date.now() - watcher.startedAt;
        if (status) {
          missingByDoc.set(watcher.documentId, 0);
          watcher.onPoll?.(status, elapsedMs);
          if (isTerminalUploadStatus(status.upload_status)) {
            this.unsubscribe(watcher.subscriptionId);
            watcher.resolve(status);
          }
        } else {
          const count = (missingByDoc.get(watcher.documentId) ?? 0) + 1;
          missingByDoc.set(watcher.documentId, count);
          if (count >= POLL_MISSING_LIMIT) {
            this.unsubscribe(watcher.subscriptionId);
            watcher.reject(
              new Error(
                "Could not load upload status — the file may belong to another account or no longer exists",
              ),
            );
          }
        }
      }

      if (this.watchers.size === 0) break;
      await sleep(pollIntervalMs(this.pollIndex));
      this.pollIndex += 1;
    }
  }
}

const documentStatusPoller = new DocumentStatusPoller();

/** Poll until worker finishes OCR (shared loop; one batch request for concurrent uploads). */
export async function waitForDocumentExtraction(
  documentId: number,
  options: {
    onPoll?: (status: DocumentStatusResponse, elapsedMs: number) => void;
    signal?: AbortSignal;
  } = {},
): Promise<DocumentUploadItem> {
  const status = await documentStatusPoller.watch(documentId, options);
  return statusToUploadItem(status);
}

export function uploadDocumentWithProgress(
  file: File,
  onProgress: (percent: number) => void,
): Promise<DocumentUploadResponse> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const form = new FormData();
    form.append("files", file);

    xhr.upload.addEventListener("progress", (event) => {
      if (event.lengthComputable) {
        onProgress(Math.round((event.loaded / event.total) * 100));
      }
    });

    xhr.addEventListener("load", () => {
      let body: DocumentUploadResponse & { message?: string } = {
        uploaded: 0,
        items: [],
      };
      try {
        body = JSON.parse(xhr.responseText) as typeof body;
      } catch {
        reject(new Error("Invalid server response"));
        return;
      }
      if (xhr.status < 200 || xhr.status >= 300) {
        reject(new Error(body.message ?? "Upload failed"));
        return;
      }
      resolve(body);
    });

    xhr.addEventListener("error", () => reject(new Error("Network error during upload")));
    xhr.addEventListener("abort", () => reject(new Error("Upload cancelled")));

    xhr.open("POST", `${API_BASE}/api/documents/upload`);
    xhr.withCredentials = true;
    xhr.send(form);
  });
}
