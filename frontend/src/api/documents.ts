const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

export interface DocumentUploadItem {
  document_id: number;
  filename: string;
  upload_status: string;
  mime_type?: string | null;
  file_size?: number | null;
  invoice_id?: number | null;
  error?: string | null;
}

export interface DocumentUploadResponse {
  uploaded: number;
  items: DocumentUploadItem[];
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
