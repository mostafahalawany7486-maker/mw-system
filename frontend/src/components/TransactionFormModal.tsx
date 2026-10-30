import { useEffect, useState } from "react";
import apiClient from "@/api/client";
import { Modal } from "@/components/ui";
import { Loader2, AlertTriangle } from "lucide-react";
import { FinancialTransaction, FinancialAccount, TenantListItem, OwnerListItem, PropertyListItem, PaginatedResponse } from "@/types";
import PropertyHierarchySelector from "@/components/PropertyHierarchySelector";

const TYPE_OPTIONS = [
  { value: "tenant_payment", label: "Tenant Payment (rent received)" },
  { value: "owner_payment", label: "Owner Payment (rent paid out)" },
  { value: "expense", label: "Expense" },
  { value: "income", label: "Other Income" },
  { value: "deposit_received", label: "Deposit Received" },
  { value: "deposit_refund", label: "Deposit Refund" },
  { value: "refund", label: "Refund" },
];

// Preset categories for genuine company operating expenses/income. The
// backend's `category` field is free text (no server-side enum), so
// these are a frontend convenience for consistent reporting — "Other"
// still allows any custom value, exactly like before this change.
// Kept aligned with the Owner Ledger recoverable-expense category list
// (see OwnerDetailPage.tsx's EXPENSE_CATEGORIES) so "electricity"/"water"
// mean the same thing in both places.
const EXPENSE_CATEGORIES = ["electricity", "water", "maintenance", "municipality_fees", "government_fees", "insurance", "cleaning", "security", "salaries", "office_rent", "petty_cash", "other"];
const INCOME_CATEGORIES = ["late_fee_income", "parking_income", "other_income", "other"];

const NEEDS_TENANT = new Set(["tenant_payment", "deposit_received", "deposit_refund", "refund"]);
const NEEDS_OWNER = new Set(["owner_payment"]);

// Mirrors CollectRentPage.tsx's fix for the exact same risk — see its
// module comment. tenant_payment routes through the protected
// confirm-payment endpoint when a specific installment is picked;
// owner_payment routes through either a specific Master Lease
// installment's settle endpoint, or the general Owner Ledger balance
// payment endpoint, both already used elsewhere and both already
// refuse an already-settled entry.
interface PendingItem { id: number; label: string; amount: string; overdue: boolean; }

const emptyForm = {
  transaction_type: "expense",
  amount: "",
  account_id: "" as number | "",
  tenant_id: "" as number | "",
  owner_id: "" as number | "",
  category: "",
  payment_method: "",
  reference_number: "",
  transaction_date: new Date().toISOString().slice(0, 10),
  description: "",
};

export default function TransactionFormModal({
  open, onClose, onSaved,
}: { open: boolean; onClose: () => void; onSaved: (txn: FinancialTransaction) => void }) {
  const [form, setForm] = useState<any>(emptyForm);
  const [accounts, setAccounts] = useState<FinancialAccount[]>([]);
  const [tenants, setTenants] = useState<TenantListItem[]>([]);
  const [owners, setOwners] = useState<OwnerListItem[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [customCategory, setCustomCategory] = useState(false);
  const [linkProperty, setLinkProperty] = useState(false);
  const [propertyOwnerId, setPropertyOwnerId] = useState<number | "">("");
  const [selectedUnit, setSelectedUnit] = useState<PropertyListItem | null>(null);

  // Pending-installment picker for tenant_payment / owner_payment —
  // see the module comment above.
  const [pendingItems, setPendingItems] = useState<PendingItem[]>([]);
  const [loadingPending, setLoadingPending] = useState(false);
  const [selectedItemId, setSelectedItemId] = useState<number | "" | "other" | "ledger_balance">("");
  const [ownerLeaseId, setOwnerLeaseId] = useState<number | "">("");
  const [ownerBalance, setOwnerBalance] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    apiClient.get<PaginatedResponse<FinancialAccount>>("/financial/accounts", { params: { page_size: 100 } }).then(({ data }) => setAccounts(data.items)).catch((err) => console.error(err));
    apiClient.get<PaginatedResponse<TenantListItem>>("/tenants", { params: { page_size: 100 } }).then(({ data }) => setTenants(data.items)).catch((err) => console.error(err));
    apiClient.get<PaginatedResponse<OwnerListItem>>("/owners", { params: { page_size: 100 } }).then(({ data }) => setOwners(data.items)).catch((err) => console.error(err));
    setForm(emptyForm);
    setCustomCategory(false);
    setLinkProperty(false);
    setPropertyOwnerId("");
    setSelectedUnit(null);
    setPendingItems([]); setSelectedItemId(""); setOwnerLeaseId(""); setOwnerBalance(null);
    setError(null);
  }, [open]);

  const handleClose = () => {
    setForm(emptyForm);
    setCustomCategory(false);
    setLinkProperty(false);
    setPropertyOwnerId("");
    setSelectedUnit(null);
    setPendingItems([]); setSelectedItemId(""); setOwnerLeaseId(""); setOwnerBalance(null);
    setError(null);
    onClose();
  };

  // Reset the picker whenever type/party changes, then (re)fetch.
  useEffect(() => {
    setPendingItems([]); setSelectedItemId(""); setOwnerLeaseId(""); setOwnerBalance(null);

    if (form.transaction_type === "tenant_payment" && form.tenant_id) {
      setLoadingPending(true);
      apiClient.get<PaginatedResponse<{ id: number }>>("/rentals", { params: { tenant_id: form.tenant_id, contract_status: "active", page_size: 1 } })
        .then(async ({ data }) => {
          const contract = data.items[0];
          if (!contract) return;
          const { data: detail } = await apiClient.get<{ installments: any[] }>(`/rentals/${contract.id}`);
          const items: PendingItem[] = (detail.installments || [])
            .filter((i) => i.payment_status === "pending" || i.payment_status === "overdue")
            .map((i) => ({ id: i.id, label: `Installment #${i.installment_number} · due ${i.due_date}`, amount: i.total_payable, overdue: i.payment_status === "overdue" }));
          setPendingItems(items);
        })
        .catch(() => setPendingItems([]))
        .finally(() => setLoadingPending(false));
    }

    if (form.transaction_type === "owner_payment" && form.owner_id) {
      setLoadingPending(true);
      Promise.all([
        apiClient.get<PaginatedResponse<{ id: number }>>("/leases", { params: { owner_id: form.owner_id, contract_status: "active", page_size: 1 } })
          .then(async ({ data }) => {
            const lease = data.items[0];
            if (!lease) return [];
            setOwnerLeaseId(lease.id);
            const { data: detail } = await apiClient.get<{ installments: any[] }>(`/leases/${lease.id}`);
            return (detail.installments || [])
              .filter((i) => i.payment_status === "pending" || i.payment_status === "overdue")
              .map((i) => ({ id: i.id, label: `Master Lease installment #${i.installment_number} · due ${i.due_date}`, amount: i.amount, overdue: i.payment_status === "overdue" }));
          }),
        apiClient.get<{ current_balance: string }>(`/owner-ledger/${form.owner_id}/dashboard`).then(({ data }) => data.current_balance).catch(() => null),
      ])
        .then(([items, balance]) => { setPendingItems(items as PendingItem[]); setOwnerBalance(balance); })
        .catch(() => setPendingItems([]))
        .finally(() => setLoadingPending(false));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [form.transaction_type, form.tenant_id, form.owner_id]);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      let data: FinancialTransaction;

      const usingSafePath = (form.transaction_type === "tenant_payment" || form.transaction_type === "owner_payment")
        && selectedItemId && selectedItemId !== "other";

      if (usingSafePath && form.transaction_type === "tenant_payment") {
        const { data: confirmed } = await apiClient.post(`/rentals/installments/${selectedItemId}/confirm-payment`, {
          account_id: Number(form.account_id), payment_method: form.payment_method || undefined,
          reference_number: form.reference_number || undefined, transaction_date: form.transaction_date,
        });
        const { data: txn } = await apiClient.get<FinancialTransaction>(`/financial/transactions/${confirmed.transaction_id}`);
        data = txn;
      } else if (usingSafePath && selectedItemId === "ledger_balance") {
        const { data: result } = await apiClient.post(`/owner-ledger/${form.owner_id}/pay`, {
          account_id: Number(form.account_id), amount: form.amount, payment_method: form.payment_method || undefined,
          transaction_date: form.transaction_date, reference_number: form.reference_number || undefined,
        });
        if (result.receipt_id) window.open(`/receipts/${result.receipt_id}/print`, "_blank", "noopener,noreferrer");
        const { data: txn } = await apiClient.get<FinancialTransaction>(`/financial/transactions/${result.transaction_id}`);
        data = txn;
      } else if (usingSafePath && form.transaction_type === "owner_payment") {
        const { data: result } = await apiClient.post(`/leases/${ownerLeaseId}/installments/${selectedItemId}/settle`, {
          account_id: Number(form.account_id), transaction_date: form.transaction_date,
          payment_method: form.payment_method || undefined, reference_number: form.reference_number || undefined,
        });
        if (result.receipt_id) window.open(`/receipts/${result.receipt_id}/print`, "_blank", "noopener,noreferrer");
        // settle doesn't return transaction_id directly (ledger_entry_id
        // only) — the receipt link above is the confirmation; refresh
        // the transactions list instead of resolving one exact row.
        data = { id: 0 } as FinancialTransaction;
      } else {
        const payload: any = {
          ...form,
          account_id: Number(form.account_id),
          tenant_id: form.tenant_id ? Number(form.tenant_id) : undefined,
          owner_id: form.owner_id ? Number(form.owner_id) : undefined,
          property_id: linkProperty && selectedUnit ? selectedUnit.id : undefined,
          category: form.category || undefined,
          payment_method: form.payment_method || undefined,
          reference_number: form.reference_number || undefined,
          description: form.description || undefined,
        };
        const { data: txn } = await apiClient.post<FinancialTransaction>("/financial/transactions", payload);
        data = txn;
      }

      setForm(emptyForm);
      onSaved(data);
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "Unable to record this transaction.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={handleClose}
      title="Record Transaction"
      footer={
        <>
          <button className="btn-secondary" onClick={handleClose}>Cancel</button>
          <button className="btn-primary" disabled={saving || ((form.transaction_type === "tenant_payment" || form.transaction_type === "owner_payment") && !!(form.tenant_id || form.owner_id) && !selectedItemId)} onClick={handleSave}>
            {saving && <Loader2 size={14} className="animate-spin" />} Save
          </button>
        </>
      }
    >
      {error && <div className="mb-3 text-sm text-rust-500 bg-rust-50 dark:bg-rust-500/10 rounded-md px-3 py-2">{error}</div>}
      <div className="space-y-4">
        <div>
          <label className="label">Transaction Type *</label>
          <select className="input" value={form.transaction_type} onChange={(e) => setForm({ ...form, transaction_type: e.target.value })}>
            {TYPE_OPTIONS.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
          </select>
        </div>

        {(form.transaction_type === "tenant_payment" || form.transaction_type === "owner_payment") && (
          <div className="flex items-start gap-2 text-xs bg-sky-50 dark:bg-sky-500/10 text-sky-700 dark:text-sky-400 rounded-md px-3 py-2">
            <AlertTriangle size={14} className="shrink-0 mt-0.5" />
            <span>
              Once you pick the {form.transaction_type === "tenant_payment" ? "tenant" : "owner"} below, pick which installment this
              payment is for — already-paid ones won't be listed, and the server refuses picking one twice. Choosing "Something else"
              skips that protection, same as before; only use it for a payment that genuinely isn't a normal scheduled installment.
            </span>
          </div>
        )}

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label">Amount *</label>
            <input className="input" type="number" min="0.01" step="0.001" required value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })}
              disabled={!!selectedItemId && selectedItemId !== "other"} />
          </div>
          <div>
            <label className="label">Account *</label>
            <select className="input" required value={form.account_id} onChange={(e) => setForm({ ...form, account_id: e.target.value })}>
              <option value="">Select account…</option>
              {accounts.map((a) => <option key={a.id} value={a.id}>{a.account_code} — {a.name} ({a.account_type})</option>)}
            </select>
          </div>
        </div>

        {NEEDS_TENANT.has(form.transaction_type) && (
          <div>
            <label className="label">Tenant *</label>
            <select className="input" required value={form.tenant_id} onChange={(e) => setForm({ ...form, tenant_id: e.target.value })}>
              <option value="">Select tenant…</option>
              {tenants.map((t) => <option key={t.id} value={t.id}>{t.tenant_code} — {t.display_name}</option>)}
            </select>
          </div>
        )}
        {NEEDS_OWNER.has(form.transaction_type) && (
          <div>
            <label className="label">Owner *</label>
            <select className="input" required value={form.owner_id} onChange={(e) => setForm({ ...form, owner_id: e.target.value })}>
              <option value="">Select owner…</option>
              {owners.map((o) => <option key={o.id} value={o.id}>{o.owner_code} — {o.display_name}</option>)}
            </select>
          </div>
        )}

        {(form.transaction_type === "tenant_payment" && form.tenant_id) || (form.transaction_type === "owner_payment" && form.owner_id) ? (
          <div>
            <label className="label">Which installment is this for? *</label>
            {loadingPending && <div className="text-xs text-ink-400 flex items-center gap-1"><Loader2 size={12} className="animate-spin" /> Checking the payment schedule…</div>}
            {!loadingPending && (
              <div className="space-y-2">
                {pendingItems.length > 0 && (
                  <div className="border border-ink-100 dark:border-ink-800 rounded-lg divide-y divide-ink-100 dark:divide-ink-800 max-h-44 overflow-y-auto">
                    {pendingItems.map((item) => (
                      <label key={item.id} className="flex items-center justify-between px-3 py-2 text-sm cursor-pointer hover:bg-ink-50 dark:hover:bg-ink-800/50">
                        <span className="flex items-center gap-2">
                          <input type="radio" name="pending_item" checked={selectedItemId === item.id}
                            onChange={() => { setSelectedItemId(item.id); setForm({ ...form, amount: item.amount }); }} />
                          <span>{item.label}{item.overdue && <span className="text-rust-500 text-xs font-medium ml-1">overdue</span>}</span>
                        </span>
                        <span className="font-medium">{Number(item.amount).toLocaleString()}</span>
                      </label>
                    ))}
                  </div>
                )}
                {form.transaction_type === "owner_payment" && ownerBalance && Number(ownerBalance) > 0 && (
                  <label className="flex items-center gap-2 text-xs cursor-pointer">
                    <input type="radio" name="pending_item" checked={selectedItemId === "ledger_balance"}
                      onChange={() => { setSelectedItemId("ledger_balance"); setForm({ ...form, amount: ownerBalance }); }} />
                    Pay down the general Owner Ledger balance ({Number(ownerBalance).toLocaleString()}) — not tied to a specific Master Lease installment
                  </label>
                )}
                <label className="flex items-center gap-2 text-xs text-ink-500 cursor-pointer">
                  <input type="radio" name="pending_item" checked={selectedItemId === "other"}
                    onChange={() => { setSelectedItemId("other"); setForm({ ...form, amount: "" }); }} />
                  {pendingItems.length > 0 || ownerBalance ? "Something else (not one of the above — won't be linked to a schedule)" : "No schedule found — enter an amount manually"}
                </label>
              </div>
            )}
          </div>
        ) : null}

        <label className="flex items-center gap-2 text-sm text-ink-600 dark:text-ink-300">
          <input type="checkbox" checked={linkProperty} onChange={(e) => { setLinkProperty(e.target.checked); if (!e.target.checked) { setPropertyOwnerId(""); setSelectedUnit(null); } }} />
          Link to a specific property/unit (optional — leave off for general company expenses)
        </label>
        {linkProperty && (
          <div className="border border-ink-100 dark:border-ink-800 rounded-lg p-3">
            <PropertyHierarchySelector ownerId={propertyOwnerId} onOwnerChange={setPropertyOwnerId} onUnitSelect={setSelectedUnit} allowWholeBuildingChoice />
          </div>
        )}

        {(form.transaction_type === "expense" || form.transaction_type === "income") && (
          <div>
            <label className="label">Category</label>
            {!customCategory ? (
              <select
                className="input"
                value={form.category}
                onChange={(e) => {
                  if (e.target.value === "other") {
                    setCustomCategory(true);
                    setForm({ ...form, category: "" });
                  } else {
                    setForm({ ...form, category: e.target.value });
                  }
                }}
              >
                <option value="">Select category…</option>
                {(form.transaction_type === "expense" ? EXPENSE_CATEGORIES : INCOME_CATEGORIES).map((c) => (
                  <option key={c} value={c}>{c.replace(/_/g, " ")}</option>
                ))}
              </select>
            ) : (
              <div className="flex gap-2">
                <input
                  className="input"
                  autoFocus
                  placeholder="Enter a custom category"
                  value={form.category}
                  onChange={(e) => setForm({ ...form, category: e.target.value })}
                />
                <button type="button" className="btn-secondary shrink-0" onClick={() => { setCustomCategory(false); setForm({ ...form, category: "" }); }}>
                  Use list
                </button>
              </div>
            )}
          </div>
        )}

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label">Payment Method</label>
            <select className="input" value={form.payment_method} onChange={(e) => setForm({ ...form, payment_method: e.target.value })}>
              <option value="">—</option>
              <option value="cash">Cash</option>
              <option value="bank_transfer">Bank Transfer</option>
              <option value="cheque">Cheque</option>
              <option value="card">Card</option>
              <option value="knet">K-Net</option>
              <option value="online">Online</option>
            </select>
          </div>
          <div>
            <label className="label">Transaction Date *</label>
            <input className="input" type="date" required value={form.transaction_date} onChange={(e) => setForm({ ...form, transaction_date: e.target.value })} />
          </div>
        </div>
        <div>
          <label className="label">Reference Number</label>
          <input className="input" value={form.reference_number} onChange={(e) => setForm({ ...form, reference_number: e.target.value })} />
        </div>
        <div>
          <label className="label">Description</label>
          <textarea className="input" rows={2} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
        </div>
        {(form.transaction_type === "tenant_payment" || form.transaction_type === "owner_payment") && (
          <p className="text-xs text-ink-400">A receipt will be issued automatically for this transaction.</p>
        )}
      </div>
    </Modal>
  );
}
