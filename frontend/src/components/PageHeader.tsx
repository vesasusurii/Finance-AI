import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

const NAV = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/invoices/upload", label: "Upload" },
  { to: "/invoices", label: "Invoices" },
  { to: "/export", label: "Export" },
];

export function PageHeader({ title }: { title: string }) {
  const { user, logout } = useAuth();

  return (
    <header className="stack-4" style={{ marginBottom: "1.5rem" }}>
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: "1rem",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <p className="eyebrow">Borek Finance</p>
        <div style={{ display: "flex", gap: "0.75rem", alignItems: "center" }}>
          <span className="text-fg2 tok">{user?.email}</span>
          <button type="button" className="btn btn-ghost" onClick={() => logout()}>
            Log out
          </button>
        </div>
      </div>
      <nav style={{ display: "flex", flexWrap: "wrap", gap: "0.75rem" }}>
        {NAV.map((item) => (
          <Link key={item.to} to={item.to} className="btn btn-ghost">
            {item.label}
          </Link>
        ))}
      </nav>
      <h1>{title}</h1>
    </header>
  );
}
