import { useEffect, useState, useCallback } from "react";
import apiClient from "@/api/client";
import { useAuth } from "@/context/AuthContext";
import { PageHeader, Pagination, EmptyState } from "@/components/ui";
import { Plus, Loader2, CheckCircle2, RotateCcw, Trash2, ChevronRight, ChevronDown } from "lucide-react";
import {
  ChartOfAccountItem, CostCenterItem, VatRateItem, PostingRuleItem,
  JournalEntryListItem, JournalEntryDetail, TrialBalance, BalanceSheet,
  IncomeStatement, CashFlow, VatReport, PaginatedResponse,
} from "@/types";
import ChartOfAccountFormModal from "@/components/ChartOfAccountFormModal";
import JournalEntryFormModal from "@/components/JournalEntryFormModal";

type TabKey = "coa" | "journal" | "costcenters" | "reports";
const TABS: { key: TabKey; label: string }[] = [
  { key: "coa", label: "Chart of Accounts" },
  { key: "journal", label: "Journal Entries" },
  { key: "costcenters", label: "Cost Centers & VAT" },
  { key: "reports", label: "Reports" },
];

export default function AccountingPage() {
  const { hasPermission } = useAuth();
  const [tab, setTab] = useState<TabKey>("coa");
  const canCreate = hasPermission("accounting.create");
  const canEdit = hasPermission("accounting.edit");
  const canDelete = hasPermission("accounting.delete");

  return (
    <div>
      <PageHeader title="Accounting" description="Chart of accounts, journal entries, general ledger, and financial reports." />

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

      {tab === "coa" && <ChartOfAccountsTab canCreate={canCreate} canDelete={canDelete} />}
      {tab === "journal" && <JournalEntriesTab canCreate={canCreate} canEdit={canEdit} canDelete={canDelete} />}
      {tab === "costcenters" && <CostCentersVatTab canCreate={canCreate} />}
      {tab === "reports" && <ReportsTab />}
    </div>
  );
}

// ==================== Chart of Accounts ====================
function ChartOfAccountsTab({ canCreate, canDelete }: { canCreate: boolean; canDelete: boolean }) {
  const [accounts, setAccounts] = useState<ChartOfAccountItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [expanded, setExpanded] = useState<Set<number>>(new Set());

  const load = useCallback(() => {
    setLoading(true);
    apiClient.get<ChartOfAccountItem[]>("/accounting/chart-of-accounts", { params: { with_balances: true } })
      .then(({ data }) => setAccounts(data)).finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleDelete = async (a: ChartOfAccountItem) => {
    if (!confirm(`Delete account ${a.account_code} — ${a.account_name}?`)) return;
    try {
      await apiClient.delete(`/accounting/chart-of-accounts/${a.id}`);
      load();
    } catch (err: any) {
      alert(err?.response?.data?.detail || "Unable to delete this account.");
    }
  };

  const topLevel = accounts.filter((a) => !a.parent_account_id);
  const childrenOf = (id: number) => accounts.filter((a) => a.parent_account_id === id);

  const toggle = (id: number) => setExpanded((prev) => { const next = new Set(prev); next.has(id) ? next.delete(id) : next.add(id); return next; });

  const renderRow = (a: ChartOfAccountItem, depth: number) => {
    const kids = childrenOf(a.id);
    const isExpanded = expanded.has(a.id);
    return (
      <div key={a.id}>
        <div className="flex items-center justify-between px-5 py-2.5 hover:bg-ink-50 dark:hover:bg-ink-800/40" style={{ paddingLeft: `${20 + depth * 24}px` }}>
          <div className="flex items-center gap-2">
            {kids.length > 0 ? (
              <button onClick={() => toggle(a.id)} className="text-ink-400">{isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}</button>
            ) : <span className="w-3.5" />}
            <span className="font-mono text-xs text-ink-400 w-14">{a.account_code}</span>
            <span className={a.allow_posting ? "text-sm" : "text-sm font-semibold"}>{a.account_name}</span>
            {!a.allow_posting && <span className="badge-inactive">Header</span>}
          </div>
          <div className="flex items-center gap-3">
            {a.allow_posting && <span className="text-sm text-ink-500">{a.balance ? Number(a.balance).toLocaleString() : "0"}</span>}
            {canDelete && <button className="btn-secondary !px-2 !py-1 text-rust-500" onClick={() => handleDelete(a)}><Trash2 size={12} /></button>}
          </div>
        </div>
        {isExpanded && kids.map((k) => renderRow(k, depth + 1))}
      </div>
    );
  };

  return (
    <div className="card">
      <div className="flex justify-between items-center px-5 py-4 border-b border-ink-100 dark:border-ink-800">
        <h3 className="font-display font-semibold text-sm">Chart of Accounts</h3>
        {canCreate && <button className="btn-primary" onClick={() => setModalOpen(true)}><Plus size={14} /> Add Account</button>}
      </div>
      {loading && <div className="flex justify-center py-10"><Loader2 className="animate-spin text-ink-400" /></div>}
      {!loading && accounts.length === 0 && <EmptyState title="No accounts yet" description="Build out a chart of accounts to start recording journal entries." />}
      {!loading && accounts.length > 0 && (
        <div className="divide-y divide-ink-50 dark:divide-ink-800/60 py-1">
          {topLevel.map((a) => renderRow(a, 0))}
        </div>
      )}
      <ChartOfAccountFormModal open={modalOpen} onClose={() => setModalOpen(false)} onSaved={() => { setModalOpen(false); load(); }} />
    </div>
  );
}

// ==================== Journal Entries ====================
function JournalEntriesTab({ canCreate, canEdit, canDelete }: { canCreate: boolean; canEdit: boolean; canDelete: boolean }) {
  const [data, setData] = useState<PaginatedResponse<JournalEntryListItem> | null>(null);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState("");
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [selected, setSelected] = useState<JournalEntryDetail | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    apiClient.get<PaginatedResponse<JournalEntryListItem>>("/accounting/journal-entries", {
      params: { page, page_size: 10, entry_status: statusFilter || undefined },
    }).then(({ data }) => setData(data)).finally(() => setLoading(false));
  }, [page, statusFilter]);

  useEffect(() => { load(); }, [load]);

  const openDetail = async (id: number) => {
    const { data } = await apiClient.get<JournalEntryDetail>(`/accounting/journal-entries/${id}`);
    setSelected(data);
  };

  const handlePost = async (id: number) => { await apiClient.post(`/accounting/journal-entries/${id}/post`); load(); if (selected) openDetail(id); };
  const handleReverse = async (id: number) => {
    if (!confirm("Reverse this journal entry? This creates a new offsetting entry.")) return;
    await apiClient.post(`/accounting/journal-entries/${id}/reverse`, null, { params: { reversal_date: new Date().toISOString().slice(0, 10) } });
    load(); setSelected(null);
  };
  const handleDeleteDraft = async (id: number) => {
    if (!confirm("Delete this draft entry?")) return;
    await apiClient.delete(`/accounting/journal-entries/${id}`);
    load(); setSelected(null);
  };

  const STATUS_TONE: Record<string, string> = { draft: "badge-inactive", posted: "badge-active", reversed: "badge-warn" };

  return (
    <div className="card">
      <div className="flex justify-between items-center px-5 py-4 border-b border-ink-100 dark:border-ink-800 flex-wrap gap-2">
        <select className="input max-w-[160px]" value={statusFilter} onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}>
          <option value="">All statuses</option>
          <option value="draft">Draft</option>
          <option value="posted">Posted</option>
          <option value="reversed">Reversed</option>
        </select>
        {canCreate && <button className="btn-primary" onClick={() => setModalOpen(true)}><Plus size={14} /> New Entry</button>}
      </div>
      {loading && <div className="flex justify-center py-10"><Loader2 className="animate-spin text-ink-400" /></div>}
      {!loading && data && data.items.length === 0 && <EmptyState title="No journal entries yet" />}
      {!loading && data && data.items.length > 0 && (
        <div className="overflow-x-auto">
          <table className="table-shell">
            <thead><tr><th>#</th><th>Date</th><th>Description</th><th>Source</th><th>Debit</th><th>Credit</th><th>Status</th></tr></thead>
            <tbody>
              {data.items.map((e) => (
                <tr key={e.id} className="cursor-pointer" onClick={() => openDetail(e.id)}>
                  <td className="font-mono text-xs">{e.entry_number}</td>
                  <td className="text-ink-500">{e.entry_date}</td>
                  <td className="max-w-[220px] truncate">{e.description || "—"}</td>
                  <td className="capitalize text-ink-500">{e.source_type}</td>
                  <td>{Number(e.total_debit).toLocaleString()}</td>
                  <td>{Number(e.total_credit).toLocaleString()}</td>
                  <td><span className={STATUS_TONE[e.entry_status]}>{e.entry_status}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {data && <Pagination page={data.page} totalPages={data.total_pages} onChange={setPage} />}

      <JournalEntryFormModal open={modalOpen} onClose={() => setModalOpen(false)} onSaved={() => { setModalOpen(false); load(); }} />

      {selected && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink-950/50 p-4" onClick={() => setSelected(null)}>
          <div className="card p-6 max-w-2xl w-full max-h-[85vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <div className="flex justify-between items-start mb-4">
              <div>
                <h3 className="font-display font-semibold text-base font-mono">{selected.entry_number}</h3>
                <p className="text-sm text-ink-500 mt-1">{selected.description}</p>
              </div>
              <span className={STATUS_TONE[selected.entry_status]}>{selected.entry_status}</span>
            </div>
            <table className="table-shell mb-4">
              <thead><tr><th>Account</th><th>Cost Center</th><th>Debit</th><th>Credit</th></tr></thead>
              <tbody>
                {selected.lines.map((l) => (
                  <tr key={l.id}>
                    <td>{l.account_code} — {l.account_name}</td>
                    <td className="text-ink-500">{l.cost_center_id || "—"}</td>
                    <td>{Number(l.debit_amount) > 0 ? Number(l.debit_amount).toLocaleString() : ""}</td>
                    <td>{Number(l.credit_amount) > 0 ? Number(l.credit_amount).toLocaleString() : ""}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot><tr><td colSpan={2} className="text-right font-medium">Total</td><td className="font-semibold">{Number(selected.total_debit).toLocaleString()}</td><td className="font-semibold">{Number(selected.total_credit).toLocaleString()}</td></tr></tfoot>
            </table>
            <div className="flex justify-end gap-2">
              <button className="btn-secondary" onClick={() => setSelected(null)}>Close</button>
              {canEdit && selected.entry_status === "draft" && <button className="btn-primary" onClick={() => handlePost(selected.id)}><CheckCircle2 size={14} /> Post</button>}
              {canEdit && selected.entry_status === "posted" && <button className="btn-secondary" onClick={() => handleReverse(selected.id)}><RotateCcw size={14} /> Reverse</button>}
              {canDelete && selected.entry_status === "draft" && <button className="btn-secondary text-rust-500" onClick={() => handleDeleteDraft(selected.id)}><Trash2 size={14} /> Delete</button>}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ==================== Cost Centers & VAT ====================
function CostCentersVatTab({ canCreate }: { canCreate: boolean }) {
  const [costCenters, setCostCenters] = useState<CostCenterItem[]>([]);
  const [vatRates, setVatRates] = useState<VatRateItem[]>([]);
  const [rules, setRules] = useState<PostingRuleItem[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    setLoading(true);
    Promise.all([
      apiClient.get<CostCenterItem[]>("/accounting/cost-centers"),
      apiClient.get<VatRateItem[]>("/accounting/vat-rates"),
      apiClient.get<PostingRuleItem[]>("/accounting/posting-rules"),
    ]).then(([cc, vat, pr]) => { setCostCenters(cc.data); setVatRates(vat.data); setRules(pr.data); }).finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading) return <div className="flex justify-center py-10"><Loader2 className="animate-spin text-ink-400" /></div>;

  return (
    <div className="space-y-6">
      <div className="card">
        <div className="px-5 py-4 border-b border-ink-100 dark:border-ink-800"><h3 className="font-display font-semibold text-sm">Cost Centers</h3></div>
        {costCenters.length === 0 ? <EmptyState title="No cost centers yet" /> : (
          <div className="overflow-x-auto"><table className="table-shell">
            <thead><tr><th>Code</th><th>Name</th><th>Property</th></tr></thead>
            <tbody>{costCenters.map((c) => <tr key={c.id}><td className="font-mono text-xs">{c.cost_center_code}</td><td className="font-medium">{c.name}</td><td className="text-ink-500">{c.property_title || "—"}</td></tr>)}</tbody>
          </table></div>
        )}
      </div>

      <div className="card">
        <div className="px-5 py-4 border-b border-ink-100 dark:border-ink-800"><h3 className="font-display font-semibold text-sm">VAT Rates</h3></div>
        {vatRates.length === 0 ? <EmptyState title="No VAT rates yet" /> : (
          <div className="overflow-x-auto"><table className="table-shell">
            <thead><tr><th>Code</th><th>Name</th><th>Rate</th><th>GL Account</th></tr></thead>
            <tbody>{vatRates.map((v) => <tr key={v.id}><td className="font-mono text-xs">{v.code}</td><td className="font-medium">{v.name}</td><td>{v.rate_percentage}%</td><td className="text-ink-500">{v.gl_account_name || "—"}</td></tr>)}</tbody>
          </table></div>
        )}
      </div>

      <div className="card">
        <div className="px-5 py-4 border-b border-ink-100 dark:border-ink-800">
          <h3 className="font-display font-semibold text-sm">Automatic Posting Rules</h3>
          <p className="text-xs text-ink-400 mt-0.5">Maps Financial transactions to GL accounts so new transactions post to the ledger automatically.</p>
        </div>
        {rules.length === 0 ? <EmptyState title="No posting rules yet" description="Without a rule, new transactions of that type won't be posted to the GL automatically." /> : (
          <div className="overflow-x-auto"><table className="table-shell">
            <thead><tr><th>Transaction Type</th><th>Category</th><th>Offset Account</th></tr></thead>
            <tbody>{rules.map((r) => <tr key={r.id}><td className="capitalize">{r.transaction_type.replace(/_/g, " ")}</td><td className="text-ink-500">{r.category || "any"}</td><td>{r.offset_account_name}</td></tr>)}</tbody>
          </table></div>
        )}
      </div>
    </div>
  );
}

// ==================== Reports ====================
function ReportsTab() {
  const [reportType, setReportType] = useState<"trial_balance" | "balance_sheet" | "income_statement" | "cash_flow" | "vat">("trial_balance");
  const today = new Date().toISOString().slice(0, 10);
  const monthAgo = new Date(Date.now() - 30 * 86400000).toISOString().slice(0, 10);
  const [asOfDate, setAsOfDate] = useState(today);
  const [dateFrom, setDateFrom] = useState(monthAgo);
  const [dateTo, setDateTo] = useState(today);

  const [trialBalance, setTrialBalance] = useState<TrialBalance | null>(null);
  const [balanceSheet, setBalanceSheet] = useState<BalanceSheet | null>(null);
  const [incomeStatement, setIncomeStatement] = useState<IncomeStatement | null>(null);
  const [cashFlow, setCashFlow] = useState<CashFlow | null>(null);
  const [vatReport, setVatReport] = useState<VatReport | null>(null);
  const [loading, setLoading] = useState(false);

  const runReport = useCallback(() => {
    setLoading(true);
    const done = () => setLoading(false);
    if (reportType === "trial_balance") {
      apiClient.get<TrialBalance>("/accounting/reports/trial-balance", { params: { as_of_date: asOfDate } }).then(({ data }) => setTrialBalance(data)).finally(done);
    } else if (reportType === "balance_sheet") {
      apiClient.get<BalanceSheet>("/accounting/reports/balance-sheet", { params: { as_of_date: asOfDate } }).then(({ data }) => setBalanceSheet(data)).finally(done);
    } else if (reportType === "income_statement") {
      apiClient.get<IncomeStatement>("/accounting/reports/income-statement", { params: { date_from: dateFrom, date_to: dateTo } }).then(({ data }) => setIncomeStatement(data)).finally(done);
    } else if (reportType === "cash_flow") {
      apiClient.get<CashFlow>("/accounting/reports/cash-flow", { params: { date_from: dateFrom, date_to: dateTo } }).then(({ data }) => setCashFlow(data)).finally(done);
    } else if (reportType === "vat") {
      apiClient.get<VatReport>("/accounting/reports/vat", { params: { date_from: dateFrom, date_to: dateTo } }).then(({ data }) => setVatReport(data)).finally(done);
    }
  }, [reportType, asOfDate, dateFrom, dateTo]);

  useEffect(() => { runReport(); }, [runReport]);

  const usesAsOfDate = reportType === "trial_balance" || reportType === "balance_sheet";

  return (
    <div className="space-y-4">
      <div className="card p-4 flex flex-wrap gap-3 items-end">
        <div>
          <label className="label">Report</label>
          <select className="input" value={reportType} onChange={(e) => setReportType(e.target.value as any)}>
            <option value="trial_balance">Trial Balance</option>
            <option value="balance_sheet">Balance Sheet</option>
            <option value="income_statement">Income Statement</option>
            <option value="cash_flow">Cash Flow</option>
            <option value="vat">VAT Report</option>
          </select>
        </div>
        {usesAsOfDate ? (
          <div>
            <label className="label">As Of Date</label>
            <input className="input" type="date" value={asOfDate} onChange={(e) => setAsOfDate(e.target.value)} />
          </div>
        ) : (
          <>
            <div><label className="label">From</label><input className="input" type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} /></div>
            <div><label className="label">To</label><input className="input" type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} /></div>
          </>
        )}
      </div>

      {loading && <div className="flex justify-center py-10"><Loader2 className="animate-spin text-ink-400" /></div>}

      {!loading && reportType === "trial_balance" && trialBalance && (
        <div className="card">
          <div className="flex justify-between items-center px-5 py-4 border-b border-ink-100 dark:border-ink-800">
            <h3 className="font-display font-semibold text-sm">Trial Balance as of {trialBalance.as_of_date}</h3>
            <span className={trialBalance.is_balanced ? "badge-active" : "badge-warn"}>{trialBalance.is_balanced ? "Balanced" : "Out of Balance"}</span>
          </div>
          <div className="overflow-x-auto"><table className="table-shell">
            <thead><tr><th>Code</th><th>Account</th><th>Type</th><th>Debit</th><th>Credit</th></tr></thead>
            <tbody>{trialBalance.lines.map((l) => (
              <tr key={l.account_id}><td className="font-mono text-xs">{l.account_code}</td><td>{l.account_name}</td><td className="capitalize text-ink-500">{l.account_type}</td>
                <td>{Number(l.debit_balance) > 0 ? Number(l.debit_balance).toLocaleString() : ""}</td>
                <td>{Number(l.credit_balance) > 0 ? Number(l.credit_balance).toLocaleString() : ""}</td></tr>
            ))}</tbody>
            <tfoot><tr><td colSpan={3} className="text-right font-medium">Total</td><td className="font-semibold">{Number(trialBalance.total_debit).toLocaleString()}</td><td className="font-semibold">{Number(trialBalance.total_credit).toLocaleString()}</td></tr></tfoot>
          </table></div>
        </div>
      )}

      {!loading && reportType === "balance_sheet" && balanceSheet && (
        <div className="card p-5">
          <div className="flex justify-between items-center mb-4">
            <h3 className="font-display font-semibold text-sm">Balance Sheet as of {balanceSheet.as_of_date}</h3>
            <span className={balanceSheet.is_balanced ? "badge-active" : "badge-warn"}>{balanceSheet.is_balanced ? "Balanced" : "Out of Balance"}</span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {[["Assets", balanceSheet.assets, balanceSheet.total_assets], ["Liabilities", balanceSheet.liabilities, balanceSheet.total_liabilities], ["Equity", balanceSheet.equity, balanceSheet.total_equity]].map(([label, items, total]: any) => (
              <div key={label}>
                <p className="text-xs font-semibold uppercase text-ink-400 mb-2">{label}</p>
                {items.length === 0 && <p className="text-sm text-ink-400">—</p>}
                {items.map((i: any) => <div key={i.account_id} className="flex justify-between text-sm py-1"><span>{i.account_name}</span><span>{Number(i.balance).toLocaleString()}</span></div>)}
                <div className="flex justify-between text-sm font-semibold border-t border-ink-100 dark:border-ink-800 mt-2 pt-2"><span>Total</span><span>{Number(total).toLocaleString()}</span></div>
              </div>
            ))}
          </div>
        </div>
      )}

      {!loading && reportType === "income_statement" && incomeStatement && (
        <div className="card p-5">
          <h3 className="font-display font-semibold text-sm mb-4">Income Statement: {incomeStatement.date_from} – {incomeStatement.date_to}</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-4">
            <div>
              <p className="text-xs font-semibold uppercase text-ink-400 mb-2">Revenue</p>
              {incomeStatement.revenue.map((r) => <div key={r.account_id} className="flex justify-between text-sm py-1"><span>{r.account_name}</span><span>{Number(r.balance).toLocaleString()}</span></div>)}
              <div className="flex justify-between text-sm font-semibold border-t border-ink-100 dark:border-ink-800 mt-2 pt-2"><span>Total Revenue</span><span>{Number(incomeStatement.total_revenue).toLocaleString()}</span></div>
            </div>
            <div>
              <p className="text-xs font-semibold uppercase text-ink-400 mb-2">Expenses</p>
              {incomeStatement.expenses.map((e) => <div key={e.account_id} className="flex justify-between text-sm py-1"><span>{e.account_name}</span><span>{Number(e.balance).toLocaleString()}</span></div>)}
              <div className="flex justify-between text-sm font-semibold border-t border-ink-100 dark:border-ink-800 mt-2 pt-2"><span>Total Expenses</span><span>{Number(incomeStatement.total_expenses).toLocaleString()}</span></div>
            </div>
          </div>
          <div className="flex justify-between text-base font-display font-bold border-t border-ink-200 dark:border-ink-700 pt-3"><span>Net Income</span><span>{Number(incomeStatement.net_income).toLocaleString()}</span></div>
        </div>
      )}

      {!loading && reportType === "cash_flow" && cashFlow && (
        <div className="card p-5">
          <h3 className="font-display font-semibold text-sm mb-1">Cash Flow: {cashFlow.date_from} – {cashFlow.date_to}</h3>
          <p className="text-xs text-ink-400 mb-4">Operating activities only — transfers between own accounts are excluded, as are investing/financing activities (not yet modeled).</p>
          {cashFlow.operating_activities.map((a) => (
            <div key={a.transaction_type} className="flex justify-between text-sm py-1 capitalize"><span>{a.transaction_type.replace(/_/g, " ")}</span><span>{Number(a.total_amount).toLocaleString()}</span></div>
          ))}
          <div className="flex justify-between text-sm font-semibold border-t border-ink-100 dark:border-ink-800 mt-2 pt-2"><span>Net Operating Cash Flow</span><span>{Number(cashFlow.net_operating_cash_flow).toLocaleString()}</span></div>
          <div className="grid grid-cols-2 gap-4 mt-4 text-sm">
            <div className="flex justify-between"><span className="text-ink-500">Opening Balance</span><span>{Number(cashFlow.opening_cash_balance).toLocaleString()}</span></div>
            <div className="flex justify-between"><span className="text-ink-500">Closing Balance</span><span>{Number(cashFlow.closing_cash_balance).toLocaleString()}</span></div>
          </div>
        </div>
      )}

      {!loading && reportType === "vat" && vatReport && (
        <div className="card">
          <div className="px-5 py-4 border-b border-ink-100 dark:border-ink-800"><h3 className="font-display font-semibold text-sm">VAT Report: {vatReport.date_from} – {vatReport.date_to}</h3></div>
          {vatReport.lines.length === 0 ? <EmptyState title="No VAT activity in this period" /> : (
            <div className="overflow-x-auto"><table className="table-shell">
              <thead><tr><th>Rate</th><th>Output VAT</th><th>Input VAT</th><th>Net VAT</th></tr></thead>
              <tbody>{vatReport.lines.map((l) => <tr key={l.vat_rate_id}><td>{l.vat_name} ({l.rate_percentage}%)</td><td>{Number(l.output_vat).toLocaleString()}</td><td>{Number(l.input_vat).toLocaleString()}</td><td className="font-medium">{Number(l.net_vat).toLocaleString()}</td></tr>)}</tbody>
              <tfoot><tr><td className="text-right font-medium">Total</td><td className="font-semibold">{Number(vatReport.total_output_vat).toLocaleString()}</td><td className="font-semibold">{Number(vatReport.total_input_vat).toLocaleString()}</td><td className="font-semibold">{Number(vatReport.total_net_vat).toLocaleString()}</td></tr></tfoot>
            </table></div>
          )}
        </div>
      )}
    </div>
  );
}
