import { useRef, useState } from "react";
import { Upload, RefreshCw } from "lucide-react";
import { PageHeader } from "@/components/ui-finance/PageHeader";
import { Button } from "@/components/ui-finance/Button";
import { InvoiceDetailsDrawer } from "@/components/invoices/InvoiceDetailsDrawer";
import { ProcessingQueueTable } from "@/components/invoices/ProcessingQueueTable";
import { useUploadQueue } from "@/hooks/useUploadQueue";
import type { UploadQueueItem } from "@/types/uploadQueue";

export function UploadPage() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedItem, setSelectedItem] = useState<UploadQueueItem | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const {
    items,
    isRunning,
    enqueueFiles,
    retryItem,
    clearCompleted,
    clearAll,
  } = useUploadQueue();

  const onFiles = (files: FileList | null) => {
    if (!files?.length) return;
    setError(null);
    enqueueFiles(files);
    if (inputRef.current) inputRef.current.value = "";
  };

  function handleView(item: UploadQueueItem) {
    setSelectedItem(item);
    setDrawerOpen(true);
  }

  return (
    <div>
      <PageHeader
        eyebrow="Workflow · Step 1"
        title="Upload invoices"
        description="Upload supplier invoices and scans. OpenAI Vision reads each document and extracts structured data; uncertain rows go to review."
        actions={
          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              icon={<RefreshCw className="h-3.5 w-3.5" />}
              disabled={isRunning || items.length === 0}
              onClick={clearCompleted}
            >
              Clear finished
            </Button>
            <Button
              variant="ghost"
              disabled={isRunning || items.length === 0}
              onClick={clearAll}
            >
              Clear all
            </Button>
          </div>
        }
      />

      <input
        ref={inputRef}
        type="file"
        multiple
        accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png"
        className="hidden"
        onChange={(e) => onFiles(e.target.files)}
      />

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          onFiles(e.dataTransfer.files);
        }}
        className={
          "mb-6 rounded-xl border-2 border-dashed bg-surface-muted px-8 py-12 text-center transition-colors " +
          (dragging ? "border-primary bg-accent" : "border-border")
        }
      >
        <div className="mx-auto grid h-12 w-12 place-items-center rounded-full bg-accent">
          <Upload className="h-5 w-5 text-primary" />
        </div>
        <h3 className="mt-4 text-[15px] font-semibold text-foreground">
          Drop invoices here to upload
        </h3>
        <p className="mt-1 text-[13px] text-muted-foreground">
          PDF, JPG, PNG · scanned PDFs supported · up to 20 MB each · bulk batches supported
        </p>
        <div className="mt-4 flex items-center justify-center gap-2">
          <Button
            onClick={() => inputRef.current?.click()}
            icon={<Upload className="h-3.5 w-3.5" />}
          >
            Select files
          </Button>
        </div>
      </div>

      {error && (
        <p className="mb-4 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-[13px] text-destructive">
          {error}
        </p>
      )}

      <ProcessingQueueTable
        items={items}
        onView={handleView}
        onRetry={(item) => retryItem(item.id)}
      />

      <InvoiceDetailsDrawer
        item={selectedItem}
        open={drawerOpen}
        onOpenChange={setDrawerOpen}
      />
    </div>
  );
}
