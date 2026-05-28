export type ReviewStatus = "pending" | "approved" | "needs_review";
export type MatchStatus = "unmatched" | "matched" | "needs_review";

export interface Invoice {
  id: number;
  invoice_date: string | null;
  name_of_company: string | null;
  address_of_company: string | null;
  invoice_number: string | null;
  amount: number | null;
  debt: number | null;
  currency: string | null;
  account_details: string | null;
  internal_note_description: string | null;
  client_employee_related: string | null;
  paid_at_date: string | null;
  paid_by: string | null;
  fixed_status: string | null;
  category: string | null;
  extraction_confidence: number | null;
  /** Per-field confidence map, e.g. { name_of_company: 0.95, amount: 0.72 } */
  field_confidences: Record<string, number> | null;
  review_status: ReviewStatus;
  match_status: MatchStatus;
  source_file_id: number | null;
  source_filename: string | null;
  source_mime_type: string | null;
  created_at: string;
  updated_at: string;
}

export interface InvoiceListResponse {
  items: Invoice[];
  total: number;
  page: number;
  limit: number;
}

export interface InvoiceFilters {
  review_status?: string;
  match_status?: string;
  invoice_date_from?: string;
  invoice_date_to?: string;
  company?: string;
  sort?: string;
  page?: number;
  limit?: number;
}

export interface UploadItem {
  upload_id: number;
  original_filename: string;
  processing_status: string;
  invoice_id?: number | null;
  error?: string | null;
}

export interface UploadResponse {
  uploaded: number;
  items: UploadItem[];
}
