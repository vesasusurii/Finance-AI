export interface ReconciliationSummary {
  matched: number;
  unmatched_invoices: number;
  unmatched_transactions: number;
  review_tasks_created: number;
  run_at: string;
  status?: string;
}

export interface MatchInvoiceSnapshot {
  id: number;
  invoice_number: string | null;
  name_of_company: string | null;
  amount: number | null;
  currency: string | null;
}

export interface MatchBankTransactionSnapshot {
  id: number;
  transaction_date: string | null;
  comment: string | null;
  debited_amount: number | null;
  credited_amount: number | null;
  detected_invoice_numbers: string[];
  reconciliation_status: string;
}

export interface InvoicePaymentMatch {
  id: number;
  invoice_id: number;
  bank_transaction_id: number;
  invoice_number: string;
  match_type: string;
  match_confidence: number;
  status: string;
  paid_at_date: string;
  paid_amount?: number | null;
  created_at: string;
  invoice: MatchInvoiceSnapshot | null;
  bank_transaction: MatchBankTransactionSnapshot | null;
}

export interface MatchListResponse {
  items: InvoicePaymentMatch[];
  total: number;
  page: number;
  limit: number;
}
