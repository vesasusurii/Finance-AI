import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { getInvoice, uploadInvoices } from "@/api/invoices";
import {
  MOCK_PIPELINE,
  STAGE_LABELS,
  STAGE_PROGRESS,
  isProcessingStatus,
  statusFromUploadResult,
} from "@/lib/uploadQueueStages";
import { uploadProgressEvents } from "@/services/uploadProgressEvents";
import type {
  BatchProgressStats,
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

function computeStats(items: UploadQueueItem[]): BatchProgressStats {
  const total = items.length;
  const processing = items.filter((i) => isProcessingStatus(i.status)).length;
  const completed = items.filter((i) => i.status === "completed").length;
  const failed = items.filter((i) => i.status === "failed").length;
  const requiresReview = items.filter((i) => i.status === "requires_review").length;
  const overallProgress =
    total === 0
      ? 0
      : Math.round(
          items.reduce((sum, item) => sum + item.progress, 0) / total,
        );
  return {
    total,
    processing,
    completed,
    failed,
    requiresReview,
    overallProgress,
  };
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
      appendLog(item.id, "uploading", "Sending file to server");

      const timer = window.setInterval(advanceStage, STAGE_INTERVAL_MS);

      try {
        const res = await uploadInvoices([item.file]);
        const result = res.items[0];
        if (!result) {
          throw new Error("No upload result returned");
        }

        let invoice = null;
        let getInvoiceError: string | null = null;
        if (result.invoice_id) {
          try {
            invoice = await getInvoice(result.invoice_id);
          } catch (err) {
            getInvoiceError = err instanceof Error ? err.message : "getInvoice failed";
            invoice = null;
          }
        }

        const finalStatus =
          getInvoiceError && result.processing_status === "processed"
            ? "requires_review"
            : statusFromUploadResult(
                result.processing_status,
                invoice?.review_status,
              );

        const detailError =
          getInvoiceError ??
          (result.processing_status === "failed" ? result.error ?? null : null);

        patchItem(item.id, {
          status: finalStatus,
          progress: 100,
          stageLabel: STAGE_LABELS[finalStatus],
          uploadId: result.upload_id || undefined,
          invoiceId: result.invoice_id ?? null,
          confidence: invoice?.extraction_confidence ?? null,
          error: detailError,
          invoice,
        });

        appendLog(
          item.id,
          finalStatus,
          finalStatus === "failed"
            ? result.error ?? "Processing failed"
            : STAGE_LABELS[finalStatus],
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
      setItems((prev) => {
        const next = [...queued, ...prev];
        itemsRef.current = next;
        return next;
      });
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

  const stats = useMemo(() => computeStats(items), [items]);
  const isRunning = useMemo(
    () =>
      activeWorkers > 0 ||
      items.some((item) => isProcessingStatus(item.status)),
    [activeWorkers, items],
  );

  return {
    items,
    stats,
    isRunning,
    enqueueFiles,
    retryItem,
    clearCompleted,
    clearAll,
  };
}
