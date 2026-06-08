import { Navigate, Outlet } from "react-router-dom";
import { LoadingSpinner } from "@/components/LoadingSpinner";
import { useAuth } from "./AuthContext";

export function FinanceRoute() {
  const { user, loading, isAdmin } = useAuth();

  if (loading) {
    return (
      <LoadingSpinner
        centered
        className="text-muted-foreground"
        containerClassName="min-h-[40vh] py-0"
      />
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
