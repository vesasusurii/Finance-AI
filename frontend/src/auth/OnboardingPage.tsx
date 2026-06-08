import { useEffect, useState, type FormEvent } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "./AuthContext";
import { changePassword, resendVerificationCode, verifyEmail } from "@/api/auth";
import { ApiError } from "@/api/client";
import { LoadingSpinner } from "@/components/LoadingSpinner";
import { Button } from "@/components/ui-finance/Button";
import { BrandLogo } from "@/components/shell/BrandLogo";
import { ThemeToggle } from "@/components/theme/ThemeToggle";
import { isAdminRole, needsOnboarding } from "@/types/auth";

const RESEND_COOLDOWN_SECONDS = 120;

function homePath(role: string) {
  return isAdminRole(role) ? "/admin/users" : "/";
}

function formatResendWait(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${minutes}:${secs.toString().padStart(2, "0")}`;
}

export function OnboardingPage() {
  const { user, loading, updateUser } = useAuth();
  const [verificationCode, setVerificationCode] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [resendCooldown, setResendCooldown] = useState(0);

  useEffect(() => {
    if (!user || user.must_change_password) {
      setResendCooldown(0);
      return;
    }
    setResendCooldown(user.verification_resend_in_seconds ?? 0);
    if (!user.email_verified) {
      setNotice(
        `A verification code was sent to ${user.email}. It expires in 10 minutes.`,
      );
    }
  }, [user]);

  useEffect(() => {
    if (resendCooldown <= 0) return;
    const timer = window.setInterval(() => {
      setResendCooldown((seconds) => (seconds <= 1 ? 0 : seconds - 1));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [resendCooldown]);

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

  const step = user.must_change_password ? "password" : "verify";
  const resendBlocked = resendCooldown > 0;

  async function handleVerifyEmail(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    setNotice(null);
    try {
      const updated = await verifyEmail(verificationCode);
      updateUser(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Verification failed");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleChangePassword(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setNotice(null);

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
      setResendCooldown(updated.verification_resend_in_seconds ?? RESEND_COOLDOWN_SECONDS);
      setNotice(
        `Verification code sent to ${updated.email}. It expires in 10 minutes. You can request a new code after 2 minutes.`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Password change failed");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleResendCode() {
    if (resendBlocked) return;
    setSubmitting(true);
    setError(null);
    setNotice(null);
    try {
      const updated = await resendVerificationCode();
      updateUser(updated);
      setResendCooldown(updated.verification_resend_in_seconds ?? RESEND_COOLDOWN_SECONDS);
      setNotice(`A new code was sent to ${updated.email}. It expires in 10 minutes.`);
    } catch (err) {
      if (err instanceof ApiError && err.retryAfterSeconds) {
        setResendCooldown(err.retryAfterSeconds);
      }
      setError(err instanceof Error ? err.message : "Could not send a new code");
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
            {step === "verify" ? "Enter verification code" : "Set a new password"}
          </h1>
          <p className="mt-1 text-[13px] text-muted-foreground">
            {step === "verify"
              ? "We sent a 6-digit code to your email. Codes expire after 10 minutes. You can request a new code after 2 minutes."
              : "Change your temporary password before continuing."}
          </p>
        </header>

        {step === "verify" ? (
          <form
            className="rounded-lg border border-border bg-card p-6"
            onSubmit={handleVerifyEmail}
          >
            {error && (
              <p className="mb-4 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-[13px] text-destructive">
                {error}
              </p>
            )}
            {notice && (
              <p className="mb-4 rounded-md border border-border bg-surface-muted px-3 py-2 text-[13px] text-foreground">
                {notice}
              </p>
            )}
            <p className="mb-4 text-[13px] text-muted-foreground">
              Account: <span className="font-medium text-foreground">{user.email}</span>
            </p>
            <label className="mb-6 block">
              <span className="mb-1.5 block text-[13px] font-medium text-foreground">
                Verification code
              </span>
              <input
                type="text"
                inputMode="numeric"
                pattern="\d{6}"
                maxLength={6}
                value={verificationCode}
                onChange={(e) => setVerificationCode(e.target.value.replace(/\D/g, ""))}
                required
                autoComplete="one-time-code"
                className="h-9 w-full rounded-md border border-input bg-background px-3 text-[13px] tracking-[0.2em] text-foreground focus:border-ring focus:outline-none"
              />
            </label>
            <Button type="submit" className="w-full" disabled={submitting}>
              {submitting ? "Verifying…" : "Verify email"}
            </Button>
            <Button
              type="button"
              variant="ghost"
              className="mt-3 w-full"
              disabled={submitting || resendBlocked}
              onClick={() => void handleResendCode()}
            >
              {submitting
                ? "Sending…"
                : resendBlocked
                  ? `Resend available in ${formatResendWait(resendCooldown)}`
                  : "Send a new code"}
            </Button>
          </form>
        ) : (
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
              {submitting ? "Saving…" : "Save password"}
            </Button>
          </form>
        )}
      </div>
    </div>
  );
}
