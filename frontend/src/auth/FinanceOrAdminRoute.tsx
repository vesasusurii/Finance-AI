import { Navigate, Outlet } from "react-router-dom";
import { LoadingSpinner } from "@/components/LoadingSpinner";
import { useAuth } from "./AuthContext";

/** Bank statement routes — finance users see their own uploads; admins see all. */
export function FinanceOrAdminRoute() {
  const { user, loading } = useAuth();

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

  return <Outlet />;
}
