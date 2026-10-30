import { useEffect, useState } from "react";
import apiClient from "@/api/client";
import { Modal } from "@/components/ui";
import { Loader2 } from "lucide-react";
import { FinancialAccount, PaginatedResponse } from "@/types";

export default function TransferModal({
  open, onClose, onSaved,
}: { open: boolean; onClose: () => void; onSaved: () => void }) {
  const [accounts, setAccounts] = useState<FinancialAccount[]>([]);
  const [fromAccountId, setFromAccountId] = useState<number | "">("");
  const [toAccountId, setToAccountId] = useState<number | "">("");
  const [amount, setAmount] = useState("");
  const [transactionDate, setTransactionDate] = useState(new Date().toISOString().slice(0, 10));
  const [description, setDescription] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    apiClient.get<PaginatedResponse<FinancialAccount>>("/financial/accounts", { params: { page_size: 100 } }).then(({ data }) => setAccounts(data.items));
    setFromAccountId("");
    setToAccountId("");
    setAmount("");
    setDescription("");
    setError(null);
  }, [open]);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      await apiClient.post("/financial/transfers", {
        from_account_id: Number(fromAccountId), to_account_id: Number(toAccountId),
        amount, transaction_date: transactionDate, description: description || undefined,
      });
      onSaved();
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "Unable to complete this transfer.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Transfer Funds"
      footer={
        <>
          <button className="btn-secondary" onClick={onClose}>Cancel</button>
          <button className="btn-primary" disabled={saving || !fromAccountId || !toAccountId || !amount} onClick={handleSave}>
            {saving && <Loader2 size={14} className="animate-spin" />} Transfer
          </button>
        </>
      }
    >
      {error && <div className="mb-3 text-sm text-rust-500 bg-rust-50 dark:bg-rust-500/10 rounded-md px-3 py-2">{error}</div>}
      <div className="space-y-4">
        <div>
          <label className="label">From Account *</label>
          <select className="input" required value={fromAccountId} onChange={(e) => setFromAccountId(Number(e.target.value))}>
            <option value="">Select source account…</option>
            {accounts.map((a) => <option key={a.id} value={a.id}>{a.account_code} — {a.name} ({Number(a.current_balance).toLocaleString()})</option>)}
          </select>
        </div>
        <div>
          <label className="label">To Account *</label>
          <select className="input" required value={toAccountId} onChange={(e) => setToAccountId(Number(e.target.value))}>
            <option value="">Select destination account…</option>
            {accounts.filter((a) => a.id !== fromAccountId).map((a) => <option key={a.id} value={a.id}>{a.account_code} — {a.name}</option>)}
          </select>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label">Amount *</label>
            <input className="input" type="number" min="0.01" step="0.001" required value={amount} onChange={(e) => setAmount(e.target.value)} />
          </div>
          <div>
            <label className="label">Date *</label>
            <input className="input" type="date" required value={transactionDate} onChange={(e) => setTransactionDate(e.target.value)} />
          </div>
        </div>
        <div>
          <label className="label">Description</label>
          <input className="input" value={description} onChange={(e) => setDescription(e.target.value)} />
        </div>
      </div>
    </Modal>
  );
}
