import { useEffect, useState } from "react";
import apiClient from "@/api/client";
import { PageHeader, EmptyState, Pagination } from "@/components/ui";
import { AuditLogEntry } from "@/types";
import { Loader2 } from "lucide-react";

export default function AuditLogPage() {
  const [entries, setEntries] = useState<AuditLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);

  useEffect(() => {
    setLoading(true);
    apiClient.get<AuditLogEntry[]>("/audit-logs", { params: { page, page_size: 25 } })
      .then(({ data }) => setEntries(data))
      .finally(() => setLoading(false));
  }, [page]);

  return (
    <div>
      <PageHeader title="Audit Log" description="Precise, field-level record of every change for compliance and security review. Restricted to authorized roles." />
      <div className="card">
        {loading && <div className="flex justify-center py-10"><Loader2 className="animate-spin text-ink-400" /></div>}
        {!loading && entries.length === 0 && <EmptyState title="No audit records yet" />}
        {!loading && entries.length > 0 && (
          <div className="overflow-x-auto">
            <table className="table-shell">
              <thead>
                <tr><th>Entity</th><th>Action</th><th>Changes</th><th>IP Address</th><th>When</th></tr>
              </thead>
              <tbody>
                {entries.map((e) => (
                  <tr key={e.id}>
                    <td className="capitalize">{e.entity_type} #{e.entity_id}</td>
                    <td className="capitalize">{e.action.replace(/_/g, " ")}</td>
                    <td className="font-mono text-xs max-w-xs truncate">
                      {e.changed_fields ? Object.keys(e.changed_fields).join(", ") : "—"}
                    </td>
                    <td className="text-ink-500">{e.ip_address || "—"}</td>
                    <td className="text-ink-400 text-xs">{new Date(e.created_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <Pagination page={page} totalPages={entries.length === 25 ? page + 1 : page} onChange={setPage} />
      </div>
    </div>
  );
}
