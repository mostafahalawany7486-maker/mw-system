import { useEffect, useState, useCallback } from "react";
import { useNavigate, Link } from "react-router-dom";
import apiClient from "@/api/client";
import { useAuth } from "@/context/AuthContext";
import { PageHeader, Pagination, EmptyState, ToolbarSearch } from "@/components/ui";
import {
  Plus, Loader2, Wallet, Landmark, TrendingUp, TrendingDown, ArrowLeftRight,
  Users, UserSquare2, Send, Ban, CheckCircle2, FileText,
} from "lucide-react";
import {
  FinancialDashboard, FinancialAccount, FinancialTransaction, Invoice, Receipt, OutstandingBalance, PaginatedResponse,
} from "@/types";
import AccountFormModal from "@/components/AccountFormModal";
import TransactionFormModal from "@/components/TransactionFormModal";
import TransferModal from "@/components/TransferModal";
import InvoiceFormModal from "@/components/InvoiceFormModal";

type TabKey = "overview" | "accounts" | "transactions" | "receipts" | "balances";

// "Invoices" removed from here per a confirmed architecture decision:
// the Rent Billing Engine's Invoice system and the Rent Cycle Engine's
// RentalPaymentInstallment schedule were two entirely separate,
// never-reconciled ways of tracking "what's due, when" for the same
// contract — Rent Cycles won out (it's what Rent Collection, the
// dashboard's outstanding totals, and every recent fix in this
// codebase are actually built on). The Invoice model, its endpoints,
// and any historical Invoice rows are untouched — same "hide the
// front door, don't touch the data" approach already used for
// Currencies/Countries — this is a routing-only change.
const TABS: { key: TabKey; label: string }[] = [
  { key: "overview", label: "Overview" },
  { key: "accounts", label: "Accounts" },
  { key: "transactions", label: "Transactions" },
  { key: "receipts", label: "Receipts" },
  { key: "balances", label: "Outstanding Balances" },
];

export default function FinancialPage() {
  const { hasPermission } = useAuth();
  const navigate = useNavigate();
  const [tab, setTab] = useState<TabKey>("overview");
  const [dashboard, setDashboard] = useState<FinancialDashboard | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  const canCreate = hasPermission("financial.create");
  const canEdit = hasPermission("financial.edit");

  const loadDashboard = useCallback(() => {
    apiClient.get<FinancialDashboard>("/financial/dashboard/summary").then(({ data }) => setDashboard(data));
  }, []);

  useEffect(() => { loadDashboard(); }, [loadDashboard, refreshKey]);

  const bump = () => setRefreshKey((k) => k + 1);

  return (
    <div>
      <PageHeader
        title="Financial Management"
        description="Payments, receipts, expenses, and account balances."
      />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <div className="card p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-ink-500 dark:text-ink-400">Cash Balance</span>
            <Wallet size={16} className="text-ink-400" />
          </div>
          <div className="font-display text-2xl font-bold">{dashboard ? Number(dashboard.total_cash_balance).toLocaleString() : "—"}</div>
        </div>
        <div className="card p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-ink-500 dark:text-ink-400">Bank Balance</span>
            <Landmark size={16} className="text-ink-400" />
          </div>
          <div className="font-display text-2xl font-bold">{dashboard ? Number(dashboard.total_bank_balance).toLocaleString() : "—"}</div>
        </div>
        <div className="card p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-ink-500 dark:text-ink-400">Income (this month)</span>
            <TrendingUp size={16} className="text-brand-500" />
          </div>
          <div className="font-display text-2xl font-bold">{dashboard ? Number(dashboard.total_income_this_month).toLocaleString() : "—"}</div>
        </div>
        <div className="card p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-ink-500 dark:text-ink-400">Expenses (this month)</span>
            <TrendingDown size={16} className="text-rust-500" />
          </div>
          <div className="font-display text-2xl font-bold">{dashboard ? Number(dashboard.total_expense_this_month).toLocaleString() : "—"}</div>
        </div>
      </div>

      <div className="flex gap-1 border-b border-ink-100 dark:border-ink-800 mb-6 overflow-x-auto">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`px-3.5 py-2.5 text-sm font-medium border-b-2 whitespace-nowrap transition-colors ${
              tab === t.key ? "border-brand-500 text-brand-600 dark:text-brand-400" : "border-transparent text-ink-500 hover:text-ink-800 dark:hover:text-ink-100"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "overview" && <OverviewTab dashboard={dashboard} />}
      {tab === "accounts" && <AccountsTab canCreate={canCreate} refreshKey={refreshKey} onChanged={bump} />}
      {tab === "transactions" && <TransactionsTab canCreate={canCreate} refreshKey={refreshKey} onChanged={bump} />}
      {/* "invoices" tab intentionally removed from TABS above — InvoicesTab
          component below is kept, just unreached, so nothing about how
          it works is lost if this decision is ever revisited. */}
      {tab === "receipts" && <ReceiptsTab refreshKey={refreshKey} />}
      {tab === "balances" && <BalancesTab refreshKey={refreshKey} />}
    </div>
  );
}

// ==================== Overview ====================
function OverviewTab({ dashboard }: { dashboard: FinancialDashboard | null }) {
  if (!dashboard) return <div className="flex justify-center py-10"><Loader2 className="animate-spin text-ink-400" /></div>;
  return (
    <div className="space-y-6">
      <div className="card p-6">
        <h3 className="font-display font-semibold text-sm mb-4">Accounts</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {dashboard.accounts.map((a) => (
            <div key={a.id} className="flex items-center justify-between p-3 rounded-md border border-ink-100 dark:border-ink-800">
              <div className="flex items-center gap-2">
                {a.account_type === "cash" ? <Wallet size={16} className="text-ink-400" /> : <Landmark size={16} className="text-ink-400" />}
                <div>
                  <p className="text-sm font-medium">{a.name}</p>
                  <p className="text-xs text-ink-400 font-mono">{a.account_code}</p>
                </div>
              </div>
              <span className="font-display font-semibold">{Number(a.current_balance).toLocaleString()}</span>
            </div>
          ))}
        </div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="card p-4">
          <div className="flex items-center gap-2 mb-1">
            <Users size={15} className="text-amber-500" />
            <h3 className="font-display font-semibold text-sm">Tenant Outstanding</h3>
          </div>
          <div className="font-display text-xl font-bold">{Number(dashboard.total_tenant_outstanding).toLocaleString()}</div>
        </div>
        <div className="card p-4">
          <div className="flex items-center gap-2 mb-1">
            <UserSquare2 size={15} className="text-amber-500" />
            <h3 className="font-display font-semibold text-sm">Owner Outstanding</h3>
          </div>
          <div className="font-display text-xl font-bold">{Number(dashboard.total_owner_outstanding).toLocaleString()}</div>
        </div>
      </div>
    </div>
  );
}

// ==================== Accounts ====================
function AccountsTab({ canCreate, refreshKey, onChanged }: { canCreate: boolean; refreshKey: number; onChanged: () => void }) {
  const [data, setData] = useState<PaginatedResponse<FinancialAccount> | null>(null);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    apiClient.get<PaginatedResponse<FinancialAccount>>("/financial/accounts", { params: { page_size: 50 } })
      .then(({ data }) => setData(data)).finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load, refreshKey]);

  return (
    <div className="card">
      <div className="flex justify-between items-center px-5 py-4 border-b border-ink-100 dark:border-ink-800">
        <h3 className="font-display font-semibold text-sm">Cash & Bank Accounts</h3>
        {canCreate && <button className="btn-primary" onClick={() => setModalOpen(true)}><Plus size={14} /> Add Account</button>}
      </div>
      {loading && <div className="flex justify-center py-10"><Loader2 className="animate-spin text-ink-400" /></div>}
      {!loading && data && data.items.length === 0 && <EmptyState title="No accounts yet" description="Add a cash or bank account to start recording transactions." />}
      {!loading && data && data.items.length > 0 && (
        <div className="overflow-x-auto">
          <table className="table-shell">
            <thead><tr><th>Code</th><th>Name</th><th>Type</th><th>Bank</th><th>Balance</th></tr></thead>
            <tbody>
              {data.items.map((a) => (
                <tr key={a.id}>
                  <td className="font-mono text-xs">{a.account_code}</td>
                  <td className="font-medium">{a.name} {a.is_default && <span className="badge-active ml-1">Default</span>}</td>
                  <td className="capitalize">{a.account_type}</td>
                  <td className="text-ink-500">{a.bank_name || "—"}</td>
                  <td className="font-medium">{Number(a.current_balance).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <AccountFormModal open={modalOpen} onClose={() => setModalOpen(false)} onSaved={() => { setModalOpen(false); load(); onChanged(); }} />
    </div>
  );
}

// ==================== Transactions ====================
function TransactionsTab({ canCreate, refreshKey, onChanged }: { canCreate: boolean; refreshKey: number; onChanged: () => void }) {
  const [data, setData] = useState<PaginatedResponse<FinancialTransaction> | null>(null);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [loading, setLoading] = useState(false);
  const [txnModalOpen, setTxnModalOpen] = useState(false);
  const [transferModalOpen, setTransferModalOpen] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    apiClient.get<PaginatedResponse<FinancialTransaction>>("/financial/transactions", {
      params: { page, page_size: 10, search: search || undefined, transaction_type: typeFilter || undefined },
    }).then(({ data }) => setData(data)).finally(() => setLoading(false));
  }, [page, search, typeFilter]);

  useEffect(() => { load(); }, [load, refreshKey]);

  return (
    <div className="card">
      <div className="flex justify-between items-center px-5 py-4 border-b border-ink-100 dark:border-ink-800 flex-wrap gap-2">
        <ToolbarSearch value={search} onChange={(v) => { setSearch(v); setPage(1); }} placeholder="Search by number, reference, name…" />
        <div className="flex gap-2 items-center">
          <select className="input max-w-[180px]" value={typeFilter} onChange={(e) => { setTypeFilter(e.target.value); setPage(1); }}>
            <option value="">All types</option>
            <option value="tenant_payment">Tenant Payment</option>
            <option value="owner_payment">Owner Payment</option>
            <option value="expense">Expense</option>
            <option value="income">Income</option>
            <option value="deposit_received">Deposit Received</option>
            <option value="deposit_refund">Deposit Refund</option>
            <option value="refund">Refund</option>
            <option value="transfer_in">Transfer In</option>
            <option value="transfer_out">Transfer Out</option>
          </select>
          {canCreate && (
            <>
              <button className="btn-secondary" onClick={() => setTransferModalOpen(true)}><ArrowLeftRight size={14} /> Transfer</button>
              <button className="btn-primary" onClick={() => setTxnModalOpen(true)}><Plus size={14} /> Record Transaction</button>
            </>
          )}
        </div>
      </div>

      {loading && <div className="flex justify-center py-10"><Loader2 className="animate-spin text-ink-400" /></div>}
      {!loading && data && data.items.length === 0 && <EmptyState title="No transactions yet" />}
      {!loading && data && data.items.length > 0 && (
        <div className="overflow-x-auto">
          <table className="table-shell">
            <thead><tr><th>#</th><th>Date</th><th>Type</th><th>Party</th><th>Account</th><th>Amount</th><th>Receipt</th></tr></thead>
            <tbody>
              {data.items.map((t) => (
                <tr key={t.id}>
                  <td className="font-mono text-xs">{t.transaction_number}</td>
                  <td className="text-ink-500">{t.transaction_date}</td>
                  <td className="capitalize">{t.transaction_type.replace(/_/g, " ")}</td>
                  <td className="text-ink-500">{t.tenant_display_name || t.owner_display_name || "—"}</td>
                  <td className="text-ink-500">{t.account_name}</td>
                  <td className={t.direction === "in" ? "text-brand-600 font-medium" : "text-rust-500 font-medium"}>
                    {t.direction === "in" ? "+" : "-"}{Number(t.amount).toLocaleString()}
                  </td>
                  <td className="font-mono text-xs">
                    {t.receipt_id ? (
                      <Link to={`/receipts/${t.receipt_id}/print`} className="text-brand-600 dark:text-brand-400 hover:underline" target="_blank" rel="noopener noreferrer">
                        {t.receipt_number} ↗
                      </Link>
                    ) : (
                      <span className="text-ink-400">{t.receipt_number || "—"}</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {data && <Pagination page={data.page} totalPages={data.total_pages} onChange={setPage} />}

      <TransactionFormModal open={txnModalOpen} onClose={() => setTxnModalOpen(false)} onSaved={() => { setTxnModalOpen(false); load(); onChanged(); }} />
      <TransferModal open={transferModalOpen} onClose={() => setTransferModalOpen(false)} onSaved={() => { setTransferModalOpen(false); load(); onChanged(); }} />
    </div>
  );
}

// ==================== Invoices ====================
function InvoicesTab({ canCreate, canEdit, refreshKey, onChanged }: { canCreate: boolean; canEdit: boolean; refreshKey: number; onChanged: () => void }) {
  const [data, setData] = useState<PaginatedResponse<Invoice> | null>(null);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState("");
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [payModal, setPayModal] = useState<Invoice | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    apiClient.get<PaginatedResponse<Invoice>>("/financial/invoices", {
      params: { page, page_size: 10, invoice_status: statusFilter || undefined },
    }).then(({ data }) => setData(data)).finally(() => setLoading(false));
  }, [page, statusFilter]);

  useEffect(() => { load(); }, [load, refreshKey]);

  const handleSend = async (inv: Invoice) => { await apiClient.post(`/financial/invoices/${inv.id}/send`); load(); onChanged(); };
  const handleCancel = async (inv: Invoice) => { if (confirm("Cancel this invoice?")) { await apiClient.post(`/financial/invoices/${inv.id}/cancel`); load(); onChanged(); } };

  const STATUS_TONE: Record<string, string> = { draft: "badge-inactive", sent: "badge-warn", paid: "badge-active", overdue: "badge-warn", cancelled: "badge-inactive" };

  return (
    <div className="card">
      <div className="flex justify-between items-center px-5 py-4 border-b border-ink-100 dark:border-ink-800 flex-wrap gap-2">
        <select className="input max-w-[160px]" value={statusFilter} onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}>
          <option value="">All statuses</option>
          <option value="draft">Draft</option>
          <option value="sent">Sent</option>
          <option value="paid">Paid</option>
          <option value="overdue">Overdue</option>
          <option value="cancelled">Cancelled</option>
        </select>
        {canCreate && <button className="btn-primary" onClick={() => setModalOpen(true)}><Plus size={14} /> Create Invoice</button>}
      </div>
      {loading && <div className="flex justify-center py-10"><Loader2 className="animate-spin text-ink-400" /></div>}
      {!loading && data && data.items.length === 0 && <EmptyState title="No invoices yet" />}
      {!loading && data && data.items.length > 0 && (
        <div className="overflow-x-auto">
          <table className="table-shell">
            <thead><tr><th>#</th><th>Tenant</th><th>Amount</th><th>Issue</th><th>Due</th><th>Status</th><th className="text-right">Actions</th></tr></thead>
            <tbody>
              {data.items.map((inv) => (
                <tr key={inv.id}>
                  <td className="font-mono text-xs">{inv.invoice_number}</td>
                  <td className="font-medium">{inv.tenant_display_name}</td>
                  <td>{Number(inv.amount).toLocaleString()}</td>
                  <td className="text-ink-500">{inv.issue_date}</td>
                  <td className="text-ink-500">{inv.due_date}</td>
                  <td><span className={STATUS_TONE[inv.invoice_status]}>{inv.invoice_status}</span></td>
                  <td className="text-right">
                    {canEdit && (
                      <div className="flex justify-end gap-1">
                        {inv.invoice_status === "draft" && <button className="btn-secondary !px-2 !py-1" onClick={() => handleSend(inv)}><Send size={13} /></button>}
                        {(inv.invoice_status === "sent" || inv.invoice_status === "overdue") && <button className="btn-secondary !px-2 !py-1" onClick={() => setPayModal(inv)}><CheckCircle2 size={13} /> Record Payment</button>}
                        {inv.invoice_status !== "paid" && inv.invoice_status !== "cancelled" && <button className="btn-secondary !px-2 !py-1 text-rust-500" onClick={() => handleCancel(inv)}><Ban size={13} /></button>}
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {data && <Pagination page={data.page} totalPages={data.total_pages} onChange={setPage} />}

      <InvoiceFormModal open={modalOpen} onClose={() => setModalOpen(false)} onSaved={() => { setModalOpen(false); load(); onChanged(); }} />
      {payModal && (
        <RecordPaymentModal invoice={payModal} onClose={() => setPayModal(null)} onDone={() => { setPayModal(null); load(); onChanged(); }} />
      )}
    </div>
  );
}

function RecordPaymentModal({ invoice, onClose, onDone }: { invoice: Invoice; onClose: () => void; onDone: () => void }) {
  const [accounts, setAccounts] = useState<FinancialAccount[]>([]);
  const [accountId, setAccountId] = useState<number | "">("");
  const [transactionDate, setTransactionDate] = useState(new Date().toISOString().slice(0, 10));
  const [paymentMethod, setPaymentMethod] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiClient.get<PaginatedResponse<FinancialAccount>>("/financial/accounts", { params: { page_size: 100 } }).then(({ data }) => setAccounts(data.items));
  }, []);

  const handleSubmit = async () => {
    setSaving(true);
    setError(null);
    try {
      await apiClient.post(`/financial/invoices/${invoice.id}/record-payment`, {
        account_id: Number(accountId), transaction_date: transactionDate, payment_method: paymentMethod || undefined,
      });
      onDone();
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Unable to record this payment.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink-950/50 p-4" onClick={onClose}>
      <div className="card p-6 max-w-md w-full" onClick={(e) => e.stopPropagation()}>
        <h3 className="font-display font-semibold text-sm mb-4">Record Payment — {invoice.invoice_number}</h3>
        {error && <div className="mb-3 text-sm text-rust-500 bg-rust-50 dark:bg-rust-500/10 rounded-md px-3 py-2">{error}</div>}
        <div className="space-y-4">
          <div>
            <label className="label">Deposit Into Account *</label>
            <select className="input" required value={accountId} onChange={(e) => setAccountId(Number(e.target.value))}>
              <option value="">Select account…</option>
              {accounts.map((a) => <option key={a.id} value={a.id}>{a.account_code} — {a.name}</option>)}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label">Payment Method</label>
              <select className="input" value={paymentMethod} onChange={(e) => setPaymentMethod(e.target.value)}>
                <option value="">—</option>
                <option value="cash">Cash</option>
                <option value="bank_transfer">Bank Transfer</option>
                <option value="cheque">Cheque</option>
                <option value="card">Card</option>
                <option value="online">Online</option>
              </select>
            </div>
            <div>
              <label className="label">Date *</label>
              <input className="input" type="date" required value={transactionDate} onChange={(e) => setTransactionDate(e.target.value)} />
            </div>
          </div>
        </div>
        <div className="flex justify-end gap-2 mt-6">
          <button className="btn-secondary" onClick={onClose}>Cancel</button>
          <button className="btn-primary" disabled={saving || !accountId} onClick={handleSubmit}>
            {saving && <Loader2 size={14} className="animate-spin" />} Record Payment
          </button>
        </div>
      </div>
    </div>
  );
}

// ==================== Receipts ====================
function ReceiptsTab({ refreshKey }: { refreshKey: number }) {
  const [data, setData] = useState<PaginatedResponse<Receipt> | null>(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    apiClient.get<PaginatedResponse<Receipt>>("/financial/receipts", { params: { page, page_size: 10 } })
      .then(({ data }) => setData(data)).finally(() => setLoading(false));
  }, [page]);

  useEffect(() => { load(); }, [load, refreshKey]);

  return (
    <div className="card">
      <div className="px-5 py-4 border-b border-ink-100 dark:border-ink-800">
        <h3 className="font-display font-semibold text-sm">Receipts</h3>
        <p className="text-xs text-ink-400 mt-0.5">Automatically issued for owner payments and invoice payments. Rental tenant payments have their own dedicated Rental Receipt — see Rentals → Receipts.</p>
      </div>
      {loading && <div className="flex justify-center py-10"><Loader2 className="animate-spin text-ink-400" /></div>}
      {!loading && data && data.items.length === 0 && <EmptyState title="No receipts yet" />}
      {!loading && data && data.items.length > 0 && (
        <div className="divide-y divide-ink-50 dark:divide-ink-800/60">
          {data.items.map((r) => (
            <div key={r.id} className="px-5 py-3 flex items-center justify-between">
              <div>
                <p className="text-sm font-medium font-mono">{r.receipt_number}</p>
                <p className="text-xs text-ink-400 mt-0.5">
                  {r.transaction?.transaction_type.replace(/_/g, " ")} · {r.transaction?.tenant_display_name || r.transaction?.owner_display_name} · {Number(r.transaction?.amount || 0).toLocaleString()}
                </p>
              </div>
              <span className="text-xs text-ink-400">{r.issued_date}</span>
            </div>
          ))}
        </div>
      )}
      {data && <Pagination page={data.page} totalPages={data.total_pages} onChange={setPage} />}
    </div>
  );
}

// ==================== Outstanding Balances ====================
function BalancesTab({ refreshKey }: { refreshKey: number }) {
  const navigate = useNavigate();
  const [balances, setBalances] = useState<OutstandingBalance | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    apiClient.get<OutstandingBalance>("/financial/outstanding-balances").then(({ data }) => setBalances(data)).finally(() => setLoading(false));
  }, [refreshKey]);

  if (loading) return <div className="flex justify-center py-10"><Loader2 className="animate-spin text-ink-400" /></div>;
  if (!balances) return null;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <div className="card">
        <div className="px-5 py-4 border-b border-ink-100 dark:border-ink-800 flex items-center justify-between">
          <h3 className="font-display font-semibold text-sm">Tenants Owing Rent</h3>
          <span className="font-display font-semibold">{Number(balances.total_tenant_outstanding).toLocaleString()}</span>
        </div>
        {balances.tenants.length === 0 && <EmptyState title="No outstanding tenant balances" />}
        <div className="divide-y divide-ink-50 dark:divide-ink-800/60">
          {balances.tenants.map((t) => (
            <div key={t.id} className="px-5 py-3 flex items-center justify-between cursor-pointer hover:bg-ink-50 dark:hover:bg-ink-800/40" onClick={() => navigate(`/tenants/${t.id}`)}>
              <div>
                <p className="text-sm font-medium">{t.display_name}</p>
                <p className="text-xs text-ink-400 mt-0.5">{t.overdue_count} overdue · {t.pending_count} pending</p>
              </div>
              <span className="font-medium text-rust-500">{Number(t.outstanding_amount).toLocaleString()}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="card">
        <div className="px-5 py-4 border-b border-ink-100 dark:border-ink-800 flex items-center justify-between">
          <h3 className="font-display font-semibold text-sm">Owners Owed Rent</h3>
          <span className="font-display font-semibold">{Number(balances.total_owner_outstanding).toLocaleString()}</span>
        </div>
        {balances.owners.length === 0 && <EmptyState title="No outstanding owner balances" />}
        <div className="divide-y divide-ink-50 dark:divide-ink-800/60">
          {balances.owners.map((o) => (
            <div key={o.id} className="px-5 py-3 flex items-center justify-between cursor-pointer hover:bg-ink-50 dark:hover:bg-ink-800/40" onClick={() => navigate(`/owners/${o.id}`)}>
              <div>
                <p className="text-sm font-medium">{o.display_name}</p>
                <p className="text-xs text-ink-400 mt-0.5">{o.overdue_count} overdue · {o.pending_count} pending</p>
              </div>
              <span className="font-medium text-rust-500">{Number(o.outstanding_amount).toLocaleString()}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
