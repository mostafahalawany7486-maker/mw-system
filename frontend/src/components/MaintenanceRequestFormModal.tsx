import { useEffect, useState } from "react";
import apiClient from "@/api/client";
import { Modal } from "@/components/ui";
import { Loader2 } from "lucide-react";
import { MaintenanceRequestDetail, PropertyListItem, TenantListItem, PaginatedResponse } from "@/types";

const CATEGORIES = ["plumbing", "electrical", "hvac", "appliance", "structural", "pest_control", "painting", "cleaning", "security", "elevator", "landscaping", "other"];

const emptyForm = {
  property_id: "" as number | "",
  tenant_id: "" as number | "",
  title: "",
  description: "",
  category: "",
  priority: "medium",
  reported_date: new Date().toISOString().slice(0, 10),
  scheduled_date: "",
  estimated_cost: "",
  notes: "",
};

export default function MaintenanceRequestFormModal({
  open, onClose, onSaved,
}: { open: boolean; onClose: () => void; onSaved: (req: MaintenanceRequestDetail) => void }) {
  const [form, setForm] = useState<any>(emptyForm);
  const [properties, setProperties] = useState<PropertyListItem[]>([]);
  const [tenants, setTenants] = useState<TenantListItem[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    apiClient.get<PaginatedResponse<PropertyListItem>>("/properties", { params: { page_size: 100 } }).then(({ data }) => setProperties(data.items)).catch((err) => console.error(err));
    apiClient.get<PaginatedResponse<TenantListItem>>("/tenants", { params: { page_size: 100 } }).then(({ data }) => setTenants(data.items)).catch((err) => console.error(err));
    setForm(emptyForm);
    setError(null);
  }, [open]);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      const payload: any = {
        ...form,
        property_id: Number(form.property_id),
        tenant_id: form.tenant_id ? Number(form.tenant_id) : undefined,
        category: form.category || undefined,
        scheduled_date: form.scheduled_date || undefined,
        estimated_cost: form.estimated_cost || undefined,
        description: form.description || undefined,
        notes: form.notes || undefined,
      };
      const { data } = await apiClient.post<MaintenanceRequestDetail>("/maintenance/requests", payload);
      onSaved(data);
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "Unable to create this request. Please check the form.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Report Maintenance Issue"
      footer={
        <>
          <button className="btn-secondary" onClick={onClose}>Cancel</button>
          <button className="btn-primary" disabled={saving} onClick={handleSave}>
            {saving && <Loader2 size={14} className="animate-spin" />} Create Request
          </button>
        </>
      }
    >
      {error && <div className="mb-3 text-sm text-rust-500 bg-rust-50 dark:bg-rust-500/10 rounded-md px-3 py-2">{error}</div>}
      <div className="space-y-4">
        <div>
          <label className="label">Property / Unit *</label>
          <select className="input" required value={form.property_id} onChange={(e) => setForm({ ...form, property_id: e.target.value })}>
            <option value="">Select a property…</option>
            {properties.map((p) => <option key={p.id} value={p.id}>{p.property_code} — {p.title}</option>)}
          </select>
        </div>
        <div>
          <label className="label">Reported By (Tenant)</label>
          <select className="input" value={form.tenant_id} onChange={(e) => setForm({ ...form, tenant_id: e.target.value })}>
            <option value="">Staff-reported / not tenant-specific</option>
            {tenants.map((t) => <option key={t.id} value={t.id}>{t.tenant_code} — {t.display_name}</option>)}
          </select>
        </div>
        <div>
          <label className="label">Title *</label>
          <input className="input" required value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="e.g. Kitchen sink leak" />
        </div>
        <div>
          <label className="label">Description</label>
          <textarea className="input" rows={3} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label">Category</label>
            <select className="input" value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>
              <option value="">—</option>
              {CATEGORIES.map((c) => <option key={c} value={c}>{c.replace(/_/g, " ")}</option>)}
            </select>
          </div>
          <div>
            <label className="label">Priority</label>
            <select className="input" value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value })}>
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
              <option value="urgent">Urgent</option>
            </select>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label">Reported Date *</label>
            <input className="input" type="date" required value={form.reported_date} onChange={(e) => setForm({ ...form, reported_date: e.target.value })} />
          </div>
          <div>
            <label className="label">Scheduled Date</label>
            <input className="input" type="date" value={form.scheduled_date} onChange={(e) => setForm({ ...form, scheduled_date: e.target.value })} />
          </div>
        </div>
        <div>
          <label className="label">Estimated Cost</label>
          <input className="input" type="number" min="0" step="0.001" value={form.estimated_cost} onChange={(e) => setForm({ ...form, estimated_cost: e.target.value })} />
        </div>
      </div>
    </Modal>
  );
}
