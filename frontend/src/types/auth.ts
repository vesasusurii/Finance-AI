export type UserRole = "finance" | "admin";

export interface AuthUser {
  user_id: number;
  email: string;
  role: UserRole;
  email_verified: boolean;
  must_change_password: boolean;
  verification_resend_in_seconds?: number;
}

export function needsOnboarding(user: AuthUser | null | undefined): boolean {
  if (!user) return false;
  return !user.email_verified || user.must_change_password;
}

export function isAdminRole(role: string | undefined): role is "admin" {
  return role === "admin";
}

export function roleLabel(role: UserRole): string {
  return role === "admin" ? "Admin" : "Finance";
}
