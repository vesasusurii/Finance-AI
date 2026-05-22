import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { approveInvoice, updateInvoice } from "../../api/invoices";
import { ConfidenceBadge } from "../../components/ConfidenceBadge";
import { EditableCell } from "../../components/EditableCell";
import { PageHeader } from "../../components/PageHeader";
import { StatusBadge } from "../../components/StatusBadge";
import { useInvoices } from "../../hooks/useInvoices";
import type { Invoice } from "../../types/invoice";

export function PurchaseInvoicesTablePage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [reviewFilter, setReviewFilter] = useState(
    searchParams.get("review_status") ?? "",
  );
  const [matchFilter, setMatchFilter] = useState(
    searchParams.get("match_status") ?? "",
  );
  const [company, setCompany] = useState("");

  const filters = useMemo(
    () => ({
      review_status: reviewFilter || undefined,
      match_status: matchFilter || undefined,
      company: company || undefined,
      limit: 100,
    }),
    [reviewFilter, matchFilter, company],
  );

  const { invoices, loading, error, refetch } = useInvoices(filters);

  async function saveField(inv: Invoice, field: keyof Invoice, value: string) {
    await updateInvoice(inv.id, { [field]: value } as Partial<Invoice>);
    refetch();
  }

  async function handleApprove(id: number) {
    await approveInvoice(id);
    refetch();
  }

  function applyFilters() {
    const next = new URLSearchParams();
    if (reviewFilter) next.set("review_status", reviewFilter);
    if (matchFilter) next.set("match_status", matchFilter);
    setSearchParams(next);
    refetch();
  }

  return (
    <div className="section">
      <div className="container stack-5">
        <PageHeader title="Purchase invoices" />
        <div className="card stack-3" style={{ display: "flex", flexWrap: "wrap", gap: "1rem" }}>
          <select
            value={reviewFilter}
            onChange={(e) => setReviewFilter(e.target.value)}
            aria-label="Review status"
          >
            <option value="">All review</option>
            <option value="pending">Pending</option>
            <option value="needs_review">Needs review</option>
            <option value="approved">Approved</option>
          </select>
          <select
            value={matchFilter}
            onChange={(e) => setMatchFilter(e.target.value)}
            aria-label="Match status"
          >
            <option value="">All match</option>
            <option value="unmatched">Unmatched</option>
            <option value="matched">Matched</option>
          </select>
          <input
            placeholder="Company"
            value={company}
            onChange={(e) => setCompany(e.target.value)}
          />
          <button type="button" className="btn btn-ghost" onClick={applyFilters}>
            Apply filters
          </button>
        </div>
        {loading && <p className="text-fg2">Loading…</p>}
        {error && <p className="text-accent">{error}</p>}
        <div style={{ overflowX: "auto" }}>
          <table className="card" style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                {[
                  "Date",
                  "Company",
                  "Address",
                  "Invoice #",
                  "Amount",
                  "Currency",
                  "Account",
                  "Note",
                  "Client",
                  "Paid at",
                  "Paid by",
                  "Fixed",
                  "Category",
                  "Confidence",
                  "Review",
                  "Match",
                  "",
                ].map((h) => (
                  <th key={h} style={{ padding: "8px", textAlign: "left" }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {invoices.map((inv) => (
                <tr key={inv.id}>
                  <td style={{ padding: "8px" }}>{inv.invoice_date ?? "—"}</td>
                  <td style={{ padding: "8px" }}>{inv.name_of_company ?? "—"}</td>
                  <td style={{ padding: "8px" }}>{inv.address_of_company ?? "—"}</td>
                  <td style={{ padding: "8px" }}>{inv.invoice_number ?? "—"}</td>
                  <td style={{ padding: "8px" }}>{inv.amount ?? "—"}</td>
                  <td style={{ padding: "8px" }}>{inv.currency ?? "—"}</td>
                  <td style={{ padding: "8px" }}>{inv.account_details ?? "—"}</td>
                  <td style={{ padding: "8px" }}>
                    <EditableCell
                      value={inv.internal_note_description}
                      onSave={(v) => saveField(inv, "internal_note_description", v)}
                    />
                  </td>
                  <td style={{ padding: "8px" }}>{inv.client_employee_related ?? "—"}</td>
                  <td style={{ padding: "8px" }}>{inv.paid_at_date ?? "—"}</td>
                  <td style={{ padding: "8px" }}>
                    <EditableCell
                      value={inv.paid_by}
                      onSave={(v) => saveField(inv, "paid_by", v)}
                    />
                  </td>
                  <td style={{ padding: "8px" }}>
                    <EditableCell
                      value={inv.fixed_status}
                      onSave={(v) => saveField(inv, "fixed_status", v)}
                    />
                  </td>
                  <td style={{ padding: "8px" }}>
                    <EditableCell
                      value={inv.category}
                      onSave={(v) => saveField(inv, "category", v)}
                    />
                  </td>
                  <td style={{ padding: "8px" }}>
                    <ConfidenceBadge score={inv.extraction_confidence} />
                  </td>
                  <td style={{ padding: "8px" }}>
                    <StatusBadge status={inv.review_status} domain="review" />
                  </td>
                  <td style={{ padding: "8px" }}>
                    <StatusBadge status={inv.match_status} domain="match" />
                  </td>
                  <td style={{ padding: "8px" }}>
                    {inv.review_status !== "approved" && (
                      <button
                        type="button"
                        className="btn btn-ghost"
                        onClick={() => handleApprove(inv.id)}
                      >
                        Approve
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
