import { useEffect, useState } from "react";
import apiClient from "@/api/client";
import { Modal } from "@/components/ui";
import { Loader2 } from "lucide-react";
import { ChartOfAccountItem } from "@/types";

const emptyForm = {
  account_code: "", account_name: "", account_type: "asset",
  parent_account_id: "", allow_posting: true, description: "",
};

export default function ChartOfAccountFormModal({
  open, onClose, onSaved,
}: { open: boolean; onClose: () => void; onSaved: (account: ChartOfAccountItem) => void }) {
  const [form, setForm] = useState<any>(emptyForm);
  const [accounts, setAccounts] = useState<ChartOfAccountItem[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    apiClient.get<ChartOfAccountItem[]>("/accounting/chart-of-accounts").then(({ data }) => setAccounts(data));
    setForm(emptyForm);
    setError(null);
  }, [open]);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      const payload: any = { ...form };
      if (payload.parent_account_id) payload.parent_account_id = Number(payload.parent_account_id); else delete payload.parent_account_id;
      const { data } = await apiClient.post<ChartOfAccountItem>("/accounting/chart-of-accounts", payload);
      onSaved(data);
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "Unable to create this account.");
    } finally {
      setSaving(false);
    }
  };

  const eligibleParents = accounts.filter((a) => a.account_type === form.account_type);

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Add GL Account"
      footer={
        <>
          <button className="btn-secondary" onClick={onClose}>Cancel</button>
          <button className="btn-primary" disabled={saving || !form.account_code || !form.account_name} onClick={handleSave}>
            {saving && <Loader2 size={14} className="animate-spin" />} Create Account
          </button>
        </>
      }
    >
      {error && <div className="mb-3 text-sm text-rust-500 bg-rust-50 dark:bg-rust-500/10 rounded-md px-3 py-2">{error}</div>}
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label">Account Code *</label>
            <input className="input" required value={form.account_code} onChange={(e) => setForm({ ...form, account_code: e.target.value })} placeholder="e.g. 1130" />
          </div>
          <div>
            <label className="label">Account Type *</label>
            <select className="input" value={form.account_type} onChange={(e) => setForm({ ...form, account_type: e.target.value, parent_account_id: "" })}>
              <option value="asset">Asset</option>
              <option value="liability">Liability</option>
              <option value="equity">Equity</option>
              <option value="revenue">Revenue</option>
              <option value="expense">Expense</option>
            </select>
          </div>
        </div>
        <div>
          <label className="label">Account Name *</label>
          <input className="input" required value={form.account_name} onChange={(e) => setForm({ ...form, account_name: e.target.value })} />
        </div>
        <div>
          <label className="label">Parent Account</label>
          <select className="input" value={form.parent_account_id} onChange={(e) => setForm({ ...form, parent_account_id: e.target.value })}>
            <option value="">None (top-level)</option>
            {eligibleParents.map((a) => <option key={a.id} value={a.id}>{a.account_code} — {a.account_name}</option>)}
          </select>
          <p className="text-xs text-ink-400 mt-1">A child account must share the same account type as its parent.</p>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={form.allow_posting} onChange={(e) => setForm({ ...form, allow_posting: e.target.checked })} />
          Allow direct posting (uncheck for header/summary accounts)
        </label>
        <div>
          <label className="label">Description</label>
          <textarea className="input" rows={2} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
        </div>
      </div>
    </Modal>
  );
}
