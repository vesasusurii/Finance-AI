/** Phase 3: Documents drawer Save sends partial Invoice (writable fields only). */

export type ReviewStatus = "pending" | "approved" | "needs_review" | "manual_review";
export type MatchStatus = "unmatched" | "matched" | "partially_matched" | "needs_review";

export interface Invoice {
  id: number;
  invoice_date: string | null;
  name_of_company: string | null;
  address_of_company: string | null;
  invoice_number: string | null;
  /** Canonical matching key; may differ from display (e.g. slashes/hyphens stripped). */
  invoice_number_normalized: string | null;
  amount: number | null;
  debt: number | null;
  currency: string | null;
  original_amount: number | null;
  original_currency: string | null;
  exchange_rate: number | null;
  exchange_rate_date: string | null;
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
  /** Why this invoice needs human review (extraction or matching). */
  review_reasons: string[] | null;
  review_status: ReviewStatus;
  match_status: MatchStatus;
  uploaded_by: number;
  source_file_id: number | null;
  source_filename: string | null;
  source_mime_type: string | null;
  upload_source?: string | null;
  ingest_sender_email?: string | null;
  ingest_sender_name?: string | null;
  ingest_email_subject?: string | null;
  ingest_message_id?: string | null;
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
  search?: string;
  sort?: string;
  upload_source?: string;
  page?: number;
  limit?: number;
}

export interface UploadItem {
  upload_id: number;
  original_filename: string;
  processing_status: string;
  invoice_id?: number | null;
  error?: string | null;
  message?: string | null;
  original_uploader_email?: string | null;
}

export interface UploadResponse {
  uploaded: number;
  items: UploadItem[];
}
