import { useState, type FormEvent } from "react";
import { Navigate } from "react-router-dom";
import { changePassword } from "@/api/auth";
import { LoadingSpinner } from "@/components/LoadingSpinner";
import { BrandLogo } from "@/components/shell/BrandLogo";
import { ThemeToggle } from "@/components/theme/ThemeToggle";
import { Button } from "@/components/ui-finance/Button";
import { isAdminRole, needsOnboarding } from "@/types/auth";
import { useAuth } from "./AuthContext";

function homePath(role: string) {
  return isAdminRole(role) ? "/admin/users" : "/";
}

export function OnboardingPage() {
  const { user, loading, updateUser } = useAuth();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (loading) {
    return (
      <div className="min-h-screen bg-background">
        <LoadingSpinner
          centered
          className="text-muted-foreground"
          containerClassName="min-h-screen py-0"
        />
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  if (!needsOnboarding(user)) {
    return <Navigate to={homePath(user.role)} replace />;
  }

  async function handleChangePassword(e: FormEvent) {
    e.preventDefault();
    setError(null);

    if (newPassword !== confirmPassword) {
      setError("New passwords do not match.");
      return;
    }

    setSubmitting(true);
    try {
      const updated = await changePassword(currentPassword, newPassword);
      updateUser(updated);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Password change failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center bg-background px-4">
      <ThemeToggle className="absolute right-4 top-4" />
      <div className="w-full max-w-md">
        <header className="mb-8 text-center">
          <BrandLogo className="mb-4 justify-center" imageClassName="h-14" />
          <h1 className="mt-2 text-[22px] font-semibold tracking-tight text-foreground">
            Set a new password
          </h1>
          <p className="mt-1 text-[13px] text-muted-foreground">
            Change your temporary password before continuing.
          </p>
        </header>

        <form
          className="rounded-lg border border-border bg-card p-6"
          onSubmit={handleChangePassword}
        >
          {error && (
            <p className="mb-4 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-[13px] text-destructive">
              {error}
            </p>
          )}
          <label className="mb-4 block">
            <span className="mb-1.5 block text-[13px] font-medium text-foreground">
              Current password
            </span>
            <input
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              required
              autoComplete="current-password"
              className="h-9 w-full rounded-md border border-input bg-background px-3 text-[13px] text-foreground focus:border-ring focus:outline-none"
            />
          </label>
          <label className="mb-4 block">
            <span className="mb-1.5 block text-[13px] font-medium text-foreground">
              New password
            </span>
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              required
              minLength={12}
              autoComplete="new-password"
              className="h-9 w-full rounded-md border border-input bg-background px-3 text-[13px] text-foreground focus:border-ring focus:outline-none"
            />
            <span className="mt-1 block text-[11px] text-muted-foreground">
              Minimum 12 characters
            </span>
          </label>
          <label className="mb-6 block">
            <span className="mb-1.5 block text-[13px] font-medium text-foreground">
              Confirm new password
            </span>
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              minLength={12}
              autoComplete="new-password"
              className="h-9 w-full rounded-md border border-input bg-background px-3 text-[13px] text-foreground focus:border-ring focus:outline-none"
            />
          </label>
          <Button type="submit" className="w-full" disabled={submitting}>
            {submitting ? "Saving..." : "Save password"}
          </Button>
        </form>
      </div>
    </div>
  );
}
