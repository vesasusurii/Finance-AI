import { useState, type FormEvent } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "./AuthContext";
import { Button } from "@/components/ui-finance/Button";

/** Matches backend/scripts/seed_admin.py defaults — remove hint before production. */
const DEV_LOGIN_EMAIL = "finance@borek.com";
const DEV_LOGIN_PASSWORD = "changeme";

const showDevLoginHint =
  import.meta.env.VITE_SHOW_DEV_LOGIN_HINT !== "false" &&
  (import.meta.env.DEV || import.meta.env.VITE_SHOW_DEV_LOGIN_HINT === "true");

export function LoginPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState(showDevLoginHint ? DEV_LOGIN_EMAIL : "");
  const [password, setPassword] = useState(showDevLoginHint ? DEV_LOGIN_PASSWORD : "");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (user) {
    return <Navigate to="/" replace />;
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await login(email, password);
      navigate("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="w-full max-w-md">
        <header className="mb-8 text-center">
          <div className="mx-auto mb-4 grid h-10 w-10 place-items-center rounded-md bg-primary text-[13px] font-bold text-primary-foreground">
            B
          </div>
          <p className="text-[11px] font-medium uppercase tracking-[0.08em] text-muted-foreground">
            Borek Finance
          </p>
          <h1 className="mt-2 text-[22px] font-semibold tracking-tight text-foreground">Sign in</h1>
          <p className="mt-1 text-[13px] text-muted-foreground">
            Internal operations platform for Borek Solutions Group
          </p>
        </header>

        {showDevLoginHint && (
          <div
            className="mb-4 rounded-lg border border-border bg-surface-muted px-4 py-3 text-[13px] text-muted-foreground"
            role="note"
          >
            <p className="font-medium text-foreground">Dev login (temporary)</p>
            <p className="mt-1">
              Email: <span className="font-mono text-foreground">{DEV_LOGIN_EMAIL}</span>
              <br />
              Password: <span className="font-mono text-foreground">{DEV_LOGIN_PASSWORD}</span>
            </p>
            <p className="mt-2 text-[11px]">Hide: set VITE_SHOW_DEV_LOGIN_HINT=false in .env</p>
          </div>
        )}

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
          <label className="mb-6 block">
            <span className="mb-1.5 block text-[13px] font-medium text-foreground">Password</span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
              className="h-9 w-full rounded-md border border-input bg-background px-3 text-[13px] text-foreground focus:border-ring focus:outline-none"
            />
          </label>
          <Button type="submit" className="w-full" disabled={submitting}>
            {submitting ? "Signing in…" : "Sign in"}
          </Button>
        </form>
      </div>
    </div>
  );
}
