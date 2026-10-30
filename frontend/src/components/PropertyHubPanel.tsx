import { useEffect, useState } from "react";
import apiClient from "@/api/client";
import { Loader2, Home, DoorOpen, DoorClosed, FileSignature, AlertTriangle, TrendingUp, Wrench, Activity, UserSquare2 } from "lucide-react";

interface PropertyHubSummary {
  owner_id: number | null;
  owner_display_name: string | null;
  master_lease_id: number | null;
  master_lease_contract_number: string | null;
  occupied_units: number;
  vacant_units: number;
  occupancy_percentage: number;
  active_contracts: number;
  expiring_contracts: number;
  upcoming_rent_due: string;
  upcoming_owner_payment_due: string;
  upcoming_window_days: number;
  income_this_month: string;
  owner_paid_this_month: string;
  maintenance_cost_this_month: string;
  estimated_profit_this_month: string;
  open_maintenance_count: number;
  alerts: Array<{ severity: "info" | "warning"; message: string }>;
  recent_activity: Array<{ action: string; description: string; created_at: string }>;
}

/**
 * "Everything about this property, on one screen" — shown above the
 * tabs so it's visible regardless of which tab is open. Read-only,
 * composed entirely from existing services (see
 * app/business_workflows/property_hub_service.py); nothing here
 * duplicates the detailed tabs below it, it's a glance-level summary
 * that links deeper only through the numbers already shown elsewhere.
 */
export default function PropertyHubPanel({ propertyId }: { propertyId: number }) {
  const [summary, setSummary] = useState<PropertyHubSummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    apiClient.get<PropertyHubSummary>(`/properties/${propertyId}/hub-summary`)
      .then(({ data }) => setSummary(data))
      .catch(() => setSummary(null))
      .finally(() => setLoading(false));
  }, [propertyId]);

  if (loading) {
    return <div className="card p-4 mb-6 flex justify-center"><Loader2 size={16} className="animate-spin text-ink-400" /></div>;
  }
  if (!summary) return null;

  const money = (v: string) => Number(v).toLocaleString(undefined, { minimumFractionDigits: 3 });

  return (
    <div className="card mb-6">
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 divide-x divide-y md:divide-y-0 divide-ink-50 dark:divide-ink-800/60">
        <HubStat icon={UserSquare2} label="Owner" value={summary.owner_display_name || "—"} small />
        <HubStat icon={DoorClosed} label="Occupied" value={String(summary.occupied_units)} tone="text-emerald-500" />
        <HubStat icon={DoorOpen} label="Vacant" value={String(summary.vacant_units)} tone="text-amber-500" />
        <HubStat icon={FileSignature} label="Active Contracts" value={String(summary.active_contracts)} tone="text-fuchsia-500" />
        <HubStat icon={Wrench} label="Open Maintenance" value={String(summary.open_maintenance_count)} tone="text-orange-500" />
        <HubStat icon={TrendingUp} label="Est. Profit (This Month)" value={money(summary.estimated_profit_this_month)} tone={Number(summary.estimated_profit_this_month) >= 0 ? "text-emerald-500" : "text-rust-500"} />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 p-4 border-t border-ink-100 dark:border-ink-800">
        <div className="text-sm space-y-1.5">
          <p className="text-xs font-semibold uppercase text-ink-400 mb-1">Upcoming (next {summary.upcoming_window_days} days)</p>
          <div className="flex justify-between"><span className="text-ink-500">Rent due from tenants</span><span className="font-medium">{money(summary.upcoming_rent_due)}</span></div>
          <div className="flex justify-between">
            <span className="text-ink-500">Owed to owner{summary.master_lease_contract_number ? ` (${summary.master_lease_contract_number})` : ""}</span>
            <span className="font-medium">{summary.master_lease_id ? money(summary.upcoming_owner_payment_due) : "no master lease"}</span>
          </div>
        </div>

        <div>
          {summary.alerts.length > 0 ? (
            <div className="space-y-1.5">
              <p className="text-xs font-semibold uppercase text-ink-400 mb-1">Alerts</p>
              {summary.alerts.map((a, i) => (
                <div key={i} className={`flex items-center gap-1.5 text-sm ${a.severity === "warning" ? "text-amber-600" : "text-ink-500"}`}>
                  <AlertTriangle size={13} /> {a.message}
                </div>
              ))}
            </div>
          ) : (
            <div className="flex items-center gap-1.5 text-sm text-emerald-600"><Home size={13} /> Nothing needs attention right now.</div>
          )}
        </div>
      </div>

      {summary.recent_activity.length > 0 && (
        <div className="p-4 border-t border-ink-100 dark:border-ink-800">
          <p className="text-xs font-semibold uppercase text-ink-400 mb-2 flex items-center gap-1.5"><Activity size={12} /> Recent Activity</p>
          <div className="space-y-1">
            {summary.recent_activity.slice(0, 4).map((a, i) => (
              <div key={i} className="flex justify-between text-xs text-ink-500">
                <span className="truncate">{a.description}</span>
                <span className="shrink-0 ml-3">{new Date(a.created_at).toLocaleDateString()}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function HubStat({ icon: Icon, label, value, tone, small }: { icon: any; label: string; value: string; tone?: string; small?: boolean }) {
  return (
    <div className="p-3.5">
      <div className="flex items-center gap-1.5 text-xs text-ink-400 mb-1">
        <Icon size={12} className={tone || "text-ink-400"} /> {label}
      </div>
      <div className={`font-display font-bold ${small ? "text-sm truncate" : "text-lg"}`}>{value}</div>
    </div>
  );
}
