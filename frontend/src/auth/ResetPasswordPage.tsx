import { useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { resetPassword } from "@/api/auth";
import { BrandLogo } from "@/components/shell/BrandLogo";
import { ThemeToggle } from "@/components/theme/ThemeToggle";
import { Button } from "@/components/ui-finance/Button";
import { isAdminRole } from "@/types/auth";
import { useAuth } from "./AuthContext";

function homePath(role: string) {
  return isAdminRole(role) ? "/admin/users" : "/";
}

export function ResetPasswordPage() {
  const { updateUser } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const email = searchParams.get("email") ?? "";
  const token = searchParams.get("token") ?? "";

  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (!email || !token) {
    return <Navigate to="/forgot-password" replace />;
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);

    if (newPassword !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setSubmitting(true);
    try {
      const user = await resetPassword(email, token, newPassword);
      updateUser(user);
      navigate(homePath(user.role), { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Password reset failed");
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
            Choose a new password
          </h1>
          <p className="mt-1 text-[13px] text-muted-foreground">
            Set a new password for {email}
          </p>
        </header>

        <form
          className="rounded-lg border border-border bg-card p-6 shadow-sm"
          onSubmit={handleSubmit}
        >
          {error && (
            <p className="mb-4 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-[13px] text-destructive">
              {error}
            </p>
          )}
          <label className="mb-4 block">
            <span className="mb-1.5 block text-[13px] font-medium text-foreground">
              New password
            </span>
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              required
              minLength={8}
              autoComplete="new-password"
              className="h-9 w-full rounded-md border border-input bg-background px-3 text-[13px] text-foreground focus:border-ring focus:outline-none"
            />
          </label>
          <label className="mb-6 block">
            <span className="mb-1.5 block text-[13px] font-medium text-foreground">
              Confirm password
            </span>
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              minLength={8}
              autoComplete="new-password"
              className="h-9 w-full rounded-md border border-input bg-background px-3 text-[13px] text-foreground focus:border-ring focus:outline-none"
            />
          </label>
          <Button type="submit" className="w-full" disabled={submitting}>
            {submitting ? "Saving…" : "Save new password"}
          </Button>
          <p className="mt-4 text-center text-[13px] text-muted-foreground">
            <Link to="/login" className="text-foreground underline-offset-4 hover:underline">
              Back to sign in
            </Link>
          </p>
        </form>
      </div>
    </div>
  );
}
