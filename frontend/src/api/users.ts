import { apiFetch } from "./client";
import type {
  AdminUser,
  AdminUserListResponse,
  CreateUserRequest,
} from "../types/user";

export async function listUsers(): Promise<AdminUserListResponse> {
  return apiFetch<AdminUserListResponse>("/api/admin/users");
}

export async function createUser(body: CreateUserRequest): Promise<AdminUser> {
  return apiFetch<AdminUser>("/api/admin/users", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function deleteUser(userId: number): Promise<void> {
  await apiFetch(`/api/admin/users/${userId}`, { method: "DELETE" });
}

export async function resetUserPassword(
  userId: number,
  password: string,
): Promise<AdminUser> {
  return apiFetch<AdminUser>(`/api/admin/users/${userId}/reset-password`, {
    method: "POST",
    body: JSON.stringify({ password }),
  });
}
