import { useEffect, useMemo, useState } from "react";
import { Download, X, Check, Trash2, Save } from "lucide-react";
import { PageHeader } from "@/components/ui-finance/PageHeader";
import { Button } from "@/components/ui-finance/Button";
import { DataTable, type Column } from "@/components/ui-finance/DataTable";
import { StatusBadge } from "@/components/ui-finance/StatusBadge";
import { ConfidenceIndicator } from "@/components/ui-finance/ConfidenceIndicator";
import { FilterBar } from "@/components/ui-finance/FilterBar";
import { InvoiceDocumentEditor } from "@/components/invoices/InvoiceDocumentEditor";
import { useInvoices } from "@/hooks/useInvoices";
import {
  approveInvoice,
  deleteInvoice,
  updateInvoice,
} from "@/api/invoices";
import { downloadPurchaseInvoicesExcel } from "@/api/export";
import type { Invoice } from "@/types/invoice";
import {
  formatCurrency,
  formatDate,
  matchStatusLabel,
  reviewStatusLabel,
} from "@/lib/labels";

type FormState = {
  name_of_company: string;
  address_of_company: string;
  invoice_date: string;
  invoice_number: string;
  amount: string;
  currency: string;
  account_details: string;
  internal_note_description: string;
  category: string;
  client_employee_related: string;
  paid_by: string;
  fixed_status: string;
};

function invoiceToForm(inv: Invoice): FormState {
  return {
    name_of_company: inv.name_of_company ?? "",
    address_of_company: inv.address_of_company ?? "",
    invoice_date: inv.invoice_date?.slice(0, 10) ?? "",
    invoice_number: inv.invoice_number ?? "",
    amount: inv.amount != null ? String(inv.amount) : "",
    currency: inv.currency ?? "EUR",
    account_details: inv.account_details ?? "",
    internal_note_description: inv.internal_note_description ?? "",
    category: inv.category ?? "",
    client_employee_related: inv.client_employee_related ?? "",
    paid_by: inv.paid_by ?? "",
    fixed_status: inv.fixed_status ?? "",
  };
}

export function DocumentsPage() {
  const [selected, setSelected] = useState<Invoice | null>(null);
  const [search, setSearch] = useState("");
  const { items, total, loading, error, reload } = useInvoices({ limit: 100 });

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    if (!q) return items;
    return items.filter((i) =>
      [i.name_of_company, i.invoice_number, i.internal_note_description]
        .filter(Boolean)
        .some((v) => String(v).toLowerCase().includes(q)),
    );
  }, [items, search]);

  const columns: Column<Invoice>[] = [
    {
      key: "date",
      header: "Date",
      cell: (r) => (
        <span className="tabular-nums">{formatDate(r.invoice_date)}</span>
      ),
    },
    {
      key: "company",
      header: "Company",
      cell: (r) => (
        <div>
          <div className="font-medium text-foreground">
            {r.name_of_company ?? "—"}
          </div>
          <div className="text-[11px] text-muted-foreground">
            {r.address_of_company ?? ""}
          </div>
        </div>
      ),
    },
    {
      key: "num",
      header: "Invoice #",
      cell: (r) => (
        <span className="font-mono text-[12px] text-foreground">
          {r.invoice_number ?? "—"}
        </span>
      ),
    },
    {
      key: "amount",
      header: "Amount",
      align: "right",
      cell: (r) => (
        <span className="font-medium">
          {formatCurrency(
            r.amount != null ? Number(r.amount) : null,
            r.currency,
          )}
        </span>
      ),
    },
    {
      key: "review",
      header: "Review",
      cell: (r) => <StatusBadge value={reviewStatusLabel(r.review_status)} />,
    },
    {
      key: "match",
      header: "Match",
      cell: (r) => <StatusBadge value={matchStatusLabel(r.match_status)} />,
    },
    {
      key: "conf",
      header: "Confidence",
      cell: (r) => (
        <ConfidenceIndicator
          value={
            r.extraction_confidence != null
              ? Number(r.extraction_confidence)
              : 0
          }
        />
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        eyebrow="Database"
        title="Purchase invoices"
        description="Invoices extracted from uploads. Open a row to edit, save, approve, or delete."
        actions={
          <Button
            variant="secondary"
            icon={<Download className="h-3.5 w-3.5" />}
            onClick={() => void downloadPurchaseInvoicesExcel()}
          >
            Export Excel
          </Button>
        }
      />

      {error && (
        <p className="mb-4 text-[13px] text-destructive">{error}</p>
      )}

      <FilterBar
        search={search}
        onSearch={setSearch}
        placeholder="Search by company, invoice number, description…"
        right={
          <span className="text-[12px] text-muted-foreground tabular-nums">
            {loading ? "Loading…" : `${filtered.length} of ${total}`}
          </span>
        }
      />

      <DataTable
        columns={columns}
        rows={filtered}
        onRowClick={setSelected}
      />

      {selected && (
        <DocumentDrawer
          invoice={selected}
          onClose={() => setSelected(null)}
          onSaved={async (updated) => {
            await reload();
            setSelected(updated);
          }}
          onDeleted={async () => {
            await reload();
            setSelected(null);
          }}
          onApproved={async () => {
            await reload();
            setSelected(null);
          }}
        />
      )}
    </div>
  );
}

function DocumentDrawer({
  invoice,
  onClose,
  onSaved,
  onDeleted,
  onApproved,
}: {
  invoice: Invoice;
  onClose: () => void;
  onSaved: (updated: Invoice) => void;
  onDeleted: () => void;
  onApproved: () => Promise<void>;
}) {
  const [form, setForm] = useState<FormState>(() => invoiceToForm(invoice));
  const [busy, setBusy] = useState(false);
  const [drawerError, setDrawerError] = useState<string | null>(null);

  useEffect(() => {
    setForm(invoiceToForm(invoice));
    setDrawerError(null);
  }, [invoice]);

  const set = (key: keyof FormState, value: string) => {
    setForm((f) => ({ ...f, [key]: value }));
  };

  const handleSave = async () => {
    setBusy(true);
    setDrawerError(null);
    try {
      const updated = await updateInvoice(invoice.id, {
        name_of_company: form.name_of_company || null,
        address_of_company: form.address_of_company || null,
        invoice_date: form.invoice_date || null,
        invoice_number: form.invoice_number || null,
        amount: form.amount ? Number(form.amount) : null,
        currency: form.currency || null,
        account_details: form.account_details || null,
        internal_note_description: form.internal_note_description || null,
        category: form.category || null,
        client_employee_related: form.client_employee_related || null,
        paid_by: form.paid_by || null,
        fixed_status: form.fixed_status || null,
      } as Partial<Invoice>);
      onSaved(updated);
    } catch (e) {
      setDrawerError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async () => {
    if (
      !window.confirm(
        `Delete invoice ${invoice.invoice_number ?? `#${invoice.id}`}? This cannot be undone.`,
      )
    ) {
      return;
    }
    setBusy(true);
    setDrawerError(null);
    try {
      await deleteInvoice(invoice.id);
      onDeleted();
    } catch (e) {
      setDrawerError(e instanceof Error ? e.message : "Delete failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50">
      <div className="absolute inset-0 bg-foreground/20" onClick={onClose} />
      <aside className="absolute right-0 top-0 flex h-full w-full max-w-[1180px] flex-col border-l border-border bg-background shadow-xl">
        <div className="flex items-start justify-between border-b border-border px-5 py-4">
          <div>
            <div className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
              Document detail
            </div>
            <div className="mt-0.5 font-mono text-[13px] font-medium text-foreground">
              {invoice.source_filename ?? invoice.invoice_number ?? "Invoice"}
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="grid h-7 w-7 place-items-center rounded-md text-muted-foreground hover:bg-secondary hover:text-foreground"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto px-5 py-5">
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge value={reviewStatusLabel(invoice.review_status)} />
            <StatusBadge value={matchStatusLabel(invoice.match_status)} />
            <ConfidenceIndicator
              value={
                invoice.extraction_confidence != null
                  ? Number(invoice.extraction_confidence)
                  : 0
              }
            />
          </div>

          {drawerError && (
            <p className="text-[13px] text-destructive">{drawerError}</p>
          )}

          <EditableField
            label="Company name"
            value={form.name_of_company}
            onChange={(v) => set("name_of_company", v)}
          />
          <EditableField
            label="Address"
            value={form.address_of_company}
            onChange={(v) => set("address_of_company", v)}
          />
          <EditableField
            label="Invoice date"
            value={form.invoice_date}
            onChange={(v) => set("invoice_date", v)}
            type="date"
          />
          <EditableField
            label="Invoice number"
            value={form.invoice_number}
            onChange={(v) => set("invoice_number", v)}
            mono
          />
          <div className="grid grid-cols-2 gap-3">
            <EditableField
              label="Amount"
              value={form.amount}
              onChange={(v) => set("amount", v)}
            />
            <EditableField
              label="Currency"
              value={form.currency}
              onChange={(v) => set("currency", v)}
            />
          </div>
          <EditableField
            label="Account details"
            value={form.account_details}
            onChange={(v) => set("account_details", v)}
            mono
          />
          <EditableField
            label="Description"
            value={form.internal_note_description}
            onChange={(v) => set("internal_note_description", v)}
            textarea
          />
          <EditableField
            label="Category"
            value={form.category}
            onChange={(v) => set("category", v)}
          />
          <EditableField
            label="Related to"
            value={form.client_employee_related}
            onChange={(v) => set("client_employee_related", v)}
          />
          <EditableField
            label="Paid by"
            value={form.paid_by}
            onChange={(v) => set("paid_by", v)}
          />
          <EditableField
            label="Fixed / Not fixed"
            value={form.fixed_status}
            onChange={(v) => set("fixed_status", v)}
          />
          <ReadOnlyField
            label="Paid at (date)"
            value={formatDate(invoice.paid_at_date)}
            hint="Set by bank matching only"
          />
        </div>

        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border px-5 py-3">
          <Button
            variant="danger"
            size="sm"
            icon={<Trash2 className="h-3.5 w-3.5" />}
            disabled={busy}
            onClick={() => void handleDelete()}
          >
            Delete
          </Button>
          <div className="flex gap-2">
            <Button variant="secondary" onClick={onClose} disabled={busy}>
              Close
            </Button>
            <Button
              variant="primary"
              icon={<Save className="h-3.5 w-3.5" />}
              disabled={busy}
              onClick={() => void handleSave()}
            >
              Save
            </Button>
            <Button
              variant="success"
              icon={<Check className="h-3.5 w-3.5" />}
              disabled={busy || invoice.review_status === "approved"}
              onClick={async () => {
                setBusy(true);
                try {
                  await onApproved();
                } finally {
                  setBusy(false);
                }
              }}
            >
              Approve
            </Button>
          </div>
        </div>
      </aside>
    </div>
  );
}

function EditableField({
  label,
  value,
  onChange,
  textarea,
  mono,
  type = "text",
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  textarea?: boolean;
  mono?: boolean;
  type?: string;
}) {
  const cls =
    "w-full rounded-md border border-input bg-background px-3 py-2 text-[13px] text-foreground focus:border-ring focus:outline-none " +
    (mono ? "font-mono" : "");
  return (
    <label className="block">
      <div className="mb-1 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
        {label}
      </div>
      {textarea ? (
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          rows={2}
          className={cls}
        />
      ) : (
        <input
          type={type}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className={cls}
        />
      )}
    </label>
  );
}

function ReadOnlyField({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div>
      <div className="mb-1 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
        {label}
      </div>
      <div className="rounded-md border border-dashed border-border bg-surface-muted px-3 py-2 text-[13px] tabular-nums text-muted-foreground">
        {value}
      </div>
      {hint && (
        <p className="mt-1 text-[11px] text-muted-foreground">{hint}</p>
      )}
    </div>
  );
}
