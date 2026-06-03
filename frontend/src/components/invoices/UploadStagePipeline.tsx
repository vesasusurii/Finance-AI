import { cn } from "@/lib/utils";
import {
  isPipelineStepActive,
  isPipelineStepComplete,
  UPLOAD_PIPELINE_STEPS,
} from "@/lib/uploadStagePipeline";
import type { UploadQueueItem } from "@/types/uploadQueue";

export function UploadStagePipeline({ item }: { item: UploadQueueItem }) {
  return (
    <ol className="flex flex-wrap items-center gap-1">
      {UPLOAD_PIPELINE_STEPS.map((step, index) => {
        const done = isPipelineStepComplete(item, step.id);
        const active = isPipelineStepActive(item, step.id);
        return (
          <li key={step.id} className="flex items-center gap-1">
            {index > 0 && (
              <span
                className={cn(
                  "text-[10px]",
                  done ? "text-primary" : "text-muted-foreground/50",
                )}
                aria-hidden
              >
                →
              </span>
            )}
            <span
              className={cn(
                "rounded px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide",
                done && "bg-primary/15 text-primary",
                active && !done && "bg-accent text-accent-foreground",
                !done && !active && "text-muted-foreground",
              )}
            >
              {step.label}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
