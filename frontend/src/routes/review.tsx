import { useCallback, useState } from "react";
import { ChevronLeft, ChevronRight, Loader2 } from "lucide-react";
import { PageHeader } from "@/components/ui-finance/PageHeader";
import { Button } from "@/components/ui-finance/Button";
import { EmptyState } from "@/components/EmptyState";
import { InvoiceDocumentEditor } from "@/components/invoices/InvoiceDocumentEditor";
import { useInvoices } from "@/hooks/useInvoices";

export function ReviewPage() {
  const { items, loading, error, reload } = useInvoices({
    review_status: "needs_review",
    limit: 100,
  });
  const [idx, setIdx] = useState(0);
  const inv = items[idx] ?? null;

  const goTo = useCallback(
    (next: number) => {
      setIdx(Math.max(0, Math.min(next, items.length - 1)));
    },
    [items.length],
  );

  if (!loading && items.length === 0) {
    return (
      <div>
        <PageHeader
          eyebrow="OCR review"
          title="Immediate review queue"
          description="Invoices below 95% OCR confidence or missing critical fields."
        />
        <EmptyState
          title="Review queue is empty"
          description="Documents at 95% confidence or higher can be checked and edited from Purchase invoices."
        />
      </div>
    );
  }

  return (
    <div className="flex flex-col">
      <PageHeader
        eyebrow={
          inv ? `OCR review · ${idx + 1} of ${items.length}` : "OCR review"
        }
        title="Immediate review queue"
        description="Review AI-extracted fields alongside the original document. Correct any errors, then approve."
        actions={
          items.length > 1 ? (
            <div className="flex items-center gap-1.5">
              <Button
                variant="secondary"
                size="sm"
                disabled={idx === 0}
                onClick={() => goTo(idx - 1)}
                icon={<ChevronLeft className="h-3.5 w-3.5" />}
              >
                Prev
              </Button>
              <Button
                variant="secondary"
                size="sm"
                disabled={idx >= items.length - 1}
                onClick={() => goTo(idx + 1)}
              >
                Next <ChevronRight className="h-3.5 w-3.5" />
              </Button>
            </div>
          ) : undefined
        }
      />

      {error && <p className="mb-4 text-[13px] text-destructive">{error}</p>}

      {loading || !inv ? (
        <div className="flex items-center gap-2 text-[13px] text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading review queue...
        </div>
      ) : (
        <div className="mt-4">
          <InvoiceDocumentEditor
            key={inv.id}
            invoice={inv}
            onApproved={async () => {
              await reload();
              goTo(Math.min(idx, items.length - 2));
            }}
            onSaved={() => void reload()}
          />
        </div>
      )}
    </div>
  );
}
