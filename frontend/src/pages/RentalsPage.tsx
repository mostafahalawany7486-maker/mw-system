import { useEffect, useState, useCallback } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import apiClient from "@/api/client";
import { useAuth } from "@/context/AuthContext";
import { PageHeader, Pagination, EmptyState, ToolbarSearch } from "@/components/ui";
import { Plus, Loader2, FileText, AlertTriangle, CircleDollarSign, RefreshCw, ShieldBan, Receipt as ReceiptIcon, FileStack, Sparkles } from "lucide-react";
import { RentalContractListItem, RentalDashboard, PropertyListItem, PaginatedResponse } from "@/types";
import RentalFormModal from "@/components/RentalFormModal";

const STATUS_TONE: Record<string, string> = {
  draft: "badge-inactive", active: "badge-active", expired: "badge-warn",
  terminated: "badge-inactive", renewed: "badge-active",
};

export default function RentalsPage() {
  const { hasPermission } = useAuth();
  const navigate = useNavigate();
  const [data, setData] = useState<PaginatedResponse<RentalContractListItem> | null>(null);
  const [dashboard, setDashboard] = useState<RentalDashboard | null>(null);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [contractStatus, setContractStatus] = useState("");
  const [includeArchived, setIncludeArchived] = useState(false);
  const [buildingId, setBuildingId] = useState("");
  const [buildings, setBuildings] = useState<PropertyListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [searchParams] = useSearchParams();
  useEffect(() => { if (searchParams.get("new") === "true") setModalOpen(true); }, [searchParams]);
  const [runningMaintenance, setRunningMaintenance] = useState(false);

  const canCreate = hasPermission("rentals.create");
  const canEdit = hasPermission("rentals.edit");

  const load = useCallback(() => {
    setLoading(true);
    apiClient
      .get<PaginatedResponse<RentalContractListItem>>("/rentals", {
        params: { page, page_size: 10, search: search || undefined, contract_status: contractStatus || undefined, include_archived: includeArchived || undefined, building_id: buildingId || undefined },
      })
      .then(({ data }) => setData(data))
      .finally(() => setLoading(false));
  }, [page, search, contractStatus, includeArchived, buildingId]);

  useEffect(() => {
    apiClient.get<PaginatedResponse<PropertyListItem>>("/properties", { params: { top_level_only: true, page_size: 200 } })
      .then(({ data }) => setBuildings(data.items)).catch(() => {});
  }, []);

  const loadDashboard = useCallback(() => {
    apiClient.get<RentalDashboard>("/rentals/dashboard/summary").then(({ data }) => setDashboard(data));
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { loadDashboard(); }, [loadDashboard, data]);

  const runMaintenance = async () => {
    setRunningMaintenance(true);
    try {
      await apiClient.post("/rentals/maintenance/run");
      load();
      loadDashboard();
    } finally {
      setRunningMaintenance(false);
    }
  };

  return (
    <div>
      <PageHeader
        title="Rental Contracts"
        description="Contracts between the company and tenants."
        action={
          <div className="flex gap-2">
            <button className="btn-secondary" onClick={() => navigate("/payments")}>
              <ReceiptIcon size={16} /> Payments
            </button>
            <button className="btn-secondary" onClick={() => navigate("/rent-vouchers")}>
              <FileStack size={16} /> Rent Vouchers
            </button>
            {canEdit && (
              <button className="btn-secondary" onClick={runMaintenance} disabled={runningMaintenance} title="Also processes any contract with Auto-Renew turned on, in addition to sending renewal reminders for the rest">
                {runningMaintenance ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
                Check Renewals
              </button>
            )}
            {canCreate && (
              <button className="btn-primary" onClick={() => navigate("/rentals/new-wizard")}>
                <Sparkles size={16} /> New Lease Wizard
              </button>
            )}
            {canCreate && (
              <button className="btn-secondary" onClick={() => setModalOpen(true)}>
                <Plus size={16} /> Add Contract (Classic)
              </button>
            )}
          </div>
        }
      />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <div className="card p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-ink-500 dark:text-ink-400">Active Contracts</span>
            <FileText size={16} className="text-ink-400" />
          </div>
          <div className="font-display text-2xl font-bold">{dashboard ? dashboard.active_contracts : "—"}</div>
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
            <span className="text-xs font-medium text-ink-500 dark:text-ink-400">Draft Contracts</span>
            <FileText size={16} className="text-ink-400" />
          </div>
          <div className="font-display text-2xl font-bold">{dashboard ? dashboard.draft_contracts : "—"}</div>
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
            <h3 className="font-display font-semibold text-sm">Contracts needing renewal attention</h3>
          </div>
          <div className="flex flex-wrap gap-2">
            {dashboard.upcoming_renewals.map((c) => (
              <button key={c.id} className="badge-warn hover:opacity-80" onClick={() => navigate(`/rentals/${c.id}`)}>
                {c.contract_number} · {c.days_until_expiry}d left
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="card">
        <div className="p-4 border-b border-ink-100 dark:border-ink-800 flex flex-wrap gap-3 items-center">
          <ToolbarSearch value={search} onChange={(v) => { setSearch(v); setPage(1); }} placeholder="Search by contract #, tenant, property…" />
          <select className="input max-w-[160px]" value={contractStatus} onChange={(e) => { setContractStatus(e.target.value); setPage(1); }}>
            <option value="">All statuses</option>
            <option value="draft">Draft</option>
            <option value="active">Active</option>
            <option value="expired">Expired</option>
            <option value="terminated">Terminated</option>
            <option value="renewed">Renewed</option>
          </select>
          <select className="input max-w-[200px]" value={buildingId} onChange={(e) => { setBuildingId(e.target.value); setPage(1); }}>
            <option value="">All buildings/properties</option>
            {buildings.map((b) => <option key={b.id} value={b.id}>{b.property_code} — {b.title}</option>)}
          </select>
          <label className="flex items-center gap-1.5 text-sm text-ink-500 whitespace-nowrap px-1">
            <input type="checkbox" checked={includeArchived} onChange={(e) => { setIncludeArchived(e.target.checked); setPage(1); }} />
            Show Archived
          </label>
        </div>

        {loading && <div className="flex justify-center py-10"><Loader2 className="animate-spin text-ink-400" /></div>}

        {!loading && data && data.items.length === 0 && (
          <EmptyState title="No rental contracts yet" description="Add your first rental contract to get started." />
        )}

        {!loading && data && data.items.length > 0 && (
          <div className="overflow-x-auto">
            <table className="table-shell">
              <thead>
                <tr>
                  <th>Contract #</th><th>Tenant</th><th>Property</th><th>Start</th><th>End</th><th>Rent</th><th>Status</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((c) => (
                  <tr key={c.id} className="cursor-pointer" onClick={() => navigate(`/rentals/${c.id}`)}>
                    <td className="font-mono text-xs">{c.contract_number}</td>
                    <td className="font-medium">
                      <div className="flex items-center gap-1.5">
                        {c.tenant_display_name || `#${c.tenant_id}`}
                        {c.tenant_is_blacklisted && <span title="Blacklisted tenant"><ShieldBan size={13} className="text-rust-500" /></span>}
                      </div>
                    </td>
                    <td className="text-ink-500 max-w-[200px] truncate">
                      {c.property_title || `#${c.property_id}`}{c.unit_number ? ` · Unit ${c.unit_number}` : ""}
                    </td>
                    <td className="text-ink-500">{c.start_date}</td>
                    <td className="text-ink-500">{c.end_date}</td>
                    <td className="text-ink-500">{Number(c.rent_amount).toLocaleString()}</td>
                    <td>
                      <span className={STATUS_TONE[c.contract_status] || "badge-inactive"}>{c.contract_status}</span>
                      {c.status === "archived" && <span className="badge-inactive ml-1.5">Archived</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {data && <Pagination page={data.page} totalPages={data.total_pages} onChange={setPage} />}
      </div>

      <RentalFormModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onSaved={(created) => { setModalOpen(false); navigate(`/rentals/${created.id}`); }}
      />
    </div>
  );
}
