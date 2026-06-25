import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { Plus, X } from "lucide-react";
import { LoadingSpinner } from "@/components/LoadingSpinner";
import { PageHeader } from "@/components/ui-finance/PageHeader";
import { Button } from "@/components/ui-finance/Button";
import { DataTable, type Column } from "@/components/ui-finance/DataTable";
import { StatusBadge } from "@/components/ui-finance/StatusBadge";
import { useAdminUsers } from "@/hooks/useAdminUsers";
import { formatDate } from "@/lib/labels";
import { roleLabel } from "@/types/auth";
import type { AdminUser } from "@/types/user";

export function UsersPage() {
  const { items, total, loading, error, create, remove, resetPassword } = useAdminUsers();
  const [showForm, setShowForm] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<AdminUser | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [resetTarget, setResetTarget] = useState<AdminUser | null>(null);
  const [resetPasswordValue, setResetPasswordValue] = useState("");
  const [resetError, setResetError] = useState<string | null>(null);
  const [resetting, setResetting] = useState(false);

  const columns: Column<AdminUser>[] = [
    {
      key: "email",
      header: "Email",
      cell: (row) => (
        <span className="font-medium text-foreground">{row.email}</span>
      ),
    },
    {
      key: "role",
      header: "Role",
      cell: (row) => (
        <span className="text-muted-foreground">{roleLabel(row.role)}</span>
      ),
    },
    {
      key: "status",
      header: "Status",
      cell: (row) => (
        <StatusBadge value={row.is_active ? "Active" : "Disabled"} />
      ),
    },
    {
      key: "statements",
      header: "Bank statements",
      cell: (row) => (
        <span className="tabular-nums text-muted-foreground">
          {row.bank_statement_count}
        </span>
      ),
    },
    {
      key: "created",
      header: "Created",
      cell: (row) => (
        <span className="tabular-nums text-muted-foreground">
          {formatDate(row.created_at)}
        </span>
      ),
    },
    {
      key: "actions",
      header: "",
      align: "right",
      cell: (row) => (
        <div className="flex justify-end gap-2">
          {row.bank_statement_count > 0 ? (
            <Link
              to={`/bank-statements?uploaded_by=${row.id}`}
              className="inline-flex h-8 items-center rounded-md px-3 text-[12px] font-medium text-primary hover:underline"
            >
              View statements
            </Link>
          ) : null}
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => {
              setResetError(null);
              setResetPasswordValue("");
              setResetTarget(row);
            }}
          >
            Reset password
          </Button>
          <Button
            type="button"
            variant="danger"
            size="sm"
            onClick={() => {
              setDeleteError(null);
              setDeleteTarget(row);
            }}
          >
            Delete
          </Button>
        </div>
      ),
    },
  ];

  function resetForm() {
    setEmail("");
    setPassword("");
    setFormError(null);
  }

  function openForm() {
    resetForm();
    setSuccessMessage(null);
    setShowForm(true);
  }

  function closeForm() {
    setShowForm(false);
    resetForm();
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setFormError(null);
    setSuccessMessage(null);
    setSubmitting(true);
    try {
      const user = await create({ email, password });
      setSuccessMessage(
        `Finance user ${user.email} created. Share the temporary password with them. They will change it before email verification.`,
      );
      closeForm();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Failed to create user");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleResetConfirmed(e: FormEvent) {
    e.preventDefault();
    if (!resetTarget) return;

    setResetError(null);
    setResetting(true);
    try {
      const user = await resetPassword(resetTarget.id, resetPasswordValue);
      setSuccessMessage(
        `Password reset for ${user.email}. Share the temporary password securely. They must change it on next sign-in.`,
      );
      setResetTarget(null);
      setResetPasswordValue("");
    } catch (err) {
      setResetError(err instanceof Error ? err.message : "Failed to reset password");
    } finally {
      setResetting(false);
    }
  }

  async function handleDeleteConfirmed() {
    if (!deleteTarget) return;

    setDeleteError(null);
    setDeleting(true);
    try {
      await remove(deleteTarget.id);
      setSuccessMessage(`User ${deleteTarget.email} deleted.`);
      setDeleteTarget(null);
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : "Failed to delete user");
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div>
      <PageHeader
        eyebrow="Site admin"
        title="Users"
        description="Create finance accounts and manage platform access."
        actions={
          !showForm ? (
            <Button type="button" icon={<Plus className="h-3.5 w-3.5" />} onClick={openForm}>
              Add finance user
            </Button>
          ) : null
        }
      />

      {successMessage && (
        <p className="mb-4 rounded-md border border-border bg-surface-muted px-3 py-2 text-[13px] text-foreground">
          {successMessage}
        </p>
      )}

      {showForm && (
        <form
          onSubmit={handleSubmit}
          className="mb-6 rounded-lg border border-border bg-card p-5"
        >
          <div className="mb-4 flex items-start justify-between gap-4">
            <div>
              <h2 className="text-[15px] font-semibold text-foreground">
                New finance user
              </h2>
              <p className="mt-1 text-[13px] text-muted-foreground">
                The user must change this temporary password, then verify their email on first sign-in.
              </p>
            </div>
            <button
              type="button"
              onClick={closeForm}
              className="grid h-8 w-8 place-items-center rounded-md text-muted-foreground hover:bg-secondary hover:text-foreground"
              aria-label="Close form"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          {formError && (
            <p className="mb-4 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-[13px] text-destructive">
              {formError}
            </p>
          )}

          <div className="grid gap-4 md:grid-cols-2">
            <label className="block">
              <span className="mb-1.5 block text-[13px] font-medium text-foreground">
                Email
              </span>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="off"
                className="h-9 w-full rounded-md border border-input bg-background px-3 text-[13px] text-foreground focus:border-ring focus:outline-none"
              />
            </label>
            <label className="block">
              <span className="mb-1.5 block text-[13px] font-medium text-foreground">
                Password
              </span>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={12}
                autoComplete="new-password"
                className="h-9 w-full rounded-md border border-input bg-background px-3 text-[13px] text-foreground focus:border-ring focus:outline-none"
              />
              <span className="mt-1 block text-[11px] text-muted-foreground">
                Minimum 12 characters
              </span>
            </label>
          </div>

          <div className="mt-5 flex items-center gap-2">
            <Button type="submit" disabled={submitting}>
              {submitting ? "Creating…" : "Create user"}
            </Button>
            <Button type="button" variant="ghost" onClick={closeForm}>
              Cancel
            </Button>
          </div>
        </form>
      )}

      {error && (
        <p className="mb-4 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-[13px] text-destructive">
          {error}
        </p>
      )}

      {loading ? (
        <LoadingSpinner centered className="text-muted-foreground" />
      ) : (
        <>
          <p className="mb-3 text-[13px] text-muted-foreground">
            {total} {total === 1 ? "user" : "users"}
          </p>
          <DataTable columns={columns} rows={items} />
        </>
      )}

      {resetTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 px-4">
          <form
            onSubmit={handleResetConfirmed}
            className="w-full max-w-md rounded-lg border border-border bg-card p-5"
          >
            <div className="mb-4 flex items-start justify-between gap-4">
              <div>
                <h2 className="text-[15px] font-semibold text-foreground">
                  Reset password
                </h2>
                <p className="mt-1 text-[13px] leading-relaxed text-muted-foreground">
                  Set a temporary password for {resetTarget.email}. Their current session
                  will end and they must choose a new password on next sign-in.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setResetTarget(null)}
                className="grid h-8 w-8 place-items-center rounded-md text-muted-foreground hover:bg-secondary hover:text-foreground"
                aria-label="Close reset password dialog"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {resetError && (
              <p className="mb-4 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-[13px] text-destructive">
                {resetError}
              </p>
            )}

            <label className="mb-6 block">
              <span className="mb-1.5 block text-[13px] font-medium text-foreground">
                Temporary password
              </span>
              <input
                type="password"
                value={resetPasswordValue}
                onChange={(e) => setResetPasswordValue(e.target.value)}
                required
                minLength={12}
                autoComplete="new-password"
                className="h-9 w-full rounded-md border border-input bg-background px-3 text-[13px] text-foreground focus:border-ring focus:outline-none"
              />
              <span className="mt-1 block text-[11px] text-muted-foreground">
                Minimum 12 characters
              </span>
            </label>

            <div className="flex items-center justify-end gap-2">
              <Button
                type="button"
                variant="ghost"
                onClick={() => setResetTarget(null)}
                disabled={resetting}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={resetting}>
                {resetting ? "Resetting…" : "Reset password"}
              </Button>
            </div>
          </form>
        </div>
      )}

      {deleteTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 px-4">
          <div className="w-full max-w-md rounded-lg border border-border bg-card p-5">
            <div className="mb-4 flex items-start justify-between gap-4">
              <div>
                <h2 className="text-[15px] font-semibold text-foreground">
                  Delete user
                </h2>
                <p className="mt-1 text-[13px] leading-relaxed text-muted-foreground">
                  This permanently deletes {deleteTarget.email}. This action cannot be undone.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setDeleteTarget(null)}
                className="grid h-8 w-8 place-items-center rounded-md text-muted-foreground hover:bg-secondary hover:text-foreground"
                aria-label="Close delete confirmation"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {deleteError && (
              <p className="mb-4 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-[13px] text-destructive">
                {deleteError}
              </p>
            )}

            <div className="flex items-center justify-end gap-2">
              <Button
                type="button"
                variant="ghost"
                onClick={() => setDeleteTarget(null)}
                disabled={deleting}
              >
                Cancel
              </Button>
              <Button
                type="button"
                variant="danger"
                onClick={() => void handleDeleteConfirmed()}
                disabled={deleting}
              >
                {deleting ? "Deleting…" : "Delete user"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
