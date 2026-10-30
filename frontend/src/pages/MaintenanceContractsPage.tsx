import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import apiClient from "@/api/client";
import { useAuth } from "@/context/AuthContext";
import { PageHeader, Pagination, EmptyState, ToolbarSearch, Modal } from "@/components/ui";
import { Plus, Loader2, Wrench, AlertTriangle, RefreshCw, CalendarClock, ArrowLeft } from "lucide-react";
import { MaintenanceContractListItem, MaintenanceContractDashboard, PaginatedResponse } from "@/types";
import MaintenanceContractFormModal from "@/components/MaintenanceContractFormModal";

const STATUS_TONE: Record<string, string> = {
  draft: "badge-inactive",
  active: "badge-active",
  expired: "badge-warn",
  terminated: "badge-inactive",
  renewed: "badge-active",
};

const SERVICE_TYPES = ["elevator", "hvac", "electrical", "plumbing", "structural", "pest_control", "painting", "cleaning", "security", "landscaping", "appliance", "other"];

export default function MaintenanceContractsPage() {
  const { hasPermission } = useAuth();
  const navigate = useNavigate();
  const [data, setData] = useState<PaginatedResponse<MaintenanceContractListItem> | null>(null);
  const [dashboard, setDashboard] = useState<MaintenanceContractDashboard | null>(null);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [contractStatus, setContractStatus] = useState("");
  const [serviceType, setServiceType] = useState("");
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [runningSweep, setRunningSweep] = useState(false);
  const [actionTarget, setActionTarget] = useState<{ contract: MaintenanceContractListItem; action: "terminate" | "renew" | "log-visit" } | null>(null);

  const canCreate = hasPermission("maintenance.create");
  const canEdit = hasPermission("maintenance.edit");

  const load = useCallback(() => {
    setLoading(true);
    apiClient
      .get<PaginatedResponse<MaintenanceContractListItem>>("/maintenance/contracts", {
        params: { page, page_size: 10, search: search || undefined, contract_status: contractStatus || undefined, service_type: serviceType || undefined },
      })
      .then(({ data }) => setData(data))
      .finally(() => setLoading(false));
  }, [page, search, contractStatus, serviceType]);

  const loadDashboard = useCallback(() => {
    apiClient.get<MaintenanceContractDashboard>("/maintenance/contracts/dashboard/summary").then(({ data }) => setDashboard(data));
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { loadDashboard(); }, [loadDashboard, data]);

  const runSweep = async () => {
    setRunningSweep(true);
    try {
      await apiClient.post("/maintenance/contracts/maintenance/run");
      load();
      loadDashboard();
    } finally {
      setRunningSweep(false);
    }
  };

  const activate = async (contract: MaintenanceContractListItem) => {
    await apiClient.post(`/maintenance/contracts/${contract.id}/activate`);
    load();
    loadDashboard();
  };

  return (
    <div>
      <button className="flex items-center gap-1.5 text-sm text-ink-500 hover:text-ink-800 dark:hover:text-ink-100 mb-4" onClick={() => navigate("/maintenance")}>
        <ArrowLeft size={15} /> Back to Maintenance
      </button>
      <PageHeader
        title="Maintenance Contracts"
        description="Recurring/annual service contracts with contractors — elevators, HVAC/AC, generators, fire safety, and more."
        action={
          <div className="flex gap-2">
            {canEdit && (
              <button className="btn-secondary" onClick={runSweep} disabled={runningSweep}>
                {runningSweep ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
                Check Renewals &amp; Due Visits
              </button>
            )}
            {canCreate && (
              <button className="btn-primary" onClick={() => setModalOpen(true)}>
                <Plus size={16} /> Add Contract
              </button>
            )}
          </div>
        }
      />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <div className="card p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-ink-500 dark:text-ink-400">Active Contracts</span>
            <Wrench size={16} className="text-ink-400" />
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
            <span className="text-xs font-medium text-ink-500 dark:text-ink-400">Service Visits Due</span>
            <CalendarClock size={16} className="text-amber-500" />
          </div>
          <div className="font-display text-2xl font-bold">{dashboard ? dashboard.service_due_soon : "—"}</div>
        </div>
        <div className="card p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-ink-500 dark:text-ink-400">Draft Contracts</span>
            <Wrench size={16} className="text-ink-400" />
          </div>
          <div className="font-display text-2xl font-bold">{dashboard ? dashboard.draft_contracts : "—"}</div>
        </div>
      </div>

      {dashboard && dashboard.upcoming.length > 0 && (
        <div className="card p-4 mb-6 border-amber-200 dark:border-amber-500/30">
          <div className="flex items-center gap-2 mb-2">
            <AlertTriangle size={16} className="text-amber-500" />
            <h3 className="font-display font-semibold text-sm">Contracts needing renewal attention</h3>
          </div>
          <div className="flex flex-wrap gap-2">
            {dashboard.upcoming.map((c) => (
              <span key={c.id} className="badge-warn">
                {c.contract_number} · {c.service_type} · {c.days_until_expiry}d left
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="card">
        <div className="p-4 border-b border-ink-100 dark:border-ink-800 flex flex-wrap gap-3 items-center">
          <ToolbarSearch value={search} onChange={(v) => { setSearch(v); setPage(1); }} placeholder="Search by contract #, property, contractor…" />
          <select className="input max-w-[160px]" value={contractStatus} onChange={(e) => { setContractStatus(e.target.value); setPage(1); }}>
            <option value="">All statuses</option>
            <option value="draft">Draft</option>
            <option value="active">Active</option>
            <option value="expired">Expired</option>
            <option value="terminated">Terminated</option>
            <option value="renewed">Renewed</option>
          </select>
          <select className="input max-w-[160px]" value={serviceType} onChange={(e) => { setServiceType(e.target.value); setPage(1); }}>
            <option value="">All service types</option>
            {SERVICE_TYPES.map((s) => <option key={s} value={s}>{s.replace("_", " ")}</option>)}
          </select>
        </div>

        {loading && <div className="flex justify-center py-10"><Loader2 className="animate-spin text-ink-400" /></div>}

        {!loading && data && data.items.length === 0 && (
          <EmptyState title="No maintenance contracts yet" description="Add a recurring service contract (elevator, HVAC/AC, etc.) to start tracking it." icon={Wrench} />
        )}

        {!loading && data && data.items.length > 0 && (
          <div className="overflow-x-auto">
            <table className="table-shell">
              <thead>
                <tr>
                  <th>Contract #</th><th>Property</th><th>Contractor</th><th>Service</th><th>Next Visit</th><th>End Date</th><th>Annual Cost</th><th>Status</th><th></th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((c) => (
                  <tr key={c.id}>
                    <td className="font-mono text-xs">{c.contract_number}</td>
                    <td className="font-medium max-w-[180px] truncate">{c.property_title || `#${c.property_id}`}</td>
                    <td className="text-ink-500">{c.contractor_name || `#${c.contractor_id}`}</td>
                    <td className="text-ink-500 capitalize">{c.service_type.replace("_", " ")}</td>
                    <td className={c.is_service_overdue ? "text-rust-500 font-medium" : c.is_service_due_soon ? "text-amber-500 font-medium" : "text-ink-500"}>
                      {c.next_service_due_date || "—"}
                    </td>
                    <td className="text-ink-500">{c.end_date}</td>
                    <td className="text-ink-500">{Number(c.annual_cost).toLocaleString()}</td>
                    <td><span className={STATUS_TONE[c.contract_status] || "badge-inactive"}>{c.contract_status}</span></td>
                    <td className="text-right whitespace-nowrap">
                      {canEdit && c.contract_status === "draft" && (
                        <button className="text-xs font-medium text-brand-600 dark:text-brand-400 hover:underline mr-3" onClick={() => activate(c)}>Activate</button>
                      )}
                      {canEdit && c.contract_status === "active" && (
                        <>
                          <button className="text-xs font-medium text-brand-600 dark:text-brand-400 hover:underline mr-3" onClick={() => setActionTarget({ contract: c, action: "log-visit" })}>Log Visit</button>
                          <button className="text-xs font-medium text-brand-600 dark:text-brand-400 hover:underline mr-3" onClick={() => setActionTarget({ contract: c, action: "renew" })}>Renew</button>
                          <button className="text-xs font-medium text-rust-500 hover:underline" onClick={() => setActionTarget({ contract: c, action: "terminate" })}>Terminate</button>
                        </>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {data && <Pagination page={data.page} totalPages={data.total_pages} onChange={setPage} />}
      </div>

      <MaintenanceContractFormModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onSaved={() => { setModalOpen(false); load(); loadDashboard(); }}
      />

      {actionTarget && (
        <ContractActionModal
          contract={actionTarget.contract}
          action={actionTarget.action}
          onClose={() => setActionTarget(null)}
          onDone={() => { setActionTarget(null); load(); loadDashboard(); }}
        />
      )}
    </div>
  );
}

function ContractActionModal({
  contract, action, onClose, onDone,
}: { contract: MaintenanceContractListItem; action: "terminate" | "renew" | "log-visit"; onClose: () => void; onDone: () => void }) {
  const [terminatedDate, setTerminatedDate] = useState(new Date().toISOString().slice(0, 10));
  const [reason, setReason] = useState("");
  const [newEndDate, setNewEndDate] = useState("");
  const [visitDate, setVisitDate] = useState(new Date().toISOString().slice(0, 10));
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const titles: Record<string, string> = { terminate: "Terminate Contract", renew: "Renew Contract", "log-visit": "Log Service Visit" };

  const handleSubmit = async () => {
    setSaving(true);
    setError(null);
    try {
      if (action === "terminate") {
        await apiClient.post(`/maintenance/contracts/${contract.id}/terminate`, { terminated_date: terminatedDate, termination_reason: reason });
      } else if (action === "renew") {
        await apiClient.post(`/maintenance/contracts/${contract.id}/renew`, { new_end_date: newEndDate });
      } else {
        await apiClient.post(`/maintenance/contracts/${contract.id}/log-visit`, { visit_date: visitDate, notes: notes || undefined });
      }
      onDone();
    } catch (err: any) {
      setError(err?.response?.data?.detail || `Unable to ${action.replace("-", " ")} this contract.`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open onClose={onClose} title={`${titles[action]} — ${contract.contract_number}`}
      footer={
        <>
          <button className="btn-secondary" onClick={onClose}>Cancel</button>
          <button
            className={action === "terminate" ? "btn-danger" : "btn-primary"}
            disabled={saving || (action === "terminate" && !reason) || (action === "renew" && !newEndDate)}
            onClick={handleSubmit}
          >
            {saving && <Loader2 size={14} className="animate-spin" />} {titles[action]}
          </button>
        </>
      }
    >
      {error && <div className="mb-3 text-sm text-rust-500 bg-rust-50 dark:bg-rust-500/10 rounded-md px-3 py-2">{error}</div>}
      {action === "terminate" && (
        <div className="space-y-4">
          <div>
            <label className="label">Termination Date *</label>
            <input className="input" type="date" value={terminatedDate} onChange={(e) => setTerminatedDate(e.target.value)} />
          </div>
          <div>
            <label className="label">Reason *</label>
            <textarea className="input" rows={3} required value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. Switching to a different vendor" />
          </div>
        </div>
      )}
      {action === "renew" && (
        <div className="space-y-4">
          <p className="text-sm text-ink-500">Renewing creates a new contract starting the day after {contract.end_date} and marks this one as Renewed.</p>
          <div>
            <label className="label">New End Date *</label>
            <input className="input" type="date" value={newEndDate} onChange={(e) => setNewEndDate(e.target.value)} />
          </div>
        </div>
      )}
      {action === "log-visit" && (
        <div className="space-y-4">
          <div>
            <label className="label">Visit Date *</label>
            <input className="input" type="date" value={visitDate} onChange={(e) => setVisitDate(e.target.value)} />
          </div>
          <div>
            <label className="label">Notes</label>
            <textarea className="input" rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="e.g. Quarterly inspection completed, no issues found" />
          </div>
        </div>
      )}
    </Modal>
  );
}
