import { apiFetch } from "./client";
import type {
  ReviewDecisionRequest,
  ReviewTask,
  ReviewTaskDecisionResponse,
  ReviewTaskListResponse,
} from "../types/review";
import type { Invoice } from "../types/invoice";
import type { BankTransaction } from "../types/bank";

export interface ManualReviewQueueItem {
  key: string;
  mode: "bank_match" | "extraction";
  invoice: Invoice;
  task: ReviewTask | null;
}

export interface ManualReviewQueueResponse {
  items: ManualReviewQueueItem[];
  total: number;
  page: number;
  limit: number;
}

export interface BankMatchCandidatesResponse {
  items: BankTransaction[];
  bank_statement_id: number | null;
}

export async function listManualReviewQueue(filters: {
  filter?: "all" | "extraction" | "bank_match";
  page?: number;
  limit?: number;
} = {}): Promise<ManualReviewQueueResponse> {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value === undefined || value === "") return;
    params.set(key, String(value));
  });
  const qs = params.toString();
  return apiFetch<ManualReviewQueueResponse>(
    `/api/review/manual-queue${qs ? `?${qs}` : ""}`,
  );
}

export async function listBankMatchCandidates(
  invoiceId: number,
  bankStatementId?: number,
): Promise<BankMatchCandidatesResponse> {
  const params = new URLSearchParams({
    invoice_id: String(invoiceId),
  });
  if (bankStatementId != null) {
    params.set("bank_statement_id", String(bankStatementId));
  }
  return apiFetch<BankMatchCandidatesResponse>(
    `/api/review/bank-candidates?${params}`,
  );
}

export async function listReviewTasks(filters: {
  task_type?: string;
  has_invoice?: boolean;
  reasons?: string[];
  page?: number;
  limit?: number;
  /** Skip loading invoice/bank line details (faster for matching page). */
  slim?: boolean;
} = {}): Promise<ReviewTaskListResponse> {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (key === "slim") {
      if (value === true) params.set("enrich", "false");
      return;
    }
    if (value === undefined || value === "") return;
    if (key === "reasons" && Array.isArray(value)) {
      value.forEach((reason) => params.append("reasons", reason));
      return;
    }
    params.set(key, String(value));
  });
  const qs = params.toString();
  return apiFetch<ReviewTaskListResponse>(`/api/review${qs ? `?${qs}` : ""}`);
}

export async function approveReviewTask(
  id: number,
): Promise<ReviewTaskDecisionResponse> {
  return apiFetch<ReviewTaskDecisionResponse>(`/api/review/${id}/approve`, {
    method: "POST",
  });
}

export async function rejectReviewTask(
  id: number,
  reason?: string,
): Promise<ReviewTaskDecisionResponse> {
  const body: ReviewDecisionRequest = {};
  if (reason) body.reason = reason;
  return apiFetch<ReviewTaskDecisionResponse>(`/api/review/${id}/reject`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}
