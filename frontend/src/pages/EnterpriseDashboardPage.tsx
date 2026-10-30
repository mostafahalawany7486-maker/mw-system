import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import apiClient from "@/api/client";
import { useTheme } from "@/context/ThemeContext";
import { PageHeader, EmptyState } from "@/components/ui";
import {
  Loader2, RefreshCw, Home, DoorClosed, DoorOpen, PieChart as PieChartIcon,
  Wallet, TrendingUp, TrendingDown, DollarSign, AlertTriangle, Wrench,
  FileSignature, Users, Building2, Pause, Play,
} from "lucide-react";
import {
  PieChart, Pie, Cell, BarChart, Bar, AreaChart, Area, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import { DashboardAnalytics } from "@/types";

type Period = "this_month" | "last_30_days" | "this_quarter" | "this_year" | "custom";
const REFRESH_INTERVAL_MS = 60_000; // "Real-time" here means auto-refreshing on a short poll cycle, not a live socket push — the backend has no WebSocket/SSE layer, and a 60s poll keeps this dashboard current without adding new infrastructure.

function periodToRange(period: Period): { date_from: string; date_to: string } {
  const today = new Date();
  const to = today.toISOString().slice(0, 10);
  let from = new Date(today);
  if (period === "last_30_days") from.setDate(today.getDate() - 30);
  else if (period === "this_quarter") from = new Date(today.getFullYear(), Math.floor(today.getMonth() / 3) * 3, 1);
  else if (period === "this_year") from = new Date(today.getFullYear(), 0, 1);
  else from = new Date(today.getFullYear(), today.getMonth(), 1); // this_month
  return { date_from: from.toISOString().slice(0, 10), date_to: to };
}

export default function EnterpriseDashboardPage() {
  const navigate = useNavigate();
  const { theme } = useTheme();
  const { t } = useTranslation("dashboard");
  const { t: tCommon } = useTranslation("common");
  const dark = theme === "dark";

  const [period, setPeriod] = useState<Period>("this_month");
  const [customFrom, setCustomFrom] = useState(periodToRange("this_month").date_from);
  const [customTo, setCustomTo] = useState(periodToRange("this_month").date_to);
  const [propertyTypeFilter, setPropertyTypeFilter] = useState("");

  const [data, setData] = useState<DashboardAnalytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [secondsAgo, setSecondsAgo] = useState(0);

  const range = period === "custom" ? { date_from: customFrom, date_to: customTo } : periodToRange(period);

  const load = useCallback((silent = false) => {
    if (!silent) setLoading(true);
    else setRefreshing(true);
    apiClient.get<DashboardAnalytics>("/reports/analytics/dashboard", { params: range })
      .then(({ data }) => { setData(data); setLastUpdated(new Date()); })
      .finally(() => { setLoading(false); setRefreshing(false); });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [range.date_from, range.date_to]);

  useEffect(() => { load(false); }, [load]);

  useEffect(() => {
    if (!autoRefresh) return;
    const id = setInterval(() => load(true), REFRESH_INTERVAL_MS);
    return () => clearInterval(id);
  }, [autoRefresh, load]);

  useEffect(() => {
    const tick = setInterval(() => {
      if (lastUpdated) setSecondsAgo(Math.floor((Date.now() - lastUpdated.getTime()) / 1000));
    }, 1000);
    return () => clearInterval(tick);
  }, [lastUpdated]);

  // Design-system-consistent palette, pulled from tailwind.config.js brand/amber/rust/ink scales.
  const COLORS = {
    brand: "#0EA5E9", brandLight: "#7DD3FC", amber: "#C2760C", rust: "#B3402C",
    ink: dark ? "#A3ABA5" : "#57645D", grid: dark ? "#333D37" : "#E7E9E7",
    tooltipBg: dark ? "#242C27" : "#FFFFFF", tooltipBorder: dark ? "#333D37" : "#E7E9E7",
  };
  const PIE_COLORS = [COLORS.brand, COLORS.amber, COLORS.rust, COLORS.brandLight, "#75817A", "#9C5E09"];

  const tooltipStyle = {
    backgroundColor: COLORS.tooltipBg, border: `1px solid ${COLORS.tooltipBorder}`,
    borderRadius: 8, fontSize: 12, color: dark ? "#F5F6F5" : "#171D19",
  };
  const axisTick = { fill: COLORS.ink, fontSize: 11 };

  if (loading) return <div className="flex justify-center py-24"><Loader2 className="animate-spin text-ink-400" size={28} /></div>;
  if (!data) return <EmptyState title={t("enterprise.unableToLoad")} description={t("enterprise.tryRefreshing")} />;
  const k = data.kpis;

  const occupancyPieData = [
    { name: t("enterprise.charts.occupied"), value: k.occupied_units },
    { name: t("enterprise.charts.vacant"), value: k.vacant_units },
  ];

  const propertyTypeData = (propertyTypeFilter ? data.properties_by_type.filter((p) => p.property_type === propertyTypeFilter) : data.properties_by_type)
    .map((p) => ({ name: p.property_type.replace(/_/g, " "), value: p.count }));

  const revenueExpenseArea = data.monthly_trend.map((m) => ({ month: m.month, Income: Number(m.income), Expense: Number(m.expense) }));
  const profitLine = data.monthly_trend.map((m) => ({ month: m.month, Profit: Number(m.profit) }));
  const topPropertiesBar = data.top_properties_by_revenue.slice(0, 8).map((p) => ({ name: p.property_title, Revenue: Number(p.total_amount) }));
  const cashFlowBar = data.cash_flow_by_type.map((c) => ({ name: c.label.replace(/_/g, " "), Amount: Number(c.total_amount) }));
  const occupancyByTypeBar = data.occupancy_by_type.map((o) => ({ name: o.property_type.replace(/_/g, " "), Occupied: o.occupied, Total: o.total }));

  return (
    <div>
      <PageHeader
        title={t("enterprise.title")}
        description={t("enterprise.subtitle")}
        action={
          <div className="flex items-center gap-2">
            <span className="text-xs text-ink-400 hidden sm:inline">
              {refreshing ? t("enterprise.refreshing") : lastUpdated ? `${t("enterprise.updated")} ${secondsAgo}${t("enterprise.secondsAgo")}` : ""}
            </span>
            <button className="btn-secondary !px-2 !py-1.5" title={autoRefresh ? t("enterprise.pauseRefresh") : t("enterprise.resumeRefresh")} onClick={() => setAutoRefresh((a) => !a)}>
              {autoRefresh ? <Pause size={14} /> : <Play size={14} />}
            </button>
            <button className="btn-primary !px-3 !py-1.5" onClick={() => load(true)} disabled={refreshing}>
              <RefreshCw size={14} className={refreshing ? "animate-spin" : ""} /> {t("enterprise.refresh")}
            </button>
          </div>
        }
      />

      {/* Interactive filters */}
      <div className="card p-4 mb-6 flex flex-wrap gap-3 items-end">
        <div>
          <label className="label">{t("enterprise.period")}</label>
          <select className="input" value={period} onChange={(e) => setPeriod(e.target.value as Period)}>
            <option value="this_month">{t("enterprise.thisMonth")}</option>
            <option value="last_30_days">{t("enterprise.last30Days")}</option>
            <option value="this_quarter">{t("enterprise.thisQuarter")}</option>
            <option value="this_year">{t("enterprise.thisYear")}</option>
            <option value="custom">{t("enterprise.customRange")}</option>
          </select>
        </div>
        {period === "custom" && (
          <>
            <div><label className="label">{tCommon("labels.from")}</label><input className="input" type="date" value={customFrom} onChange={(e) => setCustomFrom(e.target.value)} /></div>
            <div><label className="label">{tCommon("labels.to")}</label><input className="input" type="date" value={customTo} onChange={(e) => setCustomTo(e.target.value)} /></div>
          </>
        )}
        <div>
          <label className="label">{t("enterprise.propertyType")}</label>
          <select className="input" value={propertyTypeFilter} onChange={(e) => setPropertyTypeFilter(e.target.value)}>
            <option value="">{t("enterprise.allTypes")}</option>
            {data.properties_by_type.map((p) => <option key={p.property_type} value={p.property_type}>{p.property_type.replace(/_/g, " ")}</option>)}
          </select>
        </div>
      </div>

      {/* KPI grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3 mb-6">
        <KPI label={t("enterprise.kpi.totalProperties")} value={k.total_properties} icon={Home} tone="text-brand-500" onClick={() => navigate("/properties")} />
        <KPI label={t("enterprise.kpi.totalUnits")} value={k.total_units} icon={Building2} tone="text-brand-500" />
        <KPI label={t("enterprise.kpi.occupiedUnits")} value={k.occupied_units} icon={DoorClosed} tone="text-brand-500" />
        <KPI label={t("enterprise.kpi.vacantUnits")} value={k.vacant_units} icon={DoorOpen} tone="text-amber-500" />
        <KPI label={t("enterprise.kpi.occupancyRate")} value={`${k.occupancy_rate_percentage}%`} icon={PieChartIcon} tone="text-brand-500" />
        <KPI label={t("enterprise.kpi.monthlyRevenue")} value={Number(k.total_income_this_month).toLocaleString()} icon={TrendingUp} tone="text-brand-500" />
        <KPI label={t("enterprise.kpi.monthlyExpenses")} value={Number(k.total_expense_this_month).toLocaleString()} icon={TrendingDown} tone="text-rust-500" />
        <KPI label={t("enterprise.kpi.netProfit")} value={Number(k.net_profit_this_month).toLocaleString()} icon={DollarSign} tone="text-brand-500" />
        <KPI label={t("enterprise.kpi.outstandingPayments")} value={(Number(k.total_outstanding_tenant) + Number(k.total_outstanding_owner)).toLocaleString()} icon={Wallet} tone="text-amber-500" onClick={() => navigate("/financial")} />
        <KPI label={t("enterprise.kpi.leaseExpirations")} value={k.contracts_expiring_soon} icon={FileSignature} tone="text-amber-500" onClick={() => navigate("/rentals")} />
        <KPI label={t("enterprise.kpi.maintenanceRequests")} value={k.open_maintenance_requests} icon={Wrench} tone="text-amber-500" onClick={() => navigate("/maintenance")} />
        <KPI label={t("enterprise.kpi.tenants")} value={k.total_tenants} icon={Users} tone="text-brand-500" onClick={() => navigate("/tenants")} />
      </div>

      {/* Revenue / Expense trend (Area) + Net Profit trend (Line) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
        <div className="card p-5">
          <h3 className="font-display font-semibold text-sm mb-4">{t("enterprise.charts.revenueExpenseTrend")}</h3>
          <ResponsiveContainer width="100%" height={260}>
            <AreaChart data={revenueExpenseArea}>
              <defs>
                <linearGradient id="incomeGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={COLORS.brand} stopOpacity={0.4} />
                  <stop offset="95%" stopColor={COLORS.brand} stopOpacity={0.02} />
                </linearGradient>
                <linearGradient id="expenseGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={COLORS.rust} stopOpacity={0.4} />
                  <stop offset="95%" stopColor={COLORS.rust} stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke={COLORS.grid} vertical={false} />
              <XAxis dataKey="month" tick={axisTick} axisLine={{ stroke: COLORS.grid }} tickLine={false} />
              <YAxis tick={axisTick} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={tooltipStyle} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Area type="monotone" dataKey="Income" name={t("enterprise.charts.income")} stroke={COLORS.brand} fill="url(#incomeGrad)" strokeWidth={2} />
              <Area type="monotone" dataKey="Expense" name={t("enterprise.charts.expense")} stroke={COLORS.rust} fill="url(#expenseGrad)" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        <div className="card p-5">
          <h3 className="font-display font-semibold text-sm mb-4">{t("enterprise.charts.netProfitTrend")}</h3>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={profitLine}>
              <CartesianGrid strokeDasharray="3 3" stroke={COLORS.grid} vertical={false} />
              <XAxis dataKey="month" tick={axisTick} axisLine={{ stroke: COLORS.grid }} tickLine={false} />
              <YAxis tick={axisTick} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={tooltipStyle} />
              <Line type="monotone" dataKey="Profit" name={t("enterprise.charts.profit")} stroke={COLORS.brand} strokeWidth={2.5} dot={{ r: 3, fill: COLORS.brand }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Occupancy pie + Properties by type pie */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-4">
        <div className="card p-5">
          <h3 className="font-display font-semibold text-sm mb-4">{t("enterprise.charts.occupiedVsVacant")}</h3>
          {k.total_units === 0 ? <EmptyState title={t("enterprise.noLeasableUnits")} /> : (
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie data={occupancyPieData} dataKey="value" nameKey="name" cx="50%" cy="50%" innerRadius={50} outerRadius={80} paddingAngle={2}>
                  {occupancyPieData.map((_, i) => <Cell key={i} fill={i === 0 ? COLORS.brand : COLORS.amber} />)}
                </Pie>
                <Tooltip contentStyle={tooltipStyle} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
              </PieChart>
            </ResponsiveContainer>
          )}
        </div>

        <div className="card p-5 lg:col-span-2">
          <h3 className="font-display font-semibold text-sm mb-4">{t("enterprise.charts.propertiesByType")}</h3>
          {propertyTypeData.length === 0 ? <EmptyState title={t("enterprise.noPropertiesMatch")} /> : (
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie data={propertyTypeData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label={(e: any) => `${e.name} (${e.value})`}>
                  {propertyTypeData.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
                </Pie>
                <Tooltip contentStyle={tooltipStyle} />
              </PieChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Top performing properties (Bar) + Cash flow by type (Bar) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
        <div className="card p-5">
          <h3 className="font-display font-semibold text-sm mb-4">{t("enterprise.charts.topPerformingProperties")}</h3>
          {topPropertiesBar.length === 0 ? <EmptyState title={t("enterprise.noRevenueYet")} /> : (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={topPropertiesBar} layout="vertical" margin={{ left: 24 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={COLORS.grid} horizontal={false} />
                <XAxis type="number" tick={axisTick} axisLine={false} tickLine={false} />
                <YAxis type="category" dataKey="name" tick={{ ...axisTick, fontSize: 10 }} width={120} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={tooltipStyle} />
                <Bar dataKey="Revenue" name={t("enterprise.charts.revenue")} fill={COLORS.brand} radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        <div className="card p-5">
          <h3 className="font-display font-semibold text-sm mb-1">{t("enterprise.charts.cashFlowByType")}</h3>
          <p className="text-xs text-ink-400 mb-3">{t("enterprise.charts.cashFlowNote")}</p>
          {cashFlowBar.length === 0 ? <EmptyState title={t("enterprise.noCashActivity")} /> : (
            <ResponsiveContainer width="100%" height={230}>
              <BarChart data={cashFlowBar}>
                <CartesianGrid strokeDasharray="3 3" stroke={COLORS.grid} vertical={false} />
                <XAxis dataKey="name" tick={{ ...axisTick, fontSize: 10 }} axisLine={{ stroke: COLORS.grid }} tickLine={false} />
                <YAxis tick={axisTick} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={tooltipStyle} />
                <Bar dataKey="Amount" name={t("enterprise.charts.amount")} radius={[4, 4, 0, 0]}>
                  {cashFlowBar.map((entry, i) => <Cell key={i} fill={entry.Amount >= 0 ? COLORS.brand : COLORS.rust} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Occupancy by property type */}
      <div className="card p-5 mb-4">
        <h3 className="font-display font-semibold text-sm mb-4">{t("enterprise.charts.occupancyByType")}</h3>
        {occupancyByTypeBar.length === 0 ? <EmptyState title={t("enterprise.noLeasableProperties")} /> : (
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={occupancyByTypeBar}>
              <CartesianGrid strokeDasharray="3 3" stroke={COLORS.grid} vertical={false} />
              <XAxis dataKey="name" tick={axisTick} axisLine={{ stroke: COLORS.grid }} tickLine={false} />
              <YAxis tick={axisTick} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={tooltipStyle} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar dataKey="Total" name={t("enterprise.charts.total")} fill={COLORS.grid} radius={[4, 4, 0, 0]} />
              <Bar dataKey="Occupied" name={t("enterprise.charts.occupied")} fill={COLORS.brand} radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>

      {k.contracts_expiring_soon > 0 && (
        <div className="card p-4 flex items-center gap-3 border-l-4 border-amber-500 cursor-pointer" onClick={() => navigate("/rentals")}>
          <AlertTriangle size={18} className="text-amber-500 shrink-0" />
          <p className="text-sm">{t("enterprise.leaseExpiryBanner", { count: k.contracts_expiring_soon })}</p>
        </div>
      )}
    </div>
  );
}

function KPI({ label, value, icon: Icon, tone, onClick }: { label: string; value: string | number; icon: any; tone: string; onClick?: () => void }) {
  return (
    <div className={`card p-4 ${onClick ? "cursor-pointer hover:border-brand-300 dark:hover:border-brand-700 transition-colors" : ""}`} onClick={onClick}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-medium text-ink-500 dark:text-ink-400">{label}</span>
        <Icon size={16} className={tone} />
      </div>
      <div className="font-display text-xl font-bold truncate">{value}</div>
    </div>
  );
}
