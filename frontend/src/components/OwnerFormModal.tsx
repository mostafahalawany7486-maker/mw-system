import { useState } from "react";
import apiClient from "@/api/client";
import { Modal } from "@/components/ui";
import { Loader2 } from "lucide-react";
import { OwnerDetail } from "@/types";

const emptyForm = {
  owner_type: "individual" as "individual" | "company",
  first_name: "", last_name: "",
  company_name: "",
  primary_email: "", primary_phone: "",
};

export default function OwnerFormModal({
  open, onClose, onSaved,
}: { open: boolean; onClose: () => void; onSaved: (owner: OwnerDetail) => void }) {
  const [form, setForm] = useState<any>(emptyForm);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleClose = () => {
    setForm(emptyForm);
    setError(null);
    onClose();
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      const payload: any = {
        owner_type: form.owner_type,
        primary_email: form.primary_email || undefined,
        primary_phone: form.primary_phone || undefined,
      };
      if (form.owner_type === "individual") {
        payload.first_name = form.first_name;
        payload.last_name = form.last_name;
      } else {
        payload.company_name = form.company_name;
      }
      const { data } = await apiClient.post<OwnerDetail>("/owners", payload);
      setForm(emptyForm);
      onSaved(data);
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "Unable to create this owner. Please check the form.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={handleClose}
      title="Add Property Owner"
      footer={
        <>
          <button className="btn-secondary" onClick={handleClose}>Cancel</button>
          <button className="btn-primary" disabled={saving} onClick={handleSave}>
            {saving && <Loader2 size={14} className="animate-spin" />} Create Owner
          </button>
        </>
      }
    >
      {error && <div className="mb-3 text-sm text-rust-500 bg-rust-50 dark:bg-rust-500/10 rounded-md px-3 py-2">{error}</div>}
      <div className="space-y-4">
        <div>
          <label className="label">Owner Type *</label>
          <div className="flex gap-2">
            <button
              type="button"
              className={form.owner_type === "individual" ? "btn-primary flex-1" : "btn-secondary flex-1"}
              onClick={() => setForm({ ...form, owner_type: "individual" })}
            >
              Individual
            </button>
            <button
              type="button"
              className={form.owner_type === "company" ? "btn-primary flex-1" : "btn-secondary flex-1"}
              onClick={() => setForm({ ...form, owner_type: "company" })}
            >
              Company
            </button>
          </div>
        </div>

        {form.owner_type === "individual" ? (
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label">First Name *</label>
              <input className="input" required value={form.first_name} onChange={(e) => setForm({ ...form, first_name: e.target.value })} />
            </div>
            <div>
              <label className="label">Last Name *</label>
              <input className="input" required value={form.last_name} onChange={(e) => setForm({ ...form, last_name: e.target.value })} />
            </div>
          </div>
        ) : (
          <div>
            <label className="label">Company Name *</label>
            <input className="input" required value={form.company_name} onChange={(e) => setForm({ ...form, company_name: e.target.value })} />
          </div>
        )}

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label">Email</label>
            <input className="input" type="email" value={form.primary_email} onChange={(e) => setForm({ ...form, primary_email: e.target.value })} />
          </div>
          <div>
            <label className="label">Phone</label>
            <input className="input" value={form.primary_phone} onChange={(e) => setForm({ ...form, primary_phone: e.target.value })} />
          </div>
        </div>
        <p className="text-xs text-ink-400">You can add addresses, bank accounts, contacts, and documents after creating the owner.</p>
      </div>
    </Modal>
  );
}
