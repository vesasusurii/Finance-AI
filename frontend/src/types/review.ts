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
}

export interface ReviewTaskListResponse {
  items: ReviewTask[];
  total: number;
  page: number;
  limit: number;
}
