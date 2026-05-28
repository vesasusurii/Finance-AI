import { apiFetch } from "./client";
import type { ReviewTaskListResponse } from "../types/review";

export async function listReviewTasks(filters: {
  task_type?: string;
  page?: number;
  limit?: number;
} = {}): Promise<ReviewTaskListResponse> {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== "") {
      params.set(key, String(value));
    }
  });
  const qs = params.toString();
  return apiFetch<ReviewTaskListResponse>(`/api/review${qs ? `?${qs}` : ""}`);
}
