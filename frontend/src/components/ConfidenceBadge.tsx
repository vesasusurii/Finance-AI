export function ConfidenceBadge({ score }: { score: number | null }) {
  if (score === null) {
    return <span className="badge">—</span>;
  }
  if (score >= 0.9) {
    return <span className="badge badge--matched">Auto-saved</span>;
  }
  if (score >= 0.7) {
    return <span className="badge badge--review">Needs review</span>;
  }
  return <span className="badge badge--review">Manual required</span>;
}
