import type { UserRole } from "./auth";

export interface AdminUser {
  id: number;
  email: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
  bank_statement_count: number;
}

export interface AdminUserListResponse {
  items: AdminUser[];
  total: number;
}

export interface CreateUserRequest {
  email: string;
  password: string;
}
