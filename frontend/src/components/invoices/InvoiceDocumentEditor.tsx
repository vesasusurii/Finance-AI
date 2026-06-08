import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, Check, Save, X } from "lucide-react";
import { LoadingSpinner } from "@/components/LoadingSpinner";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui-finance/Button";
import {
  approveInvoice,
  updateInvoice,
} from "@/api/invoices";
import { InvoiceFilePreview } from "@/components/invoices/InvoiceFilePreview";
import {
  formatCurrency,
  formatDate,
  formatOriginalCurrencySubtitle,
  hasForeignOriginalCurrency,
  isoDateFromInput,
  reviewReasonLabel,
} from "@/lib/labels";
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
  original_currency: string;
  account_details: string;
  internal_note_description: string;
  client_employee_related: string;
  category: string;
};

function toFormData(inv: Invoice): FormData {
  const originalCurrency =
    inv.original_currency ?? inv.currency ?? "EUR";

  return {
    name_of_company: inv.name_of_company ?? "",
    address_of_company: inv.address_of_company ?? "",
    invoice_date: inv.invoice_date ? formatDate(inv.invoice_date) : "",
    invoice_number: inv.invoice_number ?? "",
    amount: inv.amount != null ? String(inv.amount) : "",
    debt: inv.debt != null ? String(inv.debt) : "",
    original_currency: originalCurrency,
    account_details: inv.account_details ?? "",
    internal_note_description: inv.internal_note_description ?? "",
    client_employee_related: inv.client_employee_related ?? "Borek Solutions",
    category: inv.category ?? "",
  };
}

export function InvoiceDocumentEditor({
  invoice,
  onApproved,
  onSaved,
  embedded = false,
  onApprove,
  onReject,
  onRejected,
  approveLabel = "Approve",
  showReject = false,
  approveDisabled = false,
  hideApproveActions = false,
}: {
  invoice: Invoice;
  onApproved: () => void;
  onSaved: (invoice: Invoice) => void;
  /** When true, fits inside a drawer/panel instead of a full page. */
  embedded?: boolean;
  /** When set, called instead of POST /api/invoices/{id}/approve */
  onApprove?: () => Promise<void>;
  onReject?: () => Promise<void>;
  onRejected?: () => void;
  approveLabel?: string;
  showReject?: boolean;
  approveDisabled?: boolean;
  /** Hide approve/reject buttons (e.g. bank match uses a separate match action). */
  hideApproveActions?: boolean;
}) {
  const [form, setForm] = useState<FormData>(toFormData(invoice));
  const [saving, setSaving] = useState(false);
  const [approving, setApproving] = useState(false);
  const [rejecting, setRejecting] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setForm(toFormData(invoice));
    setSaveError(null);
    setSaved(false);
  }, [invoice]);

  const isDirty = JSON.stringify(form) !== JSON.stringify(toFormData(invoice));

  const handleField = useCallback((key: keyof FormData, value: string) => {
    setForm((prev) => ({ ...prev, [key]: value }));
    setSaved(false);
    setSaveError(null);
  }, []);

  const handleZeroOutDebt = useCallback(() => {
    handleField("debt", "0");
  }, [handleField]);

  const handleSave = async (): Promise<boolean> => {
    setSaving(true);
    setSaveError(null);
    const invoiceDateIso = form.invoice_date.trim()
      ? isoDateFromInput(form.invoice_date)
      : null;
    if (form.invoice_date.trim() && !invoiceDateIso) {
      setSaveError("Invoice date must be dd/mm/yyyy");
      setSaving(false);
      return false;
    }
    try {
      const updated = await updateInvoice(invoice.id, {
        name_of_company: form.name_of_company || null,
        address_of_company: form.address_of_company || null,
        invoice_date: invoiceDateIso,
        invoice_number: form.invoice_number || null,
        amount: form.amount ? Number(form.amount) : null,
        debt: form.debt ? Number(form.debt) : null,
        original_currency: form.original_currency || null,
        account_details: form.account_details || null,
        internal_note_description: form.internal_note_description || null,
        client_employee_related:
          form.client_employee_related.trim() || "Borek Solutions",
        category: form.category || null,
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
      if (onApprove) {
        await onApprove();
      } else {
        await approveInvoice(invoice.id);
      }
      onApproved();
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : "Approve failed");
      setApproving(false);
    }
  };

  const handleReject = async () => {
    if (!onReject) return;
    setRejecting(true);
    setSaveError(null);
    try {
      await onReject();
      onRejected?.();
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : "Reject failed");
      setRejecting(false);
    }
  };

  const conf = invoice.field_confidences ?? {};
  const overall = invoice.extraction_confidence
    ? Number(invoice.extraction_confidence)
    : null;

  return (
    <div
      className={cn(
        "grid grid-cols-1 gap-4 lg:grid-cols-2",
        embedded ? "min-h-[640px]" : "min-h-[calc(100vh-11rem)]",
      )}
    >
      {invoice.source_file_id ? (
        <InvoiceFilePreview
          invoiceId={invoice.id}
          displayName={
            invoice.source_filename ??
            invoice.invoice_number ??
            invoice.name_of_company ??
            `Invoice #${invoice.id}`
          }
          mimeType={invoice.source_mime_type}
          minHeightClass="min-h-[480px] lg:min-h-0"
        />
      ) : (
        <div className="flex min-h-[480px] flex-col overflow-hidden rounded-lg border border-border bg-card lg:min-h-0">
          <div className="flex h-full min-h-[420px] flex-col items-center justify-center gap-2 px-6 text-center">
            <p className="text-[13px] text-muted-foreground">
              No source file attached to this invoice.
            </p>
          </div>
        </div>
      )}

      <div className="flex min-h-[480px] flex-col overflow-hidden rounded-lg border border-border bg-card lg:min-h-0">
        <div className="flex shrink-0 items-center justify-between border-b border-border px-5 py-3">
          <div className="flex items-center gap-3">
            <span className="text-[13px] font-semibold text-foreground">
              Extracted data
            </span>
            {overall != null && <OverallConfidence value={overall} />}
          </div>
          {invoice.review_status === "manual_review" && (
            <span className="rounded-full bg-destructive/15 px-2.5 py-0.5 text-[11px] font-medium text-destructive">
              Manual review required
            </span>
          )}
          {invoice.review_status === "needs_review" && (
            <span className="rounded-full bg-warning/15 px-2.5 py-0.5 text-[11px] font-medium text-warning">
              Needs review
            </span>
          )}
        </div>

        {(invoice.review_reasons ?? []).length > 0 && (
          <div className="flex flex-wrap gap-1.5 border-b border-border px-5 py-2">
            {(invoice.review_reasons ?? []).map((reason) => (
              <span
                key={reason}
                className="rounded-full border border-border px-2 py-0.5 text-[10px] text-muted-foreground"
              >
                {reviewReasonLabel(reason)}
              </span>
            ))}
          </div>
        )}

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
                placeholder="dd/mm/yyyy"
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
                footer={
                  hasForeignOriginalCurrency(invoice)
                    ? formatOriginalCurrencySubtitle(invoice)
                    : null
                }
              />
              <FieldRow
                label="Remaining balance"
                value={form.debt}
                confidence={conf.debt}
                onChange={(v) => handleField("debt", v)}
                type="number"
                hideNumberSpinners
                inputAction={
                  <button
                    type="button"
                    onClick={handleZeroOutDebt}
                    disabled={form.debt === "0" || form.debt === ""}
                    title="Mark as fully paid"
                    className={cn(
                      "rounded px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide",
                      "text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground",
                      "disabled:pointer-events-none disabled:opacity-40",
                    )}
                  >
                    Zero out
                  </button>
                }
              />
            </div>
            <FieldRowSelect
              label="Currency"
              value={form.original_currency}
              confidence={conf.currency}
              options={CURRENCIES}
              onChange={(v) => handleField("original_currency", v)}
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

            {invoice.match_status === "partially_matched" && (
              <div className="rounded-md border border-border bg-surface-muted px-3 py-2">
                <p className="text-[12px] font-medium text-foreground">
                  Partially paid — split payment in progress
                </p>
                {invoice.debt != null && invoice.amount != null && (
                  <p className="mt-0.5 text-[11px] text-muted-foreground">
                    Remaining:{" "}
                    <span className="font-semibold tabular-nums text-foreground">
                      {formatCurrency(Number(invoice.debt), invoice.currency)}
                    </span>{" "}
                    of{" "}
                    <span className="tabular-nums">
                      {formatCurrency(Number(invoice.amount), invoice.currency)}
                    </span>
                  </p>
                )}
              </div>
            )}

            <div className="mt-2 border-t border-border pt-4">
              <div className="space-y-1">
                <label className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                  Paid by
                </label>
                <p className="min-h-[2rem] rounded-md border border-border bg-muted/30 px-3 py-2 text-[13px] text-foreground">
                  {invoice.paid_by?.trim() ? (
                    invoice.paid_by
                  ) : (
                    <span className="text-muted-foreground">
                      Set when you approve this invoice
                    </span>
                  )}
                </p>
              </div>
              {invoice.paid_at_date && (
                <p className="mt-2 text-[11px] text-muted-foreground">
                  {invoice.match_status === "partially_matched"
                    ? "First payment date: "
                    : "Paid at (date): "}
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
            <div className="flex flex-wrap justify-end gap-2">
              {!hideApproveActions && showReject && onReject && (
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={rejecting || approving}
                  onClick={handleReject}
                  icon={
                    rejecting ? (
                      <LoadingSpinner size="sm" />
                    ) : (
                      <X className="h-3.5 w-3.5" />
                    )
                  }
                >
                  Reject
                </Button>
              )}
              <Button
                variant="secondary"
                size="sm"
                disabled={!isDirty || saving}
                onClick={handleSave}
                icon={
                  saving ? (
                    <LoadingSpinner size="sm" />
                  ) : (
                    <Save className="h-3.5 w-3.5" />
                  )
                }
              >
                Save
              </Button>
              {!hideApproveActions && (
                <Button
                  variant="success"
                  size="sm"
                  disabled={
                    approving ||
                    approveDisabled ||
                    (!onApprove && invoice.review_status === "approved")
                  }
                  onClick={handleApprove}
                  icon={
                    approving ? (
                      <LoadingSpinner size="sm" />
                    ) : (
                      <Check className="h-3.5 w-3.5" />
                    )
                  }
                >
                  {approveLabel}
                </Button>
              )}
            </div>
          </div>
        </div>
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
  footer,
  headerAction,
  inputAction,
  hideNumberSpinners = false,
}: {
  label: string;
  value: string;
  confidence?: number;
  onChange: (v: string) => void;
  type?: "text" | "date" | "number";
  multiline?: boolean;
  mono?: boolean;
  placeholder?: string;
  footer?: string | null;
  headerAction?: React.ReactNode;
  inputAction?: React.ReactNode;
  hideNumberSpinners?: boolean;
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
        <div className="flex items-center gap-2">
          {headerAction}
          {pct != null && <MiniConfidence pct={pct} tone={tone} />}
        </div>
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
        <div className="relative">
          <input
            type={type}
            value={value}
            placeholder={placeholder}
            onChange={(e) => onChange(e.target.value)}
            className={cn(
              "w-full rounded border border-input bg-background px-2.5 py-1.5 text-[13px]",
              "placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring/60",
              mono && "font-mono",
              hideNumberSpinners &&
                type === "number" &&
                "[appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none",
              inputAction && "pr-[4.75rem]",
            )}
          />
          {inputAction ? (
            <div className="pointer-events-none absolute inset-y-0 right-1.5 flex items-center">
              <div className="pointer-events-auto">{inputAction}</div>
            </div>
          ) : null}
        </div>
      )}
      {footer ? (
        <p className="mt-1.5 text-[11px] text-muted-foreground tabular-nums">
          {footer}
        </p>
      ) : null}
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
