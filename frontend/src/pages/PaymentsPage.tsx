import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import apiClient from "@/api/client";
import { useAuth } from "@/context/AuthContext";
import { PageHeader, Pagination, EmptyState, Modal, FormField, ToolbarSearch } from "@/components/ui";
import { Loader2, Plus, CheckCircle2, Ban, Undo2, RotateCcw, Wallet, TrendingUp, AlertTriangle, Zap } from "lucide-react";
import { Payment, PaymentAllocation, CollectionDashboard, TenantListItem, Invoice, FinancialAccount, PaginatedResponse } from "@/types";

const PAYMENT_METHODS = ["cash", "knet", "bank_transfer", "cheque", "online", "mixed"];
const STATUS_TONE: Record<string, string> = {
  pending: "badge-warn", verified: "badge-active", partially_paid: "badge-warn", paid: "badge-active",
  cancelled: "badge-inactive", refunded: "badge-inactive", reversed: "badge-inactive",
};

function money(v: string | number) {
  return Number(v).toLocaleString(undefined, { minimumFractionDigits: 3 });
}

export default function PaymentsPage() {
  const { hasPermission } = useAuth();
  const navigate = useNavigate();
  const canCreate = hasPermission("payments.create");
  const canEdit = hasPermission("payments.edit");

  const [dashboard, setDashboard] = useState<CollectionDashboard | null>(null);
  const [data, setData] = useState<PaginatedResponse<Payment> | null>(null);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState("");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [detailTarget, setDetailTarget] = useState<Payment | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    Promise.all([
      apiClient.get<CollectionDashboard>("/payments/dashboard/summary"),
      apiClient.get<PaginatedResponse<Payment>>("/payments", { params: { page, page_size: 20, payment_status: statusFilter || undefined, search: search || undefined } }),
    ]).then(([d, p]) => { setDashboard(d.data); setData(p.data); }).finally(() => setLoading(false));
  }, [page, statusFilter, search]);

  useEffect(() => { load(); }, [load]);

  return (
    <div>
      <PageHeader
        title="Payments"
        description="Capture, verify, refund, and reverse tenant rent payments — every payment can cover one or more invoices."
        action={canCreate && (
          <div className="flex gap-2">
            <button className="btn-secondary" onClick={() => navigate("/payments/collect-rent")}>
              <Zap size={16} /> Collect Rent &amp; Print Voucher
            </button>
            <button className="btn-primary" onClick={() => setCreateOpen(true)}>
              <Plus size={16} /> Record Payment
            </button>
          </div>
        )}
      />

      <div className="flex items-start gap-2 text-sm bg-amber-50 dark:bg-amber-500/10 text-amber-700 dark:text-amber-400 rounded-lg px-4 py-3 mb-4">
        <AlertTriangle size={16} className="shrink-0 mt-0.5" />
        <span>
          This list shows the older Invoice-based payment system — real rent payments collected through{" "}
          <button className="underline font-medium" onClick={() => navigate("/payments/collect-rent")}>Collect Rent &amp; Print Voucher</button>{" "}
          won't appear here. To see every actual payment, check <button className="underline font-medium" onClick={() => navigate("/financial")}>Financial → Transactions</button> instead — that's the single source of truth for what's really been collected.
        </span>
      </div>

      {dashboard && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-4">
          <SummaryCard icon={TrendingUp} label="Collected Today" value={money(dashboard.collected_today)} />
          <SummaryCard icon={TrendingUp} label="Collected This Month" value={money(dashboard.collected_this_month)} />
          <SummaryCard icon={Wallet} label="Total Outstanding" value={money(dashboard.total_outstanding)} />
          <SummaryCard icon={AlertTriangle} label="Overdue" value={money(dashboard.overdue_amount)} tone="text-rust-500" />
          <SummaryCard icon={CheckCircle2} label="Collection Rate" value={`${money(dashboard.collection_percentage)}%`} />
        </div>
      )}

      <div className="card">
        <div className="p-4 border-b border-ink-100 dark:border-ink-800 flex flex-wrap gap-3 items-center">
          <ToolbarSearch value={search} onChange={(v) => { setSearch(v); setPage(1); }} placeholder="Search by payment number, reference…" />
          <select className="input max-w-[180px]" value={statusFilter} onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}>
            <option value="">All statuses</option>
            {Object.keys(STATUS_TONE).map((s) => <option key={s} value={s}>{s.replace(/_/g, " ")}</option>)}
          </select>
        </div>

        {loading && <div className="flex justify-center py-10"><Loader2 className="animate-spin text-ink-400" /></div>}

        {!loading && data && data.items.length === 0 && (
          <EmptyState icon={Wallet} title="No payments yet" description="Use Record Payment to capture a tenant's rent payment against one or more invoices." />
        )}

        {!loading && data && data.items.length > 0 && (
          <div className="overflow-x-auto">
            <table className="table-shell">
              <thead>
                <tr><th>Payment #</th><th>Tenant</th><th>Amount</th><th>Method</th><th>Date</th><th>Status</th><th>Actions</th></tr>
              </thead>
              <tbody>
                {data.items.map((p) => (
                  <tr key={p.id} className="cursor-pointer" onClick={() => setDetailTarget(p)}>
                    <td className="font-mono text-xs">{p.payment_number}</td>
                    <td className="font-medium">{p.tenant_name || `#${p.tenant_id}`}</td>
                    <td>{money(p.amount)}</td>
                    <td className="capitalize">{p.payment_method.replace(/_/g, " ")}</td>
                    <td className="text-ink-500">{p.payment_date}</td>
                    <td><span className={STATUS_TONE[p.payment_status] || "badge-inactive"}>{p.payment_status.replace(/_/g, " ")}</span></td>
                    <td onClick={(e) => e.stopPropagation()}>
                      <PaymentRowActions payment={p} canEdit={canEdit} onChanged={load} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {data && <Pagination page={page} totalPages={Math.ceil(data.total / 20)} onChange={setPage} />}
      </div>

      {createOpen && <CreatePaymentModal onClose={() => setCreateOpen(false)} onCreated={load} />}
      {detailTarget && <PaymentDetailModal payment={detailTarget} canEdit={canEdit} onClose={() => setDetailTarget(null)} onChanged={() => { load(); setDetailTarget(null); }} />}
    </div>
  );
}

function SummaryCard({ icon: Icon, label, value, tone }: { icon: typeof Wallet; label: string; value: string; tone?: string }) {
  return (
    <div className="card p-4">
      <div className="flex items-center gap-1.5 text-ink-500"><Icon size={14} /><p className="text-xs">{label}</p></div>
      <p className={`text-lg font-display font-bold mt-1 ${tone || ""}`}>{value}</p>
    </div>
  );
}

function PaymentRowActions({ payment, canEdit, onChanged }: { payment: Payment; canEdit: boolean; onChanged: () => void }) {
  const [busy, setBusy] = useState(false);
  const [actionOpen, setActionOpen] = useState<"cancel" | "refund" | "reverse" | null>(null);

  const verify = async () => {
    setBusy(true);
    try {
      await apiClient.post(`/payments/${payment.id}/verify`, {});
      onChanged();
    } finally {
      setBusy(false);
    }
  };

  if (!canEdit) return null;

  return (
    <div className="flex gap-1.5">
      {payment.payment_status === "pending" && (
        <>
          <button className="btn-secondary !px-2 !py-1 text-brand-600" title="Verify — posts to the ledger" onClick={verify} disabled={busy}>
            {busy ? <Loader2 size={13} className="animate-spin" /> : <CheckCircle2 size={13} />}
          </button>
          <button className="btn-secondary !px-2 !py-1 text-rust-500" title="Cancel" onClick={() => setActionOpen("cancel")}>
            <Ban size={13} />
          </button>
        </>
      )}
      {["verified", "partially_paid", "paid"].includes(payment.payment_status) && (
        <>
          <button className="btn-secondary !px-2 !py-1" title="Refund" onClick={() => setActionOpen("refund")}>
            <RotateCcw size={13} />
          </button>
          <button className="btn-secondary !px-2 !py-1 text-rust-500" title="Reverse" onClick={() => setActionOpen("reverse")}>
            <Undo2 size={13} />
          </button>
        </>
      )}
      {actionOpen && <PaymentActionModal payment={payment} action={actionOpen} onClose={() => setActionOpen(null)} onDone={onChanged} />}
    </div>
  );
}

function PaymentActionModal({ payment, action, onClose, onDone }: { payment: Payment; action: "cancel" | "refund" | "reverse"; onClose: () => void; onDone: () => void }) {
  const [reason, setReason] = useState("");
  const [amount, setAmount] = useState(payment.amount);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const titles = { cancel: "Cancel Payment", refund: "Refund Payment", reverse: "Reverse Payment" };
  const endpoints = { cancel: "cancel", refund: "refund", reverse: "reverse" };

  const submit = async () => {
    if (!reason.trim()) { setError("A reason is required."); return; }
    setSubmitting(true);
    setError("");
    try {
      const body: any = { reason };
      if (action === "refund") body.amount = amount;
      await apiClient.post(`/payments/${payment.id}/${endpoints[action]}`, body);
      onDone();
      onClose();
    } catch (err: any) {
      setError(err?.response?.data?.detail || `Could not ${action} this payment.`);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal open onClose={onClose} title={`${titles[action]} — ${payment.payment_number}`} footer={
      <>
        <button className="btn-secondary" onClick={onClose}>Cancel</button>
        <button className="btn-primary" onClick={submit} disabled={submitting}>
          {submitting ? <Loader2 size={16} className="animate-spin" /> : null} Confirm
        </button>
      </>
    }>
      <div className="space-y-3">
        {action === "reverse" && (
          <p className="text-xs text-ink-400 bg-ink-50 dark:bg-ink-800/60 rounded-md p-2">
            Reverses the underlying ledger entry properly (never deletes it) and un-applies the amount from the invoice(s) this payment covered.
          </p>
        )}
        {error && <p className="text-xs text-rust-500">{error}</p>}
        {action === "refund" && (
          <FormField label="Refund Amount" hint={`Full payment amount: ${money(payment.amount)}`}>
            <input className="input" type="number" min="0" step="0.001" max={payment.amount} value={amount} onChange={(e) => setAmount(e.target.value)} />
          </FormField>
        )}
        <FormField label="Reason" required>
          <input className="input" value={reason} onChange={(e) => setReason(e.target.value)} />
        </FormField>
      </div>
    </Modal>
  );
}

function PaymentDetailModal({ payment, canEdit, onClose, onChanged }: { payment: Payment; canEdit: boolean; onClose: () => void; onChanged: () => void }) {
  return (
    <Modal open onClose={onClose} title={`Payment ${payment.payment_number}`} footer={<button className="btn-secondary" onClick={onClose}>Close</button>}>
      <div className="space-y-3 text-sm">
        <div className="grid grid-cols-2 gap-3">
          <div><p className="text-xs text-ink-400">Tenant</p><p className="font-medium">{payment.tenant_name}</p></div>
          <div><p className="text-xs text-ink-400">Status</p><span className={STATUS_TONE[payment.payment_status] || "badge-inactive"}>{payment.payment_status.replace(/_/g, " ")}</span></div>
          <div><p className="text-xs text-ink-400">Amount</p><p className="font-medium">{money(payment.amount)} {payment.currency || ""}</p></div>
          <div><p className="text-xs text-ink-400">Method</p><p className="capitalize">{payment.payment_method.replace(/_/g, " ")}</p></div>
          <div><p className="text-xs text-ink-400">Date</p><p>{payment.payment_date}</p></div>
          <div><p className="text-xs text-ink-400">Reference</p><p>{payment.reference_number || "—"}</p></div>
        </div>
        {payment.property_title && (
          <div><p className="text-xs text-ink-400">Property</p><p>{payment.property_title}{payment.building_name ? ` · ${payment.building_name}` : ""}</p></div>
        )}
        <div>
          <p className="text-xs text-ink-400 mb-1">Invoice Allocations</p>
          <div className="border border-ink-100 dark:border-ink-800 rounded-md divide-y divide-ink-100 dark:divide-ink-800">
            {payment.allocations.map((a: PaymentAllocation) => (
              <div key={a.id} className="flex justify-between px-3 py-2">
                <span className="font-mono text-xs">{a.invoice_number || `#${a.invoice_id}`}</span>
                <span className="font-medium">{money(a.amount)}</span>
              </div>
            ))}
          </div>
        </div>
        {payment.notes && <div><p className="text-xs text-ink-400">Notes</p><p>{payment.notes}</p></div>}
        {payment.cancellation_reason && <div><p className="text-xs text-ink-400">Cancellation Reason</p><p>{payment.cancellation_reason}</p></div>}
        {payment.refund_reason && <div><p className="text-xs text-ink-400">Refund Reason</p><p>{payment.refund_reason}</p></div>}
      </div>
    </Modal>
  );
}

interface AllocationDraft { invoice: Invoice; amount: string; }

function CreatePaymentModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [tenants, setTenants] = useState<TenantListItem[]>([]);
  const [tenantId, setTenantId] = useState<number | "">("");
  const [accounts, setAccounts] = useState<FinancialAccount[]>([]);
  const [accountId, setAccountId] = useState<number | "">("");
  const [paymentMethod, setPaymentMethod] = useState("cash");
  const [paymentDate, setPaymentDate] = useState(new Date().toISOString().slice(0, 10));
  const [referenceNumber, setReferenceNumber] = useState("");
  const [notes, setNotes] = useState("");
  const [outstandingInvoices, setOutstandingInvoices] = useState<Invoice[]>([]);
  const [loadingInvoices, setLoadingInvoices] = useState(false);
  const [allocations, setAllocations] = useState<Record<number, AllocationDraft>>({});
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    apiClient.get<PaginatedResponse<TenantListItem>>("/tenants", { params: { page_size: 100 } }).then(({ data }) => setTenants(data.items));
    apiClient.get<PaginatedResponse<FinancialAccount>>("/financial/accounts", { params: { page_size: 100 } }).then(({ data }) => setAccounts(data.items));
  }, []);

  useEffect(() => {
    setAllocations({});
    if (!tenantId) { setOutstandingInvoices([]); return; }
    setLoadingInvoices(true);
    apiClient.get<PaginatedResponse<Invoice>>("/financial/invoices", { params: { tenant_id: tenantId, page_size: 100 } })
      .then(({ data }) => setOutstandingInvoices(data.items.filter((i) => ["sent", "overdue", "partially_paid"].includes(i.invoice_status) && Number(i.outstanding_amount) > 0)))
      .finally(() => setLoadingInvoices(false));
  }, [tenantId]);

  const toggleInvoice = (invoice: Invoice) => {
    setAllocations((prev) => {
      const next = { ...prev };
      if (next[invoice.id]) delete next[invoice.id];
      else next[invoice.id] = { invoice, amount: invoice.outstanding_amount };
      return next;
    });
  };

  const setAllocationAmount = (invoiceId: number, amount: string) => {
    setAllocations((prev) => ({ ...prev, [invoiceId]: { ...prev[invoiceId], amount } }));
  };

  const total = Object.values(allocations).reduce((sum, a) => sum + (Number(a.amount) || 0), 0);

  const submit = async () => {
    const selected = Object.values(allocations);
    if (!tenantId || !accountId || selected.length === 0) { setError("Tenant, account, and at least one invoice allocation are required."); return; }
    setSubmitting(true);
    setError("");
    try {
      await apiClient.post("/payments", {
        tenant_id: tenantId, account_id: accountId, payment_method: paymentMethod, payment_date: paymentDate,
        amount: total.toFixed(3), reference_number: referenceNumber || undefined, notes: notes || undefined,
        allocations: selected.map((a) => ({ invoice_id: a.invoice.id, amount: a.amount })),
      });
      onCreated();
      onClose();
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Could not capture this payment.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal open onClose={onClose} title="Record Payment" footer={
      <>
        <button className="btn-secondary" onClick={onClose}>Cancel</button>
        <button className="btn-primary" onClick={submit} disabled={submitting}>
          {submitting ? <Loader2 size={16} className="animate-spin" /> : <Plus size={16} />} Capture Payment ({money(total)})
        </button>
      </>
    }>
      <div className="space-y-3">
        <p className="text-xs text-ink-400 bg-ink-50 dark:bg-ink-800/60 rounded-md p-2">
          Capturing a payment only records it (Pending) — it doesn't move money yet. Verify it afterward to actually post it to the ledger.
        </p>
        {error && <p className="text-xs text-rust-500">{error}</p>}
        <div className="grid grid-cols-2 gap-3">
          <FormField label="Tenant" required>
            <select className="input" value={tenantId} onChange={(e) => setTenantId(Number(e.target.value))}>
              <option value="">Select tenant…</option>
              {tenants.map((t) => <option key={t.id} value={t.id}>{t.tenant_code} — {t.display_name}</option>)}
            </select>
          </FormField>
          <FormField label="Account" required>
            <select className="input" value={accountId} onChange={(e) => setAccountId(Number(e.target.value))}>
              <option value="">Select account…</option>
              {accounts.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
            </select>
          </FormField>
          <FormField label="Payment Method" required>
            <select className="input" value={paymentMethod} onChange={(e) => setPaymentMethod(e.target.value)}>
              {PAYMENT_METHODS.map((m) => <option key={m} value={m}>{m.replace(/_/g, " ")}</option>)}
            </select>
          </FormField>
          <FormField label="Payment Date" required>
            <input className="input" type="date" value={paymentDate} onChange={(e) => setPaymentDate(e.target.value)} />
          </FormField>
          <FormField label="Reference Number">
            <input className="input" value={referenceNumber} onChange={(e) => setReferenceNumber(e.target.value)} />
          </FormField>
          <FormField label="Notes">
            <input className="input" value={notes} onChange={(e) => setNotes(e.target.value)} />
          </FormField>
        </div>

        <FormField label="Allocate Against Invoices" required hint="One payment can cover multiple invoices — check every one this payment should apply to.">
          {!tenantId ? (
            <p className="text-sm text-ink-400 py-2">Select a tenant first.</p>
          ) : loadingInvoices ? (
            <div className="flex justify-center py-4"><Loader2 className="animate-spin text-ink-400" size={18} /></div>
          ) : outstandingInvoices.length === 0 ? (
            <p className="text-sm text-ink-400 py-2">No outstanding invoices for this tenant.</p>
          ) : (
            <div className="border border-ink-100 dark:border-ink-800 rounded-md divide-y divide-ink-100 dark:divide-ink-800 max-h-56 overflow-y-auto">
              {outstandingInvoices.map((inv) => (
                <div key={inv.id} className="flex items-center gap-2 px-3 py-2 text-sm">
                  <input type="checkbox" className="w-4 h-4" checked={!!allocations[inv.id]} onChange={() => toggleInvoice(inv)} />
                  <span className="font-mono text-xs text-ink-400">{inv.invoice_number}</span>
                  <span className="text-ink-500">Due {inv.due_date}</span>
                  <span className="ml-auto text-ink-400">of {money(inv.outstanding_amount)}</span>
                  {allocations[inv.id] && (
                    <input
                      className="input !w-24 !py-1" type="number" min="0" max={inv.outstanding_amount} step="0.001"
                      value={allocations[inv.id].amount} onChange={(e) => setAllocationAmount(inv.id, e.target.value)}
                    />
                  )}
                </div>
              ))}
            </div>
          )}
        </FormField>
      </div>
    </Modal>
  );
}
