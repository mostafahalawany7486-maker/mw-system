import { useEffect, useState } from "react";
import apiClient from "@/api/client";
import { Modal } from "@/components/ui";
import { Loader2 } from "lucide-react";
import { MaintenanceContractDetail, PropertyListItem, Contractor, PaginatedResponse } from "@/types";

const SERVICE_TYPES = ["elevator", "hvac", "electrical", "plumbing", "structural", "pest_control", "painting", "cleaning", "security", "landscaping", "appliance", "other"];

const emptyForm = {
  property_id: "" as number | "",
  contractor_id: "" as number | "",
  service_type: "elevator",
  title: "",
  description: "",
  start_date: "",
  end_date: "",
  visit_frequency: "quarterly",
  annual_cost: "",
  renewal_notice_days: 30,
};

export default function MaintenanceContractFormModal({
  open, onClose, onSaved, defaultPropertyId,
}: { open: boolean; onClose: () => void; onSaved: (contract: MaintenanceContractDetail) => void; defaultPropertyId?: number }) {
  const [form, setForm] = useState<any>(emptyForm);
  const [properties, setProperties] = useState<PropertyListItem[]>([]);
  const [contractors, setContractors] = useState<Contractor[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    apiClient.get<PaginatedResponse<PropertyListItem>>("/properties", { params: { page_size: 100 } })
      .then(({ data }) => setProperties(data.items)).catch((err) => console.error(err));
    apiClient.get<PaginatedResponse<Contractor>>("/maintenance/contractors", { params: { page_size: 100 } })
      .then(({ data }) => setContractors(data.items)).catch((err) => console.error(err));
    setForm({ ...emptyForm, property_id: defaultPropertyId ?? "" });
    setError(null);
  }, [open, defaultPropertyId]);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      const { data } = await apiClient.post<MaintenanceContractDetail>("/maintenance/contracts", {
        ...form,
        property_id: Number(form.property_id),
        contractor_id: Number(form.contractor_id),
        renewal_notice_days: Number(form.renewal_notice_days),
        description: form.description || undefined,
      });
      onSaved(data);
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "Unable to create this maintenance contract. Please check the form.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Add Maintenance Contract"
      footer={
        <>
          <button className="btn-secondary" onClick={onClose}>Cancel</button>
          <button className="btn-primary" disabled={saving} onClick={handleSave}>
            {saving && <Loader2 size={14} className="animate-spin" />} Create Contract
          </button>
        </>
      }
    >
      {error && <div className="mb-3 text-sm text-rust-500 bg-rust-50 dark:bg-rust-500/10 rounded-md px-3 py-2">{error}</div>}
      <div className="space-y-4">
        <div>
          <label className="label">Property / Building *</label>
          <select className="input" required value={form.property_id} onChange={(e) => setForm({ ...form, property_id: e.target.value })}>
            <option value="">Select a property…</option>
            {properties.map((p) => <option key={p.id} value={p.id}>{p.property_code} — {p.title}</option>)}
          </select>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label">Contractor *</label>
            <select className="input" required value={form.contractor_id} onChange={(e) => setForm({ ...form, contractor_id: e.target.value })}>
              <option value="">Select a contractor…</option>
              {contractors.map((c) => <option key={c.id} value={c.id}>{c.contractor_code} — {c.company_name}</option>)}
            </select>
          </div>
          <div>
            <label className="label">Service Type *</label>
            <select className="input" required value={form.service_type} onChange={(e) => setForm({ ...form, service_type: e.target.value })}>
              {SERVICE_TYPES.map((s) => <option key={s} value={s}>{s.replace("_", " ")}</option>)}
            </select>
          </div>
        </div>
        <div>
          <label className="label">Contract Title *</label>
          <input className="input" required placeholder="e.g. Annual Elevator Maintenance Contract — Business Bay Tower"
            value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
        </div>
        <div>
          <label className="label">Description</label>
          <textarea className="input" rows={2} placeholder="Scope of work, coverage, exclusions…"
            value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label">Start Date *</label>
            <input className="input" type="date" required value={form.start_date} onChange={(e) => setForm({ ...form, start_date: e.target.value })} />
          </div>
          <div>
            <label className="label">End Date *</label>
            <input className="input" type="date" required value={form.end_date} onChange={(e) => setForm({ ...form, end_date: e.target.value })} />
          </div>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label">Annual Cost *</label>
            <input className="input" type="number" min="0" step="0.001" required value={form.annual_cost} onChange={(e) => setForm({ ...form, annual_cost: e.target.value })} />
          </div>
          <div>
            <label className="label">Visit Frequency</label>
            <select className="input" value={form.visit_frequency} onChange={(e) => setForm({ ...form, visit_frequency: e.target.value })}>
              <option value="monthly">Monthly</option>
              <option value="quarterly">Quarterly</option>
              <option value="semi_annual">Semi-Annual</option>
              <option value="annual">Annual</option>
              <option value="custom">Custom</option>
            </select>
          </div>
        </div>
        <div>
          <label className="label">Renewal Notice (days)</label>
          <input className="input" type="number" min="0" value={form.renewal_notice_days} onChange={(e) => setForm({ ...form, renewal_notice_days: e.target.value })} />
        </div>
        <p className="text-xs text-ink-400">The contract is created as a Draft. Activate it once signed to start tracking the service schedule and renewal reminders.</p>
      </div>
    </Modal>
  );
}
