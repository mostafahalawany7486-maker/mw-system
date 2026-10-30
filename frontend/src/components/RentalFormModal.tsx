import { useEffect, useState } from "react";
import apiClient from "@/api/client";
import { Modal } from "@/components/ui";
import { Loader2, AlertTriangle } from "lucide-react";
import { RentalContractDetail, TenantListItem, PropertyListItem, PaginatedResponse } from "@/types";
import PropertyHierarchySelector from "@/components/PropertyHierarchySelector";

const emptyForm = {
  tenant_id: "" as number | "",
  property_id: "" as number | "",
  start_date: "",
  end_date: "",
  payment_frequency: "monthly",
  rent_amount: "",
  security_deposit_amount: "0",
  discount_type: "none",
  discount_value: "0",
  discount_reason: "",
  tax_rate: "0",
  late_fee_type: "fixed",
  late_fee_value: "0",
  late_fee_grace_period_days: 5,
};

// Mirrors FREQUENCY_MONTHS in app/services/rental_service.py exactly —
// used only to preview the schedule client-side before saving.
const FREQUENCY_MONTHS: Record<string, number> = { monthly: 1, quarterly: 3, semi_annual: 6, annual: 12 };
const FREQUENCY_LABELS: Record<string, string> = {
  monthly: "per month", quarterly: "per quarter", semi_annual: "per half-year", annual: "per year", one_time: "one-time, full amount",
};

export default function RentalFormModal({
  open, onClose, onSaved,
}: { open: boolean; onClose: () => void; onSaved: (contract: RentalContractDetail) => void }) {
  const [form, setForm] = useState<any>(emptyForm);
  const [tenants, setTenants] = useState<TenantListItem[]>([]);
  const [ownerId, setOwnerId] = useState<number | "">("");
  const [selectedUnit, setSelectedUnit] = useState<PropertyListItem | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    apiClient.get<PaginatedResponse<TenantListItem>>("/tenants", { params: { page_size: 100 } }).then(({ data }) => setTenants(data.items)).catch((err) => console.error(err));
    setForm(emptyForm);
    setOwnerId("");
    setSelectedUnit(null);
    setError(null);
  }, [open]);

  const selectedTenant = tenants.find((t) => t.id === form.tenant_id);

  // Client-side preview only — the real schedule is generated
  // server-side, same reasoning as LeaseFormModal's identical block.
  const scheduleEstimate = (() => {
    if (!form.start_date || !form.end_date || !form.rent_amount || Number(form.rent_amount) <= 0) return null;
    const start = new Date(form.start_date);
    const end = new Date(form.end_date);
    if (isNaN(start.getTime()) || isNaN(end.getTime()) || end <= start) return null;
    let count: number;
    if (form.payment_frequency === "one_time") {
      count = 1;
    } else if (form.payment_frequency === "custom") {
      return null;
    } else {
      const stepMonths = FREQUENCY_MONTHS[form.payment_frequency] || 1;
      const totalMonths = (end.getFullYear() - start.getFullYear()) * 12 + (end.getMonth() - start.getMonth());
      count = Math.max(1, Math.floor(totalMonths / stepMonths) + 1);
    }
    return { count, total: count * Number(form.rent_amount) };
  })();

  const handleSave = async () => {
    if (!selectedUnit) {
      setError("Select a property/unit through Owner → Property → Floor → Apartment first.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const { data } = await apiClient.post<RentalContractDetail>("/rentals", {
        ...form,
        tenant_id: Number(form.tenant_id),
        property_id: selectedUnit.id,
        late_fee_grace_period_days: Number(form.late_fee_grace_period_days),
        discount_reason: form.discount_reason || undefined,
      });
      onSaved(data);
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "Unable to create this rental contract. Please check the form.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Add Rental Contract"
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
          <label className="label">Tenant *</label>
          <select className="input" required value={form.tenant_id} onChange={(e) => setForm({ ...form, tenant_id: e.target.value })}>
            <option value="">Select a tenant…</option>
            {tenants.map((t) => <option key={t.id} value={t.id}>{t.tenant_code} — {t.display_name}</option>)}
          </select>
        </div>

        {selectedTenant?.is_blacklisted && (
          <div className="flex items-center gap-2 text-sm text-rust-600 bg-rust-50 dark:bg-rust-500/10 rounded-md px-3 py-2">
            <AlertTriangle size={15} /> This tenant is blacklisted. You can still proceed, but review their history first.
          </div>
        )}

        <div className="border-t border-ink-100 dark:border-ink-800 pt-4">
          <p className="text-xs font-semibold uppercase text-ink-400 mb-3">Property (Owner → Property → Floor → Apartment)</p>
          <PropertyHierarchySelector
            ownerId={ownerId}
            onOwnerChange={setOwnerId}
            allowWholeFloorChoice
            onUnitSelect={(unit) => {
              setSelectedUnit(unit);
              if (unit?.rent_price && !form.rent_amount) setForm((f: any) => ({ ...f, rent_amount: unit.rent_price }));
            }}
          />
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
        <div>
          <label className="label">Security Deposit</label>
          <input className="input" type="number" min="0" step="0.001" value={form.security_deposit_amount} onChange={(e) => setForm({ ...form, security_deposit_amount: e.target.value })} />
        </div>

        <div className="border-t border-ink-100 dark:border-ink-800 pt-4">
          <p className="text-xs font-semibold uppercase text-ink-400 mb-2">Discount</p>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label">Discount Type</label>
              <select className="input" value={form.discount_type} onChange={(e) => setForm({ ...form, discount_type: e.target.value })}>
                <option value="none">None</option>
                <option value="percentage">Percentage</option>
                <option value="fixed">Fixed Amount</option>
              </select>
            </div>
            {form.discount_type !== "none" && (
              <div>
                <label className="label">Discount Value {form.discount_type === "percentage" ? "(%)" : ""}</label>
                <input className="input" type="number" min="0" max={form.discount_type === "percentage" ? "100" : undefined} step={form.discount_type === "percentage" ? "0.01" : "0.001"} value={form.discount_value} onChange={(e) => setForm({ ...form, discount_value: e.target.value })} />
              </div>
            )}
          </div>
          {form.discount_type !== "none" && (
            <div className="mt-3">
              <label className="label">Discount Reason</label>
              <input className="input" value={form.discount_reason} onChange={(e) => setForm({ ...form, discount_reason: e.target.value })} placeholder="e.g. Loyalty discount" />
            </div>
          )}
        </div>

        <div className="border-t border-ink-100 dark:border-ink-800 pt-4">
          <p className="text-xs font-semibold uppercase text-ink-400 mb-2">Tax</p>
          <div>
            <label className="label">Tax Rate (%)</label>
            <input className="input" type="number" min="0" max="100" step="0.01" value={form.tax_rate} onChange={(e) => setForm({ ...form, tax_rate: e.target.value })} />
          </div>
        </div>

        <div className="border-t border-ink-100 dark:border-ink-800 pt-4">
          <p className="text-xs font-semibold uppercase text-ink-400 mb-2">Late Fees</p>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="label">Type</label>
              <select className="input" value={form.late_fee_type} onChange={(e) => setForm({ ...form, late_fee_type: e.target.value })}>
                <option value="fixed">Fixed</option>
                <option value="percentage">Percentage</option>
              </select>
            </div>
            <div>
              <label className="label">Value</label>
              <input className="input" type="number" min="0" step={form.late_fee_type === "percentage" ? "0.01" : "0.001"} value={form.late_fee_value} onChange={(e) => setForm({ ...form, late_fee_value: e.target.value })} />
            </div>
            <div>
              <label className="label">Grace (days)</label>
              <input className="input" type="number" min="0" value={form.late_fee_grace_period_days} onChange={(e) => setForm({ ...form, late_fee_grace_period_days: e.target.value })} />
            </div>
          </div>
        </div>

        <p className="text-xs text-ink-400">The contract is created as a Draft. Activate it once signed to start tracking payments — this also marks the property as "Leased".</p>
      </div>
    </Modal>
  );
}
