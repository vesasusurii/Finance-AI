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
  error?: string | null;
  invoice?: Invoice | null;
  logs: ProcessingLogEntry[];
  addedAt: string;
}

export interface BatchProgressStats {
  total: number;
  processing: number;
  completed: number;
  failed: number;
  requiresReview: number;
  overallProgress: number;
}
