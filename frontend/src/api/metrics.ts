import { apiFetch } from "./client";
import type { WorkerMetricsResponse } from "../types/metrics";

export async function getWorkerMetrics(): Promise<WorkerMetricsResponse> {
  return apiFetch<WorkerMetricsResponse>("/api/metrics/workers");
}
