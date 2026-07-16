import { useEffect, useState } from "react";
import apiClient from "@/api/client";
import { PageHeader, EmptyState } from "@/components/ui";
import { ActivityLogEntry } from "@/types";
import { Loader2 } from "lucide-react";

/**
 * Phase 1 note: the activity log API is entity-scoped (?entity_type=&entity_id=)
 * so any future module (properties, leases, tenants) can show its own history
 * inline. This page shows the Administrator account's own activity as a
 * working example; once business modules exist, each record's detail page
 * will embed this same feed for that specific record.
 */
export default function ActivityLogPage() {
  const [entries, setEntries] = useState<ActivityLogEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiClient.get<{ id: number }>("/auth/me").then(({ data }) => {
      apiClient
        .get<ActivityLogEntry[]>("/activity-logs", { params: { entity_type: "user", entity_id: data.id } })
        .then(({ data }) => setEntries(data))
        .finally(() => setLoading(false));
    });
  }, []);

  return (
    <div>
      <PageHeader title="Activity Log" description="A human-readable timeline of actions on your account. Business modules will show their own activity here in later phases." />
      <div className="card">
        {loading && <div className="flex justify-center py-10"><Loader2 className="animate-spin text-ink-400" /></div>}
        {!loading && entries.length === 0 && <EmptyState title="No activity yet" />}
        <div className="divide-y divide-ink-50 dark:divide-ink-800/60">
          {entries.map((e) => (
            <div key={e.id} className="px-5 py-3 flex items-center justify-between">
              <div>
                <p className="text-sm">{e.description}</p>
                <p className="text-xs text-ink-400 mt-0.5 capitalize">{e.action.replace(/_/g, " ")}</p>
              </div>
              <span className="text-xs text-ink-400 shrink-0 ml-4">{new Date(e.created_at).toLocaleString()}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
