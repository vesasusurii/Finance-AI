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
  row_count: number;
  processing_status: string;
  unparsed_date_rows?: number;
  preview: BankTransactionPreview[];
}

export interface BankStatement {
  id: number;
  original_filename: string;
  uploaded_at: string;
  uploaded_by: number;
  row_count: number;
  processing_status: string;
}

export interface BankStatementListResponse {
  items: BankStatement[];
  total: number;
  page: number;
  limit: number;
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
  page?: number;
  limit?: number;
}
