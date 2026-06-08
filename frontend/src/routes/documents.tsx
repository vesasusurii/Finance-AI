import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { useSearchParams } from "react-router-dom";
import { Download, Trash2, X } from "lucide-react";
import { downloadPurchaseInvoicesExcel } from "@/api/export";
import {
  LoadingSpinner,
  SectionLoadingSpinner,
} from "@/components/LoadingSpinner";
import { InvoiceDocumentEditor } from "@/components/invoices/InvoiceDocumentEditor";
import { InvoiceMatchedTransactionsSection } from "@/components/invoices/InvoiceMatchedTransactionsSection";
import { PageHeader } from "@/components/ui-finance/PageHeader";
import { Button } from "@/components/ui-finance/Button";
import { DataTable, type Column } from "@/components/ui-finance/DataTable";
import { TablePagination } from "@/components/ui-finance/TablePagination";
import { StatusBadge } from "@/components/ui-finance/StatusBadge";
import { ConfidenceIndicator } from "@/components/ui-finance/ConfidenceIndicator";
import { FilterBar } from "@/components/ui-finance/FilterBar";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useAuth } from "@/auth/AuthContext";
import { deleteInvoice, listInvoices } from "@/api/invoices";
import { useAppDialog } from "@/components/dialogs/AppDialogProvider";
import { uploadProgressEvents } from "@/services/uploadProgressEvents";
import type { Invoice } from "@/types/invoice";
import { isAdminRole } from "@/types/auth";
import {
  formatCurrency,
  formatDate,
  matchStatusLabel,
  reviewStatusLabel,
} from "@/lib/labels";
import { cn } from "@/lib/utils";

const PAGE_SIZE = 10;
const EMAIL_UPLOAD_SOURCE = "outlook_email";

type DocumentsTab = "all" | "email-ingest" | "needs-review" | "unmatched";

const DOCUMENT_TABS: { id: DocumentsTab; label: string }[] = [
  { id: "all", label: "All invoices" },
  { id: "email-ingest", label: "Email ingest" },
  { id: "needs-review", label: "Needs review" },
  { id: "unmatched", label: "Unmatched" },
];

type SortOrder = "invoice_date_desc" | "invoice_date_asc";

function isDocumentsTab(value: string | null): value is DocumentsTab {
  return DOCUMENT_TABS.some((tab) => tab.id === value);
}

function tabFilters(tab: DocumentsTab): {
  upload_source?: string;
  review_status?: string;
  match_status?: string;
} {
  switch (tab) {
    case "email-ingest":
      return { upload_source: EMAIL_UPLOAD_SOURCE };
    case "needs-review":
      return { review_status: "needs_review" };
    case "unmatched":
      return { match_status: "unmatched" };
    default:
      return {};
  }
}

function uploadSourceLabel(source: string | null | undefined): string {
  if (source === EMAIL_UPLOAD_SOURCE) return "Email";
  return "Portal";
}

export function DocumentsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [activeTab, setActiveTab] = useState<DocumentsTab>(() => {
    const tab = searchParams.get("tab");
    return isDocumentsTab(tab) ? tab : "all";
  });
  const [selected, setSelected] = useState<Invoice | null>(null);
  const [search, setSearch] = useState(() => searchParams.get("search") ?? "");
  const [debouncedSearch, setDebouncedSearch] = useState(
    () => searchParams.get("search")?.trim() ?? "",
  );
  const [sortOrder, setSortOrder] = useState<SortOrder>("invoice_date_desc");
  const [page, setPage] = useState(1);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const [loadingTab, setLoadingTab] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [items, setItems] = useState<Invoice[]>([]);
  const [total, setTotal] = useState(0);
  const [tabTotals, setTabTotals] = useState<Record<DocumentsTab, number>>({
    all: 0,
    "email-ingest": 0,
    "needs-review": 0,
    unmatched: 0,
  });

  useEffect(() => {
    const tab = searchParams.get("tab");
    if (isDocumentsTab(tab)) setActiveTab(tab);
    const q = searchParams.get("search");
    if (q !== null) {
      setSearch(q);
      setDebouncedSearch(q.trim());
    }
  }, [searchParams]);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedSearch(search.trim()), 300);
    return () => window.clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    const trimmed = debouncedSearch;
    const current = searchParams.get("search")?.trim() ?? "";
    if (trimmed === current) return;
    const next = new URLSearchParams(searchParams);
    if (trimmed) {
      next.set("search", trimmed);
    } else {
      next.delete("search");
    }
    setSearchParams(next, { replace: true });
  }, [debouncedSearch, searchParams, setSearchParams]);

  useEffect(() => {
    setPage(1);
  }, [debouncedSearch, sortOrder, activeTab]);

  const sharedFilters = useMemo(
    () => ({
      ...(debouncedSearch ? { search: debouncedSearch } : {}),
      sort: sortOrder,
    }),
    [debouncedSearch, sortOrder],
  );

  const loadTotals = useCallback(async () => {
    const countFilters = debouncedSearch ? { search: debouncedSearch } : {};
    const totals = {} as Record<DocumentsTab, number>;
    for (const tab of DOCUMENT_TABS) {
      const res = await listInvoices({
        ...countFilters,
        ...tabFilters(tab.id),
        page: 1,
        limit: 1,
      });
      totals[tab.id] = res.total;
    }
    setTabTotals(totals);
  }, [debouncedSearch]);

  const loadActiveTab = useCallback(async () => {
    setLoadingTab(true);
    try {
      const res = await listInvoices({
        ...sharedFilters,
        ...tabFilters(activeTab),
        page,
        limit: PAGE_SIZE,
      });
      setItems(res.items);
      setTotal(res.total);
      setTabTotals((prev) => ({ ...prev, [activeTab]: res.total }));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load invoices");
      setItems([]);
      setTotal(0);
    } finally {
      setLoadingTab(false);
    }
  }, [activeTab, page, sharedFilters]);

  const reload = useCallback(async () => {
    await loadActiveTab();
    await loadTotals();
  }, [loadTotals, loadActiveTab]);

  useEffect(() => {
    void loadTotals().catch(() => {
      /* tab counts are optional */
    });
  }, [loadTotals]);

  useEffect(() => {
    void loadActiveTab();
  }, [loadActiveTab]);

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

  const onTabChange = (tab: string) => {
    if (!isDocumentsTab(tab)) return;
    setActiveTab(tab);
    const next = new URLSearchParams(searchParams);
    if (tab === "all") {
      next.delete("tab");
    } else {
      next.set("tab", tab);
    }
    setSearchParams(next);
  };

  const columns: Column<Invoice>[] = useMemo(() => {
    const base: Column<Invoice>[] = [
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
    ];

    if (activeTab === "all" || activeTab === "email-ingest") {
      base.push({
        key: "source",
        header: "Source",
        cell: (r) => (
          <span className="text-[12px] text-muted-foreground">
            {uploadSourceLabel(r.upload_source)}
          </span>
        ),
      });
    }

    if (activeTab === "email-ingest") {
      base.push(
        {
          key: "sender",
          header: "Sender",
          cell: (r) => (
            <div>
              <div className="text-[12px] text-foreground">
                {r.ingest_sender_email ?? "—"}
              </div>
              {r.ingest_sender_name ? (
                <div className="text-[11px] text-muted-foreground">
                  {r.ingest_sender_name}
                </div>
              ) : null}
            </div>
          ),
        },
        {
          key: "subject",
          header: "Subject",
          cell: (r) => (
            <span
              className="line-clamp-2 max-w-[220px] text-[12px] text-muted-foreground"
              title={r.ingest_email_subject ?? undefined}
            >
              {r.ingest_email_subject ?? "—"}
            </span>
          ),
        },
      );
    }

    base.push(
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
    );

    return base;
  }, [activeTab]);

  const emptyMessages: Record<DocumentsTab, string> = {
    all: "No invoices match your filters.",
    "email-ingest": "No invoices from email ingest yet. Connect n8n to Outlook to import attachments.",
    "needs-review": "No invoices need review.",
    unmatched: "No unmatched invoices.",
  };

  return (
    <div>
      <PageHeader
        eyebrow="Database"
        title="Purchase invoices"
        actions={
          <Button
            variant="secondary"
            size="sm"
            icon={
              exporting ? (
                <LoadingSpinner size="sm" />
              ) : (
                <Download className="h-3.5 w-3.5" />
              )
            }
            disabled={exporting || loadingTab}
            onClick={() => {
              setExporting(true);
              setExportError(null);
              void downloadPurchaseInvoicesExcel({
                ...(debouncedSearch ? { company: debouncedSearch } : {}),
                ...tabFilters(activeTab),
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
          value={sortOrder}
          onChange={(e) => setSortOrder(e.target.value as SortOrder)}
          className="h-8 rounded-md border border-input bg-background px-2 text-[12px] text-foreground"
          aria-label="Sort order"
        >
          <option value="invoice_date_desc">Date · newest first</option>
          <option value="invoice_date_asc">Date · oldest first</option>
        </select>
      </FilterBar>

      <Tabs value={activeTab} onValueChange={onTabChange} className="mt-4">
        <TabsList className="h-auto w-full flex-wrap justify-start gap-1 rounded-lg border border-border bg-card p-1">
          {DOCUMENT_TABS.map((tab) => (
            <TabsTrigger
              key={tab.id}
              value={tab.id}
              className={cn(
                "h-8 rounded-md px-3 text-[12px] font-medium text-muted-foreground",
                "data-[state=active]:bg-primary data-[state=active]:text-primary-foreground",
              )}
            >
              {tab.label}
              <span className="ml-1.5 rounded bg-background/20 px-1.5 py-0.5 text-[10px] tabular-nums">
                {tabTotals[tab.id]}
              </span>
            </TabsTrigger>
          ))}
        </TabsList>

        <TabPanel loading={loadingTab}>
          {DOCUMENT_TABS.map((tab) => (
            <TabsContent key={tab.id} value={tab.id} className="mt-4">
              <DataTable
                columns={columns}
                rows={items}
                onRowClick={setSelected}
                empty={emptyMessages[tab.id]}
              />
              <TablePagination
                page={page}
                pageSize={PAGE_SIZE}
                total={total}
                onPageChange={setPage}
              />
            </TabsContent>
          ))}
        </TabPanel>
      </Tabs>

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

function TabPanel({
  loading,
  children,
}: {
  loading: boolean;
  children: ReactNode;
}) {
  if (loading) {
    return (
      <div className="min-h-[200px]">
        <SectionLoadingSpinner />
      </div>
    );
  }

  return <div className="min-h-[200px]">{children}</div>;
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
  const { confirm } = useAppDialog();
  const [busy, setBusy] = useState(false);
  const [drawerError, setDrawerError] = useState<string | null>(null);

  const isSharedView =
    user != null &&
    !isAdminRole(user.role) &&
    invoice.uploaded_by !== user.user_id;

  const handleDelete = async () => {
    const label = invoice.invoice_number ?? `#${invoice.id}`;
    const ok = await confirm({
      title: isSharedView ? "Remove from your list" : "Delete invoice",
      description: isSharedView
        ? `Remove invoice ${label} from your documents list? The original upload stays in the system for other users.`
        : `Delete invoice ${label}? This cannot be undone.`,
      confirmLabel: isSharedView ? "Remove" : "Delete",
      variant: "destructive",
    });
    if (!ok) return;
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
          {invoice.upload_source === EMAIL_UPLOAD_SOURCE ? (
            <span className="text-[11px] text-muted-foreground">Email ingest</span>
          ) : null}
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
          <InvoiceMatchedTransactionsSection invoice={invoice} />
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
