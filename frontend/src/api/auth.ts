import { apiFetch } from "./client";

export interface LoginResponse {
  user_id: number;
  email: string;
  role: string;
}

export async function login(
  email: string,
  password: string,
): Promise<LoginResponse> {
  return apiFetch<LoginResponse>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export async function logout(): Promise<void> {
  await apiFetch("/api/auth/logout", { method: "POST" });
}

export async function getMe(): Promise<LoginResponse> {
  return apiFetch<LoginResponse>("/api/auth/me");
}
