import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { getInvoice } from "@/api/invoices";
import {
  pollDocumentUntilDone,
  uploadDocumentWithProgress,
  validateClientFile,
  type DocumentUploadItem,
} from "@/api/documents";
import {
  MOCK_PIPELINE,
  STAGE_LABELS,
  STAGE_PROGRESS,
  isProcessingStatus,
  statusFromUploadResult,
} from "@/lib/uploadQueueStages";
import { uploadProgressEvents } from "@/services/uploadProgressEvents";
import type {
  ProcessingLogEntry,
  UploadQueueItem,
  InvoiceQueueStatus,
} from "@/types/uploadQueue";

const MAX_CONCURRENT = 4;
const STAGE_INTERVAL_MS = 900;

function createId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

function logEntry(
  stage: InvoiceQueueStatus,
  message: string,
): ProcessingLogEntry {
  return { at: new Date().toISOString(), stage, message };
}

function finalStatusFromDocumentResult(
  result: DocumentUploadItem,
  reviewStatus?: string | null,
): { status: InvoiceQueueStatus; stageLabel: string } {
  if (result.upload_status === "failed" || result.error) {
    return { status: "failed", stageLabel: STAGE_LABELS.failed };
  }
  if (result.upload_status === "pending") {
    return {
      status: "completed",
      stageLabel: "Stored — awaiting OCR",
    };
  }
  if (result.upload_status === "processing") {
    return {
      status: "ocr_processing",
      stageLabel: STAGE_LABELS.ocr_processing,
    };
  }
  const status = statusFromUploadResult(result.upload_status, reviewStatus);
  return { status, stageLabel: STAGE_LABELS[status] };
}

export function useUploadQueue() {
  const [items, setItems] = useState<UploadQueueItem[]>([]);
  const [activeWorkers, setActiveWorkers] = useState(0);
  const itemsRef = useRef(items);
  const pendingRef = useRef<string[]>([]);
  const activeWorkersRef = useRef(0);

  useEffect(() => {
    itemsRef.current = items;
  }, [items]);

  const patchItem = useCallback(
    (id: string, patch: Partial<UploadQueueItem>) => {
      setItems((prev) => {
        const next = prev.map((item) => {
          if (item.id !== id) return item;
          const updated = { ...item, ...patch };
          uploadProgressEvents.emit({
            itemId: id,
            status: updated.status,
            progress: updated.progress,
            stageLabel: updated.stageLabel,
            error: updated.error,
            uploadId: updated.uploadId,
            invoiceId: updated.invoiceId,
            confidence: updated.confidence,
          });
          return updated;
        });
        itemsRef.current = next;
        return next;
      });
    },
    [],
  );

  const appendLog = useCallback(
    (id: string, stage: InvoiceQueueStatus, message: string) => {
      setItems((prev) => {
        const next = prev.map((item) =>
          item.id === id
            ? { ...item, logs: [...item.logs, logEntry(stage, message)] }
            : item,
        );
        itemsRef.current = next;
        return next;
      });
    },
    [],
  );

  const processOne = useCallback(
    async (item: UploadQueueItem) => {
      const clientError = validateClientFile(item.file);
      if (clientError) {
        patchItem(item.id, {
          status: "failed",
          progress: 100,
          stageLabel: STAGE_LABELS.failed,
          error: clientError,
        });
        appendLog(item.id, "failed", clientError);
        return;
      }

      let stageIndex = 0;
      let cancelled = false;

      const advanceStage = () => {
        if (cancelled || stageIndex >= MOCK_PIPELINE.length) return;
        const stage = MOCK_PIPELINE[stageIndex];
        stageIndex += 1;
        patchItem(item.id, {
          status: stage,
          progress: STAGE_PROGRESS[stage],
          stageLabel: STAGE_LABELS[stage],
        });
        appendLog(item.id, stage, STAGE_LABELS[stage]);
      };

      patchItem(item.id, {
        status: "uploading",
        progress: STAGE_PROGRESS.uploading,
        stageLabel: STAGE_LABELS.uploading,
      });
      appendLog(item.id, "uploading", "Sending file to storage");

      const timer = window.setInterval(advanceStage, STAGE_INTERVAL_MS);

      try {
        const res = await uploadDocumentWithProgress(item.file, (pct) => {
          const uploadProgress = Math.min(
            90,
            STAGE_PROGRESS.uploading +
              Math.round((pct / 100) * (STAGE_PROGRESS.saving - STAGE_PROGRESS.uploading)),
          );
          patchItem(item.id, {
            progress: uploadProgress,
            stageLabel: pct < 100 ? `Uploading ${pct}%` : STAGE_LABELS.saving,
          });
        });

        let result = res.items[0];
        if (!result) {
          throw new Error("No upload result returned");
        }

        if (result.upload_status === "processing" && result.document_id) {
          patchItem(item.id, {
            status: "ocr_processing",
            progress: STAGE_PROGRESS.ocr_processing,
            stageLabel: STAGE_LABELS.ocr_processing,
            uploadId: result.document_id,
          });
          appendLog(item.id, "ocr_processing", "File stored — running OCR");
          result = await pollDocumentUntilDone(result.document_id);
        }

        let invoice = null;
        let getInvoiceError: string | null = null;
        if (result.invoice_id) {
          try {
            invoice = await getInvoice(result.invoice_id);
          } catch (err) {
            getInvoiceError =
              err instanceof Error ? err.message : "Could not load invoice";
          }
        }

        const { status: finalStatus, stageLabel } = finalStatusFromDocumentResult(
          result,
          invoice?.review_status,
        );

        const isLinked = result.upload_status === "linked";
        const detailError =
          result.error ??
          getInvoiceError ??
          (result.upload_status === "failed" ? "Processing failed" : null);
        const infoMessage = isLinked ? result.message ?? null : null;

        patchItem(item.id, {
          status:
            getInvoiceError && result.upload_status === "processed"
              ? "requires_review"
              : finalStatus,
          progress: 100,
          stageLabel: isLinked
            ? "Already in system"
            : getInvoiceError && result.upload_status === "processed"
              ? STAGE_LABELS.requires_review
              : stageLabel,
          uploadId: result.document_id || undefined,
          invoiceId: result.invoice_id ?? null,
          confidence: invoice?.extraction_confidence ?? null,
          error: detailError,
          infoMessage,
          invoice,
        });

        appendLog(
          item.id,
          finalStatus,
          infoMessage ?? detailError ?? stageLabel,
        );
      } catch (err) {
        const message = err instanceof Error ? err.message : "Upload failed";
        patchItem(item.id, {
          status: "failed",
          progress: 100,
          stageLabel: STAGE_LABELS.failed,
          error: message,
        });
        appendLog(item.id, "failed", message);
      } finally {
        cancelled = true;
        window.clearInterval(timer);
      }
    },
    [appendLog, patchItem],
  );

  const schedule = useCallback(() => {
    while (
      activeWorkersRef.current < MAX_CONCURRENT &&
      pendingRef.current.length > 0
    ) {
      const id = pendingRef.current[0];
      if (!id) break;

      const item = itemsRef.current.find((i) => i.id === id);
      if (!item) {
        pendingRef.current.shift();
        continue;
      }

      pendingRef.current.shift();
      activeWorkersRef.current += 1;
      setActiveWorkers(activeWorkersRef.current);

      void processOne(item).finally(() => {
        activeWorkersRef.current -= 1;
        setActiveWorkers(activeWorkersRef.current);
        schedule();
      });
    }
  }, [processOne]);

  const enqueueFiles = useCallback(
    (files: FileList | File[]) => {
      const list = Array.from(files);
      if (!list.length) return;

      const queued: UploadQueueItem[] = list.map((file) => ({
        id: createId(),
        file,
        fileName: file.name,
        status: "queued",
        progress: STAGE_PROGRESS.queued,
        stageLabel: STAGE_LABELS.queued,
        logs: [logEntry("queued", "Waiting in batch queue")],
        addedAt: new Date().toISOString(),
      }));

      pendingRef.current.push(...queued.map((item) => item.id));
      const next = [...queued, ...itemsRef.current];
      itemsRef.current = next;
      setItems(next);
      schedule();
    },
    [schedule],
  );

  const retryItem = useCallback(
    (id: string) => {
      const item = itemsRef.current.find((i) => i.id === id);
      if (!item) return;
      patchItem(id, {
        status: "queued",
        progress: STAGE_PROGRESS.queued,
        stageLabel: STAGE_LABELS.queued,
        error: null,
        uploadId: undefined,
        invoiceId: null,
        confidence: null,
        invoice: null,
      });
      appendLog(id, "queued", "Retry queued");
      pendingRef.current.push(id);
      schedule();
    },
    [appendLog, patchItem, schedule],
  );

  const clearCompleted = useCallback(() => {
    setItems((prev) => {
      const next = prev.filter((i) => isProcessingStatus(i.status));
      itemsRef.current = next;
      return next;
    });
  }, []);

  const clearAll = useCallback(() => {
    if (activeWorkersRef.current > 0 || pendingRef.current.length > 0) return;
    itemsRef.current = [];
    setItems([]);
  }, []);

  const isRunning = useMemo(
    () =>
      activeWorkers > 0 ||
      items.some((item) => isProcessingStatus(item.status)),
    [activeWorkers, items],
  );

  return {
    items,
    isRunning,
    enqueueFiles,
    retryItem,
    clearCompleted,
    clearAll,
  };
}
