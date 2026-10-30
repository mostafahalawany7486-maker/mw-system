import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import apiClient from "@/api/client";
import { useAuth } from "@/context/AuthContext";
import { PageHeader, Pagination, EmptyState, ToolbarSearch } from "@/components/ui";
import { Plus, Loader2, FileText, AlertTriangle, CircleDollarSign, RefreshCw } from "lucide-react";
import { LeaseAgreementListItem, LeaseDashboard, OwnerListItem, PaginatedResponse } from "@/types";
import LeaseFormModal from "@/components/LeaseFormModal";

const STATUS_TONE: Record<string, string> = {
  draft: "badge-inactive",
  active: "badge-active",
  expired: "badge-warn",
  terminated: "badge-inactive",
  renewed: "badge-active",
};

export default function LeasesPage() {
  const { hasPermission } = useAuth();
  const navigate = useNavigate();
  const [data, setData] = useState<PaginatedResponse<LeaseAgreementListItem> | null>(null);
  const [dashboard, setDashboard] = useState<LeaseDashboard | null>(null);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [contractStatus, setContractStatus] = useState("");
  const [includeArchived, setIncludeArchived] = useState(false);
  const [ownerId, setOwnerId] = useState("");
  const [owners, setOwners] = useState<OwnerListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [runningMaintenance, setRunningMaintenance] = useState(false);

  const canCreate = hasPermission("leases.create");
  const canEdit = hasPermission("leases.edit");

  const load = useCallback(() => {
    setLoading(true);
    apiClient
      .get<PaginatedResponse<LeaseAgreementListItem>>("/leases", {
        params: { page, page_size: 10, search: search || undefined, contract_status: contractStatus || undefined, include_archived: includeArchived || undefined, owner_id: ownerId || undefined },
      })
      .then(({ data }) => setData(data))
      .finally(() => setLoading(false));
  }, [page, search, contractStatus, includeArchived, ownerId]);

  useEffect(() => {
    apiClient.get<PaginatedResponse<OwnerListItem>>("/owners", { params: { page_size: 200 } })
      .then(({ data }) => setOwners(data.items)).catch(() => {});
  }, []);

  const loadDashboard = useCallback(() => {
    apiClient.get<LeaseDashboard>("/leases/dashboard/summary").then(({ data }) => setDashboard(data));
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { loadDashboard(); }, [loadDashboard, data]);

  const runMaintenance = async () => {
    setRunningMaintenance(true);
    try {
      await apiClient.post("/leases/maintenance/run");
      load();
      loadDashboard();
    } finally {
      setRunningMaintenance(false);
    }
  };

  return (
    <div>
      <PageHeader
        title="Lease Agreements"
        description="Contracts between the company and property owners."
        action={
          <div className="flex gap-2">
            {canEdit && (
              <button className="btn-secondary" onClick={runMaintenance} disabled={runningMaintenance}>
                {runningMaintenance ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
                Check Renewals
              </button>
            )}
            {canCreate && (
              <button className="btn-primary" onClick={() => setModalOpen(true)}>
                <Plus size={16} /> Add Lease
              </button>
            )}
          </div>
        }
      />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <div className="card p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-ink-500 dark:text-ink-400">Active Leases</span>
            <FileText size={16} className="text-ink-400" />
          </div>
          <div className="font-display text-2xl font-bold">{dashboard ? dashboard.active_leases : "—"}</div>
        </div>
        <div className="card p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-ink-500 dark:text-ink-400">Expiring Soon</span>
            <AlertTriangle size={16} className="text-amber-500" />
          </div>
          <div className="font-display text-2xl font-bold">{dashboard ? dashboard.expiring_soon : "—"}</div>
        </div>
        <div className="card p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-ink-500 dark:text-ink-400">Draft Leases</span>
            <FileText size={16} className="text-ink-400" />
          </div>
          <div className="font-display text-2xl font-bold">{dashboard ? dashboard.draft_leases : "—"}</div>
        </div>
        <div className="card p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-ink-500 dark:text-ink-400">Outstanding Payments</span>
            <CircleDollarSign size={16} className="text-ink-400" />
          </div>
          <div className="font-display text-2xl font-bold">{dashboard ? Number(dashboard.total_outstanding_amount).toLocaleString() : "—"}</div>
        </div>
      </div>

      {dashboard && dashboard.upcoming_renewals.length > 0 && (
        <div className="card p-4 mb-6 border-amber-200 dark:border-amber-500/30">
          <div className="flex items-center gap-2 mb-2">
            <AlertTriangle size={16} className="text-amber-500" />
            <h3 className="font-display font-semibold text-sm">Leases needing renewal attention</h3>
          </div>
          <div className="flex flex-wrap gap-2">
            {dashboard.upcoming_renewals.map((l) => (
              <button key={l.id} className="badge-warn hover:opacity-80" onClick={() => navigate(`/leases/${l.id}`)}>
                {l.contract_number} · {l.days_until_expiry}d left
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="card">
        <div className="p-4 border-b border-ink-100 dark:border-ink-800 flex flex-wrap gap-3 items-center">
          <ToolbarSearch value={search} onChange={(v) => { setSearch(v); setPage(1); }} placeholder="Search by contract #, property, owner…" />
          <select className="input max-w-[160px]" value={contractStatus} onChange={(e) => { setContractStatus(e.target.value); setPage(1); }}>
            <option value="">All statuses</option>
            <option value="draft">Draft</option>
            <option value="active">Active</option>
            <option value="expired">Expired</option>
            <option value="terminated">Terminated</option>
            <option value="renewed">Renewed</option>
          </select>
          <select className="input max-w-[200px]" value={ownerId} onChange={(e) => { setOwnerId(e.target.value); setPage(1); }}>
            <option value="">All owners</option>
            {owners.map((o) => <option key={o.id} value={o.id}>{o.owner_code} — {o.display_name}</option>)}
          </select>
          <label className="flex items-center gap-1.5 text-sm text-ink-500 whitespace-nowrap px-1">
            <input type="checkbox" checked={includeArchived} onChange={(e) => { setIncludeArchived(e.target.checked); setPage(1); }} />
            Show Archived
          </label>
        </div>

        {loading && <div className="flex justify-center py-10"><Loader2 className="animate-spin text-ink-400" /></div>}

        {!loading && data && data.items.length === 0 && (
          <EmptyState title="No lease agreements yet" description="Add your first lease agreement to get started." />
        )}

        {!loading && data && data.items.length > 0 && (
          <div className="overflow-x-auto">
            <table className="table-shell">
              <thead>
                <tr>
                  <th>Contract #</th><th>Owner</th><th>Property</th><th>Start</th><th>End</th><th>Rent</th><th>Status</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((l) => (
                  <tr key={l.id} className="cursor-pointer" onClick={() => navigate(`/leases/${l.id}`)}>
                    <td className="font-mono text-xs">{l.contract_number}</td>
                    <td className="font-medium">{l.owner_display_name || `#${l.owner_id}`}</td>
                    <td className="text-ink-500 max-w-[200px] truncate">
                      {l.property_reference}{l.unit_number ? ` · Unit ${l.unit_number}` : ""}
                    </td>
                    <td className="text-ink-500">{l.start_date}</td>
                    <td className="text-ink-500">{l.end_date}</td>
                    <td className="text-ink-500">{Number(l.rent_amount).toLocaleString()}</td>
                    <td>
                      <span className={STATUS_TONE[l.contract_status] || "badge-inactive"}>{l.contract_status}</span>
                      {l.status === "archived" && <span className="badge-inactive ml-1.5">Archived</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {data && <Pagination page={data.page} totalPages={data.total_pages} onChange={setPage} />}
      </div>

      <LeaseFormModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onSaved={(created) => { setModalOpen(false); navigate(`/leases/${created.id}`); }}
      />
    </div>
  );
}
