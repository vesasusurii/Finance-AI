import { apiFetch } from "./client";
import type {
  BankStatementListResponse,
  BankStatementReparseResponse,
  BankStatementUploadResponse,
  BankTransactionFilters,
  BankTransactionListResponse,
} from "../types/bank";

export async function uploadBankStatement(
  file: File,
): Promise<BankStatementUploadResponse> {
  const form = new FormData();
  form.append("file", file);
  return apiFetch<BankStatementUploadResponse>("/api/bank-statements/upload", {
    method: "POST",
    body: form,
  });
}

export async function listBankStatements(
  page = 1,
  limit = 50,
  uploadedBy?: number,
): Promise<BankStatementListResponse> {
  const params = new URLSearchParams({ page: String(page), limit: String(limit) });
  if (uploadedBy !== undefined) {
    params.set("uploaded_by", String(uploadedBy));
  }
  return apiFetch<BankStatementListResponse>(
    `/api/bank-statements?${params}`,
  );
}

export async function deleteBankStatement(id: number): Promise<void> {
  return apiFetch(`/api/bank-statements/${id}`, { method: "DELETE" });
}

export async function reparseBankStatement(
  id: number,
): Promise<BankStatementReparseResponse> {
  return apiFetch<BankStatementReparseResponse>(
    `/api/bank-statements/${id}/reparse`,
    { method: "POST" },
  );
}

export async function listBankTransactions(
  filters: BankTransactionFilters = {},
): Promise<BankTransactionListResponse> {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value === undefined || value === "") return;
    if (key === "multi_invoice") {
      if (value) params.set(key, "true");
      return;
    }
    params.set(key, String(value));
  });
  const qs = params.toString();
  return apiFetch<BankTransactionListResponse>(
    `/api/bank-transactions${qs ? `?${qs}` : ""}`,
  );
}
