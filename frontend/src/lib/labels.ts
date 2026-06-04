/** Map API snake_case statuses to display labels for StatusBadge. */

export function reviewStatusLabel(status: string): string {
  const map: Record<string, string> = {
    pending: "Pending",
    approved: "Approved",
    needs_review: "Needs review",
    manual_review: "Manual review required",
  };
  return map[status] ?? status;
}

export function matchStatusLabel(status: string): string {
  const map: Record<string, string> = {
    unmatched: "Unmatched",
    matched: "Matched",
    partially_matched: "Partially paid",
    needs_review: "Needs Review",
  };
  return map[status] ?? status;
}

export function reconciliationStatusLabel(status: string): string {
  const map: Record<string, string> = {
    pending: "Pending",
    matched: "Matched",
    partial: "Partial",
    needs_review: "Needs Review",
  };
  return map[status] ?? status;
}

export function reviewReasonLabel(reason: string): string {
  const map: Record<string, string> = {
    low_confidence: "Low extraction confidence",
    missing_fields: "Missing required fields",
    missing_invoice_number: "Invoice number missing",
    missing_amount: "Amount missing",
    missing_company_name: "Company name missing",
    unclear_company_name: "Company name unclear",
    missing_invoice_date: "Invoice date missing",
    unclear_invoice_date: "Invoice date unclear",
    low_ai_confidence: "Low AI confidence",
    bank_match_failed: "Bank match failed",
    multiple_matches: "Multiple possible matches",
    no_invoice_in_db: "Invoice not in DB",
    duplicate_invoice_in_db: "Duplicate invoice in DB",
    no_invoice_numbers_detected: "No invoice # detected",
    invoice_numbers_not_visible: "Invoice numbers not visible",
    batch_payment_incomplete: "Batch payment incomplete",
    batch_amount_suggested: "Batch amount suggested",
    missing_transaction_date: "Missing transaction date",
    internal_error: "Internal error",
  };
  return map[reason] ?? reason;
}

export function processingStatusLabel(status: string): string {
  const map: Record<string, string> = {
    pending: "Pending",
    processing: "Processing",
    processed: "Processed",
    failed: "Failed",
  };
  return map[status] ?? status;
}

export function formatCurrency(amount: number | null, currency: string | null): string {
  if (amount == null) return "—";
  const code = currency ?? "EUR";
  try {
    return new Intl.NumberFormat("de-DE", {
      style: "currency",
      currency: code,
    }).format(amount);
  } catch {
    return `${amount} ${code}`;
  }
}

export function formatDate(value: string | null): string {
  if (!value) return "—";
  return value.slice(0, 10);
}

export function formatStatementId(
  statement: {
    id?: number;
    bank_statement_id?: number;
    statement_date?: string | null;
  },
): string {
  if (statement.statement_date) {
    return statement.statement_date.replace(/-/g, "");
  }
  return String(statement.id ?? statement.bank_statement_id ?? "");
}

export function auditActionLabel(action: string): string {
  const map: Record<string, string> = {
    invoice_extracted: "Invoice extracted",
    invoice_updated: "Invoice updated",
    invoice_approved: "Invoice approved",
    payment_date_set: "Payment date set",
    match_approved: "Match approved",
    match_rejected: "Match rejected",
  };
  return map[action] ?? action.replaceAll("_", " ");
}
