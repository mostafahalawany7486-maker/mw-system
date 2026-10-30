import { useEffect, useState } from "react";
import apiClient from "@/api/client";
import { Modal } from "@/components/ui";
import { Loader2 } from "lucide-react";
import { Invoice, TenantListItem, PaginatedResponse } from "@/types";

export default function InvoiceFormModal({
  open, onClose, onSaved,
}: { open: boolean; onClose: () => void; onSaved: (invoice: Invoice) => void }) {
  const [tenants, setTenants] = useState<TenantListItem[]>([]);
  const [tenantId, setTenantId] = useState<number | "">("");
  const [amount, setAmount] = useState("");
  const [issueDate, setIssueDate] = useState(new Date().toISOString().slice(0, 10));
  const [dueDate, setDueDate] = useState("");
  const [description, setDescription] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    apiClient.get<PaginatedResponse<TenantListItem>>("/tenants", { params: { page_size: 100 } }).then(({ data }) => setTenants(data.items)).catch((err) => console.error(err));
    setTenantId("");
    setAmount("");
    setDueDate("");
    setDescription("");
    setError(null);
  }, [open]);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      const { data } = await apiClient.post<Invoice>("/financial/invoices", {
        tenant_id: Number(tenantId), amount, issue_date: issueDate, due_date: dueDate, description: description || undefined,
      });
      onSaved(data);
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "Unable to create this invoice.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Create Invoice"
      footer={
        <>
          <button className="btn-secondary" onClick={onClose}>Cancel</button>
          <button className="btn-primary" disabled={saving || !tenantId || !amount || !dueDate} onClick={handleSave}>
            {saving && <Loader2 size={14} className="animate-spin" />} Create Invoice
          </button>
        </>
      }
    >
      {error && <div className="mb-3 text-sm text-rust-500 bg-rust-50 dark:bg-rust-500/10 rounded-md px-3 py-2">{error}</div>}
      <div className="space-y-4">
        <div>
          <label className="label">Tenant *</label>
          <select className="input" required value={tenantId} onChange={(e) => setTenantId(Number(e.target.value))}>
            <option value="">Select tenant…</option>
            {tenants.map((t) => <option key={t.id} value={t.id}>{t.tenant_code} — {t.display_name}</option>)}
          </select>
        </div>
        <div>
          <label className="label">Amount *</label>
          <input className="input" type="number" min="0.01" step="0.001" required value={amount} onChange={(e) => setAmount(e.target.value)} />
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label">Issue Date *</label>
            <input className="input" type="date" required value={issueDate} onChange={(e) => setIssueDate(e.target.value)} />
          </div>
          <div>
            <label className="label">Due Date *</label>
            <input className="input" type="date" required value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
          </div>
        </div>
        <div>
          <label className="label">Description</label>
          <textarea className="input" rows={2} value={description} onChange={(e) => setDescription(e.target.value)} />
        </div>
        <p className="text-xs text-ink-400">The invoice starts as a Draft. Send it to the tenant when ready.</p>
      </div>
    </Modal>
  );
}
