import { useEffect, useState } from "react";
import apiClient from "@/api/client";
import { Modal } from "@/components/ui";
import { Loader2 } from "lucide-react";
import { LeaseAgreementDetail, PropertyListItem } from "@/types";
import PropertyHierarchySelector from "@/components/PropertyHierarchySelector";

const emptyForm = {
  owner_id: "" as number | "",
  property_id: "" as number | "",
  property_reference: "",
  start_date: "",
  end_date: "",
  payment_frequency: "monthly",
  rent_amount: "",
  security_deposit_amount: "0",
  renewal_notice_days: 30,
};

// Mirrors FREQUENCY_MONTHS in app/services/lease_service.py exactly —
// used only to preview the schedule client-side before saving, not to
// generate it (the real generation still happens server-side).
const FREQUENCY_MONTHS: Record<string, number> = { monthly: 1, quarterly: 3, semi_annual: 6, annual: 12 };
const FREQUENCY_LABELS: Record<string, string> = {
  monthly: "per month", quarterly: "per quarter", semi_annual: "per half-year", annual: "per year", one_time: "one-time, full amount",
};

export default function LeaseFormModal({
  open, onClose, onSaved, defaultOwnerId,
}: { open: boolean; onClose: () => void; onSaved: (lease: LeaseAgreementDetail) => void; defaultOwnerId?: number }) {
  const [form, setForm] = useState<any>(emptyForm);
  const [referenceEdited, setReferenceEdited] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setForm({ ...emptyForm, owner_id: defaultOwnerId ?? "" });
    setReferenceEdited(false);
    setError(null);
  }, [open, defaultOwnerId]);

  const handleUnitSelect = (unit: PropertyListItem | null) => {
    setForm((f: any) => ({
      ...f,
      property_id: unit?.id ?? "",
      // Auto-filled from the selected property/unit, but still a plain
      // editable field underneath (property_reference stays a required
      // column on LeaseAgreement — this doesn't remove it, just stops
      // it from being purely hand-typed) — once the person edits it
      // themselves, stop overwriting their wording on further selector
      // changes.
      property_reference: referenceEdited ? f.property_reference : (unit ? `${unit.title}${unit.unit_number ? ` — Unit ${unit.unit_number}` : ""} (${unit.property_code})` : ""),
    }));
  };

  // Client-side preview only — the real schedule is generated
  // server-side (Generate Schedule, after the lease is saved). This
  // exists purely so a person can catch "I typed the annual total
  // where a per-month amount was expected" before saving, not after
  // seeing 6 installments each demanding the full amount.
  const scheduleEstimate = (() => {
    if (!form.start_date || !form.end_date || !form.rent_amount || Number(form.rent_amount) <= 0) return null;
    const start = new Date(form.start_date);
    const end = new Date(form.end_date);
    if (isNaN(start.getTime()) || isNaN(end.getTime()) || end <= start) return null;
    let count: number;
    if (form.payment_frequency === "one_time") {
      count = 1;
    } else if (form.payment_frequency === "custom") {
      return null; // manual schedule — nothing to preview
    } else {
      const stepMonths = FREQUENCY_MONTHS[form.payment_frequency] || 1;
      const totalMonths = (end.getFullYear() - start.getFullYear()) * 12 + (end.getMonth() - start.getMonth());
      count = Math.max(1, Math.floor(totalMonths / stepMonths) + 1);
    }
    return { count, total: count * Number(form.rent_amount) };
  })();

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      const { data } = await apiClient.post<LeaseAgreementDetail>("/leases", {
        ...form,
        owner_id: Number(form.owner_id),
        property_id: form.property_id ? Number(form.property_id) : undefined,
        renewal_notice_days: Number(form.renewal_notice_days),
      });
      onSaved(data);
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "Unable to create this lease. Please check the form.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Add Lease Agreement"
      footer={
        <>
          <button className="btn-secondary" onClick={onClose}>Cancel</button>
          <button className="btn-primary" disabled={saving} onClick={handleSave}>
            {saving && <Loader2 size={14} className="animate-spin" />} Create Lease
          </button>
        </>
      }
    >
      {error && <div className="mb-3 text-sm text-rust-500 bg-rust-50 dark:bg-rust-500/10 rounded-md px-3 py-2">{error}</div>}
      <div className="space-y-4">
        <div className="border-b border-ink-100 dark:border-ink-800 pb-4">
          <p className="text-xs font-semibold uppercase text-ink-400 mb-3">Property (the whole building/property being leased from this owner)</p>
          <PropertyHierarchySelector
            ownerId={form.owner_id}
            onOwnerChange={(id) => setForm((f: any) => ({ ...f, owner_id: id, property_id: "", property_reference: "" }))}
            onUnitSelect={handleUnitSelect}
            buildingLevelOnly
          />
        </div>
        <div>
          <label className="label">Property Reference *</label>
          <textarea className="input" rows={2} required placeholder="Auto-filled from the selection above — edit if you need a different wording"
            value={form.property_reference} onChange={(e) => { setReferenceEdited(true); setForm({ ...form, property_reference: e.target.value }); }} />
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
            <label className="label">Rent Amount {FREQUENCY_LABELS[form.payment_frequency] ? `(${FREQUENCY_LABELS[form.payment_frequency]}) ` : ""}*</label>
            <input className="input" type="number" min="0" step="0.001" required value={form.rent_amount} onChange={(e) => setForm({ ...form, rent_amount: e.target.value })} />
          </div>
          <div>
            <label className="label">Payment Frequency</label>
            <select className="input" value={form.payment_frequency} onChange={(e) => setForm({ ...form, payment_frequency: e.target.value })}>
              <option value="monthly">Monthly</option>
              <option value="quarterly">Quarterly</option>
              <option value="semi_annual">Semi-Annual</option>
              <option value="annual">Annual</option>
              <option value="one_time">One-Time</option>
              <option value="custom">Custom (manual schedule)</option>
            </select>
          </div>
        </div>
        {scheduleEstimate && (
          <p className="text-xs text-ink-400 -mt-2">
            {scheduleEstimate.count} installment(s) of {form.rent_amount || 0} each ≈ <strong>{scheduleEstimate.total.toLocaleString()}</strong> total over the contract's full term. If that total looks too high, this amount is <strong>per {FREQUENCY_LABELS[form.payment_frequency]}</strong>, not the whole contract's value.
          </p>
        )}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label">Security Deposit</label>
            <input className="input" type="number" min="0" step="0.001" value={form.security_deposit_amount} onChange={(e) => setForm({ ...form, security_deposit_amount: e.target.value })} />
          </div>
          <div>
            <label className="label">Renewal Notice (days)</label>
            <input className="input" type="number" min="0" value={form.renewal_notice_days} onChange={(e) => setForm({ ...form, renewal_notice_days: e.target.value })} />
          </div>
        </div>
        <p className="text-xs text-ink-400">The lease is created as a Draft. Activate it once signed to start tracking payments and renewal reminders.</p>
      </div>
    </Modal>
  );
}
