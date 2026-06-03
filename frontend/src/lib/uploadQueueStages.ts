import type { InvoiceQueueStatus } from "@/types/uploadQueue";

export const ACTIVE_STATUSES: InvoiceQueueStatus[] = [
  "queued",
  "uploading",
  "ocr_processing",
  "validating",
  "saving",
];

export const TERMINAL_STATUSES: InvoiceQueueStatus[] = [
  "completed",
  "failed",
  "requires_review",
];

export const STAGE_LABELS: Record<InvoiceQueueStatus, string> = {
  queued: "Queued",
  uploading: "Uploading",
  ocr_processing: "OCR processing",
  validating: "Validating",
  saving: "Saving",
  completed: "Completed",
  failed: "Failed",
  requires_review: "Requires review",
};

export const STAGE_PROGRESS: Record<InvoiceQueueStatus, number> = {
  queued: 0,
  uploading: 8,
  ocr_processing: 45,
  validating: 72,
  saving: 90,
  completed: 100,
  failed: 100,
  requires_review: 100,
};

export function isProcessingStatus(status: InvoiceQueueStatus): boolean {
  return ACTIVE_STATUSES.includes(status);
}

export function statusFromUploadResult(
  processingStatus: string,
  reviewStatus?: string | null,
): InvoiceQueueStatus {
  if (processingStatus === "failed") return "failed";
  if (processingStatus === "linked") return "completed";
  if (reviewStatus === "manual_review" || reviewStatus === "needs_review") {
    return "requires_review";
  }
  if (
    processingStatus === "processed" ||
    processingStatus === "queued" ||
    processingStatus === "processing" ||
    processingStatus === "saved"
  ) {
    return "completed";
  }
  return "requires_review";
}
