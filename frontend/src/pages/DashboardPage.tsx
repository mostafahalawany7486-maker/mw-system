import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import apiClient from "@/api/client";
import { PageHeader, SkeletonKpiGrid, SkeletonText, Skeleton } from "@/components/ui";
import {
  Users, ShieldCheck, Building2, BellRing, Activity, UserSquare2, FileText, Home, UsersRound,
  FileSignature, Wallet, Wrench, Scale, DoorOpen, DoorClosed, AlertTriangle, Plus, Printer, ArrowRight, TrendingUp,
  TrendingDown, Layers, CalendarClock, ShieldAlert, PiggyBank, Info, AlertOctagon, GripVertical, RotateCcw, CheckCircle2,
} from "lucide-react";
import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip } from "recharts";
import type { PropertyListItem, PaginatedResponse } from "@/types";

interface DashboardSummary {
  widgets: {
    total_users: number; active_users: number; total_roles: number; total_branches: number;
    total_owners: number; active_leases: number; total_properties: number; total_buildings: number;
    total_apartments: number; occupied_apartments: number; vacant_apartments: number; total_tenants: number;
    active_rental_contracts: number; expiring_contracts: number; total_cash_bank_balance: number;
    open_maintenance_requests: number; gl_trial_balance_variance: number; unread_notifications: number;
    vacant_units_value: number; vacant_units_missing_price: number; portfolio_monthly_profit: number;
  };
  buildings_overview: Array<{
    building_id: number; building_title: string; building_code: string; unit_count: number;
    occupied_units: number; vacant_units: number; occupancy_percentage: number; active_contracts: number; expiring_contracts: number;
  }>;
  recent_contracts: Array<{ id: number; contract_number: string; contract_status: string; property_id: number }>;
  expiring_contracts_list: Array<{ id: number; contract_number: string; end_date: string; property_id: number; tenant_id: number }>;
  recent_tenants: Array<{ id: number; tenant_code: string; display_name: string; is_blacklisted: boolean }>;
  recent_activity: Array<{ action: string; description: string; entity_type: string; entity_id: number; created_at: string }>;
}

interface ExecutiveSummary {
  kpis: {
    total_buildings: number; total_floors: number; total_units: number; occupied_units: number; vacant_units: number;
    occupancy_rate: number; active_contracts: number; contracts_expiring_30: number; contracts_expiring_60: number;
    monthly_rent_collected: number; monthly_rent_collected_trend_pct: number | null; monthly_outstanding_rent: number;
    total_owner_balance: number; total_maintenance_requests: number; open_maintenance_requests: number;
    closed_maintenance_requests: number; expected_income_this_month: number; expected_income_next_month: number;
    total_security_deposits: number;
  };
  rent_collection: { collected: number; outstanding: number; expected: number; collection_percentage: number };
  occupancy: { total_units: number; occupied_units: number; vacant_units: number; occupancy_rate: number };
  financial_summary: {
    rental_income: number; other_income: number; maintenance_expenses: number; other_expenses: number;
    owner_payouts: number; net_income: number;
  };
  alerts: Array<{ severity: "info" | "warning" | "critical"; code: string; message: string; action_label: string; action_path: string }>;
}

interface TopLists {
  top_buildings_by_revenue: Array<{ id: number; title: string; code: string; value: number }>;
  top_buildings_by_occupancy: Array<{ building_id: number; building_title: string; occupancy_percentage: number; occupied_units: number; unit_count: number }>;
  top_tenants: Array<{ id: number; code: string; name: string; value: number }>;
  top_owners: Array<{ id: number; code: string; name: string; value: number }>;
  highest_expenses: Array<{ id: number; transaction_number: string; category: string | null; amount: number; date: string; description: string | null }>;
  vacant_units: Array<{ id: number; title: string; unit_number: string | null; building_title: string | null; rent_amount: number | null }>;
  late_payments: Array<{ installment_id: number; contract_number: string; tenant_id: number; due_date: string; amount: number; days_late: number }>;
}

interface CalendarEvent {
  type: "rent_due" | "contract_expiration" | "maintenance_visit" | "owner_payment" | "inspection";
  date: string;
  title: string;
  amount: number | null;
  link: string;
}

const SECTION_LABELS: Record<string, string> = {
  kpis: "KPI Cards", rent_collection: "Rent Collection Overview", occupancy: "Occupancy Analytics",
  financial_summary: "Financial Summary", alerts: "Smart Alerts", top_lists: "Top Lists", calendar: "Calendar / Upcoming",
};
const DEFAULT_SECTION_VISIBILITY: Record<string, boolean> = {
  kpis: true, rent_collection: true, occupancy: true, financial_summary: true, alerts: true, top_lists: true, calendar: true,
};
// kpis isn't in here — it's always first, not a reorderable widget
// (same reasoning most enterprise dashboards use: headline KPIs anchor
// the page, everything else flows around them).
const DEFAULT_WIDGET_ORDER = ["rent_collection", "financial_summary", "occupancy", "alerts", "top_lists", "calendar"];

// Primary cards — exactly the set requested for daily property-management
// use, shown first and largest. The previous system-admin-ish widgets
// (users, roles, branches, GL variance, cash balance, notifications)
// aren't removed — Enterprise Dashboard was retired into this single
// page per that decision, so they're kept as a smaller secondary strip
// below rather than competing for top billing.
const PRIMARY_CARDS = [
  { key: "total_buildings", icon: Building2, bar: "bg-sky-500", wash: "from-sky-50 dark:from-sky-500/10" },
  { key: "total_apartments", icon: Home, bar: "bg-indigo-500", wash: "from-indigo-50 dark:from-indigo-500/10" },
  { key: "occupied_apartments", icon: DoorClosed, bar: "bg-emerald-500", wash: "from-emerald-50 dark:from-emerald-500/10" },
  { key: "vacant_apartments", icon: DoorOpen, bar: "bg-amber-500", wash: "from-amber-50 dark:from-amber-500/10" },
  { key: "vacant_units_value", icon: Wallet, bar: "bg-rust-500", wash: "from-rust-50 dark:from-rust-500/10", money: true },
  { key: "active_rental_contracts", icon: FileSignature, bar: "bg-fuchsia-500", wash: "from-fuchsia-50 dark:from-fuchsia-500/10" },
  { key: "expiring_contracts", icon: AlertTriangle, bar: "bg-orange-500", wash: "from-orange-50 dark:from-orange-500/10" },
  { key: "total_tenants", icon: UsersRound, bar: "bg-rose-500", wash: "from-rose-50 dark:from-rose-500/10" },
] as const;

const SECONDARY_CARDS = [
  { key: "total_owners", icon: UserSquare2, color: "text-violet-500", chip: "bg-violet-500/10" },
  { key: "active_leases", icon: FileText, color: "text-teal-500", chip: "bg-teal-500/10" },
  { key: "total_cash_bank_balance", icon: Wallet, color: "text-green-500", chip: "bg-green-500/10" },
  { key: "open_maintenance_requests", icon: Wrench, color: "text-orange-500", chip: "bg-orange-500/10" },
  { key: "gl_trial_balance_variance", icon: Scale, color: "text-amber-500", chip: "bg-amber-500/10" },
  { key: "total_users", icon: Users, color: "text-purple-500", chip: "bg-purple-500/10" },
  { key: "total_roles", icon: ShieldCheck, color: "text-pink-500", chip: "bg-pink-500/10" },
  { key: "total_branches", icon: Building2, color: "text-cyan-500", chip: "bg-cyan-500/10" },
  { key: "unread_notifications", icon: BellRing, color: "text-blue-500", chip: "bg-blue-500/10" },
] as const;

export default function DashboardPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [exec, setExec] = useState<ExecutiveSummary | null>(null);
  const [topLists, setTopLists] = useState<TopLists | null>(null);
  const [calendarEvents, setCalendarEvents] = useState<CalendarEvent[] | null>(null);
  const { t } = useTranslation("dashboard");
  const navigate = useNavigate();

  // Phase 4: Dashboard Customization — show/hide AND now drag-to-reorder,
  // both saved per browser. Reordering uses the browser's native HTML5
  // drag-and-drop (draggable / onDragStart / onDragOver / onDrop) on
  // purpose instead of adding a DnD library (e.g. @dnd-kit) as a new
  // project dependency for this one feature — genuinely reorders, no
  // new package.json entry. Resizing widgets is still out of scope:
  // that needs real grid-layout math (e.g. react-grid-layout), a much
  // bigger addition than reordering, and wasn't asked for specifically.
  const [visibleSections, setVisibleSections] = useState<Record<string, boolean>>(() => {
    try {
      const saved = localStorage.getItem("dashboard_visible_sections");
      return saved ? JSON.parse(saved) : DEFAULT_SECTION_VISIBILITY;
    } catch {
      return DEFAULT_SECTION_VISIBILITY;
    }
  });
  const [widgetOrder, setWidgetOrder] = useState<string[]>(() => {
    try {
      const saved = localStorage.getItem("dashboard_widget_order");
      const parsed: string[] = saved ? JSON.parse(saved) : DEFAULT_WIDGET_ORDER;
      // If the saved order predates a widget that was added since, make
      // sure it's still included (appended at the end) rather than
      // silently disappearing.
      const missing = DEFAULT_WIDGET_ORDER.filter((k) => !parsed.includes(k));
      return [...parsed, ...missing];
    } catch {
      return DEFAULT_WIDGET_ORDER;
    }
  });
  const [customizeOpen, setCustomizeOpen] = useState(false);
  const [draggedWidget, setDraggedWidget] = useState<string | null>(null);

  const toggleSection = (key: string) => {
    setVisibleSections((prev) => {
      const next = { ...prev, [key]: !prev[key] };
      try { localStorage.setItem("dashboard_visible_sections", JSON.stringify(next)); } catch { /* ignore */ }
      return next;
    });
  };

  const reorderWidget = (draggedKey: string, targetKey: string) => {
    if (draggedKey === targetKey) return;
    setWidgetOrder((prev) => {
      const next = prev.filter((k) => k !== draggedKey);
      const targetIndex = next.indexOf(targetKey);
      next.splice(targetIndex, 0, draggedKey);
      try { localStorage.setItem("dashboard_widget_order", JSON.stringify(next)); } catch { /* ignore */ }
      return next;
    });
  };

  const resetLayout = () => {
    setWidgetOrder(DEFAULT_WIDGET_ORDER);
    setVisibleSections(DEFAULT_SECTION_VISIBILITY);
    try {
      localStorage.removeItem("dashboard_widget_order");
      localStorage.removeItem("dashboard_visible_sections");
    } catch { /* ignore */ }
  };

  useEffect(() => {
    apiClient.get<DashboardSummary>("/dashboard/summary").then(({ data }) => setSummary(data));
    apiClient.get<ExecutiveSummary>("/dashboard/executive-summary").then(({ data }) => setExec(data)).catch(() => {});
    apiClient.get<TopLists>("/dashboard/top-lists").then(({ data }) => setTopLists(data)).catch(() => {});
    apiClient.get<CalendarEvent[]>("/dashboard/calendar").then(({ data }) => setCalendarEvents(data)).catch(() => {});
  }, []);

  const widgetLabel = (key: string) => {
    const custom: Record<string, string> = {
      total_buildings: "Total Buildings", total_apartments: "Total Apartments",
      occupied_apartments: "Occupied Apartments", vacant_apartments: "Vacant Apartments",
      expiring_contracts: "Expiring Contracts", vacant_units_value: "Vacant Units Value",
    };
    return custom[key] || t(`widgets.${key}`);
  };

  return (
    <div>
      <div className="flex items-start justify-between gap-3 mb-1">
        <PageHeader title={t("originalTitle")} description={t("originalSubtitle")} />
        <div className="relative shrink-0 mt-1">
          <button className="btn-secondary !py-1.5" onClick={() => setCustomizeOpen((v) => !v)}>
            <Layers size={14} /> Customize
          </button>
          {customizeOpen && (
            <div className="absolute right-0 rtl:right-auto rtl:left-0 mt-2 w-64 card shadow-floating p-3 z-30 animate-scale-in">
              <p className="text-xs font-semibold uppercase text-ink-400 mb-2">Show / Hide Sections</p>
              {Object.keys(SECTION_LABELS).map((key) => (
                <label key={key} className="flex items-center gap-2 text-sm py-1 cursor-pointer">
                  <input type="checkbox" checked={visibleSections[key] !== false} onChange={() => toggleSection(key)} />
                  {SECTION_LABELS[key]}
                </label>
              ))}
              <p className="text-[11px] text-ink-400 mt-2">Drag any widget below by its <GripVertical size={10} className="inline" /> handle (top-left corner, on hover) to reorder it. Saved to this browser.</p>
              <button className="btn-secondary !py-1 text-xs w-full justify-center mt-2" onClick={resetLayout}>
                <RotateCcw size={12} /> Reset to Default Layout
              </button>
            </div>
          )}
        </div>
      </div>

      {/* ==================== Executive Dashboard (Phases 1-4) ====================
          Additive — everything below this block and above "Quick Actions"
          is new. Nothing from the existing dashboard (further down) was
          removed; this sits on top of it. Widgets below the KPI grid are
          drag-to-reorder (native HTML5 DnD — see the widgetOrder state
          above) and individually show/hide. */}
      {exec && (
        <div className="mb-10 space-y-6">
          {visibleSections.kpis !== false && <ExecutiveKpiGrid kpis={exec.kpis} navigate={navigate} />}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
            {widgetOrder.filter((key) => visibleSections[key] !== false).map((key) => (
              <DraggableWidget
                key={key}
                widgetKey={key}
                wide={key === "top_lists"}
                dragged={draggedWidget}
                onDragStart={setDraggedWidget}
                onDropOn={reorderWidget}
              >
                {renderWidget(key, { exec, topLists, calendarEvents, navigate })}
              </DraggableWidget>
            ))}
          </div>
        </div>
      )}

      {/* Quick Actions */}
      <div className="flex flex-wrap gap-2 mb-6">
        <button className="btn-primary" onClick={() => navigate("/properties?new=true")}><Plus size={15} /> Add Building</button>
        <button className="btn-secondary" onClick={() => navigate("/properties")}><Plus size={15} /> Add Apartment</button>
        <button className="btn-secondary" onClick={() => navigate("/rentals?new=true")}><Plus size={15} /> Create Contract</button>
        <button className="btn-secondary" onClick={() => navigate("/tenants?new=true")}><Plus size={15} /> Add Tenant</button>
        <button className="btn-secondary" onClick={() => navigate("/reports")}><Printer size={15} /> Print Reports</button>
      </div>

      {/* Top Summary Cards */}
      {!summary ? (
        <div className="mb-6"><SkeletonKpiGrid count={7} /></div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3 mb-4">
          {PRIMARY_CARDS.map((w) => (
            <div
              key={w.key}
              className={`group relative overflow-hidden rounded-2xl p-4 bg-gradient-to-br ${w.wash} to-white dark:to-ink-900 border border-ink-100 dark:border-ink-800 shadow-card hover:shadow-card-hover hover:-translate-y-0.5 transition-all duration-200 animate-fade-in-up`}
            >
              <span className={`absolute inset-x-0 top-0 h-1 ${w.bar}`} />
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-medium text-ink-500 dark:text-ink-400">{widgetLabel(w.key)}</span>
                <span className={`rounded-xl p-2 ${w.bar} shadow-sm group-hover:scale-105 transition-transform`}>
                  <w.icon size={16} className="text-white" />
                </span>
              </div>
              <div className="font-display text-2xl font-bold text-ink-900 dark:text-white">
                {(w as any).money
                  ? Number(summary.widgets[w.key as keyof DashboardSummary["widgets"]]).toLocaleString(undefined, { minimumFractionDigits: 3 })
                  : summary.widgets[w.key as keyof DashboardSummary["widgets"]]}
              </div>
              {w.key === "vacant_units_value" && summary.widgets.vacant_units_missing_price > 0 && (
                <button
                  className="text-[11px] text-amber-600 dark:text-amber-400 hover:underline mt-1 text-left"
                  onClick={(e) => { e.stopPropagation(); navigate("/properties/vacant-missing-price"); }}
                >
                  + {summary.widgets.vacant_units_missing_price} vacant unit(s) with no price set — click to fill in →
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {summary && <MonthlyProfitCard portfolioProfit={summary.widgets.portfolio_monthly_profit} />}

      {summary && (
        <details className="mb-6">
          <summary className="text-xs text-ink-400 cursor-pointer select-none mb-2">More system stats</summary>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
            {SECONDARY_CARDS.map((w) => (
              <div key={w.key} className="card p-3">
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-xs font-medium text-ink-500 dark:text-ink-400">{widgetLabel(w.key)}</span>
                  <span className={`rounded-md p-1 ${w.chip}`}><w.icon size={13} className={w.color} /></span>
                </div>
                <div className="font-display text-lg font-bold">{summary.widgets[w.key as keyof DashboardSummary["widgets"]]}</div>
              </div>
            ))}
          </div>
        </details>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
        {/* Property Overview */}
        <div className="card">
          <div className="flex items-center justify-between px-5 py-4 border-b border-ink-100 dark:border-ink-800">
            <div className="flex items-center gap-2"><Building2 size={16} className="text-ink-400" /><h2 className="font-display font-semibold text-sm">Property Overview</h2></div>
            <button className="text-xs font-medium text-brand-600 dark:text-brand-400 hover:underline flex items-center gap-1" onClick={() => navigate("/properties")}>All properties <ArrowRight size={12} /></button>
          </div>
          <div className="divide-y divide-ink-50 dark:divide-ink-800/60 max-h-80 overflow-y-auto">
            {!summary && <div className="p-5"><SkeletonText lines={4} /></div>}
            {summary?.buildings_overview.length === 0 && <div className="px-5 py-8 text-center text-sm text-ink-400">No buildings recorded yet.</div>}
            {summary?.buildings_overview.map((b) => (
              <div key={b.building_id} className="px-5 py-3 flex items-center justify-between cursor-pointer hover:bg-ink-50 dark:hover:bg-ink-800/40" onClick={() => navigate(`/properties/${b.building_id}`)}>
                <div>
                  <p className="text-sm font-medium">{b.building_title}</p>
                  <p className="text-xs text-ink-400 mt-0.5">{b.building_code} · {b.unit_count} unit(s) · {b.active_contracts} active contract(s)</p>
                </div>
                <span className={b.occupancy_percentage >= 80 ? "badge-active" : b.occupancy_percentage >= 40 ? "badge-warn" : "badge-inactive"}>
                  {Number(b.occupancy_percentage).toFixed(0)}% occupied
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Tenant Overview */}
        <div className="card">
          <div className="flex items-center justify-between px-5 py-4 border-b border-ink-100 dark:border-ink-800">
            <div className="flex items-center gap-2"><UsersRound size={16} className="text-ink-400" /><h2 className="font-display font-semibold text-sm">Tenant Overview</h2></div>
            <button className="text-xs font-medium text-brand-600 dark:text-brand-400 hover:underline flex items-center gap-1" onClick={() => navigate("/tenants")}>All tenants <ArrowRight size={12} /></button>
          </div>
          <div className="divide-y divide-ink-50 dark:divide-ink-800/60 max-h-80 overflow-y-auto">
            {!summary && <div className="p-5"><SkeletonText lines={4} /></div>}
            {summary?.recent_tenants.length === 0 && <div className="px-5 py-8 text-center text-sm text-ink-400">No tenants recorded yet.</div>}
            {summary?.recent_tenants.map((t2) => (
              <div key={t2.id} className="px-5 py-3 flex items-center justify-between cursor-pointer hover:bg-ink-50 dark:hover:bg-ink-800/40" onClick={() => navigate(`/tenants/${t2.id}`)}>
                <div>
                  <p className="text-sm font-medium">{t2.display_name}</p>
                  <p className="text-xs text-ink-400 mt-0.5">{t2.tenant_code}</p>
                </div>
                {t2.is_blacklisted && <span className="badge-warn">Blacklisted</span>}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Contract Management */}
      <div className="card mb-4">
        <div className="flex items-center justify-between px-5 py-4 border-b border-ink-100 dark:border-ink-800">
          <div className="flex items-center gap-2"><FileSignature size={16} className="text-ink-400" /><h2 className="font-display font-semibold text-sm">Contract Management</h2></div>
          <button className="text-xs font-medium text-brand-600 dark:text-brand-400 hover:underline flex items-center gap-1" onClick={() => navigate("/rentals")}>All contracts <ArrowRight size={12} /></button>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 divide-y md:divide-y-0 md:divide-x divide-ink-50 dark:divide-ink-800/60">
          <div>
            <p className="text-xs font-semibold uppercase text-ink-400 px-5 pt-4 pb-2">Recent Contracts</p>
            <div className="divide-y divide-ink-50 dark:divide-ink-800/60">
              {!summary && <div className="px-5 py-3"><SkeletonText lines={3} /></div>}
              {summary?.recent_contracts.length === 0 && <div className="px-5 py-6 text-center text-sm text-ink-400">No contracts yet.</div>}
              {summary?.recent_contracts.map((c) => (
                <div key={c.id} className="px-5 py-2.5 flex items-center justify-between cursor-pointer hover:bg-ink-50 dark:hover:bg-ink-800/40" onClick={() => navigate(`/rentals/${c.id}`)}>
                  <span className="font-mono text-xs">{c.contract_number}</span>
                  <span className="badge-inactive">{c.contract_status}</span>
                </div>
              ))}
            </div>
          </div>
          <div>
            <p className="text-xs font-semibold uppercase text-ink-400 px-5 pt-4 pb-2">Expiring Soon</p>
            <div className="divide-y divide-ink-50 dark:divide-ink-800/60">
              {!summary && <div className="px-5 py-3"><SkeletonText lines={3} /></div>}
              {summary?.expiring_contracts_list.length === 0 && <div className="px-5 py-6 text-center text-sm text-ink-400">Nothing expiring soon.</div>}
              {summary?.expiring_contracts_list.map((c) => (
                <div key={c.id} className="px-5 py-2.5 flex items-center justify-between cursor-pointer hover:bg-ink-50 dark:hover:bg-ink-800/40" onClick={() => navigate(`/rentals/${c.id}`)}>
                  <span className="font-mono text-xs">{c.contract_number}</span>
                  <span className="text-xs text-amber-600">ends {c.end_date}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="card">
        <div className="flex items-center gap-2 px-5 py-4 border-b border-ink-100 dark:border-ink-800">
          <Activity size={16} className="text-ink-400" />
          <h2 className="font-display font-semibold text-sm">{t("recentActivity")}</h2>
        </div>
        <div className="divide-y divide-ink-50 dark:divide-ink-800/60">
          {!summary && (
            <div className="p-5 space-y-4" aria-busy="true" aria-label="Loading recent activity">
              {[0, 1, 2].map((i) => (
                <div key={i} className="flex items-center justify-between">
                  <SkeletonText lines={2} className="w-64" />
                  <Skeleton className="h-3 w-20" />
                </div>
              ))}
            </div>
          )}
          {summary?.recent_activity.length === 0 && (
            <div className="px-5 py-8 text-center text-sm text-ink-400">{t("noActivityYet")}</div>
          )}
          {summary?.recent_activity.map((a, i) => (
            <div key={i} className="px-5 py-3 flex items-center justify-between">
              <div>
                <p className="text-sm">{a.description}</p>
                <p className="text-xs text-ink-400 mt-0.5 capitalize">{a.entity_type} · {a.action.replace(/_/g, " ")}</p>
              </div>
              <span className="text-xs text-ink-400 shrink-0 ml-4">{new Date(a.created_at).toLocaleString()}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/**
 * Monthly Profit — portfolio-wide total by default (from the
 * dashboard summary, no extra request), with an optional property
 * picker underneath that switches to that one property's own profit
 * instead. The per-property number reuses
 * GET /properties/{id}/hub-summary as-is (the same endpoint
 * PropertyHubPanel already uses on the property detail page) — same
 * math, computed once, not duplicated here.
 */
function MonthlyProfitCard({ portfolioProfit }: { portfolioProfit: number }) {
  const [properties, setProperties] = useState<PropertyListItem[]>([]);
  const [selectedId, setSelectedId] = useState<number | "">("");
  const [propertyProfit, setPropertyProfit] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    apiClient.get<PaginatedResponse<PropertyListItem>>("/properties", { params: { top_level_only: true, page_size: 200 } })
      .then(({ data }) => setProperties(data.items))
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!selectedId) { setPropertyProfit(null); return; }
    setLoading(true);
    apiClient.get(`/properties/${selectedId}/hub-summary`)
      .then(({ data }) => setPropertyProfit(Number(data.estimated_profit_this_month)))
      .catch(() => setPropertyProfit(null))
      .finally(() => setLoading(false));
  }, [selectedId]);

  const shown = selectedId ? propertyProfit : portfolioProfit;
  const isProfit = (shown ?? 0) >= 0;

  return (
    <div className={`relative overflow-hidden rounded-2xl p-4 mb-4 bg-gradient-to-br ${isProfit ? "from-emerald-50 dark:from-emerald-500/10" : "from-rust-50 dark:from-rust-500/10"} to-white dark:to-ink-900 border border-ink-100 dark:border-ink-800 shadow-card`}>
      <span className={`absolute inset-x-0 top-0 h-1 ${isProfit ? "bg-emerald-500" : "bg-rust-500"}`} />
      <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <span className={`rounded-xl p-2 shadow-sm ${isProfit ? "bg-emerald-500" : "bg-rust-500"}`}><TrendingUp size={16} className="text-white" /></span>
          <span className="text-sm font-medium text-ink-500 dark:text-ink-400">
            Monthly Profit {selectedId ? "— selected property" : "— whole portfolio"} (this month, estimated)
          </span>
        </div>
        <select
          className="input !w-56 !py-1.5 text-sm"
          value={selectedId}
          onChange={(e) => setSelectedId(e.target.value ? Number(e.target.value) : "")}
        >
          <option value="">All properties (total)</option>
          {properties.map((p) => <option key={p.id} value={p.id}>{p.property_code} — {p.title}</option>)}
        </select>
      </div>
      {loading ? (
        <div className="h-8 w-40 bg-ink-100 dark:bg-ink-800 rounded animate-pulse" />
      ) : (
        <div className={`font-display text-3xl font-bold ${isProfit ? "text-emerald-600 dark:text-emerald-400" : "text-rust-500"}`}>
          {(shown ?? 0).toLocaleString(undefined, { minimumFractionDigits: 3 })}
        </div>
      )}
      <p className="text-[11px] text-ink-400 mt-1">
        Rent collected minus owner payouts minus maintenance costs, so far this calendar month — a rough estimate, not full accrual accounting.
      </p>
    </div>
  );
}

// ==================== Executive Dashboard components (Phase 1) ====================

function renderWidget(
  key: string,
  ctx: { exec: ExecutiveSummary | null; topLists: TopLists | null; calendarEvents: CalendarEvent[] | null; navigate: (p: string) => void },
) {
  if (!ctx.exec) return null;
  switch (key) {
    case "rent_collection": return <RentCollectionOverview data={ctx.exec.rent_collection} />;
    case "financial_summary": return <FinancialSummaryPanel data={ctx.exec.financial_summary} />;
    case "occupancy": return <OccupancyDonut data={ctx.exec.occupancy} />;
    case "alerts": return <SmartAlertsPanel alerts={ctx.exec.alerts} navigate={ctx.navigate} />;
    case "top_lists": return ctx.topLists ? <TopListsPanel data={ctx.topLists} navigate={ctx.navigate} /> : null;
    case "calendar": return ctx.calendarEvents ? <CalendarWidget events={ctx.calendarEvents} navigate={ctx.navigate} /> : null;
    default: return null;
  }
}

/**
 * Drag handle + drop target for one dashboard widget. Native HTML5
 * drag-and-drop, not a library — see the widgetOrder state comment in
 * DashboardPage for why. `dragged` is the key currently being
 * dragged (lifted to the parent so only one drag is ever active);
 * dropping on another widget calls onDropOn(draggedKey, thisKey),
 * which reorders and persists in the parent.
 */
function DraggableWidget({
  widgetKey, wide, dragged, onDragStart, onDropOn, children,
}: {
  widgetKey: string; wide?: boolean; dragged: string | null;
  onDragStart: (key: string | null) => void; onDropOn: (draggedKey: string, targetKey: string) => void;
  children: React.ReactNode;
}) {
  const [dragOver, setDragOver] = useState(false);
  if (!children) return null;

  return (
    <div
      className={`${wide ? "lg:col-span-2" : ""} relative group transition-opacity ${dragged === widgetKey ? "opacity-40" : ""}`}
      draggable
      onDragStart={() => onDragStart(widgetKey)}
      onDragEnd={() => onDragStart(null)}
      onDragOver={(e) => { e.preventDefault(); if (dragged && dragged !== widgetKey) setDragOver(true); }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => { e.preventDefault(); setDragOver(false); if (dragged) onDropOn(dragged, widgetKey); }}
    >
      <div className={`absolute -top-2 -left-2 rtl:-left-auto rtl:-right-2 z-10 cursor-grab active:cursor-grabbing opacity-0 group-hover:opacity-100 transition-opacity bg-ink-800 dark:bg-ink-700 text-white rounded-md p-1 shadow-sm`}>
        <GripVertical size={12} />
      </div>
      <div className={`rounded-xl transition-all ${dragOver ? "ring-2 ring-brand-500 ring-offset-2 dark:ring-offset-ink-900" : ""}`}>
        {children}
      </div>
    </div>
  );
}

type KpiGroup = "portfolio" | "contracts" | "financial" | "maintenance";

const KPI_GROUPS: Record<KpiGroup, { label: string; icon: any; ring: string; iconBg: string; iconColor: string }> = {
  portfolio: { label: "Portfolio & Occupancy", icon: Building2, ring: "border-sky-100 dark:border-sky-500/20", iconBg: "bg-sky-500", iconColor: "text-white" },
  contracts: { label: "Contracts", icon: FileSignature, ring: "border-fuchsia-100 dark:border-fuchsia-500/20", iconBg: "bg-fuchsia-500", iconColor: "text-white" },
  financial: { label: "Financial", icon: Wallet, ring: "border-emerald-100 dark:border-emerald-500/20", iconBg: "bg-emerald-500", iconColor: "text-white" },
  maintenance: { label: "Maintenance", icon: Wrench, ring: "border-orange-100 dark:border-orange-500/20", iconBg: "bg-orange-500", iconColor: "text-white" },
};

// One color per GROUP, not per card — a coherent visual language you
// can scan by section instead of a wall of unrelated colors. Icons
// picked to individually describe what each number counts, not just
// decorate it.
const KPI_CONFIG: Array<{ key: keyof ExecutiveSummary["kpis"]; label: string; icon: any; group: KpiGroup; money?: boolean; pct?: boolean; reportTab?: string }> = [
  { key: "total_buildings", label: "Total Buildings", icon: Building2, group: "portfolio", reportTab: "properties" },
  { key: "total_floors", label: "Total Floors", icon: Layers, group: "portfolio" },
  { key: "total_units", label: "Total Units", icon: Home, group: "portfolio", reportTab: "units" },
  { key: "occupied_units", label: "Occupied Units", icon: DoorClosed, group: "portfolio", reportTab: "occupancy" },
  { key: "vacant_units", label: "Vacant Units", icon: DoorOpen, group: "portfolio", reportTab: "vacancy" },
  { key: "occupancy_rate", label: "Occupancy Rate", icon: Activity, group: "portfolio", pct: true, reportTab: "occupancy" },
  { key: "active_contracts", label: "Active Contracts", icon: FileSignature, group: "contracts", reportTab: "leases" },
  { key: "contracts_expiring_30", label: "Expiring in 30 Days", icon: CalendarClock, group: "contracts", reportTab: "expirations" },
  { key: "contracts_expiring_60", label: "Expiring in 60 Days", icon: CalendarClock, group: "contracts", reportTab: "expirations" },
  { key: "total_security_deposits", label: "Security Deposits Held", icon: ShieldAlert, group: "contracts", money: true, reportTab: "securityDeposits" },
  { key: "monthly_rent_collected", label: "Rent Collected", icon: Wallet, group: "financial", money: true, reportTab: "collections" },
  { key: "monthly_outstanding_rent", label: "Rent Outstanding", icon: AlertTriangle, group: "financial", money: true, reportTab: "outstanding" },
  { key: "total_owner_balance", label: "Owner Balance", icon: PiggyBank, group: "financial", money: true, reportTab: "ownerBalance" },
  { key: "expected_income_this_month", label: "Expected (This Month)", icon: TrendingUp, group: "financial", money: true, reportTab: "income" },
  { key: "expected_income_next_month", label: "Expected (Next Month)", icon: TrendingUp, group: "financial", money: true, reportTab: "income" },
  { key: "total_maintenance_requests", label: "Total Requests", icon: Wrench, group: "maintenance", reportTab: "maintenance" },
  { key: "open_maintenance_requests", label: "Open", icon: AlertOctagon, group: "maintenance", reportTab: "maintenance" },
  { key: "closed_maintenance_requests", label: "Closed", icon: CheckCircle2, group: "maintenance", reportTab: "maintenance" },
];

function ExecutiveKpiGrid({ kpis, navigate }: { kpis: ExecutiveSummary["kpis"]; navigate: (p: string) => void }) {
  const groups: KpiGroup[] = ["portfolio", "contracts", "financial", "maintenance"];
  return (
    <div className="space-y-5">
      {groups.map((groupKey) => {
        const groupMeta = KPI_GROUPS[groupKey];
        const cards = KPI_CONFIG.filter((c) => c.group === groupKey);
        return (
          <div key={groupKey}>
            <div className="flex items-center gap-2 mb-2.5">
              <span className={`rounded-lg p-1.5 ${groupMeta.iconBg}`}><groupMeta.icon size={14} className={groupMeta.iconColor} /></span>
              <h3 className="text-xs font-semibold uppercase tracking-wide text-ink-500 dark:text-ink-400">{groupMeta.label}</h3>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
              {cards.map((c) => {
                const raw = kpis[c.key];
                const value = c.pct ? `${raw}%` : c.money ? Number(raw).toLocaleString(undefined, { minimumFractionDigits: 3 }) : raw;
                const trend = c.key === "monthly_rent_collected" ? kpis.monthly_rent_collected_trend_pct : null;
                return (
                  <div
                    key={c.key}
                    className={`card p-4 border animate-fade-in-up ${groupMeta.ring} ${c.reportTab ? "cursor-pointer hover:shadow-md hover:-translate-y-0.5 transition-all" : ""}`}
                    onClick={c.reportTab ? () => navigate(`/reports?tab=${c.reportTab}`) : undefined}
                    title={c.reportTab ? "Open the full report" : undefined}
                  >
                    <div className="flex items-start justify-between mb-3">
                      <span className={`rounded-xl p-2.5 ${groupMeta.iconBg} bg-opacity-90 shadow-sm`}><c.icon size={18} className={groupMeta.iconColor} /></span>
                      {trend !== null && trend !== undefined && (
                        <span className={`flex items-center gap-0.5 text-[11px] font-medium ${trend >= 0 ? "text-emerald-500" : "text-rust-500"}`}>
                          {trend >= 0 ? <TrendingUp size={11} /> : <TrendingDown size={11} />} {Math.abs(trend)}%
                        </span>
                      )}
                    </div>
                    <div className="font-display text-xl font-bold truncate">{value}</div>
                    <div className="text-xs text-ink-500 dark:text-ink-400 mt-1">{c.label}</div>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function RentCollectionOverview({ data }: { data: ExecutiveSummary["rent_collection"] }) {
  const pct = Math.min(100, Math.max(0, data.collection_percentage));
  return (
    <div className="card p-5">
      <h3 className="font-display font-semibold text-sm mb-3 flex items-center gap-2">
        <span className="rounded-lg p-1.5 bg-emerald-500"><Wallet size={13} className="text-white" /></span>
        Rent Collection Overview
      </h3>
      <div className="grid grid-cols-3 gap-3 mb-3 text-center">
        <div><div className="text-xs text-ink-400">Collected</div><div className="font-bold text-emerald-600 dark:text-emerald-400">{data.collected.toLocaleString(undefined, { minimumFractionDigits: 3 })}</div></div>
        <div><div className="text-xs text-ink-400">Outstanding</div><div className="font-bold text-rust-500">{data.outstanding.toLocaleString(undefined, { minimumFractionDigits: 3 })}</div></div>
        <div><div className="text-xs text-ink-400">Expected</div><div className="font-bold">{data.expected.toLocaleString(undefined, { minimumFractionDigits: 3 })}</div></div>
      </div>
      <div className="h-2.5 rounded-full bg-ink-100 dark:bg-ink-800 overflow-hidden">
        <div className="h-full bg-emerald-500 transition-all duration-500" style={{ width: `${pct}%` }} />
      </div>
      <div className="text-[11px] text-ink-400 mt-1.5">{pct}% of this month's expected rent collected so far</div>
    </div>
  );
}

const OCCUPANCY_COLORS = ["#10b981", "#f59e0b"];

function OccupancyDonut({ data }: { data: ExecutiveSummary["occupancy"] }) {
  const chartData = [
    { name: "Occupied", value: data.occupied_units },
    { name: "Vacant", value: data.vacant_units },
  ];
  return (
    <div className="card p-5">
      <h3 className="font-display font-semibold text-sm mb-1 flex items-center gap-2">
        <span className="rounded-lg p-1.5 bg-sky-500"><Activity size={13} className="text-white" /></span>
        Occupancy Analytics
      </h3>
      <p className="text-xs text-ink-400 mb-2">{data.occupancy_rate}% occupied · {data.total_units} total unit(s)</p>
      {data.total_units > 0 ? (
        <div style={{ width: "100%", height: 180 }}>
          <ResponsiveContainer>
            <PieChart>
              <Pie data={chartData} dataKey="value" nameKey="name" innerRadius={45} outerRadius={70} paddingAngle={2}>
                {chartData.map((_, i) => <Cell key={i} fill={OCCUPANCY_COLORS[i]} />)}
              </Pie>
              <Tooltip />
              <Legend iconType="circle" wrapperStyle={{ fontSize: "12px" }} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <div className="text-sm text-ink-400 text-center py-8">No units recorded yet</div>
      )}
    </div>
  );
}

function FinancialSummaryPanel({ data }: { data: ExecutiveSummary["financial_summary"] }) {
  const rows: Array<[string, number, boolean]> = [
    ["Rental Income", data.rental_income, true],
    ["Other Income", data.other_income, true],
    ["Maintenance Expenses", -data.maintenance_expenses, false],
    ["Other Expenses", -data.other_expenses, false],
    ["Owner Payouts", -data.owner_payouts, false],
  ];
  return (
    <div className="card p-5">
      <h3 className="font-display font-semibold text-sm mb-3 flex items-center gap-2">
        <span className="rounded-lg p-1.5 bg-emerald-500"><PiggyBank size={13} className="text-white" /></span>
        Financial Summary (This Month)
      </h3>
      <div className="space-y-1.5">
        {rows.map(([label, amount, positive]) => (
          <div key={label} className="flex items-center justify-between text-sm">
            <span className="text-ink-500 dark:text-ink-400">{label}</span>
            <span className={positive ? "text-emerald-600 dark:text-emerald-400" : "text-rust-500"}>
              {positive ? "+" : ""}{amount.toLocaleString(undefined, { minimumFractionDigits: 3 })}
            </span>
          </div>
        ))}
      </div>
      <div className="border-t border-ink-100 dark:border-ink-800 mt-2 pt-2 flex items-center justify-between">
        <span className="font-semibold text-sm">Net Income</span>
        <span className={`font-display font-bold ${data.net_income >= 0 ? "text-emerald-600 dark:text-emerald-400" : "text-rust-500"}`}>
          {data.net_income.toLocaleString(undefined, { minimumFractionDigits: 3 })}
        </span>
      </div>
    </div>
  );
}

const ALERT_STYLE: Record<string, { icon: any; color: string; bg: string }> = {
  critical: { icon: AlertOctagon, color: "text-rust-600 dark:text-rust-400", bg: "bg-rust-50 dark:bg-rust-500/10" },
  warning: { icon: AlertTriangle, color: "text-amber-600 dark:text-amber-400", bg: "bg-amber-50 dark:bg-amber-500/10" },
  info: { icon: Info, color: "text-sky-600 dark:text-sky-400", bg: "bg-sky-50 dark:bg-sky-500/10" },
};

function SmartAlertsPanel({ alerts, navigate }: { alerts: ExecutiveSummary["alerts"]; navigate: (p: string) => void }) {
  return (
    <div className="card p-5">
      <h3 className="font-display font-semibold text-sm mb-3 flex items-center gap-2">
        <span className="rounded-lg p-1.5 bg-amber-500"><AlertTriangle size={13} className="text-white" /></span>
        Smart Alerts
      </h3>
      {alerts.length === 0 ? (
        <div className="text-sm text-ink-400 text-center py-4">Nothing needs attention right now.</div>
      ) : (
        <div className="space-y-2">
          {alerts.map((a, i) => {
            const style = ALERT_STYLE[a.severity];
            return (
              <div key={i} className={`rounded-lg p-2.5 ${style.bg} flex items-start gap-2`}>
                <style.icon size={15} className={`shrink-0 mt-0.5 ${style.color}`} />
                <div className="flex-1 min-w-0">
                  <p className="text-xs">{a.message}</p>
                  <button className={`text-xs font-medium mt-1 hover:underline ${style.color}`} onClick={() => navigate(a.action_path)}>
                    {a.action_label} →
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ==================== Phase 2 components: Top Lists + Calendar ====================

function ListCard({ title, empty, children }: { title: string; empty: boolean; children: React.ReactNode }) {
  return (
    <div>
      <h4 className="text-xs font-semibold uppercase text-ink-400 mb-1.5">{title}</h4>
      {empty ? <p className="text-xs text-ink-400 py-2">No data yet</p> : <div className="space-y-1">{children}</div>}
    </div>
  );
}

function TopListsPanel({ data, navigate }: { data: TopLists; navigate: (p: string) => void }) {
  const money = (n: number) => Number(n).toLocaleString(undefined, { minimumFractionDigits: 3 });
  return (
    <div className="card p-5">
      <h3 className="font-display font-semibold text-sm mb-3 flex items-center gap-2">
        <span className="rounded-lg p-1.5 bg-violet-500"><TrendingUp size={13} className="text-white" /></span>
        Top Lists
      </h3>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <ListCard title="Top Buildings by Revenue" empty={data.top_buildings_by_revenue.length === 0}>
          {data.top_buildings_by_revenue.map((b) => (
            <div key={b.id} className="flex justify-between text-xs cursor-pointer hover:text-brand-600" onClick={() => navigate(`/properties/${b.id}`)}>
              <span className="truncate">{b.title || b.code}</span><span className="font-medium shrink-0 ml-2">{money(b.value)}</span>
            </div>
          ))}
        </ListCard>
        <ListCard title="Top Buildings by Occupancy" empty={data.top_buildings_by_occupancy.length === 0}>
          {data.top_buildings_by_occupancy.map((b) => (
            <div key={b.building_id} className="flex justify-between text-xs cursor-pointer hover:text-brand-600" onClick={() => navigate(`/properties/${b.building_id}`)}>
              <span className="truncate">{b.building_title}</span><span className="font-medium shrink-0 ml-2">{b.occupancy_percentage}%</span>
            </div>
          ))}
        </ListCard>
        <ListCard title="Top Tenants (paid this month)" empty={data.top_tenants.length === 0}>
          {data.top_tenants.map((t) => (
            <div key={t.id} className="flex justify-between text-xs cursor-pointer hover:text-brand-600" onClick={() => navigate(`/tenants/${t.id}`)}>
              <span className="truncate">{t.name || t.code}</span><span className="font-medium shrink-0 ml-2">{money(t.value)}</span>
            </div>
          ))}
        </ListCard>
        <ListCard title="Top Owners (paid this month)" empty={data.top_owners.length === 0}>
          {data.top_owners.map((o) => (
            <div key={o.id} className="flex justify-between text-xs cursor-pointer hover:text-brand-600" onClick={() => navigate(`/owners/${o.id}`)}>
              <span className="truncate">{o.name || o.code}</span><span className="font-medium shrink-0 ml-2">{money(o.value)}</span>
            </div>
          ))}
        </ListCard>
        <ListCard title="Highest Expenses" empty={data.highest_expenses.length === 0}>
          {data.highest_expenses.map((e) => (
            <div key={e.id} className="flex justify-between text-xs">
              <span className="truncate">{e.category?.replace(/_/g, " ") || e.description || e.transaction_number}</span><span className="font-medium shrink-0 ml-2 text-rust-500">{money(e.amount)}</span>
            </div>
          ))}
        </ListCard>
        <ListCard title="Vacant Units" empty={data.vacant_units.length === 0}>
          {data.vacant_units.map((u) => (
            <div key={u.id} className="flex justify-between text-xs cursor-pointer hover:text-brand-600" onClick={() => navigate(`/properties/${u.id}`)}>
              <span className="truncate">{u.building_title ? `${u.building_title} — ` : ""}{u.unit_number || u.title}</span>
              <span className="font-medium shrink-0 ml-2">{u.rent_amount ? money(u.rent_amount) : "—"}</span>
            </div>
          ))}
        </ListCard>
        <ListCard title="Late Payments" empty={data.late_payments.length === 0}>
          {data.late_payments.map((p) => (
            <div key={p.installment_id} className="flex justify-between text-xs">
              <span className="truncate">{p.contract_number} · {p.days_late}d late</span><span className="font-medium shrink-0 ml-2 text-rust-500">{money(p.amount)}</span>
            </div>
          ))}
        </ListCard>
      </div>
    </div>
  );
}

const CALENDAR_EVENT_LABEL: Record<CalendarEvent["type"], { label: string; color: string }> = {
  rent_due: { label: "Rent Due", color: "text-emerald-500" },
  contract_expiration: { label: "Contract Ends", color: "text-rust-500" },
  maintenance_visit: { label: "Maintenance", color: "text-orange-500" },
  owner_payment: { label: "Owner Payment", color: "text-violet-500" },
  inspection: { label: "Inspection", color: "text-sky-500" },
};

function CalendarWidget({ events, navigate }: { events: CalendarEvent[]; navigate: (p: string) => void }) {
  return (
    <div className="card p-5">
      <h3 className="font-display font-semibold text-sm mb-3 flex items-center gap-2">
        <span className="rounded-lg p-1.5 bg-blue-500"><CalendarClock size={13} className="text-white" /></span>
        Upcoming (Next 30 Days)
      </h3>
      {events.length === 0 ? (
        <p className="text-sm text-ink-400 text-center py-4">Nothing scheduled in the next 30 days.</p>
      ) : (
        <div className="space-y-2 max-h-96 overflow-y-auto">
          {events.map((e, i) => {
            const cfg = CALENDAR_EVENT_LABEL[e.type];
            return (
              <div key={i} className="flex items-start gap-2 text-xs cursor-pointer hover:bg-ink-50 dark:hover:bg-ink-800/50 rounded-md p-1.5 -mx-1.5" onClick={() => navigate(e.link)}>
                <div className="w-14 shrink-0 text-ink-400">{new Date(e.date).toLocaleDateString(undefined, { month: "short", day: "numeric" })}</div>
                <div className="flex-1 min-w-0">
                  <div className={`font-medium ${cfg.color}`}>{cfg.label}</div>
                  <div className="text-ink-500 dark:text-ink-400 truncate">{e.title}</div>
                </div>
                {e.amount != null && <div className="font-medium shrink-0">{Number(e.amount).toLocaleString()}</div>}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
