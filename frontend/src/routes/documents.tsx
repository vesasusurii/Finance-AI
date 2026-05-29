import { useMemo, useState } from "react";
import { Trash2, X } from "lucide-react";
import { InvoiceDocumentEditor } from "@/components/invoices/InvoiceDocumentEditor";
import { PageHeader } from "@/components/ui-finance/PageHeader";
import { Button } from "@/components/ui-finance/Button";
import { DataTable, type Column } from "@/components/ui-finance/DataTable";
import { StatusBadge } from "@/components/ui-finance/StatusBadge";
import { ConfidenceIndicator } from "@/components/ui-finance/ConfidenceIndicator";
import { FilterBar } from "@/components/ui-finance/FilterBar";
import { useInvoices } from "@/hooks/useInvoices";
import { deleteInvoice } from "@/api/invoices";
import type { Invoice } from "@/types/invoice";
import {
  formatCurrency,
  formatDate,
  matchStatusLabel,
  reviewStatusLabel,
} from "@/lib/labels";

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
        description="Invoices you have uploaded. Open a row to edit, save, approve, or delete."
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
  const [busy, setBusy] = useState(false);
  const [drawerError, setDrawerError] = useState<string | null>(null);

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
      <aside className="absolute right-0 top-0 flex h-full w-full max-w-[1180px] flex-col border-l border-border bg-background">
        <div className="flex shrink-0 items-start justify-between border-b border-border px-5 py-4">
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

        <div className="flex shrink-0 flex-wrap items-center gap-2 border-b border-border px-5 py-3">
          <StatusBadge value={reviewStatusLabel(invoice.review_status)} />
          <StatusBadge value={matchStatusLabel(invoice.match_status)} />
        </div>

        {drawerError && (
          <p className="shrink-0 px-5 pt-3 text-[13px] text-destructive">{drawerError}</p>
        )}

        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
          <InvoiceDocumentEditor
            key={invoice.id}
            embedded
            invoice={invoice}
            onSaved={onSaved}
            onApproved={() => void onApproved()}
          />
        </div>

        <div className="flex shrink-0 items-center border-t border-border px-5 py-3">
          <Button
            variant="danger"
            size="sm"
            icon={<Trash2 className="h-3.5 w-3.5" />}
            disabled={busy}
            onClick={() => void handleDelete()}
          >
            Delete
          </Button>
        </div>
      </aside>
    </div>
  );
}
