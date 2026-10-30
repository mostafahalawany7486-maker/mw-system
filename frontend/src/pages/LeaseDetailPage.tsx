import { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import apiClient from "@/api/client";
import { useAuth } from "@/context/AuthContext";
import { Modal, EmptyState } from "@/components/ui";
import {
  Loader2, ArrowLeft, FileText, CalendarClock, Paperclip, StickyNote, History,
  Plus, Trash2, CheckCircle2, XCircle, RefreshCcw, AlertTriangle, Pin, Upload,
  Archive, ArchiveRestore,
} from "lucide-react";
import { LeaseAgreementDetail, LeasePaymentInstallment, FinancialAccount, PaginatedResponse } from "@/types";

type TabKey = "overview" | "schedule" | "attachments" | "notes" | "history";

const TABS: { key: TabKey; label: string; icon: typeof FileText }[] = [
  { key: "overview", label: "Overview", icon: FileText },
  { key: "schedule", label: "Payment Schedule", icon: CalendarClock },
  { key: "attachments", label: "Attachments", icon: Paperclip },
  { key: "notes", label: "Notes", icon: StickyNote },
  { key: "history", label: "History", icon: History },
];

const STATUS_TONE: Record<string, string> = {
  draft: "badge-inactive", active: "badge-active", expired: "badge-warn",
  terminated: "badge-inactive", renewed: "badge-active",
};

export default function LeaseDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { hasPermission } = useAuth();
  const [lease, setLease] = useState<LeaseAgreementDetail | null>(null);
  const [tab, setTab] = useState<TabKey>("overview");
  const [loading, setLoading] = useState(true);
  const [actionModal, setActionModal] = useState<"terminate" | "renew" | null>(null);

  const canEdit = hasPermission("leases.edit");
  const canDelete = hasPermission("leases.delete");

  const load = useCallback(() => {
    setLoading(true);
    apiClient.get<LeaseAgreementDetail>(`/leases/${id}`).then(({ data }) => setLease(data)).finally(() => setLoading(false));
  }, [id]);

  useEffect(() => { load(); }, [load]);

  const handleActivate = async () => {
    await apiClient.post(`/leases/${id}/activate`);
    load();
  };

  const handleDelete = async () => {
    if (!confirm("Delete this lease agreement?")) return;
    try {
      await apiClient.delete(`/leases/${id}`);
      navigate("/leases");
    } catch (err: any) {
      alert(err?.response?.data?.detail || "Unable to delete this lease agreement.");
    }
  };

  const handleArchiveToggle = async () => {
    if (!lease) return;
    const archiving = lease.status !== "archived";
    if (archiving && !confirm("Archive this lease? It stays fully intact and searchable — just hidden from the main list until unarchived.")) return;
    await apiClient.post(`/leases/${id}/${archiving ? "archive" : "unarchive"}`);
    load();
  };

  if (loading) return <div className="flex justify-center py-16"><Loader2 className="animate-spin text-ink-400" /></div>;
  if (!lease) return <EmptyState title="Lease agreement not found" />;

  return (
    <div>
      <button className="flex items-center gap-1.5 text-sm text-ink-500 hover:text-ink-800 dark:hover:text-ink-100 mb-4" onClick={() => navigate("/leases")}>
        <ArrowLeft size={15} /> Back to Leases
      </button>

      <div className="flex items-start justify-between flex-wrap gap-4 mb-6">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="font-display text-xl font-bold font-mono">{lease.contract_number}</h1>
            <span className={STATUS_TONE[lease.contract_status] || "badge-inactive"}>{lease.contract_status}</span>
            {lease.is_expiring_soon && <span className="badge-warn"><AlertTriangle size={10} /> Renewal due in {lease.days_until_expiry}d</span>}
          </div>
          <p className="text-sm text-ink-500 mt-1">{lease.owner_display_name} · {lease.property_reference}{lease.unit_number ? ` (Unit ${lease.unit_number})` : ""}</p>
        </div>
        <div className="flex gap-2">
          {canEdit && lease.contract_status === "draft" && (
            <button className="btn-primary" onClick={handleActivate}><CheckCircle2 size={15} /> Activate</button>
          )}
          {canEdit && lease.contract_status === "active" && (
            <>
              <button className="btn-secondary" onClick={() => setActionModal("renew")}><RefreshCcw size={15} /> Renew</button>
              <button className="btn-secondary text-rust-500" onClick={() => setActionModal("terminate")}><XCircle size={15} /> Terminate</button>
            </>
          )}
          {canDelete && (
            <button className="btn-secondary text-rust-500" onClick={handleDelete}><Trash2 size={15} /></button>
          )}
          {canEdit && (
            <button className="btn-secondary" onClick={handleArchiveToggle} title={lease.status === "archived" ? "Unarchive" : "Archive"}>
              {lease.status === "archived" ? <ArchiveRestore size={15} /> : <Archive size={15} />}
            </button>
          )}
        </div>
      </div>

      <div className="flex gap-1 border-b border-ink-100 dark:border-ink-800 mb-6 overflow-x-auto">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`flex items-center gap-1.5 px-3.5 py-2.5 text-sm font-medium border-b-2 whitespace-nowrap transition-colors ${
              tab === t.key
                ? "border-brand-500 text-brand-600 dark:text-brand-400"
                : "border-transparent text-ink-500 hover:text-ink-800 dark:hover:text-ink-100"
            }`}
          >
            <t.icon size={15} /> {t.label}
          </button>
        ))}
      </div>

      {tab === "overview" && <OverviewTab lease={lease} canEdit={canEdit} onSaved={load} />}
      {tab === "schedule" && <ScheduleTab lease={lease} canEdit={canEdit} onChanged={load} />}
      {tab === "attachments" && <AttachmentsTab leaseId={lease.id} canEdit={canEdit} />}
      {tab === "notes" && <NotesTab leaseId={lease.id} />}
      {tab === "history" && <HistoryTab leaseId={lease.id} />}

      {actionModal === "terminate" && (
        <TerminateModal lease={lease} onClose={() => setActionModal(null)} onDone={() => { setActionModal(null); load(); }} />
      )}
      {actionModal === "renew" && (
        <RenewModal lease={lease} onClose={() => setActionModal(null)} onDone={(newLease) => { setActionModal(null); navigate(`/leases/${newLease.id}`); }} />
      )}
    </div>
  );
}

// ==================== Overview ====================
function OverviewTab({ lease, canEdit, onSaved }: { lease: LeaseAgreementDetail; canEdit: boolean; onSaved: () => void }) {
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState<any>(lease);
  const [saving, setSaving] = useState(false);
  const editable = lease.contract_status !== "terminated" && lease.contract_status !== "renewed";

  const startEdit = () => { setForm(lease); setEditing(true); };
  const handleSave = async () => {
    setSaving(true);
    try {
      await apiClient.put(`/leases/${lease.id}`, form);
      setEditing(false);
      onSaved();
    } finally {
      setSaving(false);
    }
  };

  const Field = ({ label, value, name, type = "text" }: { label: string; value: any; name: string; type?: string }) => (
    <div>
      <label className="label">{label}</label>
      {editing ? (
        <input className="input" type={type} value={form[name] ?? ""} onChange={(e) => setForm({ ...form, [name]: e.target.value })} />
      ) : (
        <p className="text-sm text-ink-700 dark:text-ink-200 py-2">{value ?? "—"}</p>
      )}
    </div>
  );

  return (
    <div className="card p-6 max-w-3xl">
      {editable && canEdit && (
        <div className="flex justify-end mb-2">
          {!editing ? (
            <button className="btn-secondary" onClick={startEdit}>Edit</button>
          ) : (
            <div className="flex gap-2">
              <button className="btn-secondary" onClick={() => setEditing(false)}>Cancel</button>
              <button className="btn-primary" disabled={saving} onClick={handleSave}>
                {saving && <Loader2 size={14} className="animate-spin" />} Save
              </button>
            </div>
          )}
        </div>
      )}

      <div className="grid grid-cols-2 gap-4">
        <Field label="Start Date" value={lease.start_date} name="start_date" type="date" />
        <Field label="End Date" value={lease.end_date} name="end_date" type="date" />
        <Field label="Signed Date" value={lease.signed_date} name="signed_date" type="date" />
        <Field label="Renewal Notice (days)" value={lease.renewal_notice_days} name="renewal_notice_days" type="number" />
        <Field label="Rent Amount" value={lease.rent_amount} name="rent_amount" type="number" />
        <div>
          <label className="label">Payment Frequency</label>
          <p className="text-sm text-ink-700 dark:text-ink-200 py-2 capitalize">{lease.payment_frequency.replace(/_/g, " ")}</p>
        </div>
        <Field label="Security Deposit" value={lease.security_deposit_amount} name="security_deposit_amount" type="number" />
        <div>
          <label className="label">Deposit Status</label>
          <p className="text-sm text-ink-700 dark:text-ink-200 py-2 capitalize">{lease.security_deposit_status.replace(/_/g, " ")}</p>
        </div>
      </div>
      <div className="mt-4">
        <label className="label">Property Reference</label>
        <p className="text-sm text-ink-700 dark:text-ink-200 py-2">{lease.property_reference}{lease.unit_number ? ` — Unit ${lease.unit_number}` : ""}</p>
      </div>
      {lease.contract_status === "terminated" && (
        <div className="mt-4 p-3 rounded-md bg-rust-50 dark:bg-rust-500/10">
          <p className="text-sm font-medium text-rust-600">Terminated on {lease.terminated_date}</p>
          <p className="text-sm text-ink-500 mt-1">{lease.termination_reason}</p>
        </div>
      )}
      {lease.renewed_from_lease_id && (
        <p className="text-xs text-ink-400 mt-4">Renewed from lease #{lease.renewed_from_lease_id}</p>
      )}
    </div>
  );
}

// ==================== Payment Schedule ====================
function ScheduleTab({ lease, canEdit, onChanged }: { lease: LeaseAgreementDetail; canEdit: boolean; onChanged: () => void }) {
  const [generating, setGenerating] = useState(false);
  const [addModalOpen, setAddModalOpen] = useState(false);
  const [form, setForm] = useState({ due_date: "", amount: "" });
  const [saving, setSaving] = useState(false);
  const [settleTarget, setSettleTarget] = useState<LeasePaymentInstallment | null>(null);

  const handleGenerate = async (overwrite: boolean) => {
    setGenerating(true);
    try {
      await apiClient.post(`/leases/${lease.id}/installments/generate`, { overwrite_existing: overwrite });
      onChanged();
    } catch (err: any) {
      if (err?.response?.status === 409 && !overwrite) {
        if (confirm("A schedule already exists. Regenerate and replace it?")) {
          await handleGenerate(true);
        }
      }
    } finally {
      setGenerating(false);
    }
  };

  const markPaid = async (inst: LeasePaymentInstallment) => {
    await apiClient.put(`/leases/${lease.id}/installments/${inst.id}`, {
      payment_status: "paid", paid_date: new Date().toISOString().slice(0, 10),
    });
    onChanged();
  };

  const handleDelete = async (inst: LeasePaymentInstallment) => {
    if (!confirm(`Delete installment #${inst.installment_number}?`)) return;
    await apiClient.delete(`/leases/${lease.id}/installments/${inst.id}`);
    onChanged();
  };

  const handleAdd = async () => {
    setSaving(true);
    try {
      await apiClient.post(`/leases/${lease.id}/installments`, form);
      setAddModalOpen(false);
      setForm({ due_date: "", amount: "" });
      onChanged();
    } finally {
      setSaving(false);
    }
  };

  const STATUS_STYLE: Record<string, string> = {
    pending: "badge-inactive", paid: "badge-active", overdue: "badge-warn", cancelled: "badge-inactive",
  };

  return (
    <div className="card">
      <div className="flex justify-between items-center px-5 py-4 border-b border-ink-100 dark:border-ink-800 flex-wrap gap-2">
        <h3 className="font-display font-semibold text-sm">Payment Schedule</h3>
        {canEdit && (
          <div className="flex gap-2">
            <button className="btn-secondary" onClick={() => setAddModalOpen(true)}><Plus size={14} /> Add Installment</button>
            <button className="btn-secondary" disabled={generating} onClick={() => handleGenerate(false)}>
              {generating ? <Loader2 size={14} className="animate-spin" /> : <CalendarClock size={14} />} Auto-Generate
            </button>
          </div>
        )}
      </div>
      {lease.installments.length === 0 && <EmptyState title="No installments yet" description="Auto-generate a schedule from the payment frequency, or add installments manually." />}
      {lease.installments.length > 0 && (
        <div className="overflow-x-auto">
          <table className="table-shell">
            <thead>
              <tr><th>#</th><th>Due Date</th><th>Amount</th><th>Status</th><th>Paid Date</th><th className="text-right">Actions</th></tr>
            </thead>
            <tbody>
              {lease.installments.map((inst) => (
                <tr key={inst.id}>
                  <td>{inst.installment_number}</td>
                  <td>{inst.due_date}</td>
                  <td>{Number(inst.amount).toLocaleString()}</td>
                  <td><span className={STATUS_STYLE[inst.payment_status]}>{inst.payment_status}</span></td>
                  <td className="text-ink-500">{inst.paid_date || "—"}</td>
                  <td className="text-right">
                    {canEdit && (
                      <div className="flex justify-end gap-1">
                        {inst.payment_status === "pending" || inst.payment_status === "overdue" ? (
                          <>
                            <button className="btn-primary !px-2 !py-1" title="Records the real payment (Transaction + receipt) and updates the Owner Ledger balance" onClick={() => setSettleTarget(inst)}>Pay Owner</button>
                            <button className="btn-secondary !px-2 !py-1" title="Just marks this row as paid — no transaction or Owner Ledger entry is created" onClick={() => markPaid(inst)}>Mark Paid Only</button>
                          </>
                        ) : null}
                        <button className="btn-secondary !px-2 !py-1 text-rust-500" onClick={() => handleDelete(inst)}><Trash2 size={13} /></button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Modal
        open={addModalOpen} onClose={() => setAddModalOpen(false)} title="Add Installment"
        footer={<><button className="btn-secondary" onClick={() => setAddModalOpen(false)}>Cancel</button><button className="btn-primary" disabled={saving} onClick={handleAdd}>{saving && <Loader2 size={14} className="animate-spin" />} Save</button></>}
      >
        <div className="space-y-4">
          <div>
            <label className="label">Due Date *</label>
            <input className="input" type="date" required value={form.due_date} onChange={(e) => setForm({ ...form, due_date: e.target.value })} />
          </div>
          <div>
            <label className="label">Amount *</label>
            <input className="input" type="number" min="0" step="0.001" required value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} />
          </div>
        </div>
      </Modal>

      {settleTarget && (
        <SettleOwnerModal
          leaseId={lease.id}
          installment={settleTarget}
          onClose={() => setSettleTarget(null)}
          onDone={() => { setSettleTarget(null); onChanged(); }}
        />
      )}
    </div>
  );
}

function SettleOwnerModal({
  leaseId, installment, onClose, onDone,
}: { leaseId: number; installment: LeasePaymentInstallment; onClose: () => void; onDone: () => void }) {
  const [accounts, setAccounts] = useState<FinancialAccount[]>([]);
  const [accountId, setAccountId] = useState<number | "">("");
  const [paymentMethod, setPaymentMethod] = useState("bank_transfer");
  const [transactionDate, setTransactionDate] = useState(new Date().toISOString().slice(0, 10));
  const [referenceNumber, setReferenceNumber] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiClient.get<PaginatedResponse<FinancialAccount>>("/financial/accounts", { params: { page_size: 100 } })
      .then(({ data }) => { setAccounts(data.items); if (data.items.length) setAccountId(data.items.find((a) => a.is_default)?.id ?? data.items[0].id); });
  }, []);

  const handleSettle = async () => {
    if (!accountId) return;
    setSaving(true);
    setError(null);
    try {
      const { data: result } = await apiClient.post(`/leases/${leaseId}/installments/${installment.id}/settle`, {
        account_id: Number(accountId), transaction_date: transactionDate,
        payment_method: paymentMethod, reference_number: referenceNumber || undefined,
      });
      if (result.receipt_id) window.open(`/receipts/${result.receipt_id}/print`, "_blank", "noopener,noreferrer");
      onDone();
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "Unable to settle this installment.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open
      onClose={onClose}
      title={`Pay Owner — Installment #${installment.installment_number}`}
      footer={
        <>
          <button className="btn-secondary" onClick={onClose}>Cancel</button>
          <button className="btn-primary" disabled={saving || !accountId} onClick={handleSettle}>
            {saving && <Loader2 size={14} className="animate-spin" />} Pay {Number(installment.amount).toLocaleString()}
          </button>
        </>
      }
    >
      {error && <div className="mb-3 text-sm text-rust-500 bg-rust-50 dark:bg-rust-500/10 rounded-md px-3 py-2">{error}</div>}
      <p className="text-sm text-ink-500 mb-4">Records the real Owner Payment transaction (a receipt is generated) and updates this owner's Ledger balance in the same step.</p>
      <div className="space-y-4">
        <div>
          <label className="label">Pay From Account *</label>
          <select className="input" value={accountId} onChange={(e) => setAccountId(Number(e.target.value))}>
            {accounts.map((a) => <option key={a.id} value={a.id}>{a.account_code} — {a.name}</option>)}
          </select>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label">Payment Method</label>
            <select className="input" value={paymentMethod} onChange={(e) => setPaymentMethod(e.target.value)}>
              <option value="bank_transfer">Bank Transfer</option>
              <option value="cash">Cash</option>
              <option value="cheque">Cheque</option>
              <option value="knet">K-Net</option>
              <option value="online">Online</option>
            </select>
          </div>
          <div>
            <label className="label">Payment Date</label>
            <input className="input" type="date" value={transactionDate} onChange={(e) => setTransactionDate(e.target.value)} />
          </div>
        </div>
        <div>
          <label className="label">Reference Number</label>
          <input className="input" value={referenceNumber} onChange={(e) => setReferenceNumber(e.target.value)} placeholder="Optional" />
        </div>
      </div>
    </Modal>
  );
}


// ==================== Attachments ====================
function AttachmentsTab({ leaseId, canEdit }: { leaseId: number; canEdit: boolean }) {
  const [attachments, setAttachments] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [description, setDescription] = useState("");
  const [uploading, setUploading] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    apiClient.get("/attachments", { params: { entity_type: "lease", entity_id: leaseId } })
      .then(({ data }) => setAttachments(data)).finally(() => setLoading(false));
  }, [leaseId]);

  useEffect(() => { load(); }, [load]);

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append("entity_type", "lease");
      formData.append("entity_id", String(leaseId));
      if (description) formData.append("description", description);
      formData.append("file", file);
      await apiClient.post("/attachments", formData, { headers: { "Content-Type": "multipart/form-data" } });
      setModalOpen(false);
      setFile(null);
      setDescription("");
      load();
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (a: any) => {
    if (!confirm(`Delete "${a.file_name}"?`)) return;
    await apiClient.delete(`/attachments/${a.id}`);
    load();
  };

  return (
    <div className="card">
      <div className="flex justify-between items-center px-5 py-4 border-b border-ink-100 dark:border-ink-800">
        <h3 className="font-display font-semibold text-sm">Attachments</h3>
        {canEdit && <button className="btn-secondary" onClick={() => setModalOpen(true)}><Upload size={14} /> Upload File</button>}
      </div>
      {loading && <div className="flex justify-center py-10"><Loader2 className="animate-spin text-ink-400" /></div>}
      {!loading && attachments.length === 0 && <EmptyState title="No attachments yet" description="Upload the signed contract, addenda, or correspondence." />}
      <div className="divide-y divide-ink-50 dark:divide-ink-800/60">
        {attachments.map((a) => (
          <div key={a.id} className="px-5 py-3 flex items-center justify-between">
            <div>
              <a href={a.file_url ?? "#"} target="_blank" rel="noreferrer" className="text-sm font-medium text-brand-600 dark:text-brand-400 hover:underline">{a.file_name}</a>
              {a.description && <p className="text-xs text-ink-400 mt-0.5">{a.description}</p>}
            </div>
            {canEdit && <button className="btn-secondary !px-2 !py-1 text-rust-500" onClick={() => handleDelete(a)}><Trash2 size={13} /></button>}
          </div>
        ))}
      </div>

      <Modal
        open={modalOpen} onClose={() => setModalOpen(false)} title="Upload Attachment"
        footer={<><button className="btn-secondary" onClick={() => setModalOpen(false)}>Cancel</button><button className="btn-primary" disabled={uploading || !file} onClick={handleUpload}>{uploading && <Loader2 size={14} className="animate-spin" />} Upload</button></>}
      >
        <div className="space-y-4">
          <div>
            <label className="label">Description</label>
            <input className="input" value={description} onChange={(e) => setDescription(e.target.value)} />
          </div>
          <div>
            <label className="label">File *</label>
            <input className="input" type="file" onChange={(e) => setFile(e.target.files?.[0] || null)} />
          </div>
        </div>
      </Modal>
    </div>
  );
}

// ==================== Notes ====================
function NotesTab({ leaseId }: { leaseId: number }) {
  const [notes, setNotes] = useState<any[]>([]);
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(true);
  const [posting, setPosting] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    apiClient.get("/notes", { params: { entity_type: "lease", entity_id: leaseId } })
      .then(({ data }) => setNotes(data)).finally(() => setLoading(false));
  }, [leaseId]);

  useEffect(() => { load(); }, [load]);

  const handleAdd = async () => {
    if (!content.trim()) return;
    setPosting(true);
    try {
      await apiClient.post("/notes", { entity_type: "lease", entity_id: leaseId, content, is_pinned: false });
      setContent("");
      load();
    } finally {
      setPosting(false);
    }
  };

  const togglePin = async (note: any) => {
    await apiClient.put(`/notes/${note.id}`, { is_pinned: !note.is_pinned });
    load();
  };

  const handleDelete = async (note: any) => {
    if (!confirm("Delete this note?")) return;
    await apiClient.delete(`/notes/${note.id}`);
    load();
  };

  return (
    <div className="card">
      <div className="p-5 border-b border-ink-100 dark:border-ink-800 flex gap-2">
        <input className="input" placeholder="Add a note…" value={content} onChange={(e) => setContent(e.target.value)} onKeyDown={(e) => e.key === "Enter" && handleAdd()} />
        <button className="btn-primary" disabled={posting || !content.trim()} onClick={handleAdd}>
          {posting ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />} Add
        </button>
      </div>
      {loading && <div className="flex justify-center py-10"><Loader2 className="animate-spin text-ink-400" /></div>}
      {!loading && notes.length === 0 && <EmptyState title="No notes yet" />}
      <div className="divide-y divide-ink-50 dark:divide-ink-800/60">
        {notes.map((n) => (
          <div key={n.id} className="px-5 py-3 flex items-start justify-between gap-3">
            <div className="flex-1">
              <p className="text-sm">{n.content}</p>
              <p className="text-xs text-ink-400 mt-1">{new Date(n.created_at).toLocaleString()}</p>
            </div>
            <div className="flex gap-1 shrink-0">
              <button className={`btn-secondary !px-2 !py-1 ${n.is_pinned ? "text-amber-500" : ""}`} onClick={() => togglePin(n)}><Pin size={13} /></button>
              <button className="btn-secondary !px-2 !py-1 text-rust-500" onClick={() => handleDelete(n)}><Trash2 size={13} /></button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ==================== History ====================
function HistoryTab({ leaseId }: { leaseId: number }) {
  const [entries, setEntries] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiClient.get("/activity-logs", { params: { entity_type: "lease", entity_id: leaseId } })
      .then(({ data }) => setEntries(data)).finally(() => setLoading(false));
  }, [leaseId]);

  return (
    <div className="card">
      {loading && <div className="flex justify-center py-10"><Loader2 className="animate-spin text-ink-400" /></div>}
      {!loading && entries.length === 0 && <EmptyState title="No history yet" />}
      <div className="divide-y divide-ink-50 dark:divide-ink-800/60">
        {entries.map((e) => (
          <div key={e.id} className="px-5 py-3 flex items-center justify-between">
            <div>
              <p className="text-sm">{e.description}</p>
              <p className="text-xs text-ink-400 mt-0.5 capitalize">{e.action.replace(/_/g, " ")}</p>
            </div>
            <span className="text-xs text-ink-400 shrink-0 ml-4">{new Date(e.created_at).toLocaleString()}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ==================== Terminate / Renew modals ====================
function TerminateModal({ lease, onClose, onDone }: { lease: LeaseAgreementDetail; onClose: () => void; onDone: () => void }) {
  const [terminatedDate, setTerminatedDate] = useState(new Date().toISOString().slice(0, 10));
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    setSaving(true);
    setError(null);
    try {
      await apiClient.post(`/leases/${lease.id}/terminate`, { terminated_date: terminatedDate, termination_reason: reason });
      onDone();
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Unable to terminate this lease.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open onClose={onClose} title="Terminate Lease"
      footer={<><button className="btn-secondary" onClick={onClose}>Cancel</button><button className="btn-danger" disabled={saving || !reason} onClick={handleSubmit}>{saving && <Loader2 size={14} className="animate-spin" />} Terminate</button></>}
    >
      {error && <div className="mb-3 text-sm text-rust-500 bg-rust-50 dark:bg-rust-500/10 rounded-md px-3 py-2">{error}</div>}
      <div className="space-y-4">
        <div>
          <label className="label">Termination Date *</label>
          <input className="input" type="date" value={terminatedDate} onChange={(e) => setTerminatedDate(e.target.value)} />
        </div>
        <div>
          <label className="label">Reason *</label>
          <textarea className="input" rows={3} required value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. Owner sold the property" />
        </div>
      </div>
    </Modal>
  );
}

function RenewModal({ lease, onClose, onDone }: { lease: LeaseAgreementDetail; onClose: () => void; onDone: (l: LeaseAgreementDetail) => void }) {
  const [newEndDate, setNewEndDate] = useState("");
  const [rentAmount, setRentAmount] = useState(lease.rent_amount);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    setSaving(true);
    setError(null);
    try {
      const { data } = await apiClient.post<LeaseAgreementDetail>(`/leases/${lease.id}/renew`, {
        new_end_date: newEndDate, rent_amount: rentAmount,
      });
      onDone(data);
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Unable to renew this lease.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open onClose={onClose} title="Renew Lease"
      footer={<><button className="btn-secondary" onClick={onClose}>Cancel</button><button className="btn-primary" disabled={saving || !newEndDate} onClick={handleSubmit}>{saving && <Loader2 size={14} className="animate-spin" />} Renew</button></>}
    >
      {error && <div className="mb-3 text-sm text-rust-500 bg-rust-50 dark:bg-rust-500/10 rounded-md px-3 py-2">{error}</div>}
      <div className="space-y-4">
        <p className="text-sm text-ink-500">Current lease ends {lease.end_date}. A new contract will start the day after and run through the new end date.</p>
        <div>
          <label className="label">New End Date *</label>
          <input className="input" type="date" value={newEndDate} onChange={(e) => setNewEndDate(e.target.value)} />
        </div>
        <div>
          <label className="label">Rent Amount</label>
          <input className="input" type="number" min="0" step="0.001" value={rentAmount} onChange={(e) => setRentAmount(e.target.value)} />
        </div>
      </div>
    </Modal>
  );
}
