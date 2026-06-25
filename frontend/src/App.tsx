import { Navigate, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { LoginPage } from "./auth/LoginPage";
import { AdminRoute } from "./auth/AdminRoute";
import { FinanceRoute } from "./auth/FinanceRoute";
import { FinanceOrAdminRoute } from "./auth/FinanceOrAdminRoute";
import { OnboardedRoute } from "./auth/OnboardedRoute";
import { OnboardingPage } from "./auth/OnboardingPage";
import { ProtectedRoute } from "./auth/ProtectedRoute";
import { AppLayout } from "./components/shell/AppLayout";
import { AuditPage } from "./routes/admin.audit-logs";
import { PermissionsPage } from "./routes/admin.permissions";
import { SettingsPage } from "./routes/admin.settings";
import { UsersPage } from "./routes/admin.users";
import { BankPage } from "./routes/bank-statements";
import { BankTransactionsPage } from "./routes/bank-transactions";
import { DocumentsPage } from "./routes/documents";
import { ExportsPage } from "./routes/exports";
import { UploadPage } from "./routes/index";
import { ManualReviewPage } from "./routes/manual-review";
import { MatchingPage } from "./routes/matching";

const queryClient = new QueryClient();

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<ProtectedRoute />}>
            <Route path="/onboarding" element={<OnboardingPage />} />
            <Route element={<OnboardedRoute />}>
              <Route element={<AppLayout />}>
                <Route element={<FinanceOrAdminRoute />}>
                  <Route path="bank-statements" element={<BankPage />} />
                  <Route path="bank-transactions" element={<BankTransactionsPage />} />
                </Route>
                <Route element={<FinanceRoute />}>
                  <Route index element={<UploadPage />} />
                  <Route path="documents" element={<DocumentsPage />} />
                  <Route path="matching" element={<MatchingPage />} />
                  <Route path="manual-review" element={<ManualReviewPage />} />
                  <Route path="review" element={<Navigate to="/manual-review" replace />} />
                  <Route path="exports" element={<ExportsPage />} />
                </Route>
                <Route element={<AdminRoute />}>
                  <Route path="admin/users" element={<UsersPage />} />
                  <Route path="admin/permissions" element={<PermissionsPage />} />
                  <Route path="admin/audit-logs" element={<AuditPage />} />
                  <Route path="admin/settings" element={<SettingsPage />} />
                </Route>
              </Route>
            </Route>
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </QueryClientProvider>
  );
}
