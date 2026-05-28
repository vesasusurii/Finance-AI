import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "./AuthContext";

export function FinanceRoute() {
  const { user, loading, isAdmin } = useAuth();

  if (loading) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <p className="text-[13px] text-muted-foreground">Loading…</p>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  if (isAdmin) {
    return <Navigate to="/admin/users" replace />;
  }

  return <Outlet />;
}
