import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import apiClient from "@/api/client";
import { useAuth } from "@/context/AuthContext";
import { PageHeader, Pagination, EmptyState, ToolbarSearch } from "@/components/ui";
import { Plus, Loader2, Wrench, AlertTriangle, Clock, CheckCircle2 } from "lucide-react";
import { MaintenanceRequestListItem, MaintenanceDashboard, PaginatedResponse } from "@/types";
import MaintenanceRequestFormModal from "@/components/MaintenanceRequestFormModal";

const STATUS_TONE: Record<string, string> = {
  reported: "badge-inactive", assigned: "badge-warn", in_progress: "badge-warn",
  on_hold: "badge-warn", completed: "badge-active", cancelled: "badge-inactive",
};

const PRIORITY_TONE: Record<string, string> = {
  low: "text-ink-400", medium: "text-ink-600 dark:text-ink-300", high: "text-amber-500 font-medium", urgent: "text-rust-500 font-semibold",
};

export default function MaintenancePage() {
  const { hasPermission } = useAuth();
  const navigate = useNavigate();
  const [data, setData] = useState<PaginatedResponse<MaintenanceRequestListItem> | null>(null);
  const [dashboard, setDashboard] = useState<MaintenanceDashboard | null>(null);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [priorityFilter, setPriorityFilter] = useState("");
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);

  const canCreate = hasPermission("maintenance.create");

  const load = useCallback(() => {
    setLoading(true);
    apiClient
      .get<PaginatedResponse<MaintenanceRequestListItem>>("/maintenance/requests", {
        params: { page, page_size: 10, search: search || undefined, maintenance_status: statusFilter || undefined, priority: priorityFilter || undefined },
      })
      .then(({ data }) => setData(data))
      .finally(() => setLoading(false));
  }, [page, search, statusFilter, priorityFilter]);

  const loadDashboard = useCallback(() => {
    apiClient.get<MaintenanceDashboard>("/maintenance/dashboard/summary").then(({ data }) => setDashboard(data));
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { loadDashboard(); }, [loadDashboard, data]);

  return (
    <div>
      <PageHeader
        title="Maintenance"
        description="Maintenance requests, contractors, and technicians."
        action={
          <div className="flex gap-2">
            {hasPermission("maintenance.view") && (
              <button className="btn-secondary" onClick={() => navigate("/maintenance/directory")}><Wrench size={16} /> Contractors & Technicians</button>
            )}
            {hasPermission("maintenance.view") && (
              <button className="btn-secondary" onClick={() => navigate("/maintenance/contracts")}><Wrench size={16} /> Service Contracts</button>
            )}
            {canCreate && (
              <button className="btn-primary" onClick={() => setModalOpen(true)}>
                <Plus size={16} /> Report Issue
              </button>
            )}
          </div>
        }
      />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <div className="card p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-ink-500 dark:text-ink-400">Open Requests</span>
            <Wrench size={16} className="text-ink-400" />
          </div>
          <div className="font-display text-2xl font-bold">
            {dashboard ? dashboard.reported_count + dashboard.assigned_count + dashboard.in_progress_count + dashboard.on_hold_count : "—"}
          </div>
        </div>
        <div className="card p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-ink-500 dark:text-ink-400">Overdue</span>
            <Clock size={16} className="text-rust-500" />
          </div>
          <div className="font-display text-2xl font-bold">{dashboard ? dashboard.overdue_count : "—"}</div>
        </div>
        <div className="card p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-ink-500 dark:text-ink-400">Urgent (Open)</span>
            <AlertTriangle size={16} className="text-amber-500" />
          </div>
          <div className="font-display text-2xl font-bold">{dashboard ? dashboard.urgent_open_count : "—"}</div>
        </div>
        <div className="card p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-ink-500 dark:text-ink-400">Completed (this month)</span>
            <CheckCircle2 size={16} className="text-brand-500" />
          </div>
          <div className="font-display text-2xl font-bold">{dashboard ? Number(dashboard.total_actual_cost_this_month).toLocaleString() : "—"}</div>
        </div>
      </div>

      <div className="card">
        <div className="p-4 border-b border-ink-100 dark:border-ink-800 flex flex-wrap gap-3 items-center">
          <ToolbarSearch value={search} onChange={(v) => { setSearch(v); setPage(1); }} placeholder="Search by request #, title, property…" />
          <select className="input max-w-[160px]" value={statusFilter} onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}>
            <option value="">All statuses</option>
            <option value="reported">Reported</option>
            <option value="assigned">Assigned</option>
            <option value="in_progress">In Progress</option>
            <option value="on_hold">On Hold</option>
            <option value="completed">Completed</option>
            <option value="cancelled">Cancelled</option>
          </select>
          <select className="input max-w-[140px]" value={priorityFilter} onChange={(e) => { setPriorityFilter(e.target.value); setPage(1); }}>
            <option value="">All priorities</option>
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
            <option value="urgent">Urgent</option>
          </select>
        </div>

        {loading && <div className="flex justify-center py-10"><Loader2 className="animate-spin text-ink-400" /></div>}

        {!loading && data && data.items.length === 0 && (
          <EmptyState title="No maintenance requests yet" description="Report your first maintenance issue to get started." />
        )}

        {!loading && data && data.items.length > 0 && (
          <div className="overflow-x-auto">
            <table className="table-shell">
              <thead>
                <tr>
                  <th>Request #</th><th>Title</th><th>Property</th><th>Priority</th><th>Assigned</th><th>Cost</th><th>Status</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((r) => (
                  <tr key={r.id} className="cursor-pointer" onClick={() => navigate(`/maintenance/${r.id}`)}>
                    <td className="font-mono text-xs">{r.request_number}</td>
                    <td className="font-medium max-w-[220px] truncate">
                      {r.title}
                      {r.is_overdue && <AlertTriangle size={12} className="inline ml-1.5 text-rust-500" />}
                    </td>
                    <td className="text-ink-500 max-w-[180px] truncate">{r.property_title || `#${r.property_id}`}</td>
                    <td className={PRIORITY_TONE[r.priority]}>{r.priority}</td>
                    <td className="text-ink-500">{r.technician_name || r.contractor_name || "—"}</td>
                    <td className="text-ink-500">{Number(r.total_actual_cost).toLocaleString()}</td>
                    <td><span className={STATUS_TONE[r.maintenance_status] || "badge-inactive"}>{r.maintenance_status.replace(/_/g, " ")}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {data && <Pagination page={data.page} totalPages={data.total_pages} onChange={setPage} />}
      </div>

      <MaintenanceRequestFormModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onSaved={(created) => { setModalOpen(false); navigate(`/maintenance/${created.id}`); }}
      />
    </div>
  );
}
