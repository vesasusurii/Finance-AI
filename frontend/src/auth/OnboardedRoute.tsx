import { Navigate, Outlet } from "react-router-dom";
import { LoadingSpinner } from "@/components/LoadingSpinner";
import { useAuth } from "./AuthContext";
import { needsOnboarding } from "@/types/auth";

export function OnboardedRoute() {
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

  if (needsOnboarding(user)) {
    return <Navigate to="/onboarding" replace />;
  }

  return <Outlet />;
}
