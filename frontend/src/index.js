import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Routes, Route, useLocation } from "react-router-dom";
import { QueryClientProvider } from "@tanstack/react-query";
import "@/index.css";
import App from "@/App";
import AdminPage from "@/features/admin/AdminPage";
import ActivationPage from "@/features/activation/ActivationPage";
import { AuthGate } from "@/features/auth/AuthGate";
import { AuthCallback } from "@/features/auth/AuthCallback";
import { OwnerReportPage } from "@/features/owner-report/OwnerReportPage";
import { queryClient } from "@/lib/queryClient";

const AppRouter = () => {
  const location = useLocation();
  if (location.hash?.includes("session_id=")) return <AuthCallback />;
  return (
    <Routes>
      <Route path={process.env.REACT_APP_ADMIN_PATH} element={<AdminPage />} />
      <Route path="/aktivasi" element={<ActivationPage />} />
      <Route path="/report/:shareId" element={<OwnerReportPage />} />
      <Route path="*" element={<AuthGate>{(s) => <App key={s.license.id} {...s} />}</AuthGate>} />
    </Routes>
  );
};

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AppRouter />
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>,
);
