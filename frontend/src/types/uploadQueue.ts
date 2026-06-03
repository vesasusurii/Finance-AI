import type { Invoice } from "./invoice";

export type InvoiceQueueStatus =
  | "queued"
  | "uploading"
  | "ocr_processing"
  | "validating"
  | "saving"
  | "completed"
  | "failed"
  | "requires_review";

export interface ProcessingLogEntry {
  at: string;
  stage: InvoiceQueueStatus;
  message: string;
}

export interface UploadQueueItem {
  id: string;
  file: File;
  fileName: string;
  status: InvoiceQueueStatus;
  progress: number;
  stageLabel: string;
  uploadId?: number;
  invoiceId?: number | null;
  confidence?: number | null;
  /** Short summary for the queue table Details column. */
  detailSummary?: string | null;
  error?: string | null;
  /** Success info when the file was already uploaded by another user (linked). */
  infoMessage?: string | null;
  invoice?: Invoice | null;
  logs: ProcessingLogEntry[];
  addedAt: string;
}
