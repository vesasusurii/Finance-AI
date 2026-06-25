export interface BankTransactionPreview {
  transaction_date: string | null;
  debited_amount: number | null;
  credited_amount: number | null;
  transaction_type: string | null;
  comment: string | null;
  detected_invoice_numbers: string[];
}

export interface BankStatementUploadResponse {
  bank_statement_id: number;
  statement_date: string;
  row_count: number;
  processing_status: string;
  unparsed_date_rows?: number;
  duplicate_rows_skipped?: number;
  preview: BankTransactionPreview[];
}

export interface BankStatement {
  id: number;
  statement_date: string | null;
  original_filename: string;
  uploaded_at: string;
  uploaded_by: number;
  uploaded_by_email: string;
  row_count: number;
  processing_status: string;
}

export interface BankStatementListResponse {
  items: BankStatement[];
  total: number;
  page: number;
  limit: number;
}

export interface BankStatementReparseResponse {
  bank_statement_id: number;
  rows_updated: number;
  dates_fixed: number;
  unparsed_date_rows: number;
  review_tasks_resolved: number;
}

export interface BankTransaction {
  id: number;
  bank_statement_id: number;
  transaction_date: string | null;
  debited_amount: number | null;
  credited_amount: number | null;
  transaction_type: string | null;
  comment: string | null;
  detected_invoice_numbers: string[];
  reconciliation_status: string;
  created_at: string;
}

export interface BankTransactionListResponse {
  items: BankTransaction[];
  total: number;
  page: number;
  limit: number;
}

export interface BankTransactionFilters {
  bank_statement_id?: number;
  reconciliation_status?: string;
  multi_invoice?: boolean;
  page?: number;
  limit?: number;
}
