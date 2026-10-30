import { useState } from "react";
import apiClient from "@/api/client";
import { Modal } from "@/components/ui";
import { Loader2 } from "lucide-react";
import { FinancialAccount } from "@/types";

const emptyForm = {
  account_type: "cash" as "cash" | "bank",
  name: "",
  bank_name: "",
  account_number: "",
  iban: "",
  opening_balance: "0",
  is_default: false,
};

export default function AccountFormModal({
  open, onClose, onSaved,
}: { open: boolean; onClose: () => void; onSaved: (account: FinancialAccount) => void }) {
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
      const payload: any = { ...form };
      if (form.account_type === "cash") {
        delete payload.bank_name;
        delete payload.account_number;
        delete payload.iban;
      }
      const { data } = await apiClient.post<FinancialAccount>("/financial/accounts", payload);
      setForm(emptyForm);
      onSaved(data);
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "Unable to create this account.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={handleClose}
      title="Add Account"
      footer={
        <>
          <button className="btn-secondary" onClick={handleClose}>Cancel</button>
          <button className="btn-primary" disabled={saving} onClick={handleSave}>
            {saving && <Loader2 size={14} className="animate-spin" />} Create Account
          </button>
        </>
      }
    >
      {error && <div className="mb-3 text-sm text-rust-500 bg-rust-50 dark:bg-rust-500/10 rounded-md px-3 py-2">{error}</div>}
      <div className="space-y-4">
        <div>
          <label className="label">Account Type *</label>
          <div className="flex gap-2">
            <button type="button" className={form.account_type === "cash" ? "btn-primary flex-1" : "btn-secondary flex-1"} onClick={() => setForm({ ...form, account_type: "cash" })}>Cash</button>
            <button type="button" className={form.account_type === "bank" ? "btn-primary flex-1" : "btn-secondary flex-1"} onClick={() => setForm({ ...form, account_type: "bank" })}>Bank</button>
          </div>
        </div>
        <div>
          <label className="label">Account Name *</label>
          <input className="input" required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="e.g. Petty Cash, Main Operating Account" />
        </div>
        {form.account_type === "bank" && (
          <>
            <div>
              <label className="label">Bank Name *</label>
              <input className="input" required value={form.bank_name} onChange={(e) => setForm({ ...form, bank_name: e.target.value })} />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="label">Account Number</label>
                <input className="input" value={form.account_number} onChange={(e) => setForm({ ...form, account_number: e.target.value })} />
              </div>
              <div>
                <label className="label">IBAN</label>
                <input className="input" value={form.iban} onChange={(e) => setForm({ ...form, iban: e.target.value })} />
              </div>
            </div>
          </>
        )}
        <div>
          <label className="label">Opening Balance</label>
          <input className="input" type="number" step="0.001" value={form.opening_balance} onChange={(e) => setForm({ ...form, opening_balance: e.target.value })} />
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={form.is_default} onChange={(e) => setForm({ ...form, is_default: e.target.checked })} />
          Set as default account
        </label>
      </div>
    </Modal>
  );
}
