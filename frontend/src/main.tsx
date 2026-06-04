import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import { AppDialogProvider } from "./components/dialogs/AppDialogProvider";
import App from "./App";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AuthProvider>
      <AppDialogProvider>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </AppDialogProvider>
    </AuthProvider>
  </StrictMode>,
);
