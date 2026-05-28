export interface ReconciliationSummary {
  matched: number;
  unmatched_invoices: number;
  unmatched_transactions: number;
  review_tasks_created: number;
  run_at: string;
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
  created_at: string;
}

export interface MatchListResponse {
  items: InvoicePaymentMatch[];
  total: number;
  page: number;
  limit: number;
}
