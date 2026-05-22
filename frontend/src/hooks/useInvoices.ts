import { useCallback, useEffect, useState } from "react";
import { listInvoices } from "../api/invoices";
import type { Invoice, InvoiceFilters } from "../types/invoice";

export function useInvoices(filters: InvoiceFilters) {
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listInvoices(filters);
      setInvoices(data.items);
      setTotal(data.total);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load invoices");
    } finally {
      setLoading(false);
    }
  }, [JSON.stringify(filters)]);

  useEffect(() => {
    refetch();
  }, [refetch]);

  return { invoices, total, loading, error, refetch };
}
