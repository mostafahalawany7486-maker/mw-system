import { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import apiClient from "@/api/client";
import { useAuth } from "@/context/AuthContext";
import { Modal, EmptyState } from "@/components/ui";
import {
  Loader2, ArrowLeft, FileText, CalendarClock, Paperclip, StickyNote, History,
  Plus, Trash2, CheckCircle2, XCircle, RefreshCcw, AlertTriangle, Pin, Upload, ShieldBan,
  Archive, ArchiveRestore,
} from "lucide-react";
import { RentalContractDetail, RentalInstallment } from "@/types";

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

export default function RentalDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { hasPermission } = useAuth();
  const [contract, setContract] = useState<RentalContractDetail | null>(null);
  const [tab, setTab] = useState<TabKey>("overview");
  const [loading, setLoading] = useState(true);
  const [actionModal, setActionModal] = useState<"terminate" | "renew" | null>(null);

  const canEdit = hasPermission("rentals.edit");
  const canDelete = hasPermission("rentals.delete");

  const load = useCallback(() => {
    setLoading(true);
    apiClient.get<RentalContractDetail>(`/rentals/${id}`).then(({ data }) => setContract(data)).finally(() => setLoading(false));
  }, [id]);

  useEffect(() => { load(); }, [load]);

  const handleActivate = async () => {
    await apiClient.post(`/rentals/${id}/activate`);
    load();
  };

  const handleDelete = async () => {
    if (!confirm("Delete this rental contract?")) return;
    try {
      await apiClient.delete(`/rentals/${id}`);
      navigate("/rentals");
    } catch (err: any) {
      alert(err?.response?.data?.detail || "Unable to delete this rental contract.");
    }
  };

  const handleArchiveToggle = async () => {
    if (!contract) return;
    const archiving = contract.status !== "archived";
    if (archiving && !confirm("Archive this contract? It stays fully intact and searchable — just hidden from the main list until unarchived.")) return;
    await apiClient.post(`/rentals/${id}/${archiving ? "archive" : "unarchive"}`);
    load();
  };

  if (loading) return <div className="flex justify-center py-16"><Loader2 className="animate-spin text-ink-400" /></div>;
  if (!contract) return <EmptyState title="Rental contract not found" />;

  return (
    <div>
      <button className="flex items-center gap-1.5 text-sm text-ink-500 hover:text-ink-800 dark:hover:text-ink-100 mb-4" onClick={() => navigate("/rentals")}>
        <ArrowLeft size={15} /> Back to Rental Contracts
      </button>

      <div className="flex items-start justify-between flex-wrap gap-4 mb-6">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="font-display text-xl font-bold font-mono">{contract.contract_number}</h1>
            <span className={STATUS_TONE[contract.contract_status] || "badge-inactive"}>{contract.contract_status}</span>
            {contract.is_expiring_soon && <span className="badge-warn"><AlertTriangle size={10} /> Renewal due in {contract.days_until_expiry}d</span>}
            {contract.tenant_is_blacklisted && <span className="badge-warn"><ShieldBan size={10} /> Blacklisted Tenant</span>}
          </div>
          <p className="text-sm text-ink-500 mt-1">{contract.tenant_display_name} · {contract.property_title}{contract.unit_number ? ` (Unit ${contract.unit_number})` : ""}</p>
        </div>
        <div className="flex gap-2">
          {canEdit && contract.contract_status === "draft" && (
            <button className="btn-primary" onClick={handleActivate}><CheckCircle2 size={15} /> Activate</button>
          )}
          {canEdit && contract.contract_status === "active" && (
            <>
              <button className="btn-secondary" onClick={() => setActionModal("renew")}><RefreshCcw size={15} /> Renew</button>
              <button className="btn-secondary text-rust-500" onClick={() => setActionModal("terminate")}><XCircle size={15} /> Terminate</button>
            </>
          )}
          {canDelete && (
            <button className="btn-secondary text-rust-500" onClick={handleDelete}><Trash2 size={15} /></button>
          )}
          {canEdit && (
            <button className="btn-secondary" onClick={handleArchiveToggle} title={contract.status === "archived" ? "Unarchive" : "Archive"}>
              {contract.status === "archived" ? <ArchiveRestore size={15} /> : <Archive size={15} />}
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

      {tab === "overview" && <OverviewTab contract={contract} canEdit={canEdit} onSaved={load} />}
      {tab === "schedule" && <ScheduleTab contract={contract} canEdit={canEdit} onChanged={load} />}
      {tab === "attachments" && <AttachmentsTab contractId={contract.id} canEdit={canEdit} />}
      {tab === "notes" && <NotesTab contractId={contract.id} />}
      {tab === "history" && <HistoryTab contractId={contract.id} />}

      {actionModal === "terminate" && (
        <TerminateModal contract={contract} onClose={() => setActionModal(null)} onDone={() => { setActionModal(null); load(); }} />
      )}
      {actionModal === "renew" && (
        <RenewModal contract={contract} onClose={() => setActionModal(null)} onDone={(newContract) => { setActionModal(null); navigate(`/rentals/${newContract.id}`); }} />
      )}
    </div>
  );
}

// ==================== Overview ====================
function OverviewTab({ contract, canEdit, onSaved }: { contract: RentalContractDetail; canEdit: boolean; onSaved: () => void }) {
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState<any>(contract);
  const [saving, setSaving] = useState(false);
  const editable = contract.contract_status !== "terminated" && contract.contract_status !== "renewed";

  const startEdit = () => { setForm(contract); setEditing(true); };
  const handleSave = async () => {
    setSaving(true);
    try {
      await apiClient.put(`/rentals/${contract.id}`, form);
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
    <div className="space-y-6">
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

        <h3 className="font-display font-semibold text-sm mb-3">Contract Terms</h3>
        <div className="grid grid-cols-2 gap-4 mb-6">
          <Field label="Start Date" value={contract.start_date} name="start_date" type="date" />
          <Field label="End Date" value={contract.end_date} name="end_date" type="date" />
          <Field label="Signed Date" value={contract.signed_date} name="signed_date" type="date" />
          <Field label="Renewal Notice (days)" value={contract.renewal_notice_days} name="renewal_notice_days" type="number" />
          <div>
            <label className="label">Auto-Renew</label>
            {editing ? (
              <label className="flex items-center gap-2 py-2 cursor-pointer">
                <input type="checkbox" checked={!!form.auto_renew} onChange={(e) => setForm({ ...form, auto_renew: e.target.checked })} />
                <span className="text-sm text-ink-500">Renew automatically, no reminder sent</span>
              </label>
            ) : (
              <p className="text-sm text-ink-700 dark:text-ink-200 py-2">
                {contract.auto_renew ? <span className="text-emerald-600 dark:text-emerald-400 font-medium">On — will renew itself automatically</span> : "Off — manual renewal (reminder sent)"}
              </p>
            )}
          </div>
          <Field label="Rent Amount" value={contract.rent_amount} name="rent_amount" type="number" />
          <div>
            <label className="label">Payment Frequency</label>
            <p className="text-sm text-ink-700 dark:text-ink-200 py-2 capitalize">{contract.payment_frequency.replace(/_/g, " ")}</p>
          </div>
          <Field label="Security Deposit" value={contract.security_deposit_amount} name="security_deposit_amount" type="number" />
          <div>
            <label className="label">Deposit Status</label>
            <p className="text-sm text-ink-700 dark:text-ink-200 py-2 capitalize">{contract.security_deposit_status.replace(/_/g, " ")}</p>
          </div>
        </div>

        <h3 className="font-display font-semibold text-sm mb-3">Discount, Tax & Late Fees</h3>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label">Discount</label>
            <p className="text-sm text-ink-700 dark:text-ink-200 py-2 capitalize">
              {contract.discount_type === "none" ? "None" : `${contract.discount_type} (${contract.discount_value}${contract.discount_type === "percentage" ? "%" : ""}) → ${contract.discount_amount_computed}/installment`}
            </p>
            {contract.discount_reason && <p className="text-xs text-ink-400">{contract.discount_reason}</p>}
          </div>
          <div>
            <label className="label">Tax</label>
            <p className="text-sm text-ink-700 dark:text-ink-200 py-2">{contract.tax_rate}% → {contract.tax_amount_computed}/installment</p>
          </div>
          <div>
            <label className="label">Late Fee</label>
            <p className="text-sm text-ink-700 dark:text-ink-200 py-2 capitalize">
              {contract.late_fee_type} — {contract.late_fee_value}{contract.late_fee_type === "percentage" ? "%" : ""}, {contract.late_fee_grace_period_days}-day grace period
            </p>
          </div>
        </div>

        {contract.contract_status === "terminated" && (
          <div className="mt-4 p-3 rounded-md bg-rust-50 dark:bg-rust-500/10">
            <p className="text-sm font-medium text-rust-600">Terminated on {contract.terminated_date}</p>
            <p className="text-sm text-ink-500 mt-1">{contract.termination_reason}</p>
          </div>
        )}
        {contract.renewed_from_contract_id && (
          <p className="text-xs text-ink-400 mt-4">Renewed from contract #{contract.renewed_from_contract_id}</p>
        )}
      </div>
    </div>
  );
}

// ==================== Payment Schedule ====================
function ScheduleTab({ contract, canEdit, onChanged }: { contract: RentalContractDetail; canEdit: boolean; onChanged: () => void }) {
  const [generating, setGenerating] = useState(false);
  const [addModalOpen, setAddModalOpen] = useState(false);
  const [form, setForm] = useState({ due_date: "", amount: "", discount_amount: "0", tax_amount: "0" });
  const [saving, setSaving] = useState(false);

  const handleGenerate = async (overwrite: boolean) => {
    setGenerating(true);
    try {
      await apiClient.post(`/rentals/${contract.id}/installments/generate`, { overwrite_existing: overwrite });
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

  const markPaid = async (inst: RentalInstallment) => {
    await apiClient.put(`/rentals/${contract.id}/installments/${inst.id}`, {
      payment_status: "paid", paid_date: new Date().toISOString().slice(0, 10),
    });
    onChanged();
  };

  const handleDelete = async (inst: RentalInstallment) => {
    if (!confirm(`Delete installment #${inst.installment_number}?`)) return;
    await apiClient.delete(`/rentals/${contract.id}/installments/${inst.id}`);
    onChanged();
  };

  const handleAdd = async () => {
    setSaving(true);
    try {
      await apiClient.post(`/rentals/${contract.id}/installments`, form);
      setAddModalOpen(false);
      setForm({ due_date: "", amount: "", discount_amount: "0", tax_amount: "0" });
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
      {contract.installments.length === 0 && <EmptyState title="No installments yet" description="Auto-generate a schedule from the payment frequency, or add installments manually." />}
      {contract.installments.length > 0 && (
        <div className="overflow-x-auto">
          <table className="table-shell">
            <thead>
              <tr><th>#</th><th>Due Date</th><th>Rent</th><th>Discount</th><th>Tax</th><th>Late Fee</th><th>Total</th><th>Status</th><th className="text-right">Actions</th></tr>
            </thead>
            <tbody>
              {contract.installments.map((inst) => (
                <tr key={inst.id}>
                  <td>{inst.installment_number}</td>
                  <td>{inst.due_date}</td>
                  <td>{Number(inst.amount).toLocaleString()}</td>
                  <td className="text-brand-600">-{Number(inst.discount_amount).toLocaleString()}</td>
                  <td>+{Number(inst.tax_amount).toLocaleString()}</td>
                  <td className={Number(inst.late_fee_amount) > 0 ? "text-rust-500" : ""}>+{Number(inst.late_fee_amount).toLocaleString()}</td>
                  <td className="font-medium">{Number(inst.total_payable).toLocaleString()}</td>
                  <td><span className={STATUS_STYLE[inst.payment_status]}>{inst.payment_status}</span></td>
                  <td className="text-right">
                    {canEdit && (
                      <div className="flex justify-end gap-1">
                        {inst.payment_status === "pending" || inst.payment_status === "overdue" ? (
                          <button className="btn-secondary !px-2 !py-1" title="Just marks this row as paid — no real payment is recorded. Use Rent Collection to actually collect and record this month's payment." onClick={() => markPaid(inst)}>Mark Paid Only</button>
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
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label">Discount</label>
              <input className="input" type="number" min="0" step="0.001" value={form.discount_amount} onChange={(e) => setForm({ ...form, discount_amount: e.target.value })} />
            </div>
            <div>
              <label className="label">Tax</label>
              <input className="input" type="number" min="0" step="0.001" value={form.tax_amount} onChange={(e) => setForm({ ...form, tax_amount: e.target.value })} />
            </div>
          </div>
        </div>
      </Modal>
    </div>
  );
}

// ==================== Attachments ====================
function AttachmentsTab({ contractId, canEdit }: { contractId: number; canEdit: boolean }) {
  const [attachments, setAttachments] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [description, setDescription] = useState("");
  const [uploading, setUploading] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    apiClient.get("/attachments", { params: { entity_type: "rental_contract", entity_id: contractId } })
      .then(({ data }) => setAttachments(data)).finally(() => setLoading(false));
  }, [contractId]);

  useEffect(() => { load(); }, [load]);

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append("entity_type", "rental_contract");
      formData.append("entity_id", String(contractId));
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
function NotesTab({ contractId }: { contractId: number }) {
  const [notes, setNotes] = useState<any[]>([]);
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(true);
  const [posting, setPosting] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    apiClient.get("/notes", { params: { entity_type: "rental_contract", entity_id: contractId } })
      .then(({ data }) => setNotes(data)).finally(() => setLoading(false));
  }, [contractId]);

  useEffect(() => { load(); }, [load]);

  const handleAdd = async () => {
    if (!content.trim()) return;
    setPosting(true);
    try {
      await apiClient.post("/notes", { entity_type: "rental_contract", entity_id: contractId, content, is_pinned: false });
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
function HistoryTab({ contractId }: { contractId: number }) {
  const [entries, setEntries] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiClient.get("/activity-logs", { params: { entity_type: "rental_contract", entity_id: contractId } })
      .then(({ data }) => setEntries(data)).finally(() => setLoading(false));
  }, [contractId]);

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
function TerminateModal({ contract, onClose, onDone }: { contract: RentalContractDetail; onClose: () => void; onDone: () => void }) {
  const [terminatedDate, setTerminatedDate] = useState(new Date().toISOString().slice(0, 10));
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    setSaving(true);
    setError(null);
    try {
      await apiClient.post(`/rentals/${contract.id}/terminate`, { terminated_date: terminatedDate, termination_reason: reason });
      onDone();
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Unable to terminate this contract.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open onClose={onClose} title="Terminate Rental Contract"
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
          <textarea className="input" rows={3} required value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. Tenant moved out early" />
        </div>
      </div>
    </Modal>
  );
}

function RenewModal({ contract, onClose, onDone }: { contract: RentalContractDetail; onClose: () => void; onDone: (c: RentalContractDetail) => void }) {
  const [newEndDate, setNewEndDate] = useState("");
  const [rentAmount, setRentAmount] = useState(contract.rent_amount);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    setSaving(true);
    setError(null);
    try {
      const { data } = await apiClient.post<RentalContractDetail>(`/rentals/${contract.id}/renew`, {
        new_end_date: newEndDate, rent_amount: rentAmount,
      });
      onDone(data);
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Unable to renew this contract.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open onClose={onClose} title="Renew Rental Contract"
      footer={<><button className="btn-secondary" onClick={onClose}>Cancel</button><button className="btn-primary" disabled={saving || !newEndDate} onClick={handleSubmit}>{saving && <Loader2 size={14} className="animate-spin" />} Renew</button></>}
    >
      {error && <div className="mb-3 text-sm text-rust-500 bg-rust-50 dark:bg-rust-500/10 rounded-md px-3 py-2">{error}</div>}
      <div className="space-y-4">
        <p className="text-sm text-ink-500">Current contract ends {contract.end_date}. A new contract will start the day after and run through the new end date.</p>
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
