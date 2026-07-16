import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "@/context/AuthContext";
import { ThemeProvider } from "@/context/ThemeContext";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import Layout from "@/components/Layout";

import LoginPage from "@/pages/LoginPage";
import ForgotPasswordPage from "@/pages/ForgotPasswordPage";
import ResetPasswordPage from "@/pages/ResetPasswordPage";
import DashboardPage from "@/pages/DashboardPage";
import OwnersPage from "@/pages/OwnersPage";
import OwnerDetailPage from "@/pages/OwnerDetailPage";
import UsersPage from "@/pages/UsersPage";
import RolesPage from "@/pages/RolesPage";
import CompanyProfilePage from "@/pages/CompanyProfilePage";
import BranchesPage from "@/pages/BranchesPage";
import CountriesPage from "@/pages/CountriesPage";
import CitiesPage from "@/pages/CitiesPage";
import CurrenciesPage from "@/pages/CurrenciesPage";
import SettingsPage from "@/pages/SettingsPage";
import ActivityLogPage from "@/pages/ActivityLogPage";
import AuditLogPage from "@/pages/AuditLogPage";

export default function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/forgot-password" element={<ForgotPasswordPage />} />
            <Route path="/reset-password" element={<ResetPasswordPage />} />

            <Route
              element={
                <ProtectedRoute>
                  <Layout />
                </ProtectedRoute>
              }
            >
              <Route path="/dashboard" element={<DashboardPage />} />
              <Route path="/owners" element={<ProtectedRoute permission="owners.view"><OwnersPage /></ProtectedRoute>} />
              <Route path="/owners/:id" element={<ProtectedRoute permission="owners.view"><OwnerDetailPage /></ProtectedRoute>} />
              <Route path="/users" element={<ProtectedRoute permission="users.view"><UsersPage /></ProtectedRoute>} />
              <Route path="/roles" element={<ProtectedRoute permission="roles.view"><RolesPage /></ProtectedRoute>} />
              <Route path="/company-profile" element={<ProtectedRoute permission="company.view"><CompanyProfilePage /></ProtectedRoute>} />
              <Route path="/branches" element={<ProtectedRoute permission="branches.view"><BranchesPage /></ProtectedRoute>} />
              <Route path="/countries" element={<ProtectedRoute permission="countries.view"><CountriesPage /></ProtectedRoute>} />
              <Route path="/cities" element={<ProtectedRoute permission="cities.view"><CitiesPage /></ProtectedRoute>} />
              <Route path="/currencies" element={<ProtectedRoute permission="currencies.view"><CurrenciesPage /></ProtectedRoute>} />
              <Route path="/settings" element={<ProtectedRoute permission="settings.view"><SettingsPage /></ProtectedRoute>} />
              <Route path="/activity-log" element={<ActivityLogPage />} />
              <Route path="/audit-log" element={<ProtectedRoute permission="audit.view"><AuditLogPage /></ProtectedRoute>} />
            </Route>

            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
  );
}
