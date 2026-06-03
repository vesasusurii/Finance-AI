import { apiFetch } from "./client";
import type {
  ReviewDecisionRequest,
  ReviewTaskDecisionResponse,
  ReviewTaskListResponse,
} from "../types/review";

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
