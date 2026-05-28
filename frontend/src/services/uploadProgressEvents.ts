import type { InvoiceQueueStatus } from "@/types/uploadQueue";

export type UploadProgressEvent = {
  itemId: string;
  status: InvoiceQueueStatus;
  progress: number;
  stageLabel?: string;
  error?: string | null;
  uploadId?: number;
  invoiceId?: number | null;
  confidence?: number | null;
};

export type UploadProgressListener = (event: UploadProgressEvent) => void;

export type UploadProgressTransport = "mock" | "polling" | "sse" | "websocket";

/**
 * Event bus for upload progress. Today driven by local mock/polling;
 * swap transport when backend SSE or WebSocket is available.
 */
class UploadProgressEventBus {
  private listeners = new Set<UploadProgressListener>();
  private transport: UploadProgressTransport = "mock";

  setTransport(transport: UploadProgressTransport) {
    this.transport = transport;
  }

  getTransport(): UploadProgressTransport {
    return this.transport;
  }

  subscribe(listener: UploadProgressListener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  emit(event: UploadProgressEvent) {
    for (const listener of this.listeners) {
      listener(event);
    }
  }
}

export const uploadProgressEvents = new UploadProgressEventBus();
