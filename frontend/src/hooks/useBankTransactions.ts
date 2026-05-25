import { useCallback, useEffect, useState } from "react";
import { listBankTransactions } from "@/api/bankStatements";
import type {
  BankTransaction,
  BankTransactionFilters,
} from "@/types/bank";

export function useBankTransactions(filters: BankTransactionFilters = {}) {
  const [items, setItems] = useState<BankTransaction[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await listBankTransactions(filters);
      setItems(res.items);
      setTotal(res.total);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load transactions");
      setItems([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [
    filters.bank_statement_id,
    filters.reconciliation_status,
    filters.page,
    filters.limit,
  ]);

  useEffect(() => {
    void reload();
  }, [reload]);

  return { items, total, loading, error, reload };
}
