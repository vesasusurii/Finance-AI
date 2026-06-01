import type { BankTransaction } from "./bank";
import type { Invoice } from "./invoice";

export interface ReviewTask {
  id: number;
  task_type: string;
  invoice_id: number | null;
  bank_transaction_id: number | null;
  reason: string;
  status: string;
  payload: Record<string, unknown> | null;
  created_at: string;
  resolved_at: string | null;
  invoice?: Invoice | null;
  bank_transaction?: BankTransaction | null;
}

export interface ReviewTaskListResponse {
  items: ReviewTask[];
  total: number;
  page: number;
  limit: number;
}

export interface ReviewDecisionRequest {
  reason?: string | null;
}

export interface ReviewTaskDecisionResponse {
  review_task_id: number;
  status: string;
  resolved_at: string;
}
