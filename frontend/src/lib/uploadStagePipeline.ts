import type { InvoiceQueueStatus, UploadQueueItem } from "@/types/uploadQueue";

export interface UploadPipelineStep {
  id: InvoiceQueueStatus;
  label: string;
}

export const UPLOAD_PIPELINE_STEPS: UploadPipelineStep[] = [
  { id: "uploading", label: "Upload" },
  { id: "ocr_processing", label: "OCR" },
  { id: "validating", label: "Validate" },
  { id: "completed", label: "Done" },
];

const STAGE_RANK: Record<InvoiceQueueStatus, number> = {
  queued: 0,
  uploading: 1,
  ocr_processing: 2,
  validating: 3,
  saving: 3,
  completed: 4,
  requires_review: 4,
  failed: -1,
};

function effectiveRank(status: InvoiceQueueStatus): number {
  if (status === "requires_review") return STAGE_RANK.completed;
  return STAGE_RANK[status] ?? 0;
}

export function isPipelineStepComplete(
  item: UploadQueueItem,
  stepId: InvoiceQueueStatus,
): boolean {
  if (item.status === "failed") return false;
  const target = STAGE_RANK[stepId];
  if (target < 0) return false;
  const rank = effectiveRank(item.status);
  if (rank > target) return true;
  if (rank === target && item.status === stepId) return true;
  return item.logs.some((log) => log.stage === stepId);
}

export function isPipelineStepActive(
  item: UploadQueueItem,
  stepId: InvoiceQueueStatus,
): boolean {
  if (item.status === "failed") return false;
  return item.status === stepId;
}
