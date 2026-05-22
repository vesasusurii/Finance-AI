import { Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import { LoginPage } from "./auth/LoginPage";
import { ProtectedRoute } from "./auth/ProtectedRoute";
import { DashboardPage } from "./pages/Dashboard/DashboardPage";
import { ExportPage } from "./pages/Export/ExportPage";
import { PurchaseInvoicesTablePage } from "./pages/PurchaseInvoicesTable/PurchaseInvoicesTablePage";
import { UploadInvoicesPage } from "./pages/UploadInvoices/UploadInvoicesPage";

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route element={<ProtectedRoute />}>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/invoices/upload" element={<UploadInvoicesPage />} />
          <Route path="/invoices" element={<PurchaseInvoicesTablePage />} />
          <Route path="/export" element={<ExportPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </AuthProvider>
  );
}
