import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import apiClient from "@/api/client";
import { useAuth } from "@/context/AuthContext";
import { PageHeader, Modal, EmptyState } from "@/components/ui";
import { Plus, Loader2, ArrowLeft, Trash2 } from "lucide-react";
import { Contractor, Technician, PaginatedResponse } from "@/types";

const SPECIALTIES = ["plumbing", "electrical", "hvac", "appliance", "structural", "pest_control", "painting", "cleaning", "security", "elevator", "landscaping", "general", "other"];

export default function MaintenanceDirectoryPage() {
  const navigate = useNavigate();
  const { hasPermission } = useAuth();
  const [tab, setTab] = useState<"contractors" | "technicians">("contractors");
  const canCreate = hasPermission("maintenance.create");
  const canDelete = hasPermission("maintenance.delete");

  return (
    <div>
      <button className="flex items-center gap-1.5 text-sm text-ink-500 hover:text-ink-800 dark:hover:text-ink-100 mb-4" onClick={() => navigate("/maintenance")}>
        <ArrowLeft size={15} /> Back to Maintenance
      </button>
      <PageHeader title="Contractors & Technicians" description="Directory of vendors and staff who perform maintenance work." />

      <div className="flex gap-1 border-b border-ink-100 dark:border-ink-800 mb-6">
        <button onClick={() => setTab("contractors")} className={`px-3.5 py-2.5 text-sm font-medium border-b-2 ${tab === "contractors" ? "border-brand-500 text-brand-600 dark:text-brand-400" : "border-transparent text-ink-500"}`}>Contractors</button>
        <button onClick={() => setTab("technicians")} className={`px-3.5 py-2.5 text-sm font-medium border-b-2 ${tab === "technicians" ? "border-brand-500 text-brand-600 dark:text-brand-400" : "border-transparent text-ink-500"}`}>Technicians</button>
      </div>

      {tab === "contractors" ? <ContractorsTab canCreate={canCreate} canDelete={canDelete} /> : <TechniciansTab canCreate={canCreate} canDelete={canDelete} />}
    </div>
  );
}

function ContractorsTab({ canCreate, canDelete }: { canCreate: boolean; canDelete: boolean }) {
  const [data, setData] = useState<PaginatedResponse<Contractor> | null>(null);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [form, setForm] = useState({ company_name: "", contact_person: "", phone: "", email: "", specialty: "", hourly_rate: "", notes: "" });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    apiClient.get<PaginatedResponse<Contractor>>("/maintenance/contractors", { params: { page_size: 50 } }).then(({ data }) => setData(data)).finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      const payload: any = { ...form };
      if (!payload.specialty) delete payload.specialty;
      if (!payload.hourly_rate) delete payload.hourly_rate;
      await apiClient.post("/maintenance/contractors", payload);
      setModalOpen(false);
      setForm({ company_name: "", contact_person: "", phone: "", email: "", specialty: "", hourly_rate: "", notes: "" });
      load();
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Unable to create this contractor.");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (c: Contractor) => {
    if (!confirm(`Delete contractor "${c.company_name}"?`)) return;
    await apiClient.delete(`/maintenance/contractors/${c.id}`);
    load();
  };

  return (
    <div className="card">
      <div className="flex justify-between items-center px-5 py-4 border-b border-ink-100 dark:border-ink-800">
        <h3 className="font-display font-semibold text-sm">Contractors</h3>
        {canCreate && <button className="btn-primary" onClick={() => setModalOpen(true)}><Plus size={14} /> Add Contractor</button>}
      </div>
      {loading && <div className="flex justify-center py-10"><Loader2 className="animate-spin text-ink-400" /></div>}
      {!loading && data && data.items.length === 0 && <EmptyState title="No contractors yet" />}
      {!loading && data && data.items.length > 0 && (
        <div className="overflow-x-auto">
          <table className="table-shell">
            <thead><tr><th>Code</th><th>Company</th><th>Contact</th><th>Specialty</th><th>Rate</th><th>Technicians</th>{canDelete && <th></th>}</tr></thead>
            <tbody>
              {data.items.map((c) => (
                <tr key={c.id}>
                  <td className="font-mono text-xs">{c.contractor_code}</td>
                  <td className="font-medium">{c.company_name}</td>
                  <td className="text-ink-500">{c.contact_person || "—"}{c.phone ? ` · ${c.phone}` : ""}</td>
                  <td className="capitalize text-ink-500">{c.specialty?.replace(/_/g, " ") || "—"}</td>
                  <td className="text-ink-500">{c.hourly_rate ? Number(c.hourly_rate).toLocaleString() : "—"}</td>
                  <td className="text-ink-500">{c.technician_count}</td>
                  {canDelete && <td className="text-right"><button className="btn-secondary !px-2 !py-1 text-rust-500" onClick={() => handleDelete(c)}><Trash2 size={13} /></button></td>}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Modal
        open={modalOpen} onClose={() => setModalOpen(false)} title="Add Contractor"
        footer={<><button className="btn-secondary" onClick={() => setModalOpen(false)}>Cancel</button><button className="btn-primary" disabled={saving || !form.company_name} onClick={handleSave}>{saving && <Loader2 size={14} className="animate-spin" />} Save</button></>}
      >
        {error && <div className="mb-3 text-sm text-rust-500 bg-rust-50 dark:bg-rust-500/10 rounded-md px-3 py-2">{error}</div>}
        <div className="space-y-4">
          <div><label className="label">Company Name *</label><input className="input" required value={form.company_name} onChange={(e) => setForm({ ...form, company_name: e.target.value })} /></div>
          <div className="grid grid-cols-2 gap-4">
            <div><label className="label">Contact Person</label><input className="input" value={form.contact_person} onChange={(e) => setForm({ ...form, contact_person: e.target.value })} /></div>
            <div><label className="label">Phone</label><input className="input" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} /></div>
          </div>
          <div><label className="label">Email</label><input className="input" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label">Specialty</label>
              <select className="input" value={form.specialty} onChange={(e) => setForm({ ...form, specialty: e.target.value })}>
                <option value="">—</option>
                {SPECIALTIES.map((s) => <option key={s} value={s}>{s.replace(/_/g, " ")}</option>)}
              </select>
            </div>
            <div><label className="label">Hourly Rate</label><input className="input" type="number" min="0" step="0.001" value={form.hourly_rate} onChange={(e) => setForm({ ...form, hourly_rate: e.target.value })} /></div>
          </div>
          <div><label className="label">Notes</label><textarea className="input" rows={2} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} /></div>
        </div>
      </Modal>
    </div>
  );
}

function TechniciansTab({ canCreate, canDelete }: { canCreate: boolean; canDelete: boolean }) {
  const [data, setData] = useState<PaginatedResponse<Technician> | null>(null);
  const [contractors, setContractors] = useState<Contractor[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [form, setForm] = useState({ first_name: "", last_name: "", phone: "", email: "", specialty: "", contractor_id: "", hourly_rate: "" });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    apiClient.get<PaginatedResponse<Technician>>("/maintenance/technicians", { params: { page_size: 50 } }).then(({ data }) => setData(data)).finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
    apiClient.get<PaginatedResponse<Contractor>>("/maintenance/contractors", { params: { page_size: 100 } }).then(({ data }) => setContractors(data.items));
  }, [load]);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      const payload: any = { ...form };
      if (!payload.specialty) delete payload.specialty;
      if (!payload.hourly_rate) delete payload.hourly_rate;
      if (payload.contractor_id) payload.contractor_id = Number(payload.contractor_id); else delete payload.contractor_id;
      await apiClient.post("/maintenance/technicians", payload);
      setModalOpen(false);
      setForm({ first_name: "", last_name: "", phone: "", email: "", specialty: "", contractor_id: "", hourly_rate: "" });
      load();
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Unable to create this technician.");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (t: Technician) => {
    if (!confirm(`Delete technician "${t.full_name}"?`)) return;
    await apiClient.delete(`/maintenance/technicians/${t.id}`);
    load();
  };

  return (
    <div className="card">
      <div className="flex justify-between items-center px-5 py-4 border-b border-ink-100 dark:border-ink-800">
        <h3 className="font-display font-semibold text-sm">Technicians</h3>
        {canCreate && <button className="btn-primary" onClick={() => setModalOpen(true)}><Plus size={14} /> Add Technician</button>}
      </div>
      {loading && <div className="flex justify-center py-10"><Loader2 className="animate-spin text-ink-400" /></div>}
      {!loading && data && data.items.length === 0 && <EmptyState title="No technicians yet" />}
      {!loading && data && data.items.length > 0 && (
        <div className="overflow-x-auto">
          <table className="table-shell">
            <thead><tr><th>Code</th><th>Name</th><th>Specialty</th><th>Affiliation</th><th>Rate</th>{canDelete && <th></th>}</tr></thead>
            <tbody>
              {data.items.map((t) => (
                <tr key={t.id}>
                  <td className="font-mono text-xs">{t.technician_code}</td>
                  <td className="font-medium">{t.full_name}</td>
                  <td className="capitalize text-ink-500">{t.specialty?.replace(/_/g, " ") || "—"}</td>
                  <td className="text-ink-500">{t.is_in_house ? "In-House" : t.contractor_name}</td>
                  <td className="text-ink-500">{t.hourly_rate ? Number(t.hourly_rate).toLocaleString() : "—"}</td>
                  {canDelete && <td className="text-right"><button className="btn-secondary !px-2 !py-1 text-rust-500" onClick={() => handleDelete(t)}><Trash2 size={13} /></button></td>}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Modal
        open={modalOpen} onClose={() => setModalOpen(false)} title="Add Technician"
        footer={<><button className="btn-secondary" onClick={() => setModalOpen(false)}>Cancel</button><button className="btn-primary" disabled={saving || !form.first_name || !form.last_name} onClick={handleSave}>{saving && <Loader2 size={14} className="animate-spin" />} Save</button></>}
      >
        {error && <div className="mb-3 text-sm text-rust-500 bg-rust-50 dark:bg-rust-500/10 rounded-md px-3 py-2">{error}</div>}
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div><label className="label">First Name *</label><input className="input" required value={form.first_name} onChange={(e) => setForm({ ...form, first_name: e.target.value })} /></div>
            <div><label className="label">Last Name *</label><input className="input" required value={form.last_name} onChange={(e) => setForm({ ...form, last_name: e.target.value })} /></div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div><label className="label">Phone</label><input className="input" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} /></div>
            <div><label className="label">Email</label><input className="input" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></div>
          </div>
          <div>
            <label className="label">Specialty</label>
            <select className="input" value={form.specialty} onChange={(e) => setForm({ ...form, specialty: e.target.value })}>
              <option value="">—</option>
              {SPECIALTIES.map((s) => <option key={s} value={s}>{s.replace(/_/g, " ")}</option>)}
            </select>
          </div>
          <div>
            <label className="label">Contractor (leave blank if in-house)</label>
            <select className="input" value={form.contractor_id} onChange={(e) => setForm({ ...form, contractor_id: e.target.value })}>
              <option value="">In-House</option>
              {contractors.map((c) => <option key={c.id} value={c.id}>{c.contractor_code} — {c.company_name}</option>)}
            </select>
          </div>
          <div><label className="label">Hourly Rate</label><input className="input" type="number" min="0" step="0.001" value={form.hourly_rate} onChange={(e) => setForm({ ...form, hourly_rate: e.target.value })} /></div>
        </div>
      </Modal>
    </div>
  );
}
