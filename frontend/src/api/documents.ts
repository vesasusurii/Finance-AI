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
}

const ALLOWED_EXTENSIONS = [".pdf", ".jpg", ".jpeg", ".png", ".docx"];

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

const POLL_INTERVAL_MS = 750;
const POLL_TIMEOUT_MS = 5 * 60 * 1000;
const POLL_MISSING_LIMIT = 8;

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

export async function getDocumentStatus(
  documentId: number,
): Promise<DocumentStatusResponse | null> {
  const res = await fetch(`${API_BASE}/api/documents/${documentId}/status`, {
    credentials: "include",
  });
  if (res.status === 404) {
    return null;
  }
  if (!res.ok) {
    throw new Error("Could not load document status");
  }
  return res.json() as Promise<DocumentStatusResponse>;
}

/** Poll until worker finishes OCR (does not block the upload HTTP request). */
export async function waitForDocumentExtraction(
  documentId: number,
  options: {
    onPoll?: (status: DocumentStatusResponse, elapsedMs: number) => void;
    signal?: AbortSignal;
  } = {},
): Promise<DocumentUploadItem> {
  const startedAt = Date.now();
  let missingCount = 0;
  while (Date.now() - startedAt < POLL_TIMEOUT_MS) {
    if (options.signal?.aborted) {
      throw new Error("Extraction watch cancelled");
    }
    const status = await getDocumentStatus(documentId);
    const elapsedMs = Date.now() - startedAt;
    if (status) {
      missingCount = 0;
      options.onPoll?.(status, elapsedMs);
      if (status.upload_status === "processed" || status.upload_status === "failed") {
        return {
          document_id: status.document_id,
          filename: status.filename,
          upload_status: status.upload_status,
          mime_type: status.mime_type,
          file_size: status.file_size,
          invoice_id: status.invoice_id,
          error: status.error,
        };
      }
    } else {
      missingCount += 1;
      if (missingCount >= POLL_MISSING_LIMIT) {
        throw new Error(
          "Could not load upload status — the file may belong to another account or no longer exists",
        );
      }
    }
    await sleep(POLL_INTERVAL_MS);
  }
  throw new Error("Extraction is taking longer than expected — check Documents shortly");
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
