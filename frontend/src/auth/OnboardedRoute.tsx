import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "./AuthContext";
import { needsOnboarding } from "@/types/auth";

export function OnboardedRoute() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <p className="text-[13px] text-muted-foreground">Loading…</p>
      </div>
    );
  }

  if (needsOnboarding(user)) {
    return <Navigate to="/onboarding" replace />;
  }

  return <Outlet />;
}
