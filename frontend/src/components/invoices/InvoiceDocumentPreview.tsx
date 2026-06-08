import { useEffect, useState } from "react";
import { LoadingSpinner } from "@/components/LoadingSpinner";
import { InvoiceFilePreview } from "@/components/invoices/InvoiceFilePreview";
import { getInvoice } from "@/api/invoices";
import { InvoiceAmountDisplay } from "@/components/invoices/InvoiceAmountDisplay";
import { formatDate } from "@/lib/labels";
import type { Invoice } from "@/types/invoice";

export function InvoiceDocumentPreview({
  invoiceId,
  invoice: initialInvoice,
}: {
  invoiceId: number;
  /** Optional seed from list/review API; refreshed via GET /api/invoices/{id}. */
  invoice?: Invoice;
}) {
  const [invoice, setInvoice] = useState<Invoice | null>(initialInvoice ?? null);
  const [loading, setLoading] = useState(!initialInvoice);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    void getInvoice(invoiceId)
      .then((full) => {
        if (!cancelled) setInvoice(full);
      })
      .catch(() => {
        if (!cancelled && initialInvoice) setInvoice(initialInvoice);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [invoiceId, initialInvoice]);

  if (loading && !invoice) {
    return (
      <div className="rounded-lg border border-border bg-card">
        <LoadingSpinner
          centered
          size="lg"
          className="text-muted-foreground"
          containerClassName="min-h-[960px] py-0"
        />
      </div>
    );
  }

  if (!invoice) {
    return (
      <div className="flex min-h-[960px] items-center justify-center rounded-lg border border-border bg-card px-6 text-center">
        <p className="text-[13px] text-muted-foreground">
          Could not load invoice details.
        </p>
      </div>
    );
  }

  const displayName =
    invoice.source_filename ??
    invoice.invoice_number ??
    invoice.name_of_company ??
    `Invoice #${invoice.id}`;

  const canPreview = Boolean(invoice.source_file_id);

  return (
    <div className="flex min-h-[960px] flex-col overflow-hidden rounded-lg border border-border bg-card">
      <div className="shrink-0 border-b border-border px-4 py-3">
        <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <dt className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
              Company
            </dt>
            <dd className="mt-0.5 text-[13px] font-medium text-foreground">
              {invoice.name_of_company?.trim() || "—"}
            </dd>
          </div>
          <div>
            <dt className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
              Invoice date
            </dt>
            <dd className="mt-0.5 tabular-nums text-[13px] font-medium text-foreground">
              {formatDate(invoice.invoice_date)}
            </dd>
          </div>
          <div>
            <dt className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
              Value
            </dt>
            <dd className="mt-0.5">
              <InvoiceAmountDisplay invoice={invoice} />
            </dd>
          </div>
          <div>
            <dt className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
              Invoice number
            </dt>
            <dd className="mt-0.5 font-mono text-[13px] font-medium text-foreground">
              {invoice.invoice_number?.trim() || "—"}
            </dd>
          </div>
        </dl>
      </div>

      <div className="min-h-[960px] flex-1">
        {canPreview ? (
          <InvoiceFilePreview
            invoiceId={invoice.id}
            displayName={displayName}
            mimeType={invoice.source_mime_type}
            minHeightClass="min-h-[960px]"
            className="h-[960px] rounded-none border-0 border-t border-border"
          />
        ) : (
          <div className="flex h-[960px] flex-col items-center justify-center gap-2 px-6 text-center">
            <p className="text-[13px] text-muted-foreground">
              No source file attached to this invoice.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
