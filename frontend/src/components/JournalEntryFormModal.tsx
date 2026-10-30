import { useEffect, useState } from "react";
import apiClient from "@/api/client";
import { Modal } from "@/components/ui";
import { Loader2, Plus, Trash2 } from "lucide-react";
import { ChartOfAccountItem, CostCenterItem, JournalEntryDetail } from "@/types";

interface LineDraft {
  account_id: string;
  cost_center_id: string;
  debit_amount: string;
  credit_amount: string;
  description: string;
}

const emptyLine = (): LineDraft => ({ account_id: "", cost_center_id: "", debit_amount: "", credit_amount: "", description: "" });

export default function JournalEntryFormModal({
  open, onClose, onSaved,
}: { open: boolean; onClose: () => void; onSaved: (entry: JournalEntryDetail) => void }) {
  const [entryDate, setEntryDate] = useState(new Date().toISOString().slice(0, 10));
  const [description, setDescription] = useState("");
  const [referenceNumber, setReferenceNumber] = useState("");
  const [lines, setLines] = useState<LineDraft[]>([emptyLine(), emptyLine()]);
  const [accounts, setAccounts] = useState<ChartOfAccountItem[]>([]);
  const [costCenters, setCostCenters] = useState<CostCenterItem[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    apiClient.get<ChartOfAccountItem[]>("/accounting/chart-of-accounts").then(({ data }) => setAccounts(data.filter((a) => a.allow_posting)));
    apiClient.get<CostCenterItem[]>("/accounting/cost-centers").then(({ data }) => setCostCenters(data));
    setEntryDate(new Date().toISOString().slice(0, 10));
    setDescription("");
    setReferenceNumber("");
    setLines([emptyLine(), emptyLine()]);
    setError(null);
  }, [open]);

  const totalDebit = lines.reduce((sum, l) => sum + (parseFloat(l.debit_amount) || 0), 0);
  const totalCredit = lines.reduce((sum, l) => sum + (parseFloat(l.credit_amount) || 0), 0);
  const isBalanced = lines.length >= 2 && totalDebit > 0 && Math.abs(totalDebit - totalCredit) < 0.005;

  const updateLine = (idx: number, patch: Partial<LineDraft>) => {
    setLines((prev) => prev.map((l, i) => (i === idx ? { ...l, ...patch } : l)));
  };

  const addLine = () => setLines((prev) => [...prev, emptyLine()]);
  const removeLine = (idx: number) => setLines((prev) => prev.filter((_, i) => i !== idx));

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      const payload = {
        entry_date: entryDate,
        description: description || undefined,
        reference_number: referenceNumber || undefined,
        lines: lines
          .filter((l) => l.account_id && (l.debit_amount || l.credit_amount))
          .map((l) => ({
            account_id: Number(l.account_id),
            cost_center_id: l.cost_center_id ? Number(l.cost_center_id) : undefined,
            debit_amount: l.debit_amount || "0",
            credit_amount: l.credit_amount || "0",
            description: l.description || undefined,
          })),
      };
      const { data } = await apiClient.post<JournalEntryDetail>("/accounting/journal-entries", payload);
      onSaved(data);
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "Unable to create this journal entry. Please check the lines.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="New Journal Entry"
      footer={
        <>
          <button className="btn-secondary" onClick={onClose}>Cancel</button>
          <button className="btn-primary" disabled={saving || !isBalanced} onClick={handleSave}>
            {saving && <Loader2 size={14} className="animate-spin" />} Save as Draft
          </button>
        </>
      }
    >
      {error && <div className="mb-3 text-sm text-rust-500 bg-rust-50 dark:bg-rust-500/10 rounded-md px-3 py-2">{error}</div>}
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label">Entry Date *</label>
            <input className="input" type="date" required value={entryDate} onChange={(e) => setEntryDate(e.target.value)} />
          </div>
          <div>
            <label className="label">Reference Number</label>
            <input className="input" value={referenceNumber} onChange={(e) => setReferenceNumber(e.target.value)} />
          </div>
        </div>
        <div>
          <label className="label">Description</label>
          <input className="input" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="e.g. Monthly accrual adjustment" />
        </div>

        <div className="border-t border-ink-100 dark:border-ink-800 pt-4">
          <div className="flex justify-between items-center mb-2">
            <p className="text-xs font-semibold uppercase text-ink-400">Lines</p>
            <button type="button" className="btn-secondary !px-2 !py-1" onClick={addLine}><Plus size={13} /> Add Line</button>
          </div>
          <div className="space-y-2">
            {lines.map((line, idx) => (
              <div key={idx} className="grid grid-cols-12 gap-2 items-start">
                <select className="input col-span-4" value={line.account_id} onChange={(e) => updateLine(idx, { account_id: e.target.value })}>
                  <option value="">Account…</option>
                  {accounts.map((a) => <option key={a.id} value={a.id}>{a.account_code} — {a.account_name}</option>)}
                </select>
                <select className="input col-span-2" value={line.cost_center_id} onChange={(e) => updateLine(idx, { cost_center_id: e.target.value })}>
                  <option value="">Cost Center</option>
                  {costCenters.map((c) => <option key={c.id} value={c.id}>{c.cost_center_code}</option>)}
                </select>
                <input className="input col-span-2" type="number" step="0.001" placeholder="Debit" value={line.debit_amount} onChange={(e) => updateLine(idx, { debit_amount: e.target.value, credit_amount: "" })} />
                <input className="input col-span-2" type="number" step="0.001" placeholder="Credit" value={line.credit_amount} onChange={(e) => updateLine(idx, { credit_amount: e.target.value, debit_amount: "" })} />
                <input className="input col-span-1" placeholder="Memo" value={line.description} onChange={(e) => updateLine(idx, { description: e.target.value })} />
                <button type="button" className="btn-secondary col-span-1 !px-2" onClick={() => removeLine(idx)} disabled={lines.length <= 2}><Trash2 size={13} /></button>
              </div>
            ))}
          </div>
        </div>

        <div className={`flex justify-between items-center rounded-md px-3 py-2 text-sm ${isBalanced ? "bg-brand-50 dark:bg-brand-500/10 text-brand-600" : "bg-rust-50 dark:bg-rust-500/10 text-rust-500"}`}>
          <span>Debit: {totalDebit.toFixed(3)} · Credit: {totalCredit.toFixed(3)}</span>
          <span className="font-medium">{isBalanced ? "Balanced ✓" : "Not balanced"}</span>
        </div>
      </div>
    </Modal>
  );
}
