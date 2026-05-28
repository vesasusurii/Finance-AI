import { cn } from "@/lib/utils";
import { STAGE_LABELS } from "@/lib/uploadQueueStages";
import type { InvoiceQueueStatus } from "@/types/uploadQueue";

const toneClass: Record<InvoiceQueueStatus, string> = {
  queued: "bg-secondary text-muted-foreground border-border",
  uploading: "bg-accent text-primary border-accent",
  ocr_processing: "bg-primary/15 text-primary border-primary/30",
  validating: "bg-accent text-primary border-accent",
  saving: "bg-accent text-primary border-accent",
  completed: "bg-[oklch(0.96_0.05_145)] text-success border-[oklch(0.88_0.08_145)]",
  requires_review: "bg-[oklch(0.97_0.06_75)] text-[oklch(0.45_0.13_60)] border-[oklch(0.9_0.08_75)]",
  failed: "bg-[oklch(0.97_0.04_27)] text-destructive border-[oklch(0.9_0.07_27)]",
};

const dotClass: Record<InvoiceQueueStatus, string> = {
  queued: "bg-muted-foreground/60",
  uploading: "bg-primary",
  ocr_processing: "bg-primary",
  validating: "bg-warning",
  saving: "bg-primary",
  completed: "bg-success",
  requires_review: "bg-warning",
  failed: "bg-destructive",
};

export function InvoiceStatusBadge({
  status,
  className,
}: {
  status: InvoiceQueueStatus;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px] font-medium",
        toneClass[status],
        className,
      )}
    >
      <span className={cn("h-1.5 w-1.5 rounded-full", dotClass[status])} />
      {STAGE_LABELS[status]}
    </span>
  );
}
