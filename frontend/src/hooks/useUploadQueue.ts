import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { getInvoice } from "@/api/invoices";
import {
  uploadDocumentWithProgress,
  validateClientFile,
  waitForDocumentExtraction,
  type DocumentUploadItem,
} from "@/api/documents";
import { formatInvoiceDetailSummary } from "@/lib/invoiceDetailSummary";
import {
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

function createId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

function logEntry(
  stage: InvoiceQueueStatus,
  message: string,
): ProcessingLogEntry {
  return { at: new Date().toISOString(), stage, message };
}

function applyInvoiceToItem(
  invoice: Awaited<ReturnType<typeof getInvoice>> | null,
  result: DocumentUploadItem,
): Pick<
  UploadQueueItem,
  "invoice" | "invoiceId" | "confidence" | "detailSummary" | "status" | "stageLabel" | "progress"
> {
  const status = statusFromUploadResult(
    result.upload_status,
    invoice?.review_status,
  );
  return {
    invoice,
    invoiceId: result.invoice_id ?? invoice?.id ?? null,
    confidence: invoice?.extraction_confidence ?? null,
    detailSummary: formatInvoiceDetailSummary(invoice),
    status,
    stageLabel: STAGE_LABELS[status],
    progress: STAGE_PROGRESS[status],
  };
}

export function useUploadQueue() {
  const [items, setItems] = useState<UploadQueueItem[]>([]);
  const [activeWorkers, setActiveWorkers] = useState(0);
  const itemsRef = useRef(items);
  const pendingRef = useRef<string[]>([]);
  const activeWorkersRef = useRef(0);
  const watchAbortRef = useRef<Map<string, AbortController>>(new Map());

  useEffect(() => {
    itemsRef.current = items;
  }, [items]);

  useEffect(() => {
    const controllers = watchAbortRef.current;
    return () => {
      controllers.forEach((c) => c.abort());
      controllers.clear();
    };
  }, []);

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

  const watchExtraction = useCallback(
    (itemId: string, documentId: number) => {
      watchAbortRef.current.get(itemId)?.abort();
      const controller = new AbortController();
      watchAbortRef.current.set(itemId, controller);

      patchItem(itemId, {
        status: "ocr_processing",
        progress: STAGE_PROGRESS.ocr_processing,
        stageLabel: STAGE_LABELS.ocr_processing,
        uploadId: documentId,
      });
      appendLog(itemId, "ocr_processing", "Extracting invoice data");

      void (async () => {
        try {
          const extracted = await waitForDocumentExtraction(documentId, {
            signal: controller.signal,
            onPoll: (status, elapsedMs) => {
              if (status.upload_status === "processing") {
                const progress = Math.min(
                  88,
                  STAGE_PROGRESS.ocr_processing +
                    Math.floor(elapsedMs / 4000),
                );
                patchItem(itemId, {
                  status: "ocr_processing",
                  progress,
                  stageLabel: STAGE_LABELS.ocr_processing,
                });
              }
            },
          });

          if (extracted.upload_status === "failed") {
            patchItem(itemId, {
              status: "failed",
              progress: 100,
              stageLabel: STAGE_LABELS.failed,
              error: extracted.error ?? "Extraction failed",
            });
            appendLog(itemId, "failed", extracted.error ?? "Extraction failed");
            return;
          }

          patchItem(itemId, {
            status: "validating",
            progress: STAGE_PROGRESS.validating,
            stageLabel: STAGE_LABELS.validating,
          });
          appendLog(itemId, "validating", "Validating extracted fields");

          let invoice = null;
          if (extracted.invoice_id) {
            invoice = await getInvoice(extracted.invoice_id);
          }

          const applied = applyInvoiceToItem(invoice, extracted);
          patchItem(itemId, {
            ...applied,
            uploadId: documentId,
            error: null,
          });
          appendLog(
            itemId,
            applied.status,
            applied.detailSummary ?? applied.stageLabel,
          );
        } catch (err) {
          if (controller.signal.aborted) return;
          const message =
            err instanceof Error ? err.message : "Could not load extraction result";
          patchItem(itemId, {
            status: "failed",
            progress: 100,
            stageLabel: STAGE_LABELS.failed,
            error: message,
          });
          appendLog(itemId, "failed", message);
        } finally {
          watchAbortRef.current.delete(itemId);
        }
      })();
    },
    [appendLog, patchItem],
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

      patchItem(item.id, {
        status: "uploading",
        progress: STAGE_PROGRESS.uploading,
        stageLabel: STAGE_LABELS.uploading,
      });
      appendLog(item.id, "uploading", "Saving file to storage");

      try {
        const res = await uploadDocumentWithProgress(item.file, (pct) => {
          const uploadProgress = Math.min(
            35,
            STAGE_PROGRESS.uploading +
              Math.round((pct / 100) * (40 - STAGE_PROGRESS.uploading)),
          );
          patchItem(item.id, {
            progress: uploadProgress,
            stageLabel: pct < 100 ? `Uploading ${pct}%` : "Saving file",
          });
        });

        const result = res.items[0];
        if (!result) {
          throw new Error("No upload result returned");
        }

        const isLinked = result.upload_status === "linked";
        const isFailed = result.upload_status === "failed" || !!result.error;

        if (isFailed) {
          patchItem(item.id, {
            status: "failed",
            progress: 100,
            stageLabel: STAGE_LABELS.failed,
            error: result.error ?? "Upload failed",
            uploadId: result.document_id || undefined,
          });
          appendLog(item.id, "failed", result.error ?? "Upload failed");
          return;
        }

        patchItem(item.id, {
          uploadId: result.document_id || undefined,
          progress: 40,
          stageLabel: "File saved",
        });
        appendLog(item.id, "uploading", "File saved — starting extraction");

        if (
          result.invoice_id ||
          result.upload_status === "linked" ||
          result.upload_status === "processed"
        ) {
          let invoice = null;
          try {
            invoice = await getInvoice(result.invoice_id);
          } catch {
            /* drawer can load later */
          }
          const applied = applyInvoiceToItem(invoice, result);
          patchItem(item.id, {
            ...applied,
            uploadId: result.document_id || undefined,
            infoMessage: isLinked ? (result.message ?? null) : null,
            error: null,
          });
          appendLog(
            item.id,
            applied.status,
            isLinked
              ? (result.message ?? "Already in system")
              : (applied.detailSummary ?? applied.stageLabel),
          );
          return;
        }

        if (result.document_id) {
          watchExtraction(item.id, result.document_id);
          return;
        }

        patchItem(item.id, {
          status: "failed",
          progress: 100,
          stageLabel: STAGE_LABELS.failed,
          error: "No document id returned from server",
        });
      } catch (err) {
        const message = err instanceof Error ? err.message : "Upload failed";
        patchItem(item.id, {
          status: "failed",
          progress: 100,
          stageLabel: STAGE_LABELS.failed,
          error: message,
        });
        appendLog(item.id, "failed", message);
      }
    },
    [appendLog, patchItem, watchExtraction],
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
        logs: [logEntry("queued", "Waiting to save")],
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
      watchAbortRef.current.get(id)?.abort();
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
        detailSummary: null,
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
    watchAbortRef.current.forEach((c) => c.abort());
    watchAbortRef.current.clear();
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
