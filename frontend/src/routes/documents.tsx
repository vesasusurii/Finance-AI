import { useEffect, useMemo, useState } from "react";
import { Download, Trash2, X } from "lucide-react";
import { downloadPurchaseInvoicesExcel } from "@/api/export";
import { InvoiceDocumentEditor } from "@/components/invoices/InvoiceDocumentEditor";
import { PageHeader } from "@/components/ui-finance/PageHeader";
import { Button } from "@/components/ui-finance/Button";
import { DataTable, type Column } from "@/components/ui-finance/DataTable";
import { TablePagination } from "@/components/ui-finance/TablePagination";
import { StatusBadge } from "@/components/ui-finance/StatusBadge";
import { ConfidenceIndicator } from "@/components/ui-finance/ConfidenceIndicator";
import { FilterBar } from "@/components/ui-finance/FilterBar";
import { useAuth } from "@/auth/AuthContext";
import { useInvoices } from "@/hooks/useInvoices";
import { deleteInvoice } from "@/api/invoices";
import { uploadProgressEvents } from "@/services/uploadProgressEvents";
import type { Invoice, InvoiceFilters, MatchStatus } from "@/types/invoice";
import { isAdminRole } from "@/types/auth";
import {
  formatCurrency,
  formatDate,
  matchStatusLabel,
  reviewStatusLabel,
} from "@/lib/labels";

const PAGE_SIZE = 10;

const selectClass =
  "h-8 rounded-md border border-input bg-background px-2 text-[12px] text-foreground";

type MatchFilter = "" | MatchStatus;
type ReviewFilter = "" | "pending" | "needs_review" | "approved";
type SortOrder = "invoice_date_desc" | "invoice_date_asc";

export function DocumentsPage() {
  const [selected, setSelected] = useState<Invoice | null>(null);
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [matchFilter, setMatchFilter] = useState<MatchFilter>("");
  const [reviewFilter, setReviewFilter] = useState<ReviewFilter>("");
  const [sortOrder, setSortOrder] = useState<SortOrder>("invoice_date_desc");
  const [page, setPage] = useState(1);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedSearch(search.trim()), 300);
    return () => window.clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    setPage(1);
  }, [debouncedSearch, matchFilter, reviewFilter, sortOrder]);

  const invoiceFilters = useMemo((): InvoiceFilters => {
    const filters: InvoiceFilters = {
      page,
      limit: PAGE_SIZE,
      sort: sortOrder,
    };
    if (debouncedSearch) filters.search = debouncedSearch;
    if (matchFilter) filters.match_status = matchFilter;
    if (reviewFilter) filters.review_status = reviewFilter;
    return filters;
  }, [page, debouncedSearch, matchFilter, reviewFilter, sortOrder]);

  const { items, total, loading, error, reload } = useInvoices(invoiceFilters);

  useEffect(() => {
    return uploadProgressEvents.subscribe((event) => {
      if (
        event.invoiceId &&
        (event.status === "completed" || event.status === "requires_review")
      ) {
        void reload();
      }
    });
  }, [reload]);

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
        actions={
          <Button
            variant="secondary"
            size="sm"
            icon={<Download className="h-3.5 w-3.5" />}
            disabled={exporting || loading}
            onClick={() => {
              setExporting(true);
              setExportError(null);
              void downloadPurchaseInvoicesExcel({
                ...(debouncedSearch ? { company: debouncedSearch } : {}),
                ...(matchFilter ? { match_status: matchFilter } : {}),
                ...(reviewFilter ? { review_status: reviewFilter } : {}),
              })
                .catch((e) => {
                  setExportError(
                    e instanceof Error ? e.message : "Excel download failed",
                  );
                })
                .finally(() => setExporting(false));
            }}
          >
            {exporting ? "Preparing…" : "Download as Excel file"}
          </Button>
        }
      />

      {error && (
        <p className="mb-4 text-[13px] text-destructive">{error}</p>
      )}
      {exportError && (
        <p className="mb-4 text-[13px] text-destructive">{exportError}</p>
      )}

      <FilterBar
        search={search}
        onSearch={setSearch}
        placeholder="Search by company, invoice number, description…"
      >
        <select
          value={matchFilter}
          onChange={(e) => setMatchFilter(e.target.value as MatchFilter)}
          className={selectClass}
          aria-label="Filter by match status"
        >
          <option value="">All match statuses</option>
          <option value="unmatched">Unmatched</option>
          <option value="matched">Matched</option>
        </select>
        <select
          value={reviewFilter}
          onChange={(e) => setReviewFilter(e.target.value as ReviewFilter)}
          className={selectClass}
          aria-label="Filter by review status"
        >
          <option value="">All review statuses</option>
          <option value="pending">Pending</option>
          <option value="needs_review">Needs review</option>
          <option value="approved">Approved</option>
        </select>
        <select
          value={sortOrder}
          onChange={(e) => setSortOrder(e.target.value as SortOrder)}
          className={selectClass}
          aria-label="Sort order"
        >
          <option value="invoice_date_desc">Date · newest first</option>
          <option value="invoice_date_asc">Date · oldest first</option>
        </select>
      </FilterBar>

      <div className="mb-3 flex items-center justify-between gap-2 text-[12px] text-muted-foreground">
        <span className="tabular-nums">
          {loading ? "Loading…" : `${total} invoice${total === 1 ? "" : "s"}`}
        </span>
      </div>

      <DataTable
        columns={columns}
        rows={items}
        onRowClick={setSelected}
        empty="No invoices match your filters."
      />

      <TablePagination
        page={page}
        pageSize={PAGE_SIZE}
        total={total}
        onPageChange={setPage}
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
  const { user } = useAuth();
  const [busy, setBusy] = useState(false);
  const [drawerError, setDrawerError] = useState<string | null>(null);

  const isSharedView =
    user != null &&
    !isAdminRole(user.role) &&
    invoice.uploaded_by !== user.user_id;

  const handleDelete = async () => {
    const label = invoice.invoice_number ?? `#${invoice.id}`;
    const confirmMessage = isSharedView
      ? `Remove invoice ${label} from your documents list? The original upload stays in the system for other users.`
      : `Delete invoice ${label}? This cannot be undone.`;
    if (!window.confirm(confirmMessage)) {
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
            {isSharedView ? "Remove from my list" : "Delete"}
          </Button>
        </div>
      </aside>
    </div>
  );
}
