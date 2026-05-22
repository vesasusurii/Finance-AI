import { Navigate, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider } from "./auth/AuthContext";
import { LoginPage } from "./auth/LoginPage";
import { ProtectedRoute } from "./auth/ProtectedRoute";
import { AppLayout } from "./components/shell/AppLayout";
import { AuditPage } from "./routes/admin.audit-logs";
import { PermissionsPage } from "./routes/admin.permissions";
import { SettingsPage } from "./routes/admin.settings";
import { UsersPage } from "./routes/admin.users";
import { BankPage } from "./routes/bank-statements";
import { DocumentsPage } from "./routes/documents";
import { ExportsPage } from "./routes/exports";
import { UploadPage } from "./routes/index";
import { ManualReviewPage } from "./routes/manual-review";
import { MatchingPage } from "./routes/matching";
import { ReviewPage } from "./routes/review";

const queryClient = new QueryClient();

export default function App() {
  return (
    <AuthProvider>
      <QueryClientProvider client={queryClient}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<ProtectedRoute />}>
            <Route element={<AppLayout />}>
              <Route index element={<UploadPage />} />
              <Route path="documents" element={<DocumentsPage />} />
              <Route path="review" element={<ReviewPage />} />
              <Route path="bank-statements" element={<BankPage />} />
              <Route path="matching" element={<MatchingPage />} />
              <Route path="manual-review" element={<ManualReviewPage />} />
              <Route path="exports" element={<ExportsPage />} />
              <Route path="admin/users" element={<UsersPage />} />
              <Route path="admin/permissions" element={<PermissionsPage />} />
              <Route path="admin/audit-logs" element={<AuditPage />} />
              <Route path="admin/settings" element={<SettingsPage />} />
            </Route>
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </QueryClientProvider>
    </AuthProvider>
  );
}
