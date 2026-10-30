import { Suspense, lazy } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "@/context/AuthContext";
import { ThemeProvider } from "@/context/ThemeContext";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import Layout from "@/components/Layout";

// Login and its two small auxiliary pages are the very first thing an
// unauthenticated person sees, so they stay in the main bundle (no
// loading flicker on first paint). Every authenticated page behind
// Layout is lazy-loaded — a person only downloads the code for pages
// they actually visit, which meaningfully shrinks the initial bundle
// for an app with 30 routes. This changes *how* the code is loaded,
// never what it does — same components, same props, same behavior.
import LoginPage from "@/pages/LoginPage";
import ForgotPasswordPage from "@/pages/ForgotPasswordPage";
import ResetPasswordPage from "@/pages/ResetPasswordPage";

const DashboardPage = lazy(() => import("@/pages/DashboardPage"));
const EnterpriseDashboardPage = lazy(() => import("@/pages/EnterpriseDashboardPage"));
const OwnersPage = lazy(() => import("@/pages/OwnersPage"));
const OwnerDetailPage = lazy(() => import("@/pages/OwnerDetailPage"));
const LeasesPage = lazy(() => import("@/pages/LeasesPage"));
const LeaseDetailPage = lazy(() => import("@/pages/LeaseDetailPage"));
const PropertiesPage = lazy(() => import("@/pages/PropertiesPage"));
const PropertyDetailPage = lazy(() => import("@/pages/PropertyDetailPage"));
const TenantsPage = lazy(() => import("@/pages/TenantsPage"));
const TenantDetailPage = lazy(() => import("@/pages/TenantDetailPage"));
const RentalsPage = lazy(() => import("@/pages/RentalsPage"));
const RentalDetailPage = lazy(() => import("@/pages/RentalDetailPage"));
const PaymentsPage = lazy(() => import("@/pages/PaymentsPage"));
const CollectRentPage = lazy(() => import("@/pages/CollectRentPage"));
const RentCyclesPage = lazy(() => import("@/pages/RentCyclesPage"));
const RentalReceiptsPage = lazy(() => import("@/pages/RentalReceiptsPage"));
const RentalReceiptPrintPage = lazy(() => import("@/pages/RentalReceiptPrintPage"));
const RentVoucherPrintPage = lazy(() => import("@/pages/RentVoucherPrintPage"));
const ReceiptPrintPage = lazy(() => import("@/pages/ReceiptPrintPage"));
const SetVacantUnitPricesPage = lazy(() => import("@/pages/SetVacantUnitPricesPage"));
const NewLeaseWizardPage = lazy(() => import("@/pages/NewLeaseWizardPage"));
const RentVouchersPage = lazy(() => import("@/pages/RentVouchersPage"));
const PendingRentSlipsPage = lazy(() => import("@/pages/PendingRentSlipsPage"));
const FinancialPage = lazy(() => import("@/pages/FinancialPage"));
// const RentBillingPage = lazy(() => import("@/pages/RentBillingPage")); // disabled — see the route comment below
const InvoicePrintPage = lazy(() => import("@/pages/InvoicePrintPage"));
const MaintenancePage = lazy(() => import("@/pages/MaintenancePage"));
const MaintenanceDetailPage = lazy(() => import("@/pages/MaintenanceDetailPage"));
const MaintenanceDirectoryPage = lazy(() => import("@/pages/MaintenanceDirectoryPage"));
const MaintenanceContractsPage = lazy(() => import("@/pages/MaintenanceContractsPage"));
const AccountingPage = lazy(() => import("@/pages/AccountingPage"));
const ReportsPage = lazy(() => import("@/pages/ReportsPage"));
const DataAuditPage = lazy(() => import("@/pages/DataAuditPage"));
const UsersPage = lazy(() => import("@/pages/UsersPage"));
const RolesPage = lazy(() => import("@/pages/RolesPage"));
const CompanyProfilePage = lazy(() => import("@/pages/CompanyProfilePage"));
const BranchesPage = lazy(() => import("@/pages/BranchesPage"));
const CountriesPage = lazy(() => import("@/pages/CountriesPage"));
const CitiesPage = lazy(() => import("@/pages/CitiesPage"));
const CurrenciesPage = lazy(() => import("@/pages/CurrenciesPage"));
const SettingsPage = lazy(() => import("@/pages/SettingsPage"));
const ActivityLogPage = lazy(() => import("@/pages/ActivityLogPage"));
const AuditLogPage = lazy(() => import("@/pages/AuditLogPage"));

export default function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/forgot-password" element={<ForgotPasswordPage />} />
            <Route path="/reset-password" element={<ResetPasswordPage />} />

            {/* Standalone print view — deliberately outside Layout (no
                sidebar/navbar should ever be visible in a print dialog),
                but still requires authentication. Needs its own Suspense
                boundary since it isn't nested under Layout's. */}
            <Route
              path="/rentals/receipts/:installmentId/print"
              element={
                <ProtectedRoute permission="rentals.view">
                  <Suspense fallback={<div />}>
                    <RentalReceiptPrintPage />
                  </Suspense>
                </ProtectedRoute>
              }
            />

            <Route
              path="/financial/invoices/:invoiceId/print"
              element={
                <ProtectedRoute permission="financial.view">
                  <Suspense fallback={<div />}>
                    <InvoicePrintPage />
                  </Suspense>
                </ProtectedRoute>
              }
            />

            {/* Standalone print view for the Rent Voucher module (Phase
                15/backend + this page) — expects ?ids=1,2,3,4 (up to 4,
                a tenant+company pair per transaction), same "outside
                Layout, own Suspense boundary, still requires auth"
                convention as the two routes above. */}
            <Route
              path="/rent-vouchers/print"
              element={
                <ProtectedRoute permission="rent_vouchers.view">
                  <Suspense fallback={<div />}>
                    <RentVoucherPrintPage />
                  </Suspense>
                </ProtectedRoute>
              }
            />

            <Route
              path="/receipts/:receiptId/print"
              element={
                <ProtectedRoute permission="financial.view">
                  <Suspense fallback={<div />}>
                    <ReceiptPrintPage />
                  </Suspense>
                </ProtectedRoute>
              }
            />

            <Route
              element={
                <ProtectedRoute>
                  <Layout />
                </ProtectedRoute>
              }
            >
              <Route path="/dashboard" element={<DashboardPage />} />
              {/* Dashboard consolidation: Enterprise Dashboard was merged
                  into the single unified /dashboard page (its per-building
                  occupancy overview, contract, and tenant data now live
                  there). Its deeper trend charts remain available at
                  /reports. Restore by uncommenting this route (and the
                  matching Sidebar.tsx entry) if a separate page is needed
                  again — EnterpriseDashboardPage.tsx itself is untouched. */}
              {/* <Route path="/enterprise-dashboard" element={<ProtectedRoute permission="reports.view"><EnterpriseDashboardPage /></ProtectedRoute>} /> */}
              <Route path="/owners" element={<ProtectedRoute permission="owners.view"><OwnersPage /></ProtectedRoute>} />
              <Route path="/owners/:id" element={<ProtectedRoute permission="owners.view"><OwnerDetailPage /></ProtectedRoute>} />
              <Route path="/leases" element={<ProtectedRoute permission="leases.view"><LeasesPage /></ProtectedRoute>} />
              <Route path="/leases/:id" element={<ProtectedRoute permission="leases.view"><LeaseDetailPage /></ProtectedRoute>} />
              <Route path="/properties" element={<ProtectedRoute permission="properties.view"><PropertiesPage /></ProtectedRoute>} />
              <Route path="/properties/vacant-missing-price" element={<ProtectedRoute permission="properties.edit"><Suspense fallback={<div />}><SetVacantUnitPricesPage /></Suspense></ProtectedRoute>} />
              <Route path="/properties/:id" element={<ProtectedRoute permission="properties.view"><PropertyDetailPage /></ProtectedRoute>} />
              <Route path="/tenants" element={<ProtectedRoute permission="tenants.view"><TenantsPage /></ProtectedRoute>} />
              <Route path="/tenants/:id" element={<ProtectedRoute permission="tenants.view"><TenantDetailPage /></ProtectedRoute>} />
              <Route path="/rentals/new-wizard" element={<ProtectedRoute permission="rentals.create"><Suspense fallback={<div />}><NewLeaseWizardPage /></Suspense></ProtectedRoute>} />
              <Route path="/rentals" element={<ProtectedRoute permission="rentals.view"><RentalsPage /></ProtectedRoute>} />
              <Route path="/rentals/receipts" element={<ProtectedRoute permission="rentals.view"><RentalReceiptsPage /></ProtectedRoute>} />
              <Route path="/rentals/:id" element={<ProtectedRoute permission="rentals.view"><RentalDetailPage /></ProtectedRoute>} />
              <Route path="/payments" element={<ProtectedRoute permission="payments.view"><PaymentsPage /></ProtectedRoute>} />
              <Route path="/payments/collect-rent" element={<ProtectedRoute permission="payments.create"><CollectRentPage /></ProtectedRoute>} />
              <Route path="/rent-cycles" element={<ProtectedRoute permission="rent_cycles.view"><RentCyclesPage /></ProtectedRoute>} />
              <Route path="/rent-vouchers" element={<ProtectedRoute permission="rent_vouchers.view"><RentVouchersPage /></ProtectedRoute>} />
              <Route path="/pending-rent-slips" element={<ProtectedRoute permission="rent_vouchers.view"><PendingRentSlipsPage /></ProtectedRoute>} />
              <Route path="/financial" element={<ProtectedRoute permission="financial.view"><FinancialPage /></ProtectedRoute>} />
              {/* /financial/rent-billing disabled — the Invoice/Rent
                  Billing system it exposed was consolidated into the
                  Rent Cycle Engine's installment schedule (see
                  FinancialPage.tsx's TABS comment for the full
                  reasoning). Route commented out, not deleted — same
                  reversible pattern as Currencies/Countries below. */}
              {/* <Route path="/financial/rent-billing" element={<ProtectedRoute permission="financial.view"><RentBillingPage /></ProtectedRoute>} /> */}
              <Route path="/maintenance" element={<ProtectedRoute permission="maintenance.view"><MaintenancePage /></ProtectedRoute>} />
              <Route path="/maintenance/directory" element={<ProtectedRoute permission="maintenance.view"><MaintenanceDirectoryPage /></ProtectedRoute>} />
              <Route path="/maintenance/contracts" element={<ProtectedRoute permission="maintenance.view"><MaintenanceContractsPage /></ProtectedRoute>} />
              <Route path="/maintenance/:id" element={<ProtectedRoute permission="maintenance.view"><MaintenanceDetailPage /></ProtectedRoute>} />
              <Route path="/accounting" element={<ProtectedRoute permission="accounting.view"><AccountingPage /></ProtectedRoute>} />
              <Route path="/reports" element={<ProtectedRoute permission="reports.view"><ReportsPage /></ProtectedRoute>} />
              <Route path="/reports/data-audit" element={<ProtectedRoute permission="reports.view"><DataAuditPage /></ProtectedRoute>} />
              <Route path="/users" element={<ProtectedRoute permission="users.view"><UsersPage /></ProtectedRoute>} />
              <Route path="/roles" element={<ProtectedRoute permission="roles.view"><RolesPage /></ProtectedRoute>} />
              <Route path="/company-profile" element={<ProtectedRoute permission="company.view"><CompanyProfilePage /></ProtectedRoute>} />
              <Route path="/branches" element={<ProtectedRoute permission="branches.view"><BranchesPage /></ProtectedRoute>} />
              {/* Dashboard/Currency-Country simplification: standalone Country
                  and Currency management screens are intentionally disabled
                  (single-country, single-currency operation) — the underlying
                  Country/Currency tables, their read endpoints, and every FK
                  that depends on them are untouched; Company Profile's single
                  "default currency" / "country" pickers still work exactly as
                  before. Restore by uncommenting these two routes (and the
                  matching Sidebar.tsx entries) if multi-country/multi-currency
                  is ever needed again. */}
              {/* <Route path="/countries" element={<ProtectedRoute permission="countries.view"><CountriesPage /></ProtectedRoute>} /> */}
              <Route path="/cities" element={<ProtectedRoute permission="cities.view"><CitiesPage /></ProtectedRoute>} />
              {/* <Route path="/currencies" element={<ProtectedRoute permission="currencies.view"><CurrenciesPage /></ProtectedRoute>} /> */}
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
