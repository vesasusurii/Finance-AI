import { useState } from "react";
import { ChevronLeft, ChevronRight, Check, FileText } from "lucide-react";
import { PageHeader } from "@/components/ui-finance/PageHeader";
import { Button } from "@/components/ui-finance/Button";
import { StatusBadge } from "@/components/ui-finance/StatusBadge";
import { ConfidenceIndicator } from "@/components/ui-finance/ConfidenceIndicator";
import { EmptyState } from "@/components/EmptyState";
import { useInvoices } from "@/hooks/useInvoices";
import { approveInvoice } from "@/api/invoices";
import {
  formatCurrency,
  formatDate,
  reviewStatusLabel,
} from "@/lib/labels";

export function ReviewPage() {
  const { items, loading, error, reload } = useInvoices({
    review_status: "needs_review",
    limit: 100,
  });
  const [idx, setIdx] = useState(0);
  const inv = items[idx];

  if (!loading && items.length === 0) {
    return (
      <div>
        <PageHeader
          eyebrow="OCR review"
          title="Document validation"
          description="Invoices that need human review after extraction."
        />
        <EmptyState
          title="Review queue is empty"
          description="Upload invoices or check the purchase invoices table. Rows with low confidence are routed here automatically."
        />
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        eyebrow={
          inv
            ? `OCR review · ${idx + 1} of ${items.length}`
            : "OCR review"
        }
        title="Document validation"
        description="Review extracted fields before matching. Approve when values are correct."
        actions={
          items.length > 1 ? (
            <div className="flex items-center gap-1">
              <Button
                variant="secondary"
                disabled={idx === 0}
                onClick={() => setIdx((i) => Math.max(0, i - 1))}
                icon={<ChevronLeft className="h-3.5 w-3.5" />}
              >
                Prev
              </Button>
              <Button
                variant="secondary"
                disabled={idx >= items.length - 1}
                onClick={() => setIdx((i) => Math.min(items.length - 1, i + 1))}
              >
                Next <ChevronRight className="h-3.5 w-3.5" />
              </Button>
            </div>
          ) : undefined
        }
      />

      {error && (
        <p className="mb-4 text-[13px] text-destructive">{error}</p>
      )}

      {loading || !inv ? (
        <p className="text-[13px] text-muted-foreground">Loading…</p>
      ) : (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
          <div className="rounded-lg border border-border bg-card p-6">
            <div className="mb-4 flex items-center gap-2">
              <FileText className="h-4 w-4 text-muted-foreground" />
              <span className="font-mono text-[12px]">
                {inv.invoice_number ?? "—"}
              </span>
            </div>
            <p className="text-[13px] text-muted-foreground">
              Original file preview is not wired yet. Use purchase invoices for
              full detail; source file id: {inv.source_file_id ?? "—"}.
            </p>
          </div>

          <div className="rounded-lg border border-border bg-card p-5">
            <div className="mb-4 flex flex-wrap items-center gap-2">
              <StatusBadge value={reviewStatusLabel(inv.review_status)} />
              <ConfidenceIndicator
                value={
                  inv.extraction_confidence != null
                    ? Number(inv.extraction_confidence)
                    : 0
                }
              />
            </div>
            <dl className="space-y-3 text-[13px]">
              <Row label="Company" value={inv.name_of_company} />
              <Row label="Date" value={formatDate(inv.invoice_date)} />
              <Row label="Invoice #" value={inv.invoice_number} mono />
              <Row
                label="Amount"
                value={formatCurrency(
                  inv.amount != null ? Number(inv.amount) : null,
                  inv.currency,
                )}
              />
              <Row label="Category" value={inv.category} />
              <Row label="IBAN" value={inv.account_details} mono />
            </dl>
            <div className="mt-6 flex justify-end gap-2">
              <Button
                variant="success"
                icon={<Check className="h-3.5 w-3.5" />}
                onClick={async () => {
                  await approveInvoice(inv.id);
                  await reload();
                  setIdx((i) => Math.min(i, Math.max(0, items.length - 2)));
                }}
              >
                Approve
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Row({
  label,
  value,
  mono,
}: {
  label: string;
  value: string | null | undefined;
  mono?: boolean;
}) {
  return (
    <div className="flex justify-between gap-4 border-b border-border pb-2 last:border-0">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className={mono ? "font-mono text-foreground" : "text-foreground"}>
        {value ?? "—"}
      </dd>
    </div>
  );
}
