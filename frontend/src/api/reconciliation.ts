import { apiFetch } from "./client";
import type { MatchListResponse, ReconciliationSummary } from "../types/match";

export async function runReconciliation(
  bankStatementId?: number,
): Promise<ReconciliationSummary> {
  return apiFetch<ReconciliationSummary>("/api/reconciliation/run", {
    method: "POST",
    body: JSON.stringify(
      bankStatementId != null ? { bank_statement_id: bankStatementId } : {},
    ),
  });
}

export async function getReconciliationResults(filters: {
  status?: string;
  bank_statement_id?: number;
  page?: number;
  limit?: number;
} = {}): Promise<MatchListResponse> {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== "") {
      params.set(key, String(value));
    }
  });
  const qs = params.toString();
  return apiFetch<MatchListResponse>(
    `/api/reconciliation/results${qs ? `?${qs}` : ""}`,
  );
}

export async function manualMatch(body: {
  invoice_id: number;
  bank_transaction_id: number;
  review_task_id?: number;
}): Promise<{
  match_id: number;
  status: string;
  invoice_id: number;
  bank_transaction_id: number;
  review_task_id: number | null;
}> {
  return apiFetch("/api/reconciliation/manual-match", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function approveMatch(matchId: number): Promise<{
  match_id: number;
  status: string;
}> {
  return apiFetch("/api/reconciliation/approve-match", {
    method: "POST",
    body: JSON.stringify({ match_id: matchId }),
  });
}

export async function rejectMatch(
  matchId: number,
  reason?: string,
): Promise<{ match_id: number; status: string }> {
  return apiFetch("/api/reconciliation/reject-match", {
    method: "POST",
    body: JSON.stringify({ match_id: matchId, reason }),
  });
}
