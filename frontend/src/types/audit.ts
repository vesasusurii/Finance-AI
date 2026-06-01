export interface AuditLogEntry {
  id: number;
  user_id: number | null;
  user_email: string | null;
  action: string;
  entity_type: string;
  entity_id: number;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
  created_at: string;
}

export interface AuditLogListResponse {
  items: AuditLogEntry[];
  total: number;
  page: number;
  limit: number;
}

export interface AuditLogFilters {
  page?: number;
  limit?: number;
  action?: string;
  entity_type?: string;
  user_id?: number;
  date_from?: string;
  date_to?: string;
}

export const AUDIT_ACTION_OPTIONS = [
  { value: "", label: "Any action" },
  { value: "invoice_extracted", label: "Invoice extracted" },
  { value: "invoice_updated", label: "Invoice updated" },
  { value: "invoice_approved", label: "Invoice approved" },
  { value: "payment_date_set", label: "Payment date set" },
  { value: "match_approved", label: "Match approved" },
  { value: "match_rejected", label: "Match rejected" },
] as const;

export const AUDIT_ENTITY_OPTIONS = [
  { value: "", label: "Any entity" },
  { value: "invoice", label: "Invoice" },
  { value: "invoice_payment_match", label: "Payment match" },
  { value: "bank_transaction", label: "Bank transaction" },
] as const;
