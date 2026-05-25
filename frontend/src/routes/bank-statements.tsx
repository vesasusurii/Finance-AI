import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Upload, FileSpreadsheet } from "lucide-react";
import { PageHeader } from "@/components/ui-finance/PageHeader";
import { Button } from "@/components/ui-finance/Button";
import { DataTable, type Column } from "@/components/ui-finance/DataTable";
import { StatusBadge } from "@/components/ui-finance/StatusBadge";
import {
  listBankStatements,
  uploadBankStatement,
} from "@/api/bankStatements";
import type {
  BankStatement,
  BankStatementUploadResponse,
  BankTransactionPreview,
} from "@/types/bank";
import {
  formatCurrency,
  formatDate,
  processingStatusLabel,
} from "@/lib/labels";

type PreviewRow = BankTransactionPreview & { id: string };

export function BankPage() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploadResult, setUploadResult] =
    useState<BankStatementUploadResponse | null>(null);
  const [previewRows, setPreviewRows] = useState<PreviewRow[]>([]);
  const [statements, setStatements] = useState<BankStatement[]>([]);
  const [loadingList, setLoadingList] = useState(true);

  const loadStatements = useCallback(async () => {
    setLoadingList(true);
    try {
      const res = await listBankStatements(1, 20);
      setStatements(res.items);
    } catch {
      setStatements([]);
    } finally {
      setLoadingList(false);
    }
  }, []);

  useEffect(() => {
    void loadStatements();
  }, [loadStatements]);

  const runUpload = useCallback(
    async (files: FileList | File[]) => {
      const file = Array.from(files)[0];
      if (!file) return;

      setUploading(true);
      setError(null);
      setUploadResult(null);
      try {
        const res = await uploadBankStatement(file);
        setUploadResult(res);
        setPreviewRows(
          res.preview.map((row, i) => ({
            ...row,
            id: `preview-${i}`,
          })),
        );
        await loadStatements();
      } catch (e) {
        setError(e instanceof Error ? e.message : "Upload failed");
      } finally {
        setUploading(false);
      }
    },
    [loadStatements],
  );

  const onFiles = (files: FileList | null) => {
    if (files?.length) void runUpload(files);
  };

  const previewColumns: Column<PreviewRow>[] = [
    {
      key: "date",
      header: "Date",
      cell: (r) => (
        <span className="tabular-nums">{formatDate(r.transaction_date)}</span>
      ),
    },
    {
      key: "debited",
      header: "Debited",
      cell: (r) => (
        <span className="tabular-nums">
          {formatCurrency(r.debited_amount, "EUR")}
        </span>
      ),
    },
    {
      key: "credited",
      header: "Credited",
      cell: (r) => (
        <span className="tabular-nums">
          {formatCurrency(r.credited_amount, "EUR")}
        </span>
      ),
    },
    {
      key: "type",
      header: "Type",
      cell: (r) => r.transaction_type ?? "—",
    },
    {
      key: "comment",
      header: "Comment",
      cell: (r) => (
        <span className="max-w-[280px] truncate block" title={r.comment ?? ""}>
          {r.comment ?? "—"}
        </span>
      ),
    },
    {
      key: "numbers",
      header: "Detected #",
      cell: (r) =>
        r.detected_invoice_numbers.length ? (
          <div className="flex flex-wrap gap-1">
            {r.detected_invoice_numbers.map((n) => (
              <span
                key={n}
                className="rounded border border-border bg-surface-muted px-1.5 py-0.5 text-[11px] font-medium"
              >
                {n}
              </span>
            ))}
          </div>
        ) : (
          <span className="text-muted-foreground">—</span>
        ),
    },
  ];

  const statementColumns: Column<BankStatement>[] = [
    {
      key: "file",
      header: "File",
      cell: (r) => (
        <div className="flex items-center gap-2">
          <FileSpreadsheet className="h-4 w-4 text-muted-foreground" />
          <span className="font-medium">{r.original_filename}</span>
        </div>
      ),
    },
    {
      key: "rows",
      header: "Rows",
      cell: (r) => <span className="tabular-nums">{r.row_count}</span>,
    },
    {
      key: "status",
      header: "Status",
      cell: (r) => (
        <StatusBadge value={processingStatusLabel(r.processing_status)} />
      ),
    },
    {
      key: "uploaded",
      header: "Uploaded",
      cell: (r) => (
        <span className="tabular-nums text-muted-foreground">
          {formatDate(r.uploaded_at)}
        </span>
      ),
    },
    {
      key: "view",
      header: "",
      cell: (r) => (
        <Link
          to={`/bank-transactions?bank_statement_id=${r.id}`}
          className="text-[12px] font-medium text-primary hover:underline"
        >
          View transactions
        </Link>
      ),
    },
  ];

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Workflow · Step 2"
        title="Bank statements"
        description="Upload ProCredit-style Excel exports. Invoice numbers are parsed from Komenti / Comment."
      />

      <section
        className={`rounded-lg border border-dashed p-8 transition-colors ${
          dragging
            ? "border-primary bg-accent/30"
            : "border-border bg-surface-muted/40"
        }`}
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
      >
        <input
          ref={inputRef}
          type="file"
          accept=".xlsx,.xls,.xlsm,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel"
          className="hidden"
          onChange={(e) => onFiles(e.target.files)}
        />
        <div className="flex flex-col items-center gap-3 text-center">
          <div className="grid h-12 w-12 place-items-center rounded-full bg-accent">
            <Upload className="h-5 w-5 text-primary" />
          </div>
          <div>
            <p className="text-[14px] font-medium text-foreground">
              Drop bank statement Excel here
            </p>
            <p className="mt-1 text-[12px] text-muted-foreground">
              .xlsx or .xls — must include Data / Date and Komenti / Comment columns
            </p>
          </div>
          <Button
            variant="primary"
            disabled={uploading}
            onClick={() => inputRef.current?.click()}
          >
            {uploading ? "Parsing…" : "Choose file"}
          </Button>
        </div>
      </section>

      {error && (
        <p className="text-[13px] text-destructive" role="alert">
          {error}
        </p>
      )}

      {uploadResult && (
        <section className="space-y-3">
          <p className="text-[13px] text-foreground">
            Imported{" "}
            <strong>{uploadResult.row_count}</strong> transactions (statement #
            {uploadResult.bank_statement_id}).{" "}
            <Link
              to={`/bank-transactions?bank_statement_id=${uploadResult.bank_statement_id}`}
              className="text-primary hover:underline"
            >
              View all rows
            </Link>
          </p>
          {previewRows.length > 0 && (
            <DataTable
              columns={previewColumns}
              rows={previewRows}
              empty="No preview rows"
            />
          )}
        </section>
      )}

      <section className="space-y-3">
        <h2 className="text-[14px] font-semibold text-foreground">
          Uploaded statements
        </h2>
        {loadingList ? (
          <p className="text-[13px] text-muted-foreground">Loading…</p>
        ) : (
          <DataTable
            columns={statementColumns}
            rows={statements}
            empty="No bank statements uploaded yet."
          />
        )}
      </section>
    </div>
  );
}
