import { useCallback, useEffect, useState } from "react";
import { createUser, deleteUser, listUsers, resetUserPassword } from "../api/users";
import type { AdminUser, CreateUserRequest } from "../types/user";

export function useAdminUsers() {
  const [items, setItems] = useState<AdminUser[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await listUsers();
      setItems(res.items);
      setTotal(res.total);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load users");
      setItems([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  const create = useCallback(
    async (body: CreateUserRequest): Promise<AdminUser> => {
      const user = await createUser(body);
      await reload();
      return user;
    },
    [reload],
  );

  const remove = useCallback(
    async (userId: number) => {
      await deleteUser(userId);
      await reload();
    },
    [reload],
  );

  const resetPassword = useCallback(
    async (userId: number, password: string): Promise<AdminUser> => {
      const user = await resetUserPassword(userId, password);
      await reload();
      return user;
    },
    [reload],
  );

  return { items, total, loading, error, reload, create, remove, resetPassword };
}
