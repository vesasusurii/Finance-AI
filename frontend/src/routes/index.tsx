import { useCallback, useRef, useState } from "react";
import { Upload, FileText, RefreshCw } from "lucide-react";
import { PageHeader } from "@/components/ui-finance/PageHeader";
import { Button } from "@/components/ui-finance/Button";
import { DataTable, type Column } from "@/components/ui-finance/DataTable";
import { StatusBadge } from "@/components/ui-finance/StatusBadge";
import { uploadInvoices } from "@/api/invoices";
import type { UploadItem } from "@/types/invoice";
import { processingStatusLabel } from "@/lib/labels";

type UploadRow = UploadItem & { id: string };

export function UploadPage() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rows, setRows] = useState<UploadRow[]>([]);

  const runUpload = useCallback(async (files: FileList | File[]) => {
    const list = Array.from(files);
    if (!list.length) return;

    setUploading(true);
    setError(null);
    try {
      const res = await uploadInvoices(list);
      const mapped: UploadRow[] = res.items.map((item) => ({
        ...item,
        id: `${item.upload_id}-${item.original_filename}`,
      }));
      setRows((prev) => [...mapped, ...prev]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }, []);

  const onFiles = (files: FileList | null) => {
    if (files?.length) void runUpload(files);
  };

  const columns: Column<UploadRow>[] = [
    {
      key: "file",
      header: "Filename",
      cell: (r) => (
        <div className="flex items-center gap-2.5">
          <div className="grid h-8 w-8 place-items-center rounded-md border border-border bg-surface-muted">
            <FileText className="h-3.5 w-3.5 text-muted-foreground" />
          </div>
          <div>
            <div className="font-medium text-foreground">{r.original_filename}</div>
            {r.invoice_id != null && (
              <div className="text-[11px] text-muted-foreground">
                Invoice #{r.invoice_id}
              </div>
            )}
          </div>
        </div>
      ),
    },
    {
      key: "status",
      header: "Processing",
      cell: (r) => (
        <StatusBadge value={processingStatusLabel(r.processing_status)} />
      ),
    },
    {
      key: "error",
      header: "Details",
      cell: (r) =>
        r.error ? (
          <span className="text-[12px] text-destructive">{r.error}</span>
        ) : (
          <span className="text-muted-foreground">—</span>
        ),
    },
  ];

  return (
    <div>
      <PageHeader
        eyebrow="Workflow · Step 1"
        title="Upload invoices"
        description="Upload supplier invoices and scans. OpenAI Vision reads each document and extracts structured data; uncertain rows go to review."
        actions={
          <Button
            variant="secondary"
            icon={<RefreshCw className="h-3.5 w-3.5" />}
            disabled={uploading}
            onClick={() => setRows([])}
          >
            Clear list
          </Button>
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
          PDF, JPG, PNG · scanned PDFs supported · up to 20 MB each
        </p>
        <div className="mt-4 flex items-center justify-center gap-2">
          <Button
            disabled={uploading}
            onClick={() => inputRef.current?.click()}
            icon={<Upload className="h-3.5 w-3.5" />}
          >
            {uploading ? "Uploading…" : "Select files"}
          </Button>
        </div>
      </div>

      {error && (
        <p className="mb-4 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-[13px] text-destructive">
          {error}
        </p>
      )}

      {rows.length === 0 ? (
        <p className="text-[13px] text-muted-foreground">
          No uploads in this session yet. Files you upload will appear here with
          processing status.
        </p>
      ) : (
        <DataTable columns={columns} rows={rows} />
      )}
    </div>
  );
}
