import { useCallback, useEffect, useState } from "react";
import { Check, X } from "lucide-react";
import { LoadingSpinner } from "@/components/LoadingSpinner";
import { PageHeader } from "@/components/ui-finance/PageHeader";
import { DataTable, type Column } from "@/components/ui-finance/DataTable";
import { getPermissions, updateUserRole } from "@/api/admin";
import { listUsers } from "@/api/users";
import { useAuth } from "@/auth/AuthContext";
import type { PermissionCapability } from "@/types/admin";
import type { AdminUser } from "@/types/user";
import type { UserRole } from "@/types/auth";
import { roleLabel } from "@/types/auth";

type CapabilityRow = PermissionCapability & { id: string };

export function PermissionsPage() {
  const { user: currentUser } = useAuth();
  const [capabilities, setCapabilities] = useState<CapabilityRow[]>([]);
  const [roles, setRoles] = useState<
    { role: UserRole; label: string; description: string }[]
  >([]);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updatingId, setUpdatingId] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [permRes, userRes] = await Promise.all([
        getPermissions(),
        listUsers(),
      ]);
      setRoles(permRes.roles);
      setCapabilities(
        permRes.capabilities.map((row) => ({ ...row, id: row.key })),
      );
      setUsers(userRes.items);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load permissions");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleRoleChange(target: AdminUser, role: UserRole) {
    if (target.role === role) return;
    setUpdatingId(target.id);
    setError(null);
    try {
      const updated = await updateUserRole(target.id, role);
      setUsers((prev) =>
        prev.map((u) => (u.id === updated.id ? updated : u)),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not update role");
    } finally {
      setUpdatingId(null);
    }
  }

  const matrixColumns: Column<CapabilityRow>[] = [
    {
      key: "capability",
      header: "Capability",
      cell: (r) => (
        <div>
          <p className="font-medium text-foreground">{r.label}</p>
          <p className="mt-0.5 text-[12px] text-muted-foreground">
            {r.description}
          </p>
        </div>
      ),
    },
    {
      key: "finance",
      header: "Finance",
      align: "center",
      cell: (r) => <AccessMark allowed={r.finance} />,
    },
    {
      key: "admin",
      header: "Admin",
      align: "center",
      cell: (r) => <AccessMark allowed={r.admin} />,
    },
  ];

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Site admin"
        title="Permissions"
        description="Role-based access control for finance and admin users."
      />

      {error && (
        <p className="text-[13px] text-destructive" role="alert">
          {error}
        </p>
      )}

      <section className="grid gap-3 sm:grid-cols-2">
        {roles.map((role) => (
          <div
            key={role.role}
            className="rounded-lg border border-border px-4 py-3"
          >
            <p className="text-[13px] font-semibold text-foreground">
              {role.label}
            </p>
            <p className="mt-1 text-[12px] text-muted-foreground">
              {role.description}
            </p>
          </div>
        ))}
      </section>

      <section className="space-y-3">
        <h2 className="text-[14px] font-semibold text-foreground">
          Capability matrix
        </h2>
        {loading ? (
          <LoadingSpinner centered className="text-muted-foreground" />
        ) : (
          <DataTable
            columns={matrixColumns}
            rows={capabilities}
            empty="No capabilities defined."
          />
        )}
      </section>

      <section className="space-y-3">
        <h2 className="text-[14px] font-semibold text-foreground">
          User role assignments
        </h2>
        {loading ? (
          <LoadingSpinner centered className="text-muted-foreground" />
        ) : (
          <div className="overflow-hidden rounded-lg border border-border">
            <table className="w-full text-[13px]">
              <thead>
                <tr className="border-b border-border bg-surface-muted/40 text-left">
                  <th className="px-4 py-2 font-medium text-muted-foreground">
                    Email
                  </th>
                  <th className="px-4 py-2 font-medium text-muted-foreground">
                    Status
                  </th>
                  <th className="px-4 py-2 font-medium text-muted-foreground">
                    Role
                  </th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => {
                  const isSelf = currentUser?.user_id === u.id;
                  return (
                    <tr key={u.id} className="border-b border-border last:border-0">
                      <td className="px-4 py-3 font-medium text-foreground">
                        {u.email}
                        {isSelf ? (
                          <span className="ml-2 text-[11px] text-muted-foreground">
                            (you)
                          </span>
                        ) : null}
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">
                        {u.is_active ? "Active" : "Disabled"}
                      </td>
                      <td className="px-4 py-3">
                        <select
                          value={u.role}
                          disabled={isSelf || updatingId === u.id}
                          onChange={(e) =>
                            void handleRoleChange(
                              u,
                              e.target.value as UserRole,
                            )
                          }
                          className="h-8 rounded-md border border-input bg-background px-2 text-[13px] disabled:opacity-60"
                        >
                          <option value="finance">{roleLabel("finance")}</option>
                          <option value="admin">{roleLabel("admin")}</option>
                        </select>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

function AccessMark({ allowed }: { allowed: boolean }) {
  return allowed ? (
    <Check className="mx-auto h-4 w-4 text-primary" aria-label="Allowed" />
  ) : (
    <X className="mx-auto h-4 w-4 text-muted-foreground" aria-label="Denied" />
  );
}
