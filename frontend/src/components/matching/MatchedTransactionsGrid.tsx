import { MatchedTransactionCard } from "./MatchedTransactionCard";
import {
  invoicePaymentMatchToItem,
  sortMatchedTransactionsByApproval,
} from "./matchedTransactionMappers";
import type { MatchedTransactionItem } from "./matchedTransactionTypes";
import type { InvoicePaymentMatch } from "@/types/match";

/** Sample data for standalone demos (≥3 matched examples). */
export const SAMPLE_MATCHED_TRANSACTIONS: MatchedTransactionItem[] = [
  {
    id: 1,
    companyName: "Nordic Supplies GmbH",
    invoiceAmount: 4820.5,
    invoiceCurrency: "EUR",
    invoiceNumber: "INV-2024-0842",
    invoiceDate: "2024-11-12",
    transactionDate: "2024-11-14",
    transactionAmount: 4820.5,
    transactionComment:
      "Nordic Supplies GmbH · INV-2024-0842 · SEPA credit transfer",
    detectedInvoiceNumbers: ["INV-2024-0842"],
    matchStatus: "matched",
    approvalStatus: "pending",
  },
  {
    id: 2,
    companyName: "Helios Analytics AG",
    invoiceAmount: 1299.0,
    invoiceCurrency: "EUR",
    invoiceNumber: "HA-99102",
    invoiceDate: "2024-10-28",
    transactionDate: "2024-10-30",
    transactionAmount: 1299.0,
    transactionComment: "Helios Analytics AG payment ref HA99102",
    detectedInvoiceNumbers: ["HA99102", "HA-99102"],
    matchStatus: "matched",
    approvalStatus: "approved",
  },
  {
    id: 3,
    companyName: "Blue Harbor Logistics",
    invoiceAmount: 760.25,
    invoiceCurrency: "EUR",
    invoiceNumber: "BHL-4401",
    invoiceDate: "2024-12-01",
    transactionDate: "2024-12-03",
    transactionAmount: 760.25,
    transactionComment:
      "Partial settlement — verify invoice BHL-4401 against statement line",
    detectedInvoiceNumbers: ["BHL-4401"],
    matchStatus: "needs_review",
    approvalStatus: "pending",
  },
];

export function MatchedTransactionsGrid({
  items,
  matches,
  busyMatchId = null,
  onApprove,
  onReject,
}: {
  /** Pre-mapped card items (e.g. SAMPLE_MATCHED_TRANSACTIONS). */
  items?: MatchedTransactionItem[];
  /** Live API matches; mapped internally when `items` is omitted. */
  matches?: InvoicePaymentMatch[];
  busyMatchId?: number | null;
  onApprove?: (matchId: number) => void;
  onReject?: (matchId: number) => void;
}) {
  const cards = sortMatchedTransactionsByApproval(
    items ?? (matches?.map(invoicePaymentMatchToItem) ?? []),
  );

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 lg:items-start">
      {cards.map((item) => (
        <div key={item.id} className="min-h-0 self-start">
          <MatchedTransactionCard
            item={item}
            busy={busyMatchId === item.id}
            onApprove={(id) => {
              console.log("[Matched] approve", id);
              onApprove?.(id);
            }}
            onReject={(id) => {
              console.log("[Matched] reject", id);
              onReject?.(id);
            }}
          />
        </div>
      ))}
    </div>
  );
}
