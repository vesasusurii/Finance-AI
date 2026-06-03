/** View model for the Matched tab card grid (API-agnostic for demos and live data). */

export type MatchReconciliationStatus = "matched" | "needs_review";
export type MatchApprovalStatus = "approved" | "pending" | "rejected";

export interface MatchedTransactionItem {
  id: number;
  companyName: string;
  invoiceAmount: number | null;
  invoiceCurrency: string | null;
  invoiceNumber: string | null;
  invoiceDate: string | null;
  transactionDate: string | null;
  transactionAmount: number | null;
  transactionComment: string | null;
  detectedInvoiceNumbers: string[];
  matchStatus: MatchReconciliationStatus;
  approvalStatus: MatchApprovalStatus;
}
