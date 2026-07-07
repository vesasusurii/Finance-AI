import { ApiError, apiFetch, refreshAccessToken } from "./client";
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
  const user = await refreshAccessToken<AuthUser>();
  if (!user?.user_id) {
    throw new ApiError(
      "Session expired. Please sign in again.",
      401,
      "session_expired",
    );
  }
  return user;
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

export async function forgotPassword(email: string): Promise<{ message: string }> {
  return apiFetch<{ message: string }>("/api/auth/forgot-password", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export async function resetPassword(
  email: string,
  token: string,
  newPassword: string,
): Promise<AuthUser> {
  return apiFetch<AuthUser>("/api/auth/reset-password", {
    method: "POST",
    body: JSON.stringify({
      email,
      token,
      new_password: newPassword,
    }),
  });
}
 
