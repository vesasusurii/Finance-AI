import { cn } from "@/lib/utils";
import { STAGE_LABELS } from "@/lib/uploadQueueStages";
import type { InvoiceQueueStatus } from "@/types/uploadQueue";

const toneClass: Record<InvoiceQueueStatus, string> = {
  queued: "bg-secondary text-muted-foreground border-border",
  uploading: "bg-accent text-primary border-accent",
  ocr_processing: "bg-primary/15 text-primary border-primary/30",
  validating: "bg-accent text-primary border-accent",
  saving: "bg-accent text-primary border-accent",
  completed: "bg-success/15 text-success border-success/30 dark:bg-success/20 dark:border-success/40",
  requires_review: "bg-warning/15 text-warning border-warning/30 dark:bg-warning/20 dark:border-warning/40",
  failed: "bg-destructive/15 text-destructive border-destructive/30 dark:bg-destructive/20 dark:border-destructive/40",
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
