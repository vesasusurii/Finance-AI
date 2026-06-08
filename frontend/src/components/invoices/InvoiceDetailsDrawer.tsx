import { InvoiceFilePreview } from "@/components/invoices/InvoiceFilePreview";
import { ConfidenceIndicator } from "@/components/ui-finance/ConfidenceIndicator";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { formatCurrency, formatDate } from "@/lib/labels";
import type { UploadQueueItem } from "@/types/uploadQueue";
import { InvoiceStatusBadge } from "./InvoiceStatusBadge";

function validationRows(item: UploadQueueItem) {
  const invoice = item.invoice;
  if (!invoice?.field_confidences) {
    return [];
  }
  return Object.entries(invoice.field_confidences)
    .sort(([, a], [, b]) => a - b)
    .map(([field, score]) => ({
      field,
      score,
      ok: score >= 0.75,
    }));
}

export function InvoiceDetailsDrawer({
  item,
  open,
  onOpenChange,
}: {
  item: UploadQueueItem | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  if (!item) return null;

  const invoice = item.invoice;
  const validation = validationRows(item);
  const previewInvoiceId = item.invoiceId;

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full overflow-y-auto sm:max-w-xl">
        <SheetHeader>
          <SheetTitle>{item.fileName}</SheetTitle>
          <SheetDescription>
            Processing details and extracted invoice data
          </SheetDescription>
        </SheetHeader>

        <div className="mt-6 space-y-6">
          <section>
            <p className="mb-2 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
              Status
            </p>
            <div className="flex flex-wrap items-center gap-3">
              <InvoiceStatusBadge status={item.status} />
              {item.confidence != null && (
                <ConfidenceIndicator value={item.confidence} />
              )}
            </div>
            {item.error && (
              <p className="mt-3 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-[13px] text-destructive">
                {item.error}
              </p>
            )}
          </section>

          {!invoice &&
            (item.status === "ocr_processing" ||
              item.status === "validating" ||
              item.status === "uploading") && (
              <p className="rounded-lg border border-border bg-surface-muted px-4 py-3 text-[13px] text-muted-foreground">
                Extraction is in progress. This panel will show company, invoice
                number, and amounts when OCR finishes.
              </p>
            )}

          {invoice && (
            <section>
              <p className="mb-2 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                OCR extracted data
              </p>
              <dl className="grid gap-2 rounded-lg border border-border bg-surface-muted p-4 text-[13px]">
                <div className="grid grid-cols-[120px_1fr] gap-2">
                  <dt className="text-muted-foreground">Company</dt>
                  <dd className="text-foreground">{invoice.name_of_company ?? "—"}</dd>
                </div>
                <div className="grid grid-cols-[120px_1fr] gap-2">
                  <dt className="text-muted-foreground">Invoice #</dt>
                  <dd className="font-mono text-foreground">
                    {invoice.invoice_number ?? "—"}
                  </dd>
                </div>
                <div className="grid grid-cols-[120px_1fr] gap-2">
                  <dt className="text-muted-foreground">Date</dt>
                  <dd className="text-foreground">{formatDate(invoice.invoice_date)}</dd>
                </div>
                <div className="grid grid-cols-[120px_1fr] gap-2">
                  <dt className="text-muted-foreground">Amount</dt>
                  <dd className="text-foreground">
                    {formatCurrency(
                      invoice.amount != null ? Number(invoice.amount) : null,
                      invoice.currency,
                    )}
                  </dd>
                </div>
                <div className="grid grid-cols-[120px_1fr] gap-2">
                  <dt className="text-muted-foreground">Category</dt>
                  <dd className="text-foreground">{invoice.category ?? "—"}</dd>
                </div>
              </dl>
            </section>
          )}

          {validation.length > 0 && (
            <section>
              <p className="mb-2 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                Validation results
              </p>
              <ul className="space-y-2 rounded-lg border border-border bg-card p-4">
                {validation.map((row) => (
                  <li
                    key={row.field}
                    className="flex items-center justify-between text-[13px]"
                  >
                    <span className="text-foreground">{row.field}</span>
                    <span
                      className={
                        row.ok ? "text-success" : "text-warning"
                      }
                    >
                      {Math.round(row.score * 100)}%
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          <section>
            <p className="mb-2 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
              Processing logs
            </p>
            <ul className="max-h-48 space-y-2 overflow-y-auto rounded-lg border border-border bg-card p-4">
              {item.logs.map((log, index) => (
                <li key={`${log.at}-${index}`} className="text-[12px]">
                  <span className="tabular-nums text-muted-foreground">
                    {new Date(log.at).toLocaleTimeString()}
                  </span>
                  <span className="mx-2 text-muted-foreground">·</span>
                  <span className="text-foreground">{log.message}</span>
                </li>
              ))}
            </ul>
          </section>

          {previewInvoiceId && (
            <section>
              <p className="mb-2 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                Original invoice preview
              </p>
              <InvoiceFilePreview
                invoiceId={previewInvoiceId}
                displayName={item.fileName}
                mimeType={invoice?.source_mime_type}
              />
            </section>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
