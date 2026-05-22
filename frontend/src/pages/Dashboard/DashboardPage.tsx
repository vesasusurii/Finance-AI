import { Link } from "react-router-dom";
import { PageHeader } from "../../components/PageHeader";
import { useInvoices } from "../../hooks/useInvoices";

export function DashboardPage() {
  const needsReview = useInvoices({
    review_status: "needs_review",
    limit: 1,
  });
  const unmatched = useInvoices({ match_status: "unmatched", limit: 1 });
  const recent = useInvoices({ limit: 10, sort: "created_at" });

  return (
    <div className="section">
      <div className="container stack-5">
        <PageHeader title="Dashboard" />
        <div className="two-col">
          <div className="card stack-3">
            <h3>Needs review</h3>
            <p className="display">{needsReview.total}</p>
            <Link to="/invoices?review_status=needs_review">View queue</Link>
          </div>
          <div className="card stack-3">
            <h3>Unmatched invoices</h3>
            <p className="display">{unmatched.total}</p>
            <Link to="/invoices?match_status=unmatched">View invoices</Link>
          </div>
        </div>
        <section className="card stack-4">
          <h3>Recent invoices</h3>
          {recent.loading && <p className="text-fg2">Loading…</p>}
          {recent.error && <p className="text-accent">{recent.error}</p>}
          <ul className="stack-2">
            {recent.invoices.map((inv) => (
              <li key={inv.id} className="tok">
                #{inv.id} — {inv.invoice_number ?? "—"} — {inv.name_of_company ?? "—"}
              </li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  );
}
