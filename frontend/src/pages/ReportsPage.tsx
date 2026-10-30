import { useEffect, useState, useCallback } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import apiClient from "@/api/client";
import { PageHeader, EmptyState } from "@/components/ui";
import ReportExportBar from "@/components/ReportExportBar";
import {
  Loader2, TrendingUp, TrendingDown, Users, UserSquare2, Home,
  DoorOpen, DoorClosed, Wrench, FileSignature, Calendar, Plus, Trash2, Play, Pause,
} from "lucide-react";
import {
  PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import {
  FinancialReport, TenantReport, OwnerReport, PropertyReport, VacancyReport,
  OccupancyReport, UnitReport, IncomeReport, ExpenseReport, ProfitReport, DashboardAnalytics,
  LeaseReport, MaintenanceReport, CollectionsReport, OutstandingReport, ContractExpirationReport, ReportSchedule,
} from "@/types";

type TabKey = "dashboard" | "financial" | "tenants" | "owners" | "properties" | "vacancy" | "occupancy" | "units" | "income" | "expenses" | "profit" | "leases" | "maintenance" | "collections" | "outstanding" | "expirations" | "schedules" | "ownerBalance" | "tenantLedger" | "securityDeposits" | "renewedContracts" | "topTenants" | "repeatedLatePayers";
type TabGroup = "overview" | "financial" | "occupancy" | "people" | "contracts" | "operations";

const TAB_GROUPS: { key: TabGroup; label: string; icon: string }[] = [
  { key: "overview", label: "Overview", icon: "📊" },
  { key: "financial", label: "Financial", icon: "💰" },
  { key: "occupancy", label: "Occupancy & Properties", icon: "🏢" },
  { key: "people", label: "People", icon: "👥" },
  { key: "contracts", label: "Contracts", icon: "📄" },
  { key: "operations", label: "Operations", icon: "🔧" },
];

const TABS: { key: TabKey; labelKey: string; group: TabGroup }[] = [
  { key: "dashboard", labelKey: "tabs.dashboard", group: "overview" },
  { key: "financial", labelKey: "tabs.financial", group: "financial" },
  { key: "income", labelKey: "tabs.income", group: "financial" },
  { key: "expenses", labelKey: "tabs.expenses", group: "financial" },
  { key: "profit", labelKey: "tabs.profit", group: "financial" },
  { key: "occupancy", labelKey: "tabs.occupancy", group: "occupancy" },
  { key: "units", labelKey: "tabs.units", group: "occupancy" },
  { key: "vacancy", labelKey: "tabs.vacancy", group: "occupancy" },
  { key: "properties", labelKey: "tabs.properties", group: "occupancy" },
  { key: "tenants", labelKey: "tabs.tenants", group: "people" },
  { key: "topTenants", labelKey: "tabs.topTenants", group: "people" },
  { key: "repeatedLatePayers", labelKey: "tabs.repeatedLatePayers", group: "people" },
  { key: "owners", labelKey: "tabs.owners", group: "people" },
  { key: "ownerBalance", labelKey: "tabs.ownerBalance", group: "people" },
  { key: "tenantLedger", labelKey: "tabs.tenantLedger", group: "people" },
  { key: "securityDeposits", labelKey: "tabs.securityDeposits", group: "contracts" },
  { key: "renewedContracts", labelKey: "tabs.renewedContracts", group: "contracts" },
  { key: "leases", labelKey: "tabs.leases", group: "contracts" },
  { key: "expirations", labelKey: "tabs.expirations", group: "contracts" },
  { key: "maintenance", labelKey: "tabs.maintenance", group: "operations" },
  { key: "collections", labelKey: "tabs.collections", group: "operations" },
  { key: "outstanding", labelKey: "tabs.outstanding", group: "operations" },
  { key: "schedules", labelKey: "tabs.schedules", group: "operations" },
];

const monthAgo = () => new Date(Date.now() - 30 * 86400000).toISOString().slice(0, 10);
const today = () => new Date().toISOString().slice(0, 10);

// Lightweight, dependency-free horizontal bar list used across several reports.
function BarList({ items }: { items: { label: string; value: number }[] }) {
  const max = Math.max(...items.map((i) => i.value), 1);
  return (
    <div className="space-y-2">
      {items.map((item, i) => (
        <div key={i}>
          <div className="flex justify-between text-sm mb-0.5">
            <span className="capitalize truncate max-w-[70%]">{item.label}</span>
            <span className="font-medium">{item.value.toLocaleString()}</span>
          </div>
          <div className="h-1.5 bg-ink-100 dark:bg-ink-800 rounded-full overflow-hidden">
            <div className="h-full bg-brand-500 rounded-full" style={{ width: `${(item.value / max) * 100}%` }} />
          </div>
        </div>
      ))}
    </div>
  );
}

export default function ReportsPage() {
  const [searchParams] = useSearchParams();
  const validTabs = TABS.map((t) => t.key);
  const initialTab = (searchParams.get("tab") as TabKey) || "dashboard";
  const [tab, setTab] = useState<TabKey>(validTabs.includes(initialTab) ? initialTab : "dashboard");
  const { t } = useTranslation("reports");
  const navigate = useNavigate();

  return (
    <div>
      <PageHeader
        title={t("title")}
        description={t("description")}
        action={
          <button className="btn-secondary" onClick={() => navigate("/reports/data-audit")}>
            Data Integrity Audit
          </button>
        }
      />

      <div className="mb-4">
        <div className="flex flex-wrap gap-2">
          {TAB_GROUPS.map((g) => {
            const isActiveGroup = TABS.find((t) => t.key === tab)?.group === g.key;
            return (
              <button
                key={g.key}
                onClick={() => { const firstTab = TABS.find((t) => t.group === g.key); if (firstTab) setTab(firstTab.key); }}
                className={`px-3.5 py-2 rounded-lg text-sm font-medium transition-colors flex items-center gap-1.5 ${
                  isActiveGroup ? "bg-brand-500 text-white" : "bg-ink-50 dark:bg-ink-800 text-ink-600 dark:text-ink-300 hover:bg-ink-100 dark:hover:bg-ink-700"
                }`}
              >
                <span>{g.icon}</span> {g.label}
              </button>
            );
          })}
        </div>
      </div>

      <div className="flex gap-1 border-b border-ink-100 dark:border-ink-800 mb-6 overflow-x-auto">
        {TABS.filter((t) => t.group === (TABS.find((x) => x.key === tab)?.group || "overview")).map((tabItem) => (
          <button
            key={tabItem.key}
            onClick={() => setTab(tabItem.key)}
            className={`px-3.5 py-2.5 text-sm font-medium border-b-2 whitespace-nowrap transition-colors ${
              tab === tabItem.key ? "border-brand-500 text-brand-600 dark:text-brand-400" : "border-transparent text-ink-500 hover:text-ink-800 dark:hover:text-ink-100"
            }`}
          >
            {t(tabItem.labelKey)}
          </button>
        ))}
      </div>

      {tab === "dashboard" && <DashboardTab />}
      {tab === "financial" && <FinancialTab />}
      {tab === "income" && <IncomeTab />}
      {tab === "expenses" && <ExpenseTab />}
      {tab === "profit" && <ProfitTab />}
      {tab === "occupancy" && <OccupancyTab />}
      {tab === "units" && <UnitsTab />}
      {tab === "vacancy" && <VacancyTab />}
      {tab === "properties" && <PropertyTab />}
      {tab === "tenants" && <TenantTab />}
      {tab === "topTenants" && <TopTenantsTab />}
      {tab === "repeatedLatePayers" && <RepeatedLatePayersTab />}
      {tab === "owners" && <OwnerTab />}
      {tab === "ownerBalance" && <OwnerBalanceTab />}
      {tab === "tenantLedger" && <TenantLedgerTab />}
      {tab === "securityDeposits" && <SecurityDepositsTab />}
      {tab === "renewedContracts" && <RenewedContractsTab />}
      {tab === "leases" && <LeaseTab />}
      {tab === "maintenance" && <MaintenanceTab />}
      {tab === "collections" && <CollectionsTab />}
      {tab === "outstanding" && <OutstandingTab />}
      {tab === "expirations" && <ContractExpirationTab />}
      {tab === "schedules" && <SchedulesTab />}
    </div>
  );
}

function DateRangeBar({ dateFrom, dateTo, setDateFrom, setDateTo }: { dateFrom: string; dateTo: string; setDateFrom: (v: string) => void; setDateTo: (v: string) => void }) {
  return (
    <div className="card p-4 flex flex-wrap gap-3 items-end mb-4">
      <div><label className="label">From</label><input className="input" type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} /></div>
      <div><label className="label">To</label><input className="input" type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} /></div>
    </div>
  );
}

// ==================== Dashboard Analytics ====================
function DashboardTab() {
  const navigate = useNavigate();
  const [data, setData] = useState<DashboardAnalytics | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiClient.get<DashboardAnalytics>("/reports/analytics/dashboard").then(({ data }) => setData(data)).finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="flex justify-center py-10"><Loader2 className="animate-spin text-ink-400" /></div>;
  if (!data) return null;
  const k = data.kpis;

  const KPI = ({ label, value, icon: Icon, tone }: { label: string; value: string | number; icon: any; tone: string }) => (
    <div className="card p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-medium text-ink-500 dark:text-ink-400">{label}</span>
        <Icon size={16} className={tone} />
      </div>
      <div className="font-display text-xl font-bold">{value}</div>
    </div>
  );

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KPI label="Properties" value={k.total_properties} icon={Home} tone="text-brand-500" />
        <KPI label="Occupied" value={k.occupied_properties} icon={DoorClosed} tone="text-brand-500" />
        <KPI label="Vacancy Rate" value={`${k.vacancy_rate_percentage}%`} icon={DoorOpen} tone="text-amber-500" />
        <KPI label="Tenants" value={k.total_tenants} icon={Users} tone="text-brand-500" />
        <KPI label="Owners" value={k.total_owners} icon={UserSquare2} tone="text-brand-500" />
        <KPI label="Active Rentals" value={k.active_rental_contracts} icon={FileSignature} tone="text-brand-500" />
        <KPI label="Open Maintenance" value={k.open_maintenance_requests} icon={Wrench} tone="text-amber-500" />
        <KPI label="Net Profit (MTD)" value={Number(k.net_profit_this_month).toLocaleString()} icon={TrendingUp} tone="text-brand-500" />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="card p-4">
          <div className="flex items-center gap-2 mb-1"><TrendingUp size={15} className="text-brand-500" /><h3 className="font-display font-semibold text-sm">Income (this month)</h3></div>
          <div className="font-display text-2xl font-bold">{Number(k.total_income_this_month).toLocaleString()}</div>
        </div>
        <div className="card p-4">
          <div className="flex items-center gap-2 mb-1"><TrendingDown size={15} className="text-rust-500" /><h3 className="font-display font-semibold text-sm">Expenses (this month)</h3></div>
          <div className="font-display text-2xl font-bold">{Number(k.total_expense_this_month).toLocaleString()}</div>
        </div>
      </div>

      <div className="card p-5">
        <h3 className="font-display font-semibold text-sm mb-4">Monthly Income / Expense / Profit Trend</h3>
        <div className="space-y-3">
          {data.monthly_trend.map((m) => (
            <div key={m.month}>
              <div className="flex justify-between text-xs text-ink-500 mb-1">
                <span>{m.month}</span>
                <span>Profit: {Number(m.profit).toLocaleString()}</span>
              </div>
              <div className="flex gap-1 h-2">
                <div className="bg-brand-500 rounded-full" style={{ width: `${Math.min((Number(m.income) / (Math.max(Number(m.income), Number(m.expense), 1))) * 100, 100)}%` }} />
                <div className="bg-rust-400 rounded-full" style={{ width: `${Math.min((Number(m.expense) / (Math.max(Number(m.income), Number(m.expense), 1))) * 100, 100)}%` }} />
              </div>
            </div>
          ))}
        </div>
        <div className="flex gap-4 mt-3 text-xs text-ink-400">
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-brand-500 inline-block" /> Income</span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-rust-400 inline-block" /> Expense</span>
        </div>
      </div>

      <div className="card">
        <div className="px-5 py-4 border-b border-ink-100 dark:border-ink-800"><h3 className="font-display font-semibold text-sm">Top Properties by Revenue (last 6 months)</h3></div>
        {data.top_properties_by_revenue.length === 0 ? <EmptyState title="No revenue recorded yet" /> : (
          <div className="divide-y divide-ink-50 dark:divide-ink-800/60">
            {data.top_properties_by_revenue.map((p) => (
              <div key={p.property_id} className="px-5 py-3 flex items-center justify-between cursor-pointer hover:bg-ink-50 dark:hover:bg-ink-800/40" onClick={() => navigate(`/properties/${p.property_id}`)}>
                <div><p className="text-sm font-medium">{p.property_title}</p><p className="text-xs text-ink-400 font-mono">{p.property_code}</p></div>
                <span className="font-medium">{Number(p.total_amount).toLocaleString()}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ==================== Financial ====================
function FinancialTab() {
  const [dateFrom, setDateFrom] = useState(monthAgo());
  const [dateTo, setDateTo] = useState(today());
  const [data, setData] = useState<FinancialReport | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    apiClient.get<FinancialReport>("/reports/financial", { params: { date_from: dateFrom, date_to: dateTo } }).then(({ data }) => setData(data)).finally(() => setLoading(false));
  }, [dateFrom, dateTo]);

  useEffect(() => { load(); }, [load]);

  return (
    <div>
      <DateRangeBar dateFrom={dateFrom} dateTo={dateTo} setDateFrom={setDateFrom} setDateTo={setDateTo} />
      {loading && <div className="flex justify-center py-10"><Loader2 className="animate-spin text-ink-400" /></div>}
      {!loading && data && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            <div className="card p-4"><span className="text-xs text-ink-500">Total Income</span><div className="font-display text-xl font-bold">{Number(data.total_income).toLocaleString()}</div></div>
            <div className="card p-4"><span className="text-xs text-ink-500">Total Expense</span><div className="font-display text-xl font-bold">{Number(data.total_expense).toLocaleString()}</div></div>
            <div className="card p-4"><span className="text-xs text-ink-500">Net Cash Flow</span><div className="font-display text-xl font-bold">{Number(data.net_cash_flow).toLocaleString()}</div></div>
            <div className="card p-4"><span className="text-xs text-ink-500">Outstanding (Tenants)</span><div className="font-display text-xl font-bold">{Number(data.total_outstanding_tenant).toLocaleString()}</div></div>
            <div className="card p-4"><span className="text-xs text-ink-500">Outstanding (Owners)</span><div className="font-display text-xl font-bold">{Number(data.total_outstanding_owner).toLocaleString()}</div></div>
            <div className="card p-4"><span className="text-xs text-ink-500">Collection Rate</span><div className="font-display text-xl font-bold">{data.collection_rate_percentage}%</div></div>
          </div>
          <div className="card p-5">
            <h3 className="font-display font-semibold text-sm mb-3">Transactions by Type</h3>
            {data.transactions_by_type.length === 0 ? <EmptyState title="No transactions in this period" /> : (
              <BarList items={data.transactions_by_type.map((t) => ({ label: t.label.replace(/_/g, " "), value: Number(t.total_amount) }))} />
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ==================== Income ====================
function IncomeTab() {
  const navigate = useNavigate();
  const [dateFrom, setDateFrom] = useState(monthAgo());
  const [dateTo, setDateTo] = useState(today());
  const [data, setData] = useState<IncomeReport | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    apiClient.get<IncomeReport>("/reports/income", { params: { date_from: dateFrom, date_to: dateTo } }).then(({ data }) => setData(data)).finally(() => setLoading(false));
  }, [dateFrom, dateTo]);

  useEffect(() => { load(); }, [load]);

  return (
    <div>
      <DateRangeBar dateFrom={dateFrom} dateTo={dateTo} setDateFrom={setDateFrom} setDateTo={setDateTo} />
      {loading && <div className="flex justify-center py-10"><Loader2 className="animate-spin text-ink-400" /></div>}
      {!loading && data && (
        <div className="space-y-4">
          <div className="card p-4"><span className="text-xs text-ink-500">Total Income</span><div className="font-display text-2xl font-bold">{Number(data.total_income).toLocaleString()}</div></div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="card p-5">
              <h3 className="font-display font-semibold text-sm mb-3">By Category</h3>
              {data.by_category.length === 0 ? <EmptyState title="No income in this period" /> : <BarList items={data.by_category.map((c) => ({ label: c.label.replace(/_/g, " "), value: Number(c.total_amount) }))} />}
            </div>
            <div className="card">
              <div className="px-5 py-4 border-b border-ink-100 dark:border-ink-800"><h3 className="font-display font-semibold text-sm">By Property</h3></div>
              {data.by_property.length === 0 ? <EmptyState title="No property-attributed income" /> : (
                <div className="divide-y divide-ink-50 dark:divide-ink-800/60">
                  {data.by_property.map((p) => (
                    <div key={p.property_id} className="px-5 py-3 flex items-center justify-between cursor-pointer hover:bg-ink-50 dark:hover:bg-ink-800/40" onClick={() => navigate(`/properties/${p.property_id}`)}>
                      <span className="text-sm">{p.property_title}</span><span className="font-medium">{Number(p.total_amount).toLocaleString()}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
          <div className="card p-5">
            <h3 className="font-display font-semibold text-sm mb-3">6-Month Trend</h3>
            <BarList items={data.trend.map((t) => ({ label: t.month, value: Number(t.total_amount) }))} />
          </div>
        </div>
      )}
    </div>
  );
}

// ==================== Expenses ====================
function ExpenseTab() {
  const navigate = useNavigate();
  const [dateFrom, setDateFrom] = useState(monthAgo());
  const [dateTo, setDateTo] = useState(today());
  const [data, setData] = useState<ExpenseReport | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    apiClient.get<ExpenseReport>("/reports/expenses", { params: { date_from: dateFrom, date_to: dateTo } }).then(({ data }) => setData(data)).finally(() => setLoading(false));
  }, [dateFrom, dateTo]);

  useEffect(() => { load(); }, [load]);

  return (
    <div>
      <DateRangeBar dateFrom={dateFrom} dateTo={dateTo} setDateFrom={setDateFrom} setDateTo={setDateTo} />
      {loading && <div className="flex justify-center py-10"><Loader2 className="animate-spin text-ink-400" /></div>}
      {!loading && data && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div className="card p-4"><span className="text-xs text-ink-500">Total Expense (Financial)</span><div className="font-display text-2xl font-bold">{Number(data.total_expense).toLocaleString()}</div></div>
            <div className="card p-4"><span className="text-xs text-ink-500">Maintenance Cost (separate, see notes)</span><div className="font-display text-2xl font-bold">{Number(data.total_maintenance_cost).toLocaleString()}</div></div>
          </div>
          <p className="text-xs text-ink-400">Maintenance costs are shown separately since they may or may not already be recorded as Financial expense transactions, depending on how each request was invoiced — avoiding a risk of double-counting.</p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="card p-5">
              <h3 className="font-display font-semibold text-sm mb-3">By Category</h3>
              {data.by_category.length === 0 ? <EmptyState title="No expenses in this period" /> : <BarList items={data.by_category.map((c) => ({ label: c.label.replace(/_/g, " "), value: Number(c.total_amount) }))} />}
            </div>
            <div className="card">
              <div className="px-5 py-4 border-b border-ink-100 dark:border-ink-800"><h3 className="font-display font-semibold text-sm">By Property</h3></div>
              {data.by_property.length === 0 ? <EmptyState title="No property-attributed expenses" /> : (
                <div className="divide-y divide-ink-50 dark:divide-ink-800/60">
                  {data.by_property.map((p) => (
                    <div key={p.property_id} className="px-5 py-3 flex items-center justify-between cursor-pointer hover:bg-ink-50 dark:hover:bg-ink-800/40" onClick={() => navigate(`/properties/${p.property_id}`)}>
                      <span className="text-sm">{p.property_title}</span><span className="font-medium">{Number(p.total_amount).toLocaleString()}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
          <div className="card p-5">
            <h3 className="font-display font-semibold text-sm mb-3">6-Month Trend</h3>
            <BarList items={data.trend.map((t) => ({ label: t.month, value: Number(t.total_amount) }))} />
          </div>
        </div>
      )}
    </div>
  );
}

// ==================== Profit ====================
function ProfitTab() {
  const [dateFrom, setDateFrom] = useState(monthAgo());
  const [dateTo, setDateTo] = useState(today());
  const [data, setData] = useState<ProfitReport | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    apiClient.get<ProfitReport>("/reports/profit", { params: { date_from: dateFrom, date_to: dateTo } }).then(({ data }) => setData(data)).finally(() => setLoading(false));
  }, [dateFrom, dateTo]);

  useEffect(() => { load(); }, [load]);

  return (
    <div>
      <DateRangeBar dateFrom={dateFrom} dateTo={dateTo} setDateFrom={setDateFrom} setDateTo={setDateTo} />
      {loading && <div className="flex justify-center py-10"><Loader2 className="animate-spin text-ink-400" /></div>}
      {!loading && data && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="card p-4"><span className="text-xs text-ink-500">Income</span><div className="font-display text-xl font-bold">{Number(data.total_income).toLocaleString()}</div></div>
            <div className="card p-4"><span className="text-xs text-ink-500">Expense</span><div className="font-display text-xl font-bold">{Number(data.total_expense).toLocaleString()}</div></div>
            <div className="card p-4"><span className="text-xs text-ink-500">Net Profit</span><div className="font-display text-xl font-bold">{Number(data.net_profit).toLocaleString()}</div></div>
            <div className="card p-4"><span className="text-xs text-ink-500">Margin</span><div className="font-display text-xl font-bold">{data.profit_margin_percentage}%</div></div>
          </div>
          {(data.best_performing_property || data.lowest_performing_property) && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {data.best_performing_property && (
                <div className="card p-4 border border-emerald-100 dark:border-emerald-500/20">
                  <span className="text-xs text-emerald-600 dark:text-emerald-400 font-medium">Best Performing Property</span>
                  <div className="font-display text-lg font-bold mt-1">{data.best_performing_property.property_title}</div>
                  <div className="text-xs text-ink-400">Profit: {Number(data.best_performing_property.profit).toLocaleString()}</div>
                </div>
              )}
              {data.lowest_performing_property && (
                <div className="card p-4 border border-rust-100 dark:border-rust-500/20">
                  <span className="text-xs text-rust-500 font-medium">Lowest Performing Property</span>
                  <div className="font-display text-lg font-bold mt-1">{data.lowest_performing_property.property_title}</div>
                  <div className="text-xs text-ink-400">Profit: {Number(data.lowest_performing_property.profit).toLocaleString()}</div>
                </div>
              )}
            </div>
          )}
          <div className="card">
            <div className="px-5 py-4 border-b border-ink-100 dark:border-ink-800"><h3 className="font-display font-semibold text-sm">Profit by Property</h3></div>
            {data.by_property.length === 0 ? <EmptyState title="No property-attributed activity in this period" /> : (
              <div className="overflow-x-auto"><table className="table-shell">
                <thead><tr><th>Property</th><th>Income</th><th>Expense</th><th>Profit</th></tr></thead>
                <tbody>{data.by_property.map((p) => (
                  <tr key={p.property_id}><td>{p.property_title}</td><td>{Number(p.income).toLocaleString()}</td><td>{Number(p.expense).toLocaleString()}</td><td className="font-medium">{Number(p.profit).toLocaleString()}</td></tr>
                ))}</tbody>
              </table></div>
            )}
          </div>
          <div className="card p-5">
            <h3 className="font-display font-semibold text-sm mb-3">6-Month Profit Trend</h3>
            <BarList items={data.trend.map((t) => ({ label: t.month, value: Number(t.profit) }))} />
          </div>
        </div>
      )}
    </div>
  );
}

// ==================== Occupancy ====================
function OccupancyTab() {
  const [data, setData] = useState<OccupancyReport | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiClient.get<OccupancyReport>("/reports/occupancy", { params: { months: 6 } }).then(({ data }) => setData(data)).finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="flex justify-center py-10"><Loader2 className="animate-spin text-ink-400" /></div>;
  if (!data) return null;

  return (
    <div className="space-y-4">
      <div className="card p-4">
        <span className="text-xs text-ink-500">Overall Occupancy Rate (as of {data.as_of_date})</span>
        <div className="font-display text-3xl font-bold">{data.overall_occupancy_rate_percentage}%</div>
      </div>
      <div className="card p-5">
        <h3 className="font-display font-semibold text-sm mb-3">By Property Type</h3>
        {data.by_property_type.length === 0 ? <EmptyState title="No leasable properties yet" /> : (
          <div className="space-y-3">
            {data.by_property_type.map((t) => (
              <div key={t.property_type}>
                <div className="flex justify-between text-sm mb-1"><span className="capitalize">{t.property_type.replace(/_/g, " ")}</span><span>{t.occupied}/{t.total} ({t.occupancy_rate_percentage}%)</span></div>
                <div className="h-2 bg-ink-100 dark:bg-ink-800 rounded-full overflow-hidden"><div className="h-full bg-brand-500 rounded-full" style={{ width: `${t.occupancy_rate_percentage}%` }} /></div>
              </div>
            ))}
          </div>
        )}
      </div>
      <div className="card p-5">
        <h3 className="font-display font-semibold text-sm mb-3">6-Month Occupancy Trend</h3>
        <BarList items={data.trend.map((t) => ({ label: t.month, value: Number(t.occupancy_rate_percentage) }))} />
      </div>
    </div>
  );
}

// ==================== Units (Phase 2.0: Building/Villa Units, Unit Status, Unit Availability) ====================
function UnitsTab() {
  const navigate = useNavigate();
  const [data, setData] = useState<UnitReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [propertyId, setPropertyId] = useState("");

  const load = useCallback(() => {
    setLoading(true);
    apiClient.get<UnitReport>("/reports/units", { params: { property_id: propertyId || undefined } })
      .then(({ data }) => setData(data)).finally(() => setLoading(false));
  }, [propertyId]);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="space-y-4">
      <div className="card p-4 flex flex-wrap items-end gap-3">
        <div>
          <label className="label">Building / Villa (property ID)</label>
          <input className="input max-w-[220px]" type="number" min="0" placeholder="Leave empty for all units"
            value={propertyId} onChange={(e) => setPropertyId(e.target.value)} />
        </div>
        <p className="text-xs text-ink-400 pb-2">Scope to a specific building or villa's units — Building/Villa Units Report — or leave empty for the portfolio-wide Unit Status &amp; Availability Report.</p>
        {data && <div className="ms-auto"><ReportExportBar reportType="units" filters={{ property_id: propertyId || undefined }} /></div>}
      </div>

      {loading ? <div className="flex justify-center py-10"><Loader2 className="animate-spin text-ink-400" /></div> : !data ? null : (
        <>
          {data.scoped_to_property_title && (
            <div className="card p-4"><span className="text-xs text-ink-500">Scoped to</span><div className="font-display text-lg font-bold">{data.scoped_to_property_title}</div></div>
          )}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <div className="card p-4"><span className="text-xs text-ink-500">Total Units</span><div className="font-display text-xl font-bold">{data.total_units}</div></div>
            <div className="card p-4"><span className="text-xs text-ink-500">Vacant</span><div className="font-display text-xl font-bold">{data.vacant_count}</div></div>
            <div className="card p-4"><span className="text-xs text-ink-500">Occupied</span><div className="font-display text-xl font-bold">{data.occupied_count}</div></div>
            <div className="card p-4"><span className="text-xs text-ink-500">Reserved</span><div className="font-display text-xl font-bold">{data.reserved_count}</div></div>
            <div className="card p-4"><span className="text-xs text-ink-500">Under Maintenance</span><div className="font-display text-xl font-bold">{data.under_maintenance_count}</div></div>
          </div>
          <div className="card p-5">
            <h3 className="font-display font-semibold text-sm mb-3">By Type</h3>
            {data.by_type.length === 0 ? <EmptyState title="No units yet" /> : (
              <BarList items={data.by_type.map((t) => ({ label: t.property_type.replace(/_/g, " "), value: t.count }))} />
            )}
          </div>
          <div className="card">
            <div className="px-5 py-4 border-b border-ink-100 dark:border-ink-800"><h3 className="font-display font-semibold text-sm">Units</h3></div>
            {data.units.length === 0 ? <EmptyState title="No units match this scope" /> : (
              <div className="overflow-x-auto"><table className="table-shell">
                <thead><tr><th>Code</th><th>Title</th><th>Type</th><th>Status</th><th>Building/Villa</th><th>Unit #</th><th>Rent Price</th></tr></thead>
                <tbody>{data.units.map((u) => (
                  <tr key={u.property_id} className="cursor-pointer" onClick={() => navigate(`/properties/${u.property_id}`)}>
                    <td className="font-mono text-xs">{u.property_code}</td><td>{u.title}</td>
                    <td className="capitalize text-ink-500">{u.property_type.replace(/_/g, " ")}</td>
                    <td className="capitalize">{u.availability_status.replace(/_/g, " ")}</td>
                    <td className="text-ink-500">{u.building_title || "—"}</td>
                    <td className="text-ink-500">{u.unit_number || "—"}</td>
                    <td className="text-ink-500">{u.rent_price ?? "—"}</td>
                  </tr>
                ))}</tbody>
              </table></div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

// ==================== Vacancy ====================
function VacancyTab() {
  const navigate = useNavigate();
  const [data, setData] = useState<VacancyReport | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiClient.get<VacancyReport>("/reports/vacancy").then(({ data }) => setData(data)).finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="flex justify-center py-10"><Loader2 className="animate-spin text-ink-400" /></div>;
  if (!data) return null;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="card p-4"><span className="text-xs text-ink-500">Total (leasable)</span><div className="font-display text-xl font-bold">{data.total_properties}</div></div>
        <div className="card p-4"><span className="text-xs text-ink-500">Vacant</span><div className="font-display text-xl font-bold">{data.vacant_count}</div></div>
        <div className="card p-4"><span className="text-xs text-ink-500">Leased</span><div className="font-display text-xl font-bold">{data.leased_count}</div></div>
        <div className="card p-4"><span className="text-xs text-ink-500">Vacancy Rate</span><div className="font-display text-xl font-bold">{data.vacancy_rate_percentage}%</div></div>
      </div>
      <div className="card">
        <div className="px-5 py-4 border-b border-ink-100 dark:border-ink-800"><h3 className="font-display font-semibold text-sm">Vacant Properties</h3></div>
        {data.vacant_properties.length === 0 ? <EmptyState title="No vacant properties — fully leased!" /> : (
          <div className="overflow-x-auto"><table className="table-shell">
            <thead><tr><th>Code</th><th>Title</th><th>Type</th><th>Last Tenant</th><th>Last Rent</th><th>Days Vacant</th></tr></thead>
            <tbody>{data.vacant_properties.map((p) => (
              <tr key={p.property_id} className="cursor-pointer" onClick={() => navigate(`/properties/${p.property_id}`)}>
                <td className="font-mono text-xs">{p.property_code}</td><td>{p.title}</td><td className="capitalize text-ink-500">{p.property_type}</td>
                <td className="text-ink-500">{p.last_tenant || "—"}</td>
                <td className="text-ink-500">{p.last_rent_amount ? Number(p.last_rent_amount).toLocaleString() : "—"}</td>
                <td className={p.days_vacant > 60 ? "text-rust-500 font-medium" : ""}>{p.days_vacant}</td>
              </tr>
            ))}</tbody>
          </table></div>
        )}
      </div>
    </div>
  );
}

// ==================== Properties ====================
function PropertyTab() {
  const navigate = useNavigate();
  const [data, setData] = useState<PropertyReport | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiClient.get<PropertyReport>("/reports/properties").then(({ data }) => setData(data)).finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="flex justify-center py-10"><Loader2 className="animate-spin text-ink-400" /></div>;
  if (!data) return null;

  return (
    <div className="space-y-4">
      <div className="card p-4"><span className="text-xs text-ink-500">Total Properties</span><div className="font-display text-2xl font-bold">{data.total_properties}</div></div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="card p-5"><h3 className="font-display font-semibold text-sm mb-3">By Type</h3><BarList items={data.by_type.map((t) => ({ label: t.property_type.replace(/_/g, " "), value: t.count }))} /></div>
        <div className="card p-5"><h3 className="font-display font-semibold text-sm mb-3">By Availability</h3><BarList items={data.by_availability.map((t) => ({ label: t.availability_status.replace(/_/g, " "), value: t.count }))} /></div>
      </div>
      <div className="card">
        <div className="px-5 py-4 border-b border-ink-100 dark:border-ink-800"><h3 className="font-display font-semibold text-sm">Top Properties by Revenue (last 30 days)</h3></div>
        {data.top_properties_by_revenue.length === 0 ? <EmptyState title="No revenue recorded yet" /> : (
          <div className="divide-y divide-ink-50 dark:divide-ink-800/60">
            {data.top_properties_by_revenue.map((p) => (
              <div key={p.property_id} className="px-5 py-3 flex items-center justify-between cursor-pointer hover:bg-ink-50 dark:hover:bg-ink-800/40" onClick={() => navigate(`/properties/${p.property_id}`)}>
                <span className="text-sm">{p.property_title}</span><span className="font-medium">{Number(p.total_amount).toLocaleString()}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ==================== Tenants ====================
function TenantTab() {
  const navigate = useNavigate();
  const [data, setData] = useState<TenantReport | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiClient.get<TenantReport>("/reports/tenants").then(({ data }) => setData(data)).finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="flex justify-center py-10"><Loader2 className="animate-spin text-ink-400" /></div>;
  if (!data) return null;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="card p-4"><span className="text-xs text-ink-500">Total Tenants</span><div className="font-display text-xl font-bold">{data.total_tenants}</div></div>
        <div className="card p-4"><span className="text-xs text-ink-500">Blacklisted</span><div className="font-display text-xl font-bold">{data.blacklisted_tenants}</div></div>
        <div className="card p-4"><span className="text-xs text-ink-500">Avg. Rating</span><div className="font-display text-xl font-bold">{data.average_rating || "—"}</div></div>
        <div className="card p-4"><span className="text-xs text-ink-500">Contracts Expiring Soon</span><div className="font-display text-xl font-bold">{data.contracts_expiring_soon}</div></div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="card">
          <div className="px-5 py-4 border-b border-ink-100 dark:border-ink-800"><h3 className="font-display font-semibold text-sm">Top Tenants by Payment</h3></div>
          {data.top_tenants_by_payment.length === 0 ? <EmptyState title="No payments yet" /> : (
            <div className="divide-y divide-ink-50 dark:divide-ink-800/60">
              {data.top_tenants_by_payment.map((t) => (
                <div key={t.tenant_id} className="px-5 py-3 flex items-center justify-between cursor-pointer hover:bg-ink-50 dark:hover:bg-ink-800/40" onClick={() => navigate(`/tenants/${t.tenant_id}`)}>
                  <span className="text-sm">{t.display_name}</span><span className="font-medium">{Number(t.total_paid).toLocaleString()}</span>
                </div>
              ))}
            </div>
          )}
        </div>
        <div className="card">
          <div className="px-5 py-4 border-b border-ink-100 dark:border-ink-800"><h3 className="font-display font-semibold text-sm">Outstanding Balances</h3></div>
          {data.outstanding_tenants.length === 0 ? <EmptyState title="No outstanding balances" /> : (
            <div className="divide-y divide-ink-50 dark:divide-ink-800/60">
              {data.outstanding_tenants.map((t) => (
                <div key={t.tenant_id} className="px-5 py-3 flex items-center justify-between cursor-pointer hover:bg-ink-50 dark:hover:bg-ink-800/40" onClick={() => navigate(`/tenants/${t.tenant_id}`)}>
                  <span className="text-sm">{t.display_name}</span><span className="font-medium text-rust-500">{Number(t.outstanding_amount).toLocaleString()}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ==================== Owners ====================
function OwnerTab() {
  const navigate = useNavigate();
  const [data, setData] = useState<OwnerReport | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiClient.get<OwnerReport>("/reports/owners").then(({ data }) => setData(data)).finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="flex justify-center py-10"><Loader2 className="animate-spin text-ink-400" /></div>;
  if (!data) return null;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        <div className="card p-4"><span className="text-xs text-ink-500">Total Owners</span><div className="font-display text-xl font-bold">{data.total_owners}</div></div>
        <div className="card p-4"><span className="text-xs text-ink-500">Individual / Company</span><div className="font-display text-xl font-bold">{data.individual_owners} / {data.company_owners}</div></div>
        <div className="card p-4"><span className="text-xs text-ink-500">Paid to Owners (30d)</span><div className="font-display text-xl font-bold">{Number(data.total_paid_to_owners).toLocaleString()}</div></div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="card">
          <div className="px-5 py-4 border-b border-ink-100 dark:border-ink-800"><h3 className="font-display font-semibold text-sm">Top Owners by Property Count</h3></div>
          {data.top_owners_by_properties.length === 0 ? <EmptyState title="No owners yet" /> : (
            <div className="divide-y divide-ink-50 dark:divide-ink-800/60">
              {data.top_owners_by_properties.map((o) => (
                <div key={o.owner_id} className="px-5 py-3 flex items-center justify-between cursor-pointer hover:bg-ink-50 dark:hover:bg-ink-800/40" onClick={() => navigate(`/owners/${o.owner_id}`)}>
                  <span className="text-sm">{o.display_name}</span><span className="font-medium">{o.property_count}</span>
                </div>
              ))}
            </div>
          )}
        </div>
        <div className="card">
          <div className="px-5 py-4 border-b border-ink-100 dark:border-ink-800"><h3 className="font-display font-semibold text-sm">Outstanding Payables</h3></div>
          {data.outstanding_owners.length === 0 ? <EmptyState title="No outstanding payables" /> : (
            <div className="divide-y divide-ink-50 dark:divide-ink-800/60">
              {data.outstanding_owners.map((o) => (
                <div key={o.owner_id} className="px-5 py-3 flex items-center justify-between cursor-pointer hover:bg-ink-50 dark:hover:bg-ink-800/40" onClick={() => navigate(`/owners/${o.owner_id}`)}>
                  <span className="text-sm">{o.display_name}</span><span className="font-medium text-rust-500">{Number(o.outstanding_amount).toLocaleString()}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function OwnerBalanceTab() {
  const navigate = useNavigate();
  const [data, setData] = useState<{ total_owners: number; total_balance: number; owners_owed_money: number; owners_negative_balance: number; rows: Array<{ id: number; owner_code: string; display_name: string; balance: number }> } | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiClient.get("/reports/owner-balance").then(({ data }) => setData(data)).finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="flex justify-center py-10"><Loader2 className="animate-spin text-ink-400" /></div>;
  if (!data) return null;

  return (
    <div className="space-y-4">
      <div className="flex justify-end"><ReportExportBar reportType="owner_balance" /></div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="card p-4"><span className="text-xs text-ink-500">Total Owners</span><div className="font-display text-xl font-bold">{data.total_owners}</div></div>
        <div className="card p-4"><span className="text-xs text-ink-500">Total Balance</span><div className="font-display text-xl font-bold">{Number(data.total_balance).toLocaleString()}</div></div>
        <div className="card p-4"><span className="text-xs text-ink-500">Owed Money</span><div className="font-display text-xl font-bold text-emerald-600">{data.owners_owed_money}</div></div>
        <div className="card p-4"><span className="text-xs text-ink-500">Negative Balance</span><div className="font-display text-xl font-bold text-rust-500">{data.owners_negative_balance}</div></div>
      </div>
      <div className="card">
        {data.rows.length === 0 ? <EmptyState title="No owners yet" /> : (
          <div className="divide-y divide-ink-50 dark:divide-ink-800/60">
            {data.rows.map((r) => (
              <div key={r.id} className="px-5 py-3 flex items-center justify-between cursor-pointer hover:bg-ink-50 dark:hover:bg-ink-800/40" onClick={() => navigate(`/owners/${r.id}`)}>
                <span className="text-sm">{r.owner_code} — {r.display_name}</span>
                <span className={`font-medium ${r.balance >= 0 ? "text-emerald-600" : "text-rust-500"}`}>{Number(r.balance).toLocaleString()}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function TenantLedgerTab() {
  const [data, setData] = useState<{ total_transactions: number; total_paid: number; rows: Array<{ transaction_number: string; date: string; type: string; tenant_display_name: string; amount: number; payment_method: string | null; description: string | null }> } | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiClient.get("/reports/tenant-ledger").then(({ data }) => setData(data)).finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="flex justify-center py-10"><Loader2 className="animate-spin text-ink-400" /></div>;
  if (!data) return null;

  return (
    <div className="space-y-4">
      <div className="flex justify-end"><ReportExportBar reportType="tenant_ledger" /></div>
      <div className="grid grid-cols-2 gap-3">
        <div className="card p-4"><span className="text-xs text-ink-500">Transactions (latest 500)</span><div className="font-display text-xl font-bold">{data.total_transactions}</div></div>
        <div className="card p-4"><span className="text-xs text-ink-500">Total Paid</span><div className="font-display text-xl font-bold">{Number(data.total_paid).toLocaleString()}</div></div>
      </div>
      <div className="card overflow-x-auto">
        {data.rows.length === 0 ? <EmptyState title="No tenant transactions yet" /> : (
          <table className="w-full text-sm">
            <thead><tr className="text-left text-xs text-ink-400 border-b border-ink-100 dark:border-ink-800">
              <th className="px-4 py-2">Date</th><th className="px-4 py-2">Tenant</th><th className="px-4 py-2">Type</th><th className="px-4 py-2">Method</th><th className="px-4 py-2 text-right">Amount</th>
            </tr></thead>
            <tbody className="divide-y divide-ink-50 dark:divide-ink-800/60">
              {data.rows.map((r, i) => (
                <tr key={i}>
                  <td className="px-4 py-2">{r.date}</td><td className="px-4 py-2">{r.tenant_display_name}</td>
                  <td className="px-4 py-2 capitalize">{r.type.replace(/_/g, " ")}</td><td className="px-4 py-2">{r.payment_method || "—"}</td>
                  <td className="px-4 py-2 text-right font-medium">{Number(r.amount).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function SecurityDepositsTab() {
  const [data, setData] = useState<{ total_contracts_with_deposit: number; total_held: number; total_returned: number; rows: Array<{ contract_number: string; deposit_amount: number; deposit_status: string }> } | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiClient.get("/reports/security-deposits").then(({ data }) => setData(data)).finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="flex justify-center py-10"><Loader2 className="animate-spin text-ink-400" /></div>;
  if (!data) return null;

  return (
    <div className="space-y-4">
      <div className="flex justify-end"><ReportExportBar reportType="security_deposit" /></div>
      <div className="grid grid-cols-3 gap-3">
        <div className="card p-4"><span className="text-xs text-ink-500">Contracts With Deposit</span><div className="font-display text-xl font-bold">{data.total_contracts_with_deposit}</div></div>
        <div className="card p-4"><span className="text-xs text-ink-500">Total Held</span><div className="font-display text-xl font-bold">{Number(data.total_held).toLocaleString()}</div></div>
        <div className="card p-4"><span className="text-xs text-ink-500">Total Returned</span><div className="font-display text-xl font-bold">{Number(data.total_returned).toLocaleString()}</div></div>
      </div>
      <div className="card">
        {data.rows.length === 0 ? <EmptyState title="No deposits recorded" /> : (
          <div className="divide-y divide-ink-50 dark:divide-ink-800/60">
            {data.rows.map((r, i) => (
              <div key={i} className="px-5 py-3 flex items-center justify-between">
                <span className="text-sm">{r.contract_number}</span>
                <span className="flex items-center gap-2">
                  <span className="text-xs px-2 py-0.5 rounded-full bg-ink-100 dark:bg-ink-800 capitalize">{r.deposit_status.replace(/_/g, " ")}</span>
                  <span className="font-medium">{Number(r.deposit_amount).toLocaleString()}</span>
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function RenewedContractsTab() {
  const [data, setData] = useState<{ total_renewed: number; rows: Array<{ contract_number: string; renewed_from_contract_id: number; start_date: string; end_date: string; rent_amount: number }> } | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiClient.get("/reports/renewed-contracts").then(({ data }) => setData(data)).finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="flex justify-center py-10"><Loader2 className="animate-spin text-ink-400" /></div>;
  if (!data) return null;

  return (
    <div className="space-y-4">
      <div className="flex justify-end"><ReportExportBar reportType="renewed_contracts" /></div>
      <div className="card p-4"><span className="text-xs text-ink-500">Total Renewed</span><div className="font-display text-xl font-bold">{data.total_renewed}</div></div>
      <div className="card">
        {data.rows.length === 0 ? <EmptyState title="No renewed contracts yet" /> : (
          <div className="divide-y divide-ink-50 dark:divide-ink-800/60">
            {data.rows.map((r, i) => (
              <div key={i} className="px-5 py-3 flex items-center justify-between">
                <span className="text-sm">{r.contract_number} · {r.start_date} → {r.end_date}</span>
                <span className="font-medium">{Number(r.rent_amount).toLocaleString()}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function TopTenantsTab() {
  const navigate = useNavigate();
  const [data, setData] = useState<{ year: number; rows: Array<{ id: number; tenant_code: string; display_name: string; total_paid: number; payment_count: number }> } | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiClient.get("/reports/top-tenants").then(({ data }) => setData(data)).finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="flex justify-center py-10"><Loader2 className="animate-spin text-ink-400" /></div>;
  if (!data) return null;

  return (
    <div className="space-y-4">
      <div className="flex justify-end"><ReportExportBar reportType="top_tenants" /></div>
      <div className="card p-4"><span className="text-xs text-ink-500">Ranked by total paid in {data.year}</span></div>
      <div className="card">
        {data.rows.length === 0 ? <EmptyState title="No tenant payments recorded this year" /> : (
          <div className="divide-y divide-ink-50 dark:divide-ink-800/60">
            {data.rows.map((r, i) => (
              <div key={r.id} className="px-5 py-3 flex items-center justify-between cursor-pointer hover:bg-ink-50 dark:hover:bg-ink-800/40" onClick={() => navigate(`/tenants/${r.id}`)}>
                <span className="text-sm flex items-center gap-2">
                  <span className="text-xs text-ink-400 w-5">#{i + 1}</span>
                  {r.display_name || r.tenant_code} <span className="text-xs text-ink-400">({r.payment_count} payment{r.payment_count === 1 ? "" : "s"})</span>
                </span>
                <span className="font-medium">{Number(r.total_paid).toLocaleString()}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function RepeatedLatePayersTab() {
  const navigate = useNavigate();
  const [data, setData] = useState<{ total_tenants: number; min_late_count: number; rows: Array<{ id: number; tenant_code: string; display_name: string; late_count: number; total_late_fees: number }> } | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiClient.get("/reports/repeated-late-payers").then(({ data }) => setData(data)).finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="flex justify-center py-10"><Loader2 className="animate-spin text-ink-400" /></div>;
  if (!data) return null;

  return (
    <div className="space-y-4">
      <div className="flex justify-end"><ReportExportBar reportType="repeated_late_payers" /></div>
      <div className="card p-4"><span className="text-xs text-ink-500">Tenants with {data.min_late_count}+ overdue installments</span><div className="font-display text-xl font-bold">{data.total_tenants}</div></div>
      <div className="card">
        {data.rows.length === 0 ? <EmptyState title="No repeated late payers — nothing to flag" /> : (
          <div className="divide-y divide-ink-50 dark:divide-ink-800/60">
            {data.rows.map((r) => (
              <div key={r.id} className="px-5 py-3 flex items-center justify-between cursor-pointer hover:bg-ink-50 dark:hover:bg-ink-800/40" onClick={() => navigate(`/tenants/${r.id}`)}>
                <span className="text-sm">{r.display_name || r.tenant_code}</span>
                <span className="flex items-center gap-3">
                  <span className="text-xs px-2 py-0.5 rounded-full bg-rust-50 dark:bg-rust-500/10 text-rust-500 font-medium">{r.late_count} late</span>
                  <span className="font-medium">{Number(r.total_late_fees).toLocaleString()}</span>
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ==================== Leases ====================
function LeaseTab() {
  const navigate = useNavigate();
  const [data, setData] = useState<LeaseReport | null>(null);
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    apiClient.get<LeaseReport>("/reports/leases", { params: { contract_status: status || undefined } })
      .then(({ data }) => setData(data)).finally(() => setLoading(false));
  }, [status]);

  if (loading) return <div className="flex justify-center py-10"><Loader2 className="animate-spin text-ink-400" /></div>;
  if (!data) return null;

  const barData = data.rental_contracts_by_status.map((s) => ({ name: s.status, Count: s.count }));

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <select className="input max-w-[180px]" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">All statuses</option>
          <option value="draft">Draft</option>
          <option value="active">Active</option>
          <option value="expired">Expired</option>
          <option value="terminated">Terminated</option>
          <option value="renewed">Renewed</option>
        </select>
        <ReportExportBar reportType="lease" filters={{ contract_status: status || undefined }} />
      </div>

      <div className="card p-5">
        <h3 className="font-display font-semibold text-sm mb-4">Rental Contracts by Status</h3>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={barData}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="name" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip />
            <Bar dataKey="Count" fill={CHART_COLORS[0]} radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="card">
        <div className="px-5 py-4 border-b border-ink-100 dark:border-ink-800"><h3 className="font-display font-semibold text-sm">Rental Contracts</h3></div>
        {data.rental_contracts.length === 0 ? <EmptyState title="No rental contracts match this filter" /> : (
          <div className="overflow-x-auto"><table className="table-shell">
            <thead><tr><th>Contract #</th><th>Tenant</th><th>Property</th><th>End Date</th><th>Rent</th><th>Status</th></tr></thead>
            <tbody>{data.rental_contracts.map((c) => (
              <tr key={c.id} className="cursor-pointer" onClick={() => navigate(`/rentals/${c.id}`)}>
                <td className="font-mono text-xs">{c.contract_number}</td><td>{c.tenant_display_name}</td><td>{c.property_title}{c.unit_number ? ` · ${c.unit_number}` : ""}</td>
                <td>{c.end_date}</td><td>{Number(c.rent_amount).toLocaleString()}</td><td className="capitalize">{c.contract_status}</td>
              </tr>
            ))}</tbody>
          </table></div>
        )}
      </div>

      <div className="card">
        <div className="px-5 py-4 border-b border-ink-100 dark:border-ink-800"><h3 className="font-display font-semibold text-sm">Lease Agreements</h3></div>
        {data.lease_agreements.length === 0 ? <EmptyState title="No lease agreements match this filter" /> : (
          <div className="overflow-x-auto"><table className="table-shell">
            <thead><tr><th>Contract #</th><th>Owner</th><th>Property</th><th>End Date</th><th>Rent</th><th>Status</th></tr></thead>
            <tbody>{data.lease_agreements.map((c) => (
              <tr key={c.id} className="cursor-pointer" onClick={() => navigate(`/leases/${c.id}`)}>
                <td className="font-mono text-xs">{c.contract_number}</td><td>{c.owner_display_name}</td><td>{c.property_title}{c.unit_number ? ` · ${c.unit_number}` : ""}</td>
                <td>{c.end_date}</td><td>{Number(c.rent_amount).toLocaleString()}</td><td className="capitalize">{c.contract_status}</td>
              </tr>
            ))}</tbody>
          </table></div>
        )}
      </div>
    </div>
  );
}

// ==================== Maintenance ====================
function MaintenanceTab() {
  const [data, setData] = useState<MaintenanceReport | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiClient.get<MaintenanceReport>("/reports/maintenance").then(({ data }) => setData(data)).finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="flex justify-center py-10"><Loader2 className="animate-spin text-ink-400" /></div>;
  if (!data) return null;

  const statusPie = data.by_status.map((s) => ({ name: s.status, value: s.count }));
  const priorityBar = data.by_priority.map((p) => ({ name: p.priority, Count: p.count }));

  return (
    <div className="space-y-4">
      <div className="flex justify-end"><ReportExportBar reportType="maintenance" /></div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="card p-4"><span className="text-xs text-ink-500">Total Requests</span><div className="font-display text-xl font-bold">{data.total_requests}</div></div>
        <div className="card p-4"><span className="text-xs text-ink-500">Total Cost</span><div className="font-display text-xl font-bold">{Number(data.total_cost).toLocaleString()}</div></div>
        <div className="card p-4"><span className="text-xs text-ink-500">Avg. Resolution (days)</span><div className="font-display text-xl font-bold">{data.average_resolution_days ?? "—"}</div></div>
        <div className="card p-4"><span className="text-xs text-ink-500">Contractors Involved</span><div className="font-display text-xl font-bold">{data.by_contractor.length}</div></div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="card p-5">
          <h3 className="font-display font-semibold text-sm mb-4">By Status</h3>
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie data={statusPie} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={75} label={(e: any) => `${e.name} (${e.value})`}>
                {statusPie.map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>
        <div className="card p-5">
          <h3 className="font-display font-semibold text-sm mb-4">By Priority</h3>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={priorityBar}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="name" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Bar dataKey="Count" fill={CHART_COLORS[2]} radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="card">
        <div className="px-5 py-4 border-b border-ink-100 dark:border-ink-800"><h3 className="font-display font-semibold text-sm">Requests</h3></div>
        {data.requests.length === 0 ? <EmptyState title="No maintenance requests found" /> : (
          <div className="overflow-x-auto"><table className="table-shell">
            <thead><tr><th>Request #</th><th>Title</th><th>Property</th><th>Priority</th><th>Status</th><th>Reported</th><th>Cost</th></tr></thead>
            <tbody>{data.requests.map((r) => (
              <tr key={r.id}>
                <td className="font-mono text-xs">{r.request_number}</td><td>{r.title}</td><td>{r.property_title}</td>
                <td className="capitalize">{r.priority}</td><td className="capitalize">{r.maintenance_status.replace(/_/g, " ")}</td>
                <td>{r.reported_date}</td><td>{Number(r.total_actual_cost).toLocaleString()}</td>
              </tr>
            ))}</tbody>
          </table></div>
        )}
      </div>
    </div>
  );
}

// ==================== Collections ====================
function CollectionsTab() {
  const [data, setData] = useState<CollectionsReport | null>(null);
  const [months, setMonths] = useState(6);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    apiClient.get<CollectionsReport>("/reports/collections", { params: { months } }).then(({ data }) => setData(data)).finally(() => setLoading(false));
  }, [months]);

  if (loading) return <div className="flex justify-center py-10"><Loader2 className="animate-spin text-ink-400" /></div>;
  if (!data) return null;

  const trendBar = data.monthly_trend.map((m) => ({ name: m.month, Due: Number(m.due), Collected: Number(m.collected) }));

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <select className="input max-w-[140px]" value={months} onChange={(e) => setMonths(Number(e.target.value))}>
          <option value={3}>3 months</option>
          <option value={6}>6 months</option>
          <option value={12}>12 months</option>
        </select>
        <ReportExportBar reportType="collections" filters={{ months }} />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        <div className="card p-4"><span className="text-xs text-ink-500">Total Due</span><div className="font-display text-xl font-bold">{Number(data.total_due).toLocaleString()}</div></div>
        <div className="card p-4"><span className="text-xs text-ink-500">Total Collected</span><div className="font-display text-xl font-bold">{Number(data.total_collected).toLocaleString()}</div></div>
        <div className="card p-4"><span className="text-xs text-ink-500">Collection Rate</span><div className="font-display text-xl font-bold">{data.collection_rate_percentage}%</div></div>
      </div>

      <div className="card p-5">
        <h3 className="font-display font-semibold text-sm mb-4">Due vs Collected</h3>
        <ResponsiveContainer width="100%" height={240}>
          <BarChart data={trendBar}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="name" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip />
            <Legend />
            <Bar dataKey="Due" fill={CHART_COLORS[4]} radius={[4, 4, 0, 0]} />
            <Bar dataKey="Collected" fill={CHART_COLORS[0]} radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="card">
        <div className="px-5 py-4 border-b border-ink-100 dark:border-ink-800"><h3 className="font-display font-semibold text-sm">By Property</h3></div>
        {data.by_property.length === 0 ? <EmptyState title="No collections data yet" /> : (
          <div className="overflow-x-auto"><table className="table-shell">
            <thead><tr><th>Property</th><th>Due</th><th>Collected</th><th>Rate %</th></tr></thead>
            <tbody>{data.by_property.map((p) => (
              <tr key={p.property_id}>
                <td>{p.property_title}</td><td>{Number(p.due).toLocaleString()}</td>
                <td>{Number(p.collected).toLocaleString()}</td><td>{p.collection_rate_percentage}%</td>
              </tr>
            ))}</tbody>
          </table></div>
        )}
      </div>
    </div>
  );
}

// ==================== Outstanding ====================
function OutstandingTab() {
  const [data, setData] = useState<OutstandingReport | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiClient.get<OutstandingReport>("/reports/outstanding").then(({ data }) => setData(data)).finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="flex justify-center py-10"><Loader2 className="animate-spin text-ink-400" /></div>;
  if (!data) return null;

  const agingBar = (["current", "days_1_30", "days_31_60", "days_61_90", "days_90_plus"] as const).map((k) => ({
    name: k.replace("days_", "").replace("_", "-"),
    Tenant: Number(data.tenant_aging[k]),
    Owner: Number(data.owner_aging[k]),
  }));

  return (
    <div className="space-y-4">
      <div className="flex justify-end"><ReportExportBar reportType="outstanding" /></div>
      <div className="grid grid-cols-2 gap-3">
        <div className="card p-4"><span className="text-xs text-ink-500">Tenant Outstanding</span><div className="font-display text-xl font-bold">{Number(data.tenant_outstanding_total).toLocaleString()}</div></div>
        <div className="card p-4"><span className="text-xs text-ink-500">Owner Outstanding</span><div className="font-display text-xl font-bold">{Number(data.owner_outstanding_total).toLocaleString()}</div></div>
      </div>

      <div className="card p-5">
        <h3 className="font-display font-semibold text-sm mb-4">Aging (days overdue)</h3>
        <ResponsiveContainer width="100%" height={240}>
          <BarChart data={agingBar}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="name" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip />
            <Legend />
            <Bar dataKey="Tenant" fill={CHART_COLORS[2]} radius={[4, 4, 0, 0]} />
            <Bar dataKey="Owner" fill={CHART_COLORS[1]} radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="card">
          <div className="px-5 py-4 border-b border-ink-100 dark:border-ink-800"><h3 className="font-display font-semibold text-sm">Outstanding Tenants</h3></div>
          {data.tenant_outstanding_list.length === 0 ? <EmptyState title="No outstanding tenant balances" /> : (
            <div className="overflow-x-auto"><table className="table-shell">
              <thead><tr><th>Tenant</th><th>Outstanding</th></tr></thead>
              <tbody>{data.tenant_outstanding_list.map((t, i) => (
                <tr key={i}><td>{t.display_name}</td><td>{Number(t.outstanding_amount).toLocaleString()}</td></tr>
              ))}</tbody>
            </table></div>
          )}
        </div>
        <div className="card">
          <div className="px-5 py-4 border-b border-ink-100 dark:border-ink-800"><h3 className="font-display font-semibold text-sm">Outstanding Owners</h3></div>
          {data.owner_outstanding_list.length === 0 ? <EmptyState title="No outstanding owner balances" /> : (
            <div className="overflow-x-auto"><table className="table-shell">
              <thead><tr><th>Owner</th><th>Outstanding</th></tr></thead>
              <tbody>{data.owner_outstanding_list.map((o, i) => (
                <tr key={i}><td>{o.display_name}</td><td>{Number(o.outstanding_amount).toLocaleString()}</td></tr>
              ))}</tbody>
            </table></div>
          )}
        </div>
      </div>
    </div>
  );
}

// ==================== Contract Expirations ====================
function ContractExpirationTab() {
  const navigate = useNavigate();
  const [data, setData] = useState<ContractExpirationReport | null>(null);
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    apiClient.get<ContractExpirationReport>("/reports/contract-expirations", { params: { days } }).then(({ data }) => setData(data)).finally(() => setLoading(false));
  }, [days]);

  if (loading) return <div className="flex justify-center py-10"><Loader2 className="animate-spin text-ink-400" /></div>;
  if (!data) return null;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <select className="input max-w-[160px]" value={days} onChange={(e) => setDays(Number(e.target.value))}>
          <option value={7}>Next 7 days</option>
          <option value={30}>Next 30 days</option>
          <option value={60}>Next 60 days</option>
          <option value={90}>Next 90 days</option>
        </select>
        <ReportExportBar reportType="contract_expiration" filters={{ days }} />
      </div>

      <div className="card p-4 flex items-center gap-3">
        <Calendar size={18} className="text-amber-500" />
        <span className="text-sm"><span className="font-semibold">{data.total_expiring}</span> contract(s) expiring within {data.window_days} days</span>
      </div>

      <div className="card">
        <div className="px-5 py-4 border-b border-ink-100 dark:border-ink-800"><h3 className="font-display font-semibold text-sm">Rental Contracts</h3></div>
        {data.expiring_rental_contracts.length === 0 ? <EmptyState title="No rental contracts expiring in this window" /> : (
          <div className="overflow-x-auto"><table className="table-shell">
            <thead><tr><th>Contract #</th><th>Tenant</th><th>Property</th><th>End Date</th><th>Days Left</th><th>Rent</th></tr></thead>
            <tbody>{data.expiring_rental_contracts.map((c) => (
              <tr key={c.id} className="cursor-pointer" onClick={() => navigate(`/rentals/${c.id}`)}>
                <td className="font-mono text-xs">{c.contract_number}</td><td>{c.tenant_display_name}</td><td>{c.property_title}{c.unit_number ? ` · ${c.unit_number}` : ""}</td>
                <td>{c.end_date}</td><td className={c.days_remaining <= 7 ? "text-rust-500 font-medium" : ""}>{c.days_remaining}</td>
                <td>{Number(c.rent_amount).toLocaleString()}</td>
              </tr>
            ))}</tbody>
          </table></div>
        )}
      </div>

      <div className="card">
        <div className="px-5 py-4 border-b border-ink-100 dark:border-ink-800"><h3 className="font-display font-semibold text-sm">Lease Agreements</h3></div>
        {data.expiring_lease_agreements.length === 0 ? <EmptyState title="No lease agreements expiring in this window" /> : (
          <div className="overflow-x-auto"><table className="table-shell">
            <thead><tr><th>Contract #</th><th>Owner</th><th>Property</th><th>End Date</th><th>Days Left</th><th>Rent</th></tr></thead>
            <tbody>{data.expiring_lease_agreements.map((c) => (
              <tr key={c.id} className="cursor-pointer" onClick={() => navigate(`/leases/${c.id}`)}>
                <td className="font-mono text-xs">{c.contract_number}</td><td>{c.owner_display_name}</td><td>{c.property_title}{c.unit_number ? ` · ${c.unit_number}` : ""}</td>
                <td>{c.end_date}</td><td className={c.days_remaining <= 7 ? "text-rust-500 font-medium" : ""}>{c.days_remaining}</td>
                <td>{Number(c.rent_amount).toLocaleString()}</td>
              </tr>
            ))}</tbody>
          </table></div>
        )}
      </div>
    </div>
  );
}

// ==================== Export Scheduling ====================
function SchedulesTab() {
  const [schedules, setSchedules] = useState<ReportSchedule[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [reportType, setReportType] = useState("financial");
  const [exportFormat, setExportFormat] = useState("pdf");
  const [frequency, setFrequency] = useState("monthly");

  const load = useCallback(() => {
    setLoading(true);
    apiClient.get<ReportSchedule[]>("/reports/schedules").then(({ data }) => setSchedules(data)).finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  const create = async () => {
    if (!name.trim()) return;
    setCreating(true);
    try {
      await apiClient.post("/reports/schedules", { name, report_type: reportType, export_format: exportFormat, frequency });
      setName("");
      load();
    } finally {
      setCreating(false);
    }
  };

  const toggleActive = async (s: ReportSchedule) => {
    await apiClient.put(`/reports/schedules/${s.id}`, { is_active: !s.is_active });
    load();
  };

  const runNow = async (s: ReportSchedule) => {
    await apiClient.post(`/reports/schedules/${s.id}/run-now`);
    load();
  };

  const remove = async (s: ReportSchedule) => {
    await apiClient.delete(`/reports/schedules/${s.id}`);
    load();
  };

  return (
    <div className="space-y-4">
      <div className="card p-4">
        <h3 className="font-display font-semibold text-sm mb-3">New Scheduled Export</h3>
        <div className="flex flex-wrap gap-3 items-end">
          <div className="flex-1 min-w-[180px]">
            <label className="label">Name</label>
            <input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Weekly Maintenance Report" />
          </div>
          <div>
            <label className="label">Report</label>
            <select className="input" value={reportType} onChange={(e) => setReportType(e.target.value)}>
              {["property", "owner", "tenant", "lease", "occupancy", "units", "financial", "maintenance", "collections", "outstanding", "contract_expiration"].map((rt) => (
                <option key={rt} value={rt}>{rt.replace(/_/g, " ")}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="label">Format</label>
            <select className="input" value={exportFormat} onChange={(e) => setExportFormat(e.target.value)}>
              <option value="pdf">PDF</option>
              <option value="excel">Excel</option>
            </select>
          </div>
          <div>
            <label className="label">Frequency</label>
            <select className="input" value={frequency} onChange={(e) => setFrequency(e.target.value)}>
              <option value="daily">Daily</option>
              <option value="weekly">Weekly</option>
              <option value="monthly">Monthly</option>
            </select>
          </div>
          <button className="btn-primary" onClick={create} disabled={creating || !name.trim()}>
            <Plus size={16} /> Create
          </button>
        </div>
      </div>

      <div className="card">
        <div className="px-5 py-4 border-b border-ink-100 dark:border-ink-800"><h3 className="font-display font-semibold text-sm">Scheduled Exports</h3></div>
        {loading ? <div className="flex justify-center py-10"><Loader2 className="animate-spin text-ink-400" /></div> : schedules.length === 0 ? (
          <EmptyState title="No scheduled exports yet" description="Create one above to have a report generated automatically on a recurring basis." />
        ) : (
          <div className="overflow-x-auto"><table className="table-shell">
            <thead><tr><th>Name</th><th>Report</th><th>Format</th><th>Frequency</th><th>Next Run</th><th>Last Run</th><th>Active</th><th>Actions</th></tr></thead>
            <tbody>{schedules.map((s) => (
              <tr key={s.id}>
                <td>{s.name}</td>
                <td className="capitalize">{s.report_type.replace(/_/g, " ")}</td>
                <td className="uppercase text-xs">{s.export_format}</td>
                <td className="capitalize">{s.frequency}</td>
                <td className="text-xs">{new Date(s.next_run_at).toLocaleString()}</td>
                <td className="text-xs">
                  {s.last_run_at ? (
                    s.last_export_file_url ? <a href={s.last_export_file_url} target="_blank" rel="noreferrer" className="text-brand-600 dark:text-brand-400 hover:underline">{new Date(s.last_run_at).toLocaleString()}</a> : new Date(s.last_run_at).toLocaleString()
                  ) : "—"}
                </td>
                <td>
                  <button className={`${s.is_active ? "badge-active" : "badge-inactive"} inline-flex items-center gap-1`} onClick={() => toggleActive(s)}>
                    {s.is_active ? <Pause size={11} /> : <Play size={11} />} {s.is_active ? "Active" : "Paused"}
                  </button>
                </td>
                <td className="flex gap-1.5">
                  <button className="btn-secondary !px-2 !py-1" title="Run now" onClick={() => runNow(s)}><Play size={13} /></button>
                  <button className="btn-secondary !px-2 !py-1 text-rust-500" title="Delete" onClick={() => remove(s)}><Trash2 size={13} /></button>
                </td>
              </tr>
            ))}</tbody>
          </table></div>
        )}
      </div>
    </div>
  );
}
