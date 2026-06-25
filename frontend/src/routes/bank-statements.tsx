import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Trash2, Upload, FileSpreadsheet, RefreshCw } from "lucide-react";
import {
  LoadingSpinner,
  SectionLoadingSpinner,
} from "@/components/LoadingSpinner";
import { PageHeader } from "@/components/ui-finance/PageHeader";
import { Button } from "@/components/ui-finance/Button";
import { DataTable, type Column } from "@/components/ui-finance/DataTable";
import { StatusBadge } from "@/components/ui-finance/StatusBadge";
import {
  deleteBankStatement,
  listBankStatements,
  reparseBankStatement,
  uploadBankStatement,
} from "@/api/bankStatements";
import type {
  BankStatement,
  BankStatementUploadResponse,
  BankTransactionPreview,
} from "@/types/bank";
import { useAppDialog } from "@/components/dialogs/AppDialogProvider";
import { useAuth } from "@/auth/AuthContext";
import { useAdminUsers } from "@/hooks/useAdminUsers";
import {
  formatCurrency,
  formatDate,
  formatStatementId,
  processingStatusLabel,
} from "@/lib/labels";

type PreviewRow = BankTransactionPreview & { id: string };

export function BankPage() {
  const { confirm } = useAppDialog();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { isAdmin } = useAuth();
  const { items: adminUsers } = useAdminUsers(isAdmin);
  const uploadedByParam = searchParams.get("uploaded_by");
  const uploadedByFilter = uploadedByParam
    ? parseInt(uploadedByParam, 10)
    : undefined;
  const filterUserId = Number.isFinite(uploadedByFilter) ? uploadedByFilter : undefined;
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploadResult, setUploadResult] =
    useState<BankStatementUploadResponse | null>(null);
  const [previewRows, setPreviewRows] = useState<PreviewRow[]>([]);
  const [statements, setStatements] = useState<BankStatement[]>([]);
  const [loadingList, setLoadingList] = useState(true);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [reparsingId, setReparsingId] = useState<number | null>(null);
  const [reparseMessage, setReparseMessage] = useState<string | null>(null);

  const loadStatements = useCallback(async () => {
    setLoadingList(true);
    try {
      const res = await listBankStatements(
        1,
        50,
        isAdmin ? filterUserId : undefined,
      );
      setStatements(res.items);
    } catch {
      setStatements([]);
    } finally {
      setLoadingList(false);
    }
  }, [filterUserId, isAdmin]);

  const filterLabel = useMemo(() => {
    if (!isAdmin || filterUserId === undefined) return null;
    const match = adminUsers.find((user) => user.id === filterUserId);
    return match?.email ?? `User #${filterUserId}`;
  }, [adminUsers, filterUserId, isAdmin]);

  function handleUploaderFilterChange(userId: string) {
    const next = new URLSearchParams(searchParams);
    if (!userId) {
      next.delete("uploaded_by");
    } else {
      next.set("uploaded_by", userId);
    }
    setSearchParams(next, { replace: true });
  }

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

  const handleDelete = useCallback(
    async (statement: BankStatement) => {
      const label = formatStatementId(statement);
      const ok = await confirm({
        title: "Delete bank statement",
        description: `Delete bank statement ${label} (${statement.original_filename})? This cannot be undone.`,
        confirmLabel: "Delete",
        variant: "destructive",
      });
      if (!ok) return;
      setDeletingId(statement.id);
      setError(null);
      try {
        await deleteBankStatement(statement.id);
        if (uploadResult?.bank_statement_id === statement.id) {
          setUploadResult(null);
          setPreviewRows([]);
        }
        await loadStatements();
      } catch (e) {
        setError(e instanceof Error ? e.message : "Delete failed");
      } finally {
        setDeletingId(null);
      }
    },
    [confirm, loadStatements, uploadResult?.bank_statement_id],
  );

  const handleReparse = useCallback(
    async (statement: BankStatement) => {
      setReparsingId(statement.id);
      setError(null);
      setReparseMessage(null);
      try {
        const res = await reparseBankStatement(statement.id);
        setReparseMessage(
          `Re-parsed ${formatStatementId(statement)}: ${res.dates_fixed} date(s) fixed, ${res.rows_updated} row(s) updated.`,
        );
      } catch (e) {
        setError(e instanceof Error ? e.message : "Re-parse failed");
      } finally {
        setReparsingId(null);
      }
    },
    [],
  );

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
      key: "id",
      header: "Statement ID",
      cell: (r) => (
        <span className="font-mono tabular-nums">{formatStatementId(r)}</span>
      ),
    },
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
    ...(isAdmin
      ? [
          {
            key: "uploader",
            header: "Uploaded by",
            cell: (r: BankStatement) => (
              <button
                type="button"
                className="text-left text-[13px] text-primary hover:underline"
                onClick={() => handleUploaderFilterChange(String(r.uploaded_by))}
              >
                {r.uploaded_by_email}
              </button>
            ),
          } satisfies Column<BankStatement>,
        ]
      : []),
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
        <div className="flex flex-wrap items-center gap-2">
          <Link
            to={`/bank-transactions?bank_statement_id=${r.id}`}
            className="text-[12px] font-medium text-primary hover:underline"
          >
            View transactions
          </Link>
          <Button
            variant="secondary"
            size="sm"
            icon={<RefreshCw className="h-3.5 w-3.5" />}
            disabled={reparsingId === r.id}
            onClick={() => void handleReparse(r)}
          >
            {reparsingId === r.id ? "Re-parsing…" : "Re-parse"}
          </Button>
          <Button
            variant="danger"
            size="sm"
            icon={<Trash2 className="h-3.5 w-3.5" />}
            disabled={deletingId === r.id}
            onClick={() => void handleDelete(r)}
          >
            {deletingId === r.id ? "Deleting…" : "Delete"}
          </Button>
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Workflow · Step 2"
        title="Bank statements"
        description={
          isAdmin
            ? "Review bank statement uploads across finance users."
            : undefined
        }
        actions={
          !isAdmin ? (
            <Link
              to="/matching"
              className="inline-flex h-9 items-center rounded-md bg-primary px-3.5 text-[13px] font-medium text-primary-foreground hover:bg-soft-navy"
            >
              Run Matching
            </Link>
          ) : null
        }
      />

      {isAdmin ? (
        <section className="rounded-lg border border-border bg-card p-4">
          <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
            <div>
              <p className="text-[13px] font-medium text-foreground">Filter by uploader</p>
              <p className="mt-1 text-[12px] text-muted-foreground">
                {filterLabel
                  ? `Showing statements uploaded by ${filterLabel}.`
                  : "Showing statements from all finance users."}
              </p>
            </div>
            <label className="block min-w-[280px]">
              <span className="mb-1.5 block text-[12px] font-medium text-muted-foreground">
                Finance user
              </span>
              <select
                value={filterUserId ?? ""}
                onChange={(e) => handleUploaderFilterChange(e.target.value)}
                className="h-9 w-full rounded-md border border-input bg-background px-3 text-[13px] text-foreground focus:border-ring focus:outline-none"
              >
                <option value="">All users</option>
                {adminUsers
                  .filter((user) => user.role === "finance")
                  .map((user) => (
                    <option key={user.id} value={user.id}>
                      {user.email}
                      {user.bank_statement_count > 0
                        ? ` (${user.bank_statement_count})`
                        : ""}
                    </option>
                  ))}
              </select>
            </label>
          </div>
        </section>
      ) : null}

      {!isAdmin ? (
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
            icon={uploading ? <LoadingSpinner size="sm" className="text-primary-foreground" /> : <Upload className="h-3.5 w-3.5" />}
            onClick={() => inputRef.current?.click()}
          >
            {uploading ? "Parsing…" : "Choose file"}
          </Button>
        </div>
      </section>
      ) : null}

      {error && (
        <p className="text-[13px] text-destructive" role="alert">
          {error}
        </p>
      )}
      {reparseMessage && (
        <p className="text-[13px] text-muted-foreground" role="status">
          {reparseMessage}
        </p>
      )}

      {uploadResult && !isAdmin ? (
        <section className="space-y-3">
          <p className="text-[13px] text-foreground">
            Imported{" "}
            <strong>{uploadResult.row_count}</strong> transactions (statement ID{" "}
            <strong>{formatStatementId(uploadResult)}</strong>).{" "}
            <Link
              to={`/bank-transactions?bank_statement_id=${uploadResult.bank_statement_id}`}
              className="text-primary hover:underline"
            >
              View all rows
            </Link>
            {" · "}
            <button
              type="button"
              className="text-primary hover:underline"
              onClick={() =>
                navigate(
                  `/matching?bank_statement_id=${uploadResult.bank_statement_id}`,
                )
              }
            >
              Run matching for this statement
            </button>
          </p>
          {uploadResult.duplicate_rows_skipped ? (
            <p className="text-[13px] text-muted-foreground">
              Skipped{" "}
              <strong>{uploadResult.duplicate_rows_skipped}</strong> duplicate
              row
              {uploadResult.duplicate_rows_skipped === 1 ? "" : "s"} during
              import.
            </p>
          ) : null}
          {uploadResult.unparsed_date_rows ? (
            <div
              className="rounded-md border border-amber-400/40 bg-amber-50 px-3 py-2 text-[13px] text-amber-900"
              role="alert"
            >
              <strong>{uploadResult.unparsed_date_rows}</strong> of{" "}
              {uploadResult.row_count} rows have an unparsable date and will be
              skipped by matching (reason: <em>missing_transaction_date</em>).
              Re-format the date column to <code>dd.mm.yyyy</code>,{" "}
              <code>dd/mm/yyyy</code>, or <code>yyyy-mm-dd</code> and re-upload,
              or backfill the dates in the DB.
            </div>
          ) : null}
          {previewRows.length > 0 && (
            <DataTable
              columns={previewColumns}
              rows={previewRows}
              empty="No preview rows"
            />
          )}
        </section>
      ) : null}

      <section className="space-y-3">
        <h2 className="text-[14px] font-semibold text-foreground">
          Uploaded statements
        </h2>
        {loadingList ? (
          <SectionLoadingSpinner />
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
