import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { forgotPassword } from "@/api/auth";
import { BrandLogo } from "@/components/shell/BrandLogo";
import { ThemeToggle } from "@/components/theme/ThemeToggle";
import { Button } from "@/components/ui-finance/Button";

export function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    setMessage(null);
    try {
      const result = await forgotPassword(email);
      setMessage(result.message);
      setEmail("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
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
            Reset password
          </h1>
          <p className="mt-1 text-[13px] text-muted-foreground">
            Enter your email and we will send a reset link if an account exists.
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
          {message && (
            <p className="mb-4 rounded-md border border-border bg-muted/40 px-3 py-2 text-[13px] text-foreground">
              {message}
            </p>
          )}
          <label className="mb-6 block">
            <span className="mb-1.5 block text-[13px] font-medium text-foreground">Email</span>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="username"
              className="h-9 w-full rounded-md border border-input bg-background px-3 text-[13px] text-foreground focus:border-ring focus:outline-none"
            />
          </label>
          <Button type="submit" className="w-full" disabled={submitting}>
            {submitting ? "Sending…" : "Send reset link"}
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
