import { apiFetch } from "./client";
import type { AuditLogFilters, AuditLogListResponse } from "../types/audit";

export async function listAuditLogs(
  filters: AuditLogFilters = {},
): Promise<AuditLogListResponse> {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== "") {
      params.set(key, String(value));
    }
  });
  const qs = params.toString();
  return apiFetch<AuditLogListResponse>(
    `/api/admin/audit-logs${qs ? `?${qs}` : ""}`,
  );
}
