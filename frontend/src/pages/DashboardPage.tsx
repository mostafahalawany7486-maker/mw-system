import { useEffect, useState } from "react";
import apiClient from "@/api/client";
import { PageHeader } from "@/components/ui";
import { Users, ShieldCheck, Building2, BellRing, Activity, UserSquare2 } from "lucide-react";

interface DashboardSummary {
  widgets: {
    total_users: number;
    active_users: number;
    total_roles: number;
    total_branches: number;
    total_owners: number;
    unread_notifications: number;
  };
  recent_activity: Array<{
    action: string; description: string; entity_type: string; entity_id: number; created_at: string;
  }>;
}

const WIDGET_CONFIG = [
  { key: "total_owners", label: "Property Owners", icon: UserSquare2, tone: "brand" },
  { key: "total_users", label: "Total Users", icon: Users, tone: "brand" },
  { key: "active_users", label: "Active Users", icon: Users, tone: "brand" },
  { key: "total_roles", label: "Roles Defined", icon: ShieldCheck, tone: "amber" },
  { key: "total_branches", label: "Branches", icon: Building2, tone: "amber" },
  { key: "unread_notifications", label: "Unread Notifications", icon: BellRing, tone: "rust" },
] as const;

export default function DashboardPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);

  useEffect(() => {
    apiClient.get<DashboardSummary>("/dashboard/summary").then(({ data }) => setSummary(data));
  }, []);

  return (
    <div>
      <PageHeader title="Dashboard" description="A snapshot of your organization's setup and recent activity." />

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-6">
        {WIDGET_CONFIG.map((w) => (
          <div key={w.key} className="card p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-medium text-ink-500 dark:text-ink-400">{w.label}</span>
              <w.icon size={16} className="text-ink-400" />
            </div>
            <div className="font-display text-2xl font-bold">
              {summary ? summary.widgets[w.key as keyof DashboardSummary["widgets"]] : "—"}
            </div>
          </div>
        ))}
      </div>

      <div className="card">
        <div className="flex items-center gap-2 px-5 py-4 border-b border-ink-100 dark:border-ink-800">
          <Activity size={16} className="text-ink-400" />
          <h2 className="font-display font-semibold text-sm">Recent Activity</h2>
        </div>
        <div className="divide-y divide-ink-50 dark:divide-ink-800/60">
          {summary?.recent_activity.length === 0 && (
            <div className="px-5 py-8 text-center text-sm text-ink-400">No activity recorded yet.</div>
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
