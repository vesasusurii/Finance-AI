/** Map API snake_case statuses to display labels for StatusBadge. */

export function reviewStatusLabel(status: string): string {
  const map: Record<string, string> = {
    pending: "Pending",
    approved: "Approved",
    needs_review: "Needs Review",
  };
  return map[status] ?? status;
}

export function matchStatusLabel(status: string): string {
  const map: Record<string, string> = {
    unmatched: "Unmatched",
    matched: "Matched",
    needs_review: "Needs Review",
  };
  return map[status] ?? status;
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
