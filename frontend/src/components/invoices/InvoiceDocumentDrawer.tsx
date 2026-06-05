import { useState } from "react";
import { Trash2, X } from "lucide-react";
import { deleteInvoice } from "@/api/invoices";
import { useAuth } from "@/auth/AuthContext";
import { useAppDialog } from "@/components/dialogs/AppDialogProvider";
import { InvoiceDocumentEditor } from "@/components/invoices/InvoiceDocumentEditor";
import { InvoiceMatchedTransactionsSection } from "@/components/invoices/InvoiceMatchedTransactionsSection";
import { Button } from "@/components/ui-finance/Button";
import { StatusBadge } from "@/components/ui-finance/StatusBadge";
import { matchStatusLabel, reviewStatusLabel } from "@/lib/labels";
import { isAdminRole } from "@/types/auth";
import type { Invoice } from "@/types/invoice";

const EMAIL_UPLOAD_SOURCE = "outlook_email";

export function InvoiceDocumentDrawer({
  invoice,
  title = "Document detail",
  onClose,
  onSaved,
  onDeleted,
  onApproved,
}: {
  invoice: Invoice;
  title?: string;
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
              {title}
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
