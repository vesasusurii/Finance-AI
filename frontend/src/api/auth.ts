import { ApiError, apiFetch } from "./client";
import type { AuthUser } from "../types/auth";
 
export type { AuthUser as LoginResponse };
 
export async function login(
  email: string,
  password: string,
): Promise<AuthUser> {
  return apiFetch<AuthUser>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}
 
export async function logout(): Promise<void> {
  await apiFetch("/api/auth/logout", { method: "POST" });
}
 
export async function refreshSession(): Promise<AuthUser> {
  return apiFetch<AuthUser>("/api/auth/refresh", { method: "POST" });
}
 
export async function getMe(): Promise<AuthUser | null> {
  try {
    const user = await apiFetch<AuthUser>("/api/auth/me");
    return user ?? null;
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) {
      return null;
    }
    throw e;
  }
}
 
export async function verifyEmail(code: string): Promise<AuthUser> {
  return apiFetch<AuthUser>("/api/auth/verify-email", {
    method: "POST",
    body: JSON.stringify({ code }),
  });
}

export async function resendVerificationCode(): Promise<AuthUser> {
  return apiFetch<AuthUser>("/api/auth/resend-verification-code", {
    method: "POST",
  });
}
 
export async function changePassword(
  currentPassword: string,
  newPassword: string,
): Promise<AuthUser> {
  return apiFetch<AuthUser>("/api/auth/change-password", {
    method: "POST",
    body: JSON.stringify({
      current_password: currentPassword,
      new_password: newPassword,
    }),
  });
}
 