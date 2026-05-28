import { useCallback, useState } from "react";
import {
  AlertTriangle,
  Check,
  ExternalLink,
  FileText,
  Loader2,
  Save,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui-finance/Button";
import {
  approveInvoice,
  invoiceFileUrl,
  updateInvoice,
} from "@/api/invoices";
import { formatDate } from "@/lib/labels";
import type { Invoice } from "@/types/invoice";

const CATEGORIES = [
  "Professional services",
  "Utilities",
  "Software",
  "IT / Hardware",
  "Office",
  "Travel",
  "Other",
];

const CURRENCIES = ["EUR", "USD", "GBP", "CHF", "ALL", "BAM", "RSD", "MKD"];

type FormData = {
  name_of_company: string;
  address_of_company: string;
  invoice_date: string;
  invoice_number: string;
  amount: string;
  debt: string;
  currency: string;
  account_details: string;
  internal_note_description: string;
  client_employee_related: string;
  category: string;
  paid_by: string;
};

function toFormData(inv: Invoice): FormData {
  return {
    name_of_company: inv.name_of_company ?? "",
    address_of_company: inv.address_of_company ?? "",
    invoice_date: inv.invoice_date ?? "",
    invoice_number: inv.invoice_number ?? "",
    amount: inv.amount != null ? String(inv.amount) : "",
    debt: inv.debt != null ? String(inv.debt) : "",
    currency: inv.currency ?? "",
    account_details: inv.account_details ?? "",
    internal_note_description: inv.internal_note_description ?? "",
    client_employee_related: inv.client_employee_related ?? "Borek Solutions",
    category: inv.category ?? "",
    paid_by: inv.paid_by ?? "",
  };
}

export function InvoiceDocumentEditor({
  invoice,
  onApproved,
  onSaved,
}: {
  invoice: Invoice;
  onApproved: () => void;
  onSaved: (invoice: Invoice) => void;
}) {
  const [form, setForm] = useState<FormData>(toFormData(invoice));
  const [saving, setSaving] = useState(false);
  const [approving, setApproving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const isDirty = JSON.stringify(form) !== JSON.stringify(toFormData(invoice));

  const handleField = useCallback((key: keyof FormData, value: string) => {
    setForm((prev) => ({ ...prev, [key]: value }));
    setSaved(false);
    setSaveError(null);
  }, []);

  const handleSave = async (): Promise<boolean> => {
    setSaving(true);
    setSaveError(null);
    try {
      const updated = await updateInvoice(invoice.id, {
        name_of_company: form.name_of_company || null,
        address_of_company: form.address_of_company || null,
        invoice_date: form.invoice_date || null,
        invoice_number: form.invoice_number || null,
        amount: form.amount ? Number(form.amount) : null,
        debt: form.debt ? Number(form.debt) : null,
        currency: form.currency || null,
        account_details: form.account_details || null,
        internal_note_description: form.internal_note_description || null,
        client_employee_related:
          form.client_employee_related.trim() || "Borek Solutions",
        category: form.category || null,
        paid_by: form.paid_by.trim() || null,
      } as Partial<Invoice>);
      setSaved(true);
      onSaved(updated);
      return true;
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : "Save failed");
      return false;
    } finally {
      setSaving(false);
    }
  };

  const handleApprove = async () => {
    if (isDirty) {
      const savedOk = await handleSave();
      if (!savedOk) return;
    }
    setApproving(true);
    try {
      await approveInvoice(invoice.id);
      onApproved();
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : "Approve failed");
      setApproving(false);
    }
  };

  const conf = invoice.field_confidences ?? {};
  const overall = invoice.extraction_confidence
    ? Number(invoice.extraction_confidence)
    : null;

  return (
    <div className="grid min-h-[calc(100vh-11rem)] grid-cols-1 gap-4 lg:grid-cols-2">
      <DocumentPreview invoice={invoice} />

      <div className="flex min-h-[480px] flex-col overflow-hidden rounded-lg border border-border bg-card lg:min-h-0">
        <div className="flex shrink-0 items-center justify-between border-b border-border px-5 py-3">
          <div className="flex items-center gap-3">
            <span className="text-[13px] font-semibold text-foreground">
              Extracted data
            </span>
            {overall != null && <OverallConfidence value={overall} />}
          </div>
          {invoice.review_status === "needs_review" && (
            <span className="rounded-full bg-warning/15 px-2.5 py-0.5 text-[11px] font-medium text-warning">
              Requires immediate review
            </span>
          )}
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-4">
          <div className="space-y-3">
            <FieldRow
              label="Company name"
              value={form.name_of_company}
              confidence={conf.name_of_company}
              onChange={(v) => handleField("name_of_company", v)}
            />
            <FieldRow
              label="Address"
              value={form.address_of_company}
              confidence={conf.address_of_company}
              onChange={(v) => handleField("address_of_company", v)}
              multiline
            />
            <div className="grid grid-cols-2 gap-3">
              <FieldRow
                label="Invoice date"
                value={form.invoice_date}
                confidence={conf.invoice_date}
                onChange={(v) => handleField("invoice_date", v)}
                type="date"
              />
              <FieldRow
                label="Invoice number"
                value={form.invoice_number}
                confidence={conf.invoice_number}
                onChange={(v) => handleField("invoice_number", v)}
                mono
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <FieldRow
                label="Bill amount"
                value={form.amount}
                confidence={conf.amount}
                onChange={(v) => handleField("amount", v)}
                type="number"
              />
              <FieldRow
                label="Debt / outstanding"
                value={form.debt}
                confidence={conf.debt}
                onChange={(v) => handleField("debt", v)}
                type="number"
              />
            </div>
            <FieldRowSelect
              label="Currency"
              value={form.currency}
              confidence={conf.currency}
              options={CURRENCIES}
              onChange={(v) => handleField("currency", v)}
            />
            <FieldRowSelect
              label="Category"
              value={form.category}
              confidence={conf.category}
              options={CATEGORIES}
              onChange={(v) => handleField("category", v)}
            />
            <FieldRow
              label="Account details (IBAN)"
              value={form.account_details}
              confidence={conf.account_details}
              onChange={(v) => handleField("account_details", v)}
              multiline
              mono
            />
            <FieldRow
              label="Description"
              value={form.internal_note_description}
              confidence={conf.internal_note_description}
              onChange={(v) => handleField("internal_note_description", v)}
              multiline
            />
            <FieldRow
              label="Related person"
              value={form.client_employee_related}
              confidence={conf.client_employee_related}
              onChange={(v) => handleField("client_employee_related", v)}
            />

            <div className="mt-2 border-t border-border pt-4">
              <FieldRow
                label="Paid by"
                value={form.paid_by}
                onChange={(v) => handleField("paid_by", v)}
                placeholder="Name of the person who paid"
              />
              {invoice.paid_at_date && (
                <p className="mt-2 text-[11px] text-muted-foreground">
                  Paid at (date):{" "}
                  <span className="tabular-nums text-foreground">
                    {formatDate(invoice.paid_at_date)}
                  </span>
                  <span className="text-muted-foreground">
                    {" "}
                    — set by bank matching
                  </span>
                </p>
              )}
            </div>
          </div>
        </div>

        <div className="shrink-0 border-t border-border px-5 py-3">
          {saveError && (
            <p className="mb-2 text-[12px] text-destructive">{saveError}</p>
          )}
          <div className="flex items-center justify-between gap-3">
            <div className="text-[12px] text-muted-foreground">
              {saved && !isDirty ? (
                <span className="text-success">Changes saved</span>
              ) : isDirty ? (
                <span className="text-warning">Unsaved changes</span>
              ) : null}
            </div>
            <div className="flex gap-2">
              <Button
                variant="secondary"
                size="sm"
                disabled={!isDirty || saving}
                onClick={handleSave}
                icon={
                  saving ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Save className="h-3.5 w-3.5" />
                  )
                }
              >
                Save
              </Button>
              <Button
                variant="success"
                size="sm"
                disabled={approving || invoice.review_status === "approved"}
                onClick={handleApprove}
                icon={
                  approving ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Check className="h-3.5 w-3.5" />
                  )
                }
              >
                Approve
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function mimeFromInvoice(invoice: Invoice): string | null {
  if (invoice.source_mime_type) return invoice.source_mime_type;
  const name = invoice.source_filename?.toLowerCase() ?? "";
  if (name.endsWith(".pdf")) return "application/pdf";
  if (name.endsWith(".png")) return "image/png";
  if (name.endsWith(".jpg") || name.endsWith(".jpeg")) return "image/jpeg";
  return null;
}

function DocumentPreview({ invoice }: { invoice: Invoice }) {
  const [imgError, setImgError] = useState(false);

  const fileSrc = invoice.source_file_id ? invoiceFileUrl(invoice.id) : null;
  const mimeType = mimeFromInvoice(invoice);
  const isImage = mimeType?.startsWith("image/") && !imgError;
  const isPdf =
    mimeType === "application/pdf" || mimeType?.includes("pdf") || !isImage;
  const typeLabel =
    isPdf && !isImage
      ? "PDF"
      : isImage
        ? mimeType?.split("/")[1]?.toUpperCase() ?? "IMAGE"
        : mimeType
          ? "FILE"
          : null;
  const displayName =
    invoice.source_filename ??
    invoice.invoice_number ??
    invoice.name_of_company ??
    `Invoice #${invoice.id}`;

  return (
    <div className="flex min-h-[480px] flex-col overflow-hidden rounded-lg border border-border bg-card lg:min-h-0">
      <div className="flex shrink-0 items-center gap-2 border-b border-border px-4 py-3">
        <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />
        <span
          className="truncate font-mono text-[12px] text-foreground"
          title={displayName}
        >
          {displayName}
        </span>
        <div className="ml-auto flex shrink-0 items-center gap-2">
          {typeLabel && (
            <span className="rounded bg-secondary px-1.5 py-0.5 text-[10px] uppercase tracking-wider text-muted-foreground">
              {typeLabel}
            </span>
          )}
          {fileSrc && (
            <a
              href={fileSrc}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-[11px] text-primary hover:underline"
            >
              Open
              <ExternalLink className="h-3 w-3" />
            </a>
          )}
        </div>
      </div>

      <div className="relative min-h-[420px] flex-1 overflow-hidden bg-muted/30">
        {!invoice.source_file_id && (
          <div className="flex h-full min-h-[420px] flex-col items-center justify-center gap-2 px-6 text-center">
            <FileText className="h-10 w-10 text-muted-foreground/40" />
            <p className="text-[13px] text-muted-foreground">
              No source file attached to this invoice.
            </p>
          </div>
        )}
        {fileSrc && isImage && (
          <div className="h-full min-h-[420px] overflow-auto p-2">
            <img
              src={fileSrc}
              alt={displayName}
              className="mx-auto h-auto max-w-full object-contain"
              onError={() => setImgError(true)}
            />
          </div>
        )}
        {fileSrc && !isImage && (
          <iframe
            src={fileSrc}
            title={displayName}
            className="h-full min-h-[420px] w-full border-0"
          />
        )}
      </div>
    </div>
  );
}

function confidenceTone(
  c: number | undefined,
): "high" | "medium" | "low" | "none" {
  if (c == null) return "none";
  if (c >= 0.95) return "high";
  if (c >= 0.70) return "medium";
  return "low";
}

function FieldRow({
  label,
  value,
  confidence,
  onChange,
  type = "text",
  multiline = false,
  mono = false,
  placeholder,
}: {
  label: string;
  value: string;
  confidence?: number;
  onChange: (v: string) => void;
  type?: "text" | "date" | "number";
  multiline?: boolean;
  mono?: boolean;
  placeholder?: string;
}) {
  const tone = confidenceTone(confidence);
  const pct = confidence != null ? Math.round(confidence * 100) : null;

  return (
    <div
      className={cn(
        "rounded-md border px-3 py-2.5 transition-colors",
        tone === "low"
          ? "border-warning/40 bg-warning/8"
          : "border-transparent bg-secondary/40",
      )}
    >
      <div className="mb-1.5 flex items-center justify-between gap-2">
        <label className="flex items-center gap-1 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
          {tone === "low" && <AlertTriangle className="h-3 w-3 text-warning" />}
          {label}
        </label>
        {pct != null && <MiniConfidence pct={pct} tone={tone} />}
      </div>
      {multiline ? (
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          rows={2}
          className={cn(
            "w-full resize-none rounded border border-input bg-background px-2.5 py-1.5 text-[13px] leading-relaxed",
            "placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring/60",
            mono && "font-mono",
          )}
        />
      ) : (
        <input
          type={type}
          value={value}
          placeholder={placeholder}
          onChange={(e) => onChange(e.target.value)}
          className={cn(
            "w-full rounded border border-input bg-background px-2.5 py-1.5 text-[13px]",
            "placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring/60",
            mono && "font-mono",
          )}
        />
      )}
    </div>
  );
}

function FieldRowSelect({
  label,
  value,
  confidence,
  options,
  onChange,
}: {
  label: string;
  value: string;
  confidence?: number;
  options: string[];
  onChange: (v: string) => void;
}) {
  const tone = confidenceTone(confidence);
  const pct = confidence != null ? Math.round(confidence * 100) : null;

  return (
    <div
      className={cn(
        "rounded-md border px-3 py-2.5 transition-colors",
        tone === "low"
          ? "border-warning/40 bg-warning/8"
          : "border-transparent bg-secondary/40",
      )}
    >
      <div className="mb-1.5 flex items-center justify-between gap-2">
        <label className="flex items-center gap-1 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
          {tone === "low" && <AlertTriangle className="h-3 w-3 text-warning" />}
          {label}
        </label>
        {pct != null && <MiniConfidence pct={pct} tone={tone} />}
      </div>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded border border-input bg-background px-2.5 py-1.5 text-[13px] focus:outline-none focus:ring-1 focus:ring-ring/60"
      >
        <option value="">- select -</option>
        {options.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
    </div>
  );
}

function MiniConfidence({
  pct,
  tone,
}: {
  pct: number;
  tone: "high" | "medium" | "low" | "none";
}) {
  const barClass =
    tone === "high"
      ? "bg-success"
      : tone === "medium"
        ? "bg-warning"
        : "bg-destructive";

  return (
    <div className="flex items-center gap-1.5">
      <div className="h-1 w-12 overflow-hidden rounded-full bg-secondary">
        <div
          className={cn("h-full rounded-full transition-all", barClass)}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span
        className={cn(
          "tabular-nums text-[11px] font-medium",
          tone === "high"
            ? "text-success"
            : tone === "medium"
              ? "text-warning"
              : tone === "low"
                ? "text-destructive"
                : "text-muted-foreground",
        )}
      >
        {pct}%
      </span>
    </div>
  );
}

function OverallConfidence({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const tone = confidenceTone(value);
  return (
    <div className="flex items-center gap-1.5">
      <span className="text-[11px] text-muted-foreground">Overall:</span>
      <MiniConfidence pct={pct} tone={tone} />
    </div>
  );
}
