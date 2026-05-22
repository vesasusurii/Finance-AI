type StatusDomain = "review" | "match" | "processing";

const LABELS: Record<string, string> = {
  pending: "Pending",
  approved: "Approved",
  needs_review: "Needs review",
  unmatched: "Unmatched",
  matched: "Matched",
  processing: "Processing",
  processed: "Processed",
  failed: "Failed",
};

export function StatusBadge({
  status,
  domain = "review",
}: {
  status: string;
  domain?: StatusDomain;
}) {
  const label = LABELS[status] ?? status;
  let className = "badge";
  if (status === "needs_review" || status === "failed") {
    className += " badge--review";
  } else if (domain === "match" && status === "matched") {
    className += " badge--matched";
  } else if (status === "unmatched" || status === "pending") {
    className += " badge--unmatched";
  }
  return <span className={className}>{label}</span>;
}
