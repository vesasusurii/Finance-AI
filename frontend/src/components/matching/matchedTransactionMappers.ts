import type { InvoicePaymentMatch } from "@/types/match";
import type {
  MatchedTransactionItem,
  MatchApprovalStatus,
  MatchReconciliationStatus,
} from "./matchedTransactionTypes";

function approvalStatusFromMatch(status: string): MatchApprovalStatus {
  if (status === "approved") return "approved";
  if (status === "rejected") return "rejected";
  return "pending";
}

function matchStatusFromTxn(
  reconciliationStatus: string | undefined,
): MatchReconciliationStatus {
  if (reconciliationStatus === "needs_review") return "needs_review";
  return "matched";
}

/** Pending / rejected first; approved matches last (stable within each group). */
export function sortMatchedTransactionsByApproval<
  T extends { approvalStatus: MatchApprovalStatus },
>(items: T[]): T[] {
  return [...items].sort((a, b) => {
    const aRank = a.approvalStatus === "approved" ? 1 : 0;
    const bRank = b.approvalStatus === "approved" ? 1 : 0;
    return aRank - bRank;
  });
}

export function invoicePaymentMatchToItem(
  match: InvoicePaymentMatch,
): MatchedTransactionItem {
  const txn = match.bank_transaction;
  const invoice = match.invoice;
  const transactionAmount =
    txn?.debited_amount ?? txn?.credited_amount ?? null;

  return {
    id: match.id,
    companyName:
      invoice?.name_of_company?.trim() ||
      match.invoice_number?.trim() ||
      "—",
    invoiceAmount: invoice?.amount ?? null,
    invoiceCurrency: invoice?.currency ?? "EUR",
    invoiceNumber:
      invoice?.invoice_number?.trim() || match.invoice_number || null,
    invoiceDate: match.paid_at_date || null,
    transactionDate: txn?.transaction_date ?? null,
    transactionAmount,
    transactionComment: txn?.comment?.trim() || null,
    detectedInvoiceNumbers: txn?.detected_invoice_numbers ?? [],
    matchStatus: matchStatusFromTxn(txn?.reconciliation_status),
    approvalStatus: approvalStatusFromMatch(match.status),
  };
}
