import { FormEvent, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "./AuthContext";

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
    return <Navigate to="/dashboard" replace />;
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await login(email, password);
      navigate("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="section">
      <div className="container" style={{ maxWidth: 420 }}>
        <header className="stack-3" style={{ marginBottom: "2rem" }}>
          <p className="eyebrow">Borek Finance</p>
          <h1>Sign in</h1>
        </header>
        {showDevLoginHint && (
          <div
            className="card card--flagged stack-3"
            style={{ marginBottom: "1rem" }}
            role="note"
          >
            <p className="eyebrow">Dev login (temporary)</p>
            <p className="text-fg2" style={{ fontSize: "0.9rem" }}>
              Email: <code className="tok">{DEV_LOGIN_EMAIL}</code>
              <br />
              Password: <code className="tok">{DEV_LOGIN_PASSWORD}</code>
            </p>
            <p className="tok" style={{ marginTop: "0.5rem" }}>
              Hide: set VITE_SHOW_DEV_LOGIN_HINT=false in .env
            </p>
          </div>
        )}
        <form className="card stack-4" onSubmit={handleSubmit}>
          {error && <p className="text-accent">{error}</p>}
          <label className="stack-2">
            <span className="text-fg2">Email</span>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="username"
              style={{ width: "100%", padding: "0.5rem" }}
            />
          </label>
          <label className="stack-2">
            <span className="text-fg2">Password</span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
              style={{ width: "100%", padding: "0.5rem" }}
            />
          </label>
          <button type="submit" className="btn btn-accent" disabled={submitting}>
            {submitting ? "Signing in…" : "Sign in"}
          </button>
        </form>
      </div>
    </div>
  );
}
