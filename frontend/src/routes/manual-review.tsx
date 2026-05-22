import { PageHeader } from "@/components/ui-finance/PageHeader";
import { EmptyState } from "@/components/EmptyState";

export function ManualReviewPage() {
  return (
    <div>
      <PageHeader
        eyebrow="Workflow"
        title="Manual review"
        description="Resolve ambiguous matches between invoices and bank lines."
      />
      <EmptyState
        title="Manual review not available in this build"
        description="Use OCR review and purchase invoices until bank matching is live."
      />
    </div>
  );
}
