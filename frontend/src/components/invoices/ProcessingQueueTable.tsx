import { Eye, FileText, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui-finance/Button";
import { ConfidenceIndicator } from "@/components/ui-finance/ConfidenceIndicator";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";
import { isProcessingStatus } from "@/lib/uploadQueueStages";
import type { UploadQueueItem } from "@/types/uploadQueue";
import { InvoiceStatusBadge } from "./InvoiceStatusBadge";
import { UploadStagePipeline } from "./UploadStagePipeline";

function detailsCell(item: UploadQueueItem): string {
  if (item.error) return item.error;
  if (item.infoMessage) return item.infoMessage;
  if (item.detailSummary) return item.detailSummary;
  if (item.status === "ocr_processing" || item.status === "validating") {
    return "Extracting invoice fields…";
  }
  if (item.status === "uploading") return "Saving to storage…";
  if (item.status === "completed" || item.status === "requires_review") {
    return "Open View for full extraction";
  }
  return "—";
}

export function ProcessingQueueTable({
  items,
  onView,
  onRetry,
}: {
  items: UploadQueueItem[];
  onView: (item: UploadQueueItem) => void;
  onRetry: (item: UploadQueueItem) => void;
}) {
  if (items.length === 0) {
    return (
      <p className="text-[13px] text-muted-foreground">
        No uploads in this session yet. Files you upload will appear here with
        live extraction progress.
      </p>
    );
  }

  return (
    <div className="overflow-hidden rounded-lg border border-border bg-card">
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-[13px]">
          <thead>
            <tr className="border-b border-border bg-surface-muted">
              <th className="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                File
              </th>
              <th className="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                Status
              </th>
              <th className="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                Progress
              </th>
              <th className="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                Stages
              </th>
              <th className="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                Confidence
              </th>
              <th className="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                Details
              </th>
              <th className="px-4 py-2.5 text-right text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                Actions
              </th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr
                key={item.id}
                className={cn(
                  "border-b border-border transition-colors last:border-0",
                  isProcessingStatus(item.status) && "bg-accent/20",
                )}
              >
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2.5">
                    <div className="grid h-8 w-8 place-items-center rounded-md border border-border bg-surface-muted">
                      <FileText className="h-3.5 w-3.5 text-muted-foreground" />
                    </div>
                    <div>
                      <div className="font-medium text-foreground">{item.fileName}</div>
                      {item.invoiceId != null && (
                        <div className="text-[11px] text-muted-foreground">
                          Invoice #{item.invoiceId}
                        </div>
                      )}
                    </div>
                  </div>
                </td>
                <td className="px-4 py-3">
                  <InvoiceStatusBadge status={item.status} />
                </td>
                <td className="px-4 py-3">
                  <div className="min-w-[140px]">
                    <div className="mb-1 flex items-center justify-between text-[11px] text-muted-foreground">
                      <span>{item.stageLabel}</span>
                      <span className="tabular-nums">{item.progress}%</span>
                    </div>
                    <Progress value={item.progress} className="h-1.5" />
                  </div>
                </td>
                <td className="px-4 py-3">
                  <UploadStagePipeline item={item} />
                </td>
                <td className="px-4 py-3">
                  {item.confidence != null ? (
                    <ConfidenceIndicator value={item.confidence} />
                  ) : item.status === "ocr_processing" ||
                    item.status === "validating" ? (
                    <span className="text-[12px] text-muted-foreground">Pending</span>
                  ) : (
                    <span className="text-[12px] text-muted-foreground">—</span>
                  )}
                </td>
                <td className="max-w-[220px] px-4 py-3">
                  <span
                    className={cn(
                      "line-clamp-2 text-[12px]",
                      item.error
                        ? "text-destructive"
                        : item.infoMessage
                          ? "text-primary"
                          : "text-foreground",
                    )}
                  >
                    {detailsCell(item)}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center justify-end gap-1">
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      icon={<Eye className="h-3.5 w-3.5" />}
                      onClick={() => onView(item)}
                      disabled={item.status === "queued"}
                    >
                      View
                    </Button>
                    {item.status === "failed" && (
                      <Button
                        type="button"
                        variant="secondary"
                        size="sm"
                        icon={<RotateCcw className="h-3.5 w-3.5" />}
                        onClick={() => onRetry(item)}
                      >
                        Retry
                      </Button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
