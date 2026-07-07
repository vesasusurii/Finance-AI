import { ApiError, apiFetch, refreshAccessToken } from "./client";
import type { AuthUser } from "../types/auth";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

export type { AuthUser as LoginResponse };

export type MeSessionState =
  | { status: "authenticated"; user: AuthUser }
  | { status: "anonymous" }
  | { status: "expired" };

/** Resolve session from /me without triggering refresh retries. */
export async function resolveMeSession(): Promise<MeSessionState> {
  const res = await fetch(`${API_BASE}/api/auth/me`, {
    credentials: "include",
  });
  if (res.status === 204) {
    return { status: "anonymous" };
  }
  if (res.status === 401) {
    return { status: "expired" };
  }
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as {
      error?: string;
      message?: string;
    };
    throw new ApiError(
      body.message ?? res.statusText,
      res.status,
      body.error,
    );
  }
  const user = (await res.json()) as AuthUser;
  return { status: "authenticated", user };
}

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
  const state = await resolveMeSession();
  if (state.status === "authenticated") {
    return state.user;
  }
  return null;
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
 
