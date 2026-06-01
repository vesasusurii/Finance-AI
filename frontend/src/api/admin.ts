import { apiFetch } from "./client";
import type { PermissionsResponse, SettingsResponse } from "../types/admin";
import type { AdminUser } from "../types/user";
import type { UserRole } from "../types/auth";

export async function getPermissions(): Promise<PermissionsResponse> {
  return apiFetch<PermissionsResponse>("/api/admin/permissions");
}

export async function getSettings(): Promise<SettingsResponse> {
  return apiFetch<SettingsResponse>("/api/admin/settings");
}

export async function updateUserRole(
  userId: number,
  role: UserRole,
): Promise<AdminUser> {
  return apiFetch<AdminUser>(`/api/admin/users/${userId}/role`, {
    method: "PATCH",
    body: JSON.stringify({ role }),
  });
}
