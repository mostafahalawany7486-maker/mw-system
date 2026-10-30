import { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import apiClient from "@/api/client";
import { useAuth } from "@/context/AuthContext";
import { StatusBadge, Modal, EmptyState, FormField, Pagination } from "@/components/ui";
import {
  Loader2, ArrowLeft, User, Building2, MapPin, Landmark, Contact2, FileText,
  StickyNote, History, Plus, Trash2, Pencil, Star, Upload, AlertTriangle, Pin,
  Wallet, ReceiptText, Undo2, ScrollText, Network,
} from "lucide-react";
import { OwnerDetail, OwnerAddress, OwnerBankAccount, OwnerContact, OwnerDocument, OwnerLedgerEntry, OwnerLedgerDashboard, OwnerStatement, FinancialAccount, PaginatedResponse, PropertyHierarchyTree } from "@/types";
import PropertyHierarchyTreeView from "@/components/PropertyHierarchyTreeView";

type TabKey = "overview" | "addresses" | "bank" | "contacts" | "documents" | "hierarchy" | "ledger" | "notes" | "history";

const TABS: { key: TabKey; label: string; icon: typeof User }[] = [
  { key: "overview", label: "Overview", icon: User },
  { key: "addresses", label: "Addresses", icon: MapPin },
  { key: "bank", label: "Bank Accounts", icon: Landmark },
  { key: "contacts", label: "Contacts", icon: Contact2 },
  { key: "documents", label: "Documents", icon: FileText },
  { key: "hierarchy", label: "Property Tree", icon: Network },
  { key: "ledger", label: "Ledger", icon: Wallet },
  { key: "notes", label: "Notes", icon: StickyNote },
  { key: "history", label: "History", icon: History },
];

export default function OwnerDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { hasPermission } = useAuth();
  const [owner, setOwner] = useState<OwnerDetail | null>(null);
  const [tab, setTab] = useState<TabKey>("overview");
  const [loading, setLoading] = useState(true);

  const canEdit = hasPermission("owners.edit");
  const canDelete = hasPermission("owners.delete");

  const load = useCallback(() => {
    setLoading(true);
    apiClient.get<OwnerDetail>(`/owners/${id}`).then(({ data }) => setOwner(data)).finally(() => setLoading(false));
  }, [id]);

  useEffect(() => { load(); }, [load]);

  const handleDeleteOwner = async () => {
    if (!confirm("Delete this owner? This can be reversed by an administrator.")) return;
    try {
      await apiClient.delete(`/owners/${id}`);
      navigate("/owners");
    } catch (err: any) {
      alert(err?.response?.data?.detail || "Unable to delete this owner.");
    }
  };

  if (loading) return <div className="flex justify-center py-16"><Loader2 className="animate-spin text-ink-400" /></div>;
  if (!owner) return <EmptyState title="Owner not found" />;

  return (
    <div>
      <button className="flex items-center gap-1.5 text-sm text-ink-500 hover:text-ink-800 dark:hover:text-ink-100 mb-4" onClick={() => navigate("/owners")}>
        <ArrowLeft size={15} /> Back to Owners
      </button>

      <div className="flex items-start justify-between flex-wrap gap-4 mb-6">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-full bg-brand-600 text-white flex items-center justify-center">
            {owner.owner_type === "company" ? <Building2 size={20} /> : <User size={20} />}
          </div>
          <div>
            <h1 className="font-display text-xl font-bold">{owner.display_name}</h1>
            <div className="flex items-center gap-2 mt-1 text-xs text-ink-500">
              <span className="font-mono">{owner.owner_code}</span>
              <span>·</span>
              <span className="capitalize">{owner.owner_type}</span>
              <span>·</span>
              <StatusBadge status={owner.status} />
            </div>
          </div>
        </div>
        {canDelete && (
          <button className="btn-secondary text-rust-500" onClick={handleDeleteOwner}>
            <Trash2 size={15} /> Delete Owner
          </button>
        )}
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

      {tab === "overview" && <OverviewTab owner={owner} canEdit={canEdit} onSaved={load} />}
      {tab === "addresses" && <AddressesTab owner={owner} canEdit={canEdit} onChanged={load} />}
      {tab === "bank" && <BankAccountsTab owner={owner} canEdit={canEdit} onChanged={load} />}
      {tab === "contacts" && <ContactsTab owner={owner} canEdit={canEdit} onChanged={load} />}
      {tab === "documents" && <DocumentsTab owner={owner} canEdit={canEdit} onChanged={load} />}
      {tab === "hierarchy" && <HierarchyTab ownerId={owner.id} />}
      {tab === "ledger" && <LedgerTab owner={owner} canEdit={canEdit} />}
      {tab === "notes" && <NotesTab ownerId={owner.id} />}
      {tab === "history" && <HistoryTab ownerId={owner.id} />}
    </div>
  );
}

// ==================== Overview ====================
function OverviewTab({ owner, canEdit, onSaved }: { owner: OwnerDetail; canEdit: boolean; onSaved: () => void }) {
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState<any>(owner);
  const [saving, setSaving] = useState(false);

  const startEdit = () => { setForm(owner); setEditing(true); };

  const handleSave = async () => {
    setSaving(true);
    try {
      await apiClient.put(`/owners/${owner.id}`, form);
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
        <p className="text-sm text-ink-700 dark:text-ink-200 py-2">{value || "—"}</p>
      )}
    </div>
  );

  return (
    <div className="card p-6 max-w-3xl">
      <div className="flex justify-end mb-2">
        {canEdit && !editing && <button className="btn-secondary" onClick={startEdit}><Pencil size={14} /> Edit</button>}
        {editing && (
          <div className="flex gap-2">
            <button className="btn-secondary" onClick={() => setEditing(false)}>Cancel</button>
            <button className="btn-primary" disabled={saving} onClick={handleSave}>
              {saving && <Loader2 size={14} className="animate-spin" />} Save
            </button>
          </div>
        )}
      </div>

      <div className="grid grid-cols-2 gap-4">
        {owner.owner_type === "individual" ? (
          <>
            <Field label="First Name" value={owner.first_name} name="first_name" />
            <Field label="Last Name" value={owner.last_name} name="last_name" />
            <Field label="National ID" value={owner.national_id} name="national_id" />
            <Field label="Date of Birth" value={owner.date_of_birth} name="date_of_birth" type="date" />
          </>
        ) : (
          <>
            <Field label="Company Name" value={owner.company_name} name="company_name" />
            <Field label="Registration Number" value={owner.registration_number} name="registration_number" />
            <Field label="Tax Number" value={owner.tax_number} name="tax_number" />
            <Field label="Contact Person" value={owner.contact_person_name} name="contact_person_name" />
          </>
        )}
        <Field label="Primary Email" value={owner.primary_email} name="primary_email" type="email" />
        <Field label="Primary Phone" value={owner.primary_phone} name="primary_phone" />
        <Field label="Secondary Phone" value={owner.secondary_phone} name="secondary_phone" />
        <Field label="Website" value={owner.website} name="website" />
      </div>
      <div className="mt-4">
        <label className="label">Notes Summary</label>
        {editing ? (
          <textarea className="input" rows={3} value={form.notes_summary ?? ""} onChange={(e) => setForm({ ...form, notes_summary: e.target.value })} />
        ) : (
          <p className="text-sm text-ink-700 dark:text-ink-200 py-2">{owner.notes_summary || "—"}</p>
        )}
      </div>
    </div>
  );
}

// ==================== Addresses ====================
function AddressesTab({ owner, canEdit, onChanged }: { owner: OwnerDetail; canEdit: boolean; onChanged: () => void }) {
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<OwnerAddress | null>(null);
  const [form, setForm] = useState<any>({ address_type: "mailing", line1: "", line2: "", postal_code: "", is_primary: false });
  const [saving, setSaving] = useState(false);

  const openCreate = () => { setEditing(null); setForm({ address_type: "mailing", line1: "", line2: "", postal_code: "", is_primary: false }); setModalOpen(true); };
  const openEdit = (a: OwnerAddress) => { setEditing(a); setForm(a); setModalOpen(true); };

  const handleSave = async () => {
    setSaving(true);
    try {
      if (editing) {
        await apiClient.put(`/owners/${owner.id}/addresses/${editing.id}`, form);
      } else {
        await apiClient.post(`/owners/${owner.id}/addresses`, form);
      }
      setModalOpen(false);
      onChanged();
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (a: OwnerAddress) => {
    if (!confirm("Delete this address?")) return;
    await apiClient.delete(`/owners/${owner.id}/addresses/${a.id}`);
    onChanged();
  };

  return (
    <div className="card">
      <div className="flex justify-between items-center px-5 py-4 border-b border-ink-100 dark:border-ink-800">
        <h3 className="font-display font-semibold text-sm">Addresses</h3>
        {canEdit && <button className="btn-secondary" onClick={openCreate}><Plus size={14} /> Add Address</button>}
      </div>
      {owner.addresses.length === 0 && <EmptyState title="No addresses on file" />}
      <div className="divide-y divide-ink-50 dark:divide-ink-800/60">
        {owner.addresses.map((a) => (
          <div key={a.id} className="px-5 py-3 flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium capitalize">{a.address_type}</span>
                {a.is_primary && <span className="badge-active"><Star size={10} /> Primary</span>}
              </div>
              <p className="text-sm text-ink-500 mt-0.5">{a.line1}{a.line2 ? `, ${a.line2}` : ""}{a.postal_code ? `, ${a.postal_code}` : ""}</p>
            </div>
            {canEdit && (
              <div className="flex gap-1">
                <button className="btn-secondary !px-2 !py-1" onClick={() => openEdit(a)}><Pencil size={13} /></button>
                <button className="btn-secondary !px-2 !py-1 text-rust-500" onClick={() => handleDelete(a)}><Trash2 size={13} /></button>
              </div>
            )}
          </div>
        ))}
      </div>

      <Modal
        open={modalOpen} onClose={() => setModalOpen(false)} title={editing ? "Edit Address" : "Add Address"}
        footer={<><button className="btn-secondary" onClick={() => setModalOpen(false)}>Cancel</button><button className="btn-primary" disabled={saving} onClick={handleSave}>{saving && <Loader2 size={14} className="animate-spin" />} Save</button></>}
      >
        <div className="space-y-4">
          <div>
            <label className="label">Address Type</label>
            <select className="input" value={form.address_type} onChange={(e) => setForm({ ...form, address_type: e.target.value })}>
              <option value="mailing">Mailing</option>
              <option value="permanent">Permanent</option>
              <option value="property">Property</option>
              <option value="other">Other</option>
            </select>
          </div>
          <div>
            <label className="label">Address Line 1 *</label>
            <input className="input" required value={form.line1} onChange={(e) => setForm({ ...form, line1: e.target.value })} />
          </div>
          <div>
            <label className="label">Address Line 2</label>
            <input className="input" value={form.line2 || ""} onChange={(e) => setForm({ ...form, line2: e.target.value })} />
          </div>
          <div>
            <label className="label">Postal Code</label>
            <input className="input" value={form.postal_code || ""} onChange={(e) => setForm({ ...form, postal_code: e.target.value })} />
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={!!form.is_primary} onChange={(e) => setForm({ ...form, is_primary: e.target.checked })} />
            Set as primary address
          </label>
        </div>
      </Modal>
    </div>
  );
}

// ==================== Bank Accounts ====================
function BankAccountsTab({ owner, canEdit, onChanged }: { owner: OwnerDetail; canEdit: boolean; onChanged: () => void }) {
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<OwnerBankAccount | null>(null);
  const [form, setForm] = useState<any>({ bank_name: "", account_holder_name: "", account_number: "", iban: "", swift_code: "", is_primary: false });
  const [saving, setSaving] = useState(false);

  const openCreate = () => { setEditing(null); setForm({ bank_name: "", account_holder_name: "", account_number: "", iban: "", swift_code: "", is_primary: false }); setModalOpen(true); };
  const openEdit = (a: OwnerBankAccount) => { setEditing(a); setForm(a); setModalOpen(true); };

  const handleSave = async () => {
    setSaving(true);
    try {
      if (editing) {
        await apiClient.put(`/owners/${owner.id}/bank-accounts/${editing.id}`, form);
      } else {
        await apiClient.post(`/owners/${owner.id}/bank-accounts`, form);
      }
      setModalOpen(false);
      onChanged();
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (a: OwnerBankAccount) => {
    if (!confirm("Delete this bank account?")) return;
    await apiClient.delete(`/owners/${owner.id}/bank-accounts/${a.id}`);
    onChanged();
  };

  return (
    <div className="card">
      <div className="flex justify-between items-center px-5 py-4 border-b border-ink-100 dark:border-ink-800">
        <h3 className="font-display font-semibold text-sm">Bank Accounts</h3>
        {canEdit && <button className="btn-secondary" onClick={openCreate}><Plus size={14} /> Add Bank Account</button>}
      </div>
      {owner.bank_accounts.length === 0 && <EmptyState title="No bank accounts on file" description="Add bank details to enable payouts to this owner." />}
      <div className="divide-y divide-ink-50 dark:divide-ink-800/60">
        {owner.bank_accounts.map((a) => (
          <div key={a.id} className="px-5 py-3 flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium">{a.bank_name}</span>
                {a.is_primary && <span className="badge-active"><Star size={10} /> Primary</span>}
              </div>
              <p className="text-sm text-ink-500 mt-0.5 font-mono">{a.iban || a.account_number || "—"}</p>
              <p className="text-xs text-ink-400">{a.account_holder_name}</p>
            </div>
            {canEdit && (
              <div className="flex gap-1">
                <button className="btn-secondary !px-2 !py-1" onClick={() => openEdit(a)}><Pencil size={13} /></button>
                <button className="btn-secondary !px-2 !py-1 text-rust-500" onClick={() => handleDelete(a)}><Trash2 size={13} /></button>
              </div>
            )}
          </div>
        ))}
      </div>

      <Modal
        open={modalOpen} onClose={() => setModalOpen(false)} title={editing ? "Edit Bank Account" : "Add Bank Account"}
        footer={<><button className="btn-secondary" onClick={() => setModalOpen(false)}>Cancel</button><button className="btn-primary" disabled={saving} onClick={handleSave}>{saving && <Loader2 size={14} className="animate-spin" />} Save</button></>}
      >
        <div className="space-y-4">
          <div>
            <label className="label">Bank Name *</label>
            <input className="input" required value={form.bank_name} onChange={(e) => setForm({ ...form, bank_name: e.target.value })} />
          </div>
          <div>
            <label className="label">Account Holder Name *</label>
            <input className="input" required value={form.account_holder_name} onChange={(e) => setForm({ ...form, account_holder_name: e.target.value })} />
          </div>
          <div>
            <label className="label">IBAN</label>
            <input className="input font-mono" value={form.iban || ""} onChange={(e) => setForm({ ...form, iban: e.target.value })} />
          </div>
          <div>
            <label className="label">Account Number</label>
            <input className="input font-mono" value={form.account_number || ""} onChange={(e) => setForm({ ...form, account_number: e.target.value })} />
          </div>
          <div>
            <label className="label">SWIFT Code</label>
            <input className="input font-mono" value={form.swift_code || ""} onChange={(e) => setForm({ ...form, swift_code: e.target.value })} />
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={!!form.is_primary} onChange={(e) => setForm({ ...form, is_primary: e.target.checked })} />
            Set as primary account
          </label>
        </div>
      </Modal>
    </div>
  );
}

// ==================== Contacts ====================
function ContactsTab({ owner, canEdit, onChanged }: { owner: OwnerDetail; canEdit: boolean; onChanged: () => void }) {
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<OwnerContact | null>(null);
  const [form, setForm] = useState<any>({ full_name: "", designation: "", email: "", phone: "", is_primary: false });
  const [saving, setSaving] = useState(false);

  const openCreate = () => { setEditing(null); setForm({ full_name: "", designation: "", email: "", phone: "", is_primary: false }); setModalOpen(true); };
  const openEdit = (c: OwnerContact) => { setEditing(c); setForm(c); setModalOpen(true); };

  const handleSave = async () => {
    setSaving(true);
    try {
      if (editing) {
        await apiClient.put(`/owners/${owner.id}/contacts/${editing.id}`, form);
      } else {
        await apiClient.post(`/owners/${owner.id}/contacts`, form);
      }
      setModalOpen(false);
      onChanged();
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (c: OwnerContact) => {
    if (!confirm("Delete this contact?")) return;
    await apiClient.delete(`/owners/${owner.id}/contacts/${c.id}`);
    onChanged();
  };

  return (
    <div className="card">
      <div className="flex justify-between items-center px-5 py-4 border-b border-ink-100 dark:border-ink-800">
        <h3 className="font-display font-semibold text-sm">Contacts</h3>
        {canEdit && <button className="btn-secondary" onClick={openCreate}><Plus size={14} /> Add Contact</button>}
      </div>
      {owner.contacts.length === 0 && <EmptyState title="No additional contacts" />}
      <div className="divide-y divide-ink-50 dark:divide-ink-800/60">
        {owner.contacts.map((c) => (
          <div key={c.id} className="px-5 py-3 flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium">{c.full_name}</span>
                {c.is_primary && <span className="badge-active"><Star size={10} /> Primary</span>}
              </div>
              <p className="text-xs text-ink-400">{c.designation || "—"}</p>
              <p className="text-sm text-ink-500 mt-0.5">{c.email || "—"} {c.phone ? `· ${c.phone}` : ""}</p>
            </div>
            {canEdit && (
              <div className="flex gap-1">
                <button className="btn-secondary !px-2 !py-1" onClick={() => openEdit(c)}><Pencil size={13} /></button>
                <button className="btn-secondary !px-2 !py-1 text-rust-500" onClick={() => handleDelete(c)}><Trash2 size={13} /></button>
              </div>
            )}
          </div>
        ))}
      </div>

      <Modal
        open={modalOpen} onClose={() => setModalOpen(false)} title={editing ? "Edit Contact" : "Add Contact"}
        footer={<><button className="btn-secondary" onClick={() => setModalOpen(false)}>Cancel</button><button className="btn-primary" disabled={saving} onClick={handleSave}>{saving && <Loader2 size={14} className="animate-spin" />} Save</button></>}
      >
        <div className="space-y-4">
          <div>
            <label className="label">Full Name *</label>
            <input className="input" required value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
          </div>
          <div>
            <label className="label">Designation</label>
            <input className="input" value={form.designation || ""} onChange={(e) => setForm({ ...form, designation: e.target.value })} />
          </div>
          <div>
            <label className="label">Email</label>
            <input className="input" type="email" value={form.email || ""} onChange={(e) => setForm({ ...form, email: e.target.value })} />
          </div>
          <div>
            <label className="label">Phone</label>
            <input className="input" value={form.phone || ""} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={!!form.is_primary} onChange={(e) => setForm({ ...form, is_primary: e.target.checked })} />
            Set as primary contact
          </label>
        </div>
      </Modal>
    </div>
  );
}

// ==================== Documents ====================
function DocumentsTab({ owner, canEdit, onChanged }: { owner: OwnerDetail; canEdit: boolean; onChanged: () => void }) {
  const [modalOpen, setModalOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [documentType, setDocumentType] = useState("id_card");
  const [documentNumber, setDocumentNumber] = useState("");
  const [expiryDate, setExpiryDate] = useState("");
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append("document_type", documentType);
      if (documentNumber) formData.append("document_number", documentNumber);
      if (expiryDate) formData.append("expiry_date", expiryDate);
      formData.append("file", file);
      await apiClient.post(`/owners/${owner.id}/documents`, formData, { headers: { "Content-Type": "multipart/form-data" } });
      setModalOpen(false);
      setFile(null);
      setDocumentNumber("");
      setExpiryDate("");
      onChanged();
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Upload failed. Check the file type and size.");
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (d: OwnerDocument) => {
    if (!confirm(`Delete "${d.file_name}"?`)) return;
    await apiClient.delete(`/owners/${owner.id}/documents/${d.id}`);
    onChanged();
  };

  return (
    <div className="card">
      <div className="flex justify-between items-center px-5 py-4 border-b border-ink-100 dark:border-ink-800">
        <h3 className="font-display font-semibold text-sm">Documents</h3>
        {canEdit && <button className="btn-secondary" onClick={() => setModalOpen(true)}><Upload size={14} /> Upload Document</button>}
      </div>
      {owner.documents.length === 0 && <EmptyState title="No documents uploaded" description="Upload ID, trade license, POA, or other legal documents." />}
      <div className="divide-y divide-ink-50 dark:divide-ink-800/60">
        {owner.documents.map((d) => (
          <div key={d.id} className="px-5 py-3 flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2">
                <a href={d.file_url ?? "#"} target="_blank" rel="noreferrer" className="text-sm font-medium text-brand-600 dark:text-brand-400 hover:underline">
                  {d.file_name}
                </a>
                {d.is_expired && <span className="badge-warn"><AlertTriangle size={10} /> Expired</span>}
              </div>
              <p className="text-xs text-ink-400 capitalize mt-0.5">
                {d.document_type.replace(/_/g, " ")} {d.document_number ? `· ${d.document_number}` : ""} {d.expiry_date ? `· expires ${d.expiry_date}` : ""}
              </p>
            </div>
            {canEdit && (
              <button className="btn-secondary !px-2 !py-1 text-rust-500" onClick={() => handleDelete(d)}><Trash2 size={13} /></button>
            )}
          </div>
        ))}
      </div>

      <Modal
        open={modalOpen} onClose={() => setModalOpen(false)} title="Upload Document"
        footer={<><button className="btn-secondary" onClick={() => setModalOpen(false)}>Cancel</button><button className="btn-primary" disabled={uploading || !file} onClick={handleUpload}>{uploading && <Loader2 size={14} className="animate-spin" />} Upload</button></>}
      >
        {error && <div className="mb-3 text-sm text-rust-500 bg-rust-50 dark:bg-rust-500/10 rounded-md px-3 py-2">{error}</div>}
        <div className="space-y-4">
          <div>
            <label className="label">Document Type</label>
            <select className="input" value={documentType} onChange={(e) => setDocumentType(e.target.value)}>
              <option value="id_card">ID Card</option>
              <option value="passport">Passport</option>
              <option value="trade_license">Trade License</option>
              <option value="tax_certificate">Tax Certificate</option>
              <option value="poa">Power of Attorney</option>
              <option value="other">Other</option>
            </select>
          </div>
          <div>
            <label className="label">Document Number</label>
            <input className="input" value={documentNumber} onChange={(e) => setDocumentNumber(e.target.value)} />
          </div>
          <div>
            <label className="label">Expiry Date</label>
            <input className="input" type="date" value={expiryDate} onChange={(e) => setExpiryDate(e.target.value)} />
          </div>
          <div>
            <label className="label">File *</label>
            <input className="input" type="file" onChange={(e) => setFile(e.target.files?.[0] || null)} />
            <p className="text-xs text-ink-400 mt-1">PDF, images, or Office documents up to 25MB.</p>
          </div>
        </div>
      </Modal>
    </div>
  );
}

// ==================== Owner Ledger ====================
const LEDGER_TYPE_LABELS: Record<string, string> = {
  rental_income: "Rental Income", management_fee: "Management Fee", maintenance_expense: "Maintenance Expense",
  recoverable_expense: "Recoverable Expense", recovered_amount: "Recovered Amount", owner_payment: "Owner Payment",
  adjustment: "Adjustment", opening_balance: "Opening Balance", closing_balance: "Closing Balance",
};
const EXPENSE_CATEGORIES = ["maintenance", "municipality_fees", "government_fees", "electricity", "water", "emergency_repairs", "insurance", "other"];
const PAYMENT_METHODS = ["cash", "bank_transfer", "cheque", "knet", "card", "online"];

function money(v: string | number) {
  return Number(v).toLocaleString(undefined, { minimumFractionDigits: 3 });
}

function LedgerTab({ owner }: { owner: OwnerDetail; canEdit: boolean }) {
  const { hasPermission } = useAuth();
  const canCreate = hasPermission("owner_ledger.create");
  const canReverse = hasPermission("owner_ledger.edit");

  const [dashboard, setDashboard] = useState<OwnerLedgerDashboard | null>(null);
  const [entries, setEntries] = useState<PaginatedResponse<OwnerLedgerEntry> | null>(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [expenseOpen, setExpenseOpen] = useState(false);
  const [reimbursementOpen, setReimbursementOpen] = useState(false);
  const [manualOpen, setManualOpen] = useState(false);
  const [statementOpen, setStatementOpen] = useState(false);
  const [payOwnerOpen, setPayOwnerOpen] = useState(false);
  const [reverseTarget, setReverseTarget] = useState<OwnerLedgerEntry | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    Promise.all([
      apiClient.get<OwnerLedgerDashboard>(`/owner-ledger/${owner.id}/dashboard`),
      apiClient.get<PaginatedResponse<OwnerLedgerEntry>>(`/owner-ledger/${owner.id}`, { params: { page, page_size: 15 } }),
    ]).then(([d, e]) => { setDashboard(d.data); setEntries(e.data); }).finally(() => setLoading(false));
  }, [owner.id, page]);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="space-y-4">
      {dashboard && (
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          <SummaryCard label="Current Balance" value={money(dashboard.current_balance)} tone={Number(dashboard.current_balance) < 0 ? "text-rust-500" : "text-brand-600"} />
          <SummaryCard label="Outstanding Recoverable" value={money(dashboard.outstanding_recoverable_expenses)} tone="text-amber-600" />
          <SummaryCard label="Monthly Income" value={money(dashboard.monthly_income)} />
          <SummaryCard label="Monthly Expenses" value={money(dashboard.monthly_expenses)} />
          <SummaryCard label="Payments Made" value={money(dashboard.payments_made)} />
          <SummaryCard label="Payments Received" value={money(dashboard.payments_received)} />
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        {canCreate && dashboard && Number(dashboard.current_balance) > 0 && (
          <button className="btn-primary" onClick={() => setPayOwnerOpen(true)}><Wallet size={15} /> Pay Owner ({money(dashboard.current_balance)})</button>
        )}
        {canCreate && (
          <>
            <button className="btn-secondary" onClick={() => setExpenseOpen(true)}><ReceiptText size={15} /> Recoverable Expense</button>
            <button className="btn-secondary" onClick={() => setReimbursementOpen(true)}><Wallet size={15} /> Record Reimbursement</button>
            <button className="btn-secondary" onClick={() => setManualOpen(true)}><Plus size={15} /> Manual Entry</button>
          </>
        )}
        <button className="btn-secondary" onClick={() => setStatementOpen(true)}><ScrollText size={15} /> Owner Statement</button>
      </div>

      <div className="card">
        {loading && <div className="flex justify-center py-10"><Loader2 className="animate-spin text-ink-400" /></div>}
        {!loading && entries && entries.items.length === 0 && (
          <EmptyState icon={Wallet} title="No ledger entries yet" description="Recoverable expenses, reimbursements, and manual entries will appear here." />
        )}
        {!loading && entries && entries.items.length > 0 && (
          <div className="overflow-x-auto">
            <table className="table-shell">
              <thead>
                <tr><th>Date</th><th>Type</th><th>Description</th><th>Debit</th><th>Credit</th><th>Balance</th><th>Status</th>{canReverse && <th></th>}</tr>
              </thead>
              <tbody>
                {entries.items.map((e) => (
                  <tr key={e.id}>
                    <td className="text-ink-500">{e.transaction_date}</td>
                    <td>{LEDGER_TYPE_LABELS[e.transaction_type] || e.transaction_type}</td>
                    <td className="max-w-[240px] truncate" title={e.description}>{e.description}</td>
                    <td className="text-rust-500">{Number(e.debit) > 0 ? money(e.debit) : "—"}</td>
                    <td className="text-brand-600">{Number(e.credit) > 0 ? money(e.credit) : "—"}</td>
                    <td className="font-medium">{money(e.balance)}</td>
                    <td>
                      {e.entry_status === "reversed" && <span className="badge-inactive">Reversed</span>}
                      {e.entry_status === "reversal" && <span className="badge-warn">Reversal</span>}
                      {e.entry_status === "active" && <span className="badge-active">Active</span>}
                    </td>
                    {canReverse && (
                      <td>
                        {e.entry_status === "active" && (
                          <button className="btn-secondary !px-2 !py-1" title="Reverse this entry" onClick={() => setReverseTarget(e)}>
                            <Undo2 size={13} />
                          </button>
                        )}
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {entries && <Pagination page={page} totalPages={Math.ceil(entries.total / 15)} onChange={setPage} />}
      </div>

      {expenseOpen && <RecoverableExpenseModal ownerId={owner.id} onClose={() => setExpenseOpen(false)} onSaved={load} />}
      {reimbursementOpen && <ReimbursementModal ownerId={owner.id} onClose={() => setReimbursementOpen(false)} onSaved={load} />}
      {manualOpen && <ManualEntryModal ownerId={owner.id} onClose={() => setManualOpen(false)} onSaved={load} />}
      {statementOpen && <StatementModal ownerId={owner.id} onClose={() => setStatementOpen(false)} />}
      {payOwnerOpen && dashboard && (
        <PayOwnerModal ownerId={owner.id} ownerName={owner.display_name} currentBalance={dashboard.current_balance} onClose={() => setPayOwnerOpen(false)} onDone={() => { setPayOwnerOpen(false); load(); }} />
      )}
      {reverseTarget && <ReverseEntryModal entry={reverseTarget} onClose={() => setReverseTarget(null)} onReversed={load} />}
    </div>
  );
}

function SummaryCard({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className="card p-4">
      <p className="text-xs text-ink-500">{label}</p>
      <p className={`text-lg font-display font-bold mt-1 ${tone || ""}`}>{value}</p>
    </div>
  );
}

function RecoverableExpenseModal({ ownerId, onClose, onSaved }: { ownerId: number; onClose: () => void; onSaved: () => void }) {
  const [accounts, setAccounts] = useState<FinancialAccount[]>([]);
  const [accountId, setAccountId] = useState<number | "">("");
  const [amount, setAmount] = useState("");
  const [category, setCategory] = useState("maintenance");
  const [description, setDescription] = useState("");
  const [paymentDate, setPaymentDate] = useState(new Date().toISOString().slice(0, 10));
  const [referenceNumber, setReferenceNumber] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    apiClient.get<PaginatedResponse<FinancialAccount>>("/financial/accounts", { params: { page_size: 100 } }).then(({ data }) => setAccounts(data.items));
  }, []);

  const submit = async () => {
    if (!accountId || !amount || !description.trim()) { setError("Account, amount, and description are required."); return; }
    setSubmitting(true);
    setError("");
    try {
      await apiClient.post("/owner-ledger/recoverable-expense", {
        owner_id: ownerId, account_id: accountId, amount, expense_category: category,
        description, payment_date: paymentDate, reference_number: referenceNumber || undefined,
      });
      onSaved();
      onClose();
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Could not record this expense.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal open onClose={onClose} title="Recoverable Expense" footer={
      <>
        <button className="btn-secondary" onClick={onClose}>Cancel</button>
        <button className="btn-primary" onClick={submit} disabled={submitting}>
          {submitting ? <Loader2 size={16} className="animate-spin" /> : <ReceiptText size={16} />} Record Expense
        </button>
      </>
    }>
      <div className="space-y-3">
        <p className="text-xs text-ink-400 bg-ink-50 dark:bg-ink-800/60 rounded-md p-2">
          For company-paid expenses on this owner's behalf (municipality fees, emergency repairs, insurance, ...). This is never recorded as a company operating expense — it increases what the owner owes back.
        </p>
        {error && <p className="text-xs text-rust-500">{error}</p>}
        <FormField label="Paid From Account" required>
          <select className="input" value={accountId} onChange={(e) => setAccountId(Number(e.target.value))}>
            <option value="">Select account…</option>
            {accounts.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
          </select>
        </FormField>
        <FormField label="Category" required>
          <select className="input" value={category} onChange={(e) => setCategory(e.target.value)}>
            {EXPENSE_CATEGORIES.map((c) => <option key={c} value={c}>{c.replace(/_/g, " ")}</option>)}
          </select>
        </FormField>
        <FormField label="Amount" required>
          <input className="input" type="number" min="0" step="0.001" value={amount} onChange={(e) => setAmount(e.target.value)} />
        </FormField>
        <FormField label="Description" required>
          <input className="input" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="e.g. Annual municipality fee" />
        </FormField>
        <FormField label="Payment Date" required>
          <input className="input" type="date" value={paymentDate} onChange={(e) => setPaymentDate(e.target.value)} />
        </FormField>
        <FormField label="Reference Number">
          <input className="input" value={referenceNumber} onChange={(e) => setReferenceNumber(e.target.value)} />
        </FormField>
      </div>
    </Modal>
  );
}

function ReimbursementModal({ ownerId, onClose, onSaved }: { ownerId: number; onClose: () => void; onSaved: () => void }) {
  const [accounts, setAccounts] = useState<FinancialAccount[]>([]);
  const [accountId, setAccountId] = useState<number | "">("");
  const [amount, setAmount] = useState("");
  const [paymentMethod, setPaymentMethod] = useState("bank_transfer");
  const [paymentDate, setPaymentDate] = useState(new Date().toISOString().slice(0, 10));
  const [referenceNumber, setReferenceNumber] = useState("");
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    apiClient.get<PaginatedResponse<FinancialAccount>>("/financial/accounts", { params: { page_size: 100 } }).then(({ data }) => setAccounts(data.items));
  }, []);

  const submit = async () => {
    if (!accountId || !amount) { setError("Account and amount are required."); return; }
    setSubmitting(true);
    setError("");
    try {
      await apiClient.post("/owner-ledger/recovered-payment", {
        owner_id: ownerId, account_id: accountId, amount, payment_method: paymentMethod,
        payment_date: paymentDate, reference_number: referenceNumber || undefined, notes: notes || undefined,
      });
      onSaved();
      onClose();
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Could not record this reimbursement.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal open onClose={onClose} title="Record Owner Reimbursement" footer={
      <>
        <button className="btn-secondary" onClick={onClose}>Cancel</button>
        <button className="btn-primary" onClick={submit} disabled={submitting}>
          {submitting ? <Loader2 size={16} className="animate-spin" /> : <Wallet size={16} />} Record Reimbursement
        </button>
      </>
    }>
      <div className="space-y-3">
        <p className="text-xs text-ink-400 bg-ink-50 dark:bg-ink-800/60 rounded-md p-2">
          When the owner pays the company back for previously recorded recoverable expenses. Reduces the outstanding recoverable balance.
        </p>
        {error && <p className="text-xs text-rust-500">{error}</p>}
        <FormField label="Received Into Account" required>
          <select className="input" value={accountId} onChange={(e) => setAccountId(Number(e.target.value))}>
            <option value="">Select account…</option>
            {accounts.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
          </select>
        </FormField>
        <FormField label="Amount" required>
          <input className="input" type="number" min="0" step="0.001" value={amount} onChange={(e) => setAmount(e.target.value)} />
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
    </Modal>
  );
}

function PayOwnerModal({
  ownerId, ownerName, currentBalance, onClose, onDone,
}: { ownerId: number; ownerName: string; currentBalance: string; onClose: () => void; onDone: () => void }) {
  const [accounts, setAccounts] = useState<FinancialAccount[]>([]);
  const [accountId, setAccountId] = useState<number | "">("");
  const [amount, setAmount] = useState(currentBalance);
  const [paymentMethod, setPaymentMethod] = useState("bank_transfer");
  const [transactionDate, setTransactionDate] = useState(new Date().toISOString().slice(0, 10));
  const [referenceNumber, setReferenceNumber] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    apiClient.get<PaginatedResponse<FinancialAccount>>("/financial/accounts", { params: { page_size: 100 } })
      .then(({ data }) => { setAccounts(data.items); if (data.items.length) setAccountId(data.items.find((a) => a.is_default)?.id ?? data.items[0].id); });
  }, []);

  const submit = async () => {
    if (!accountId || !amount) { setError("Account and amount are required."); return; }
    setSubmitting(true);
    setError("");
    try {
      const { data: result } = await apiClient.post(`/owner-ledger/${ownerId}/pay`, {
        account_id: accountId, amount, payment_method: paymentMethod,
        transaction_date: transactionDate, reference_number: referenceNumber || undefined,
      });
      if (result.receipt_id) window.open(`/receipts/${result.receipt_id}/print`, "_blank", "noopener,noreferrer");
      onDone();
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Could not pay this owner.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal open onClose={onClose} title={`Pay Owner — ${ownerName}`} footer={
      <>
        <button className="btn-secondary" onClick={onClose}>Cancel</button>
        <button className="btn-primary" onClick={submit} disabled={submitting}>
          {submitting ? <Loader2 size={16} className="animate-spin" /> : <Wallet size={16} />} Pay {money(amount)}
        </button>
      </>
    }>
      <div className="space-y-3">
        <p className="text-xs text-ink-400 bg-ink-50 dark:bg-ink-800/60 rounded-md p-2">
          Pays down this owner's current outstanding balance ({money(currentBalance)}) directly — records the real
          transaction (a receipt is generated) and reduces this balance in the same step. For a partial payment,
          just change the amount below.
        </p>
        {error && <p className="text-xs text-rust-500">{error}</p>}
        <FormField label="Pay From Account" required>
          <select className="input" value={accountId} onChange={(e) => setAccountId(Number(e.target.value))}>
            <option value="">Select account…</option>
            {accounts.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
          </select>
        </FormField>
        <FormField label="Amount" required>
          <input className="input" type="number" min="0" step="0.001" max={currentBalance} value={amount} onChange={(e) => setAmount(e.target.value)} />
        </FormField>
        <FormField label="Payment Method" required>
          <select className="input" value={paymentMethod} onChange={(e) => setPaymentMethod(e.target.value)}>
            {PAYMENT_METHODS.map((m) => <option key={m} value={m}>{m.replace(/_/g, " ")}</option>)}
          </select>
        </FormField>
        <FormField label="Payment Date" required>
          <input className="input" type="date" value={transactionDate} onChange={(e) => setTransactionDate(e.target.value)} />
        </FormField>
        <FormField label="Reference Number">
          <input className="input" value={referenceNumber} onChange={(e) => setReferenceNumber(e.target.value)} />
        </FormField>
      </div>
    </Modal>
  );
}

const MANUAL_ENTRY_TYPES = ["rental_income", "management_fee", "adjustment", "opening_balance"];

function ManualEntryModal({ ownerId, onClose, onSaved }: { ownerId: number; onClose: () => void; onSaved: () => void }) {
  const [transactionType, setTransactionType] = useState("adjustment");
  const [side, setSide] = useState<"debit" | "credit">("credit");
  const [amount, setAmount] = useState("");
  const [description, setDescription] = useState("");
  const [transactionDate, setTransactionDate] = useState(new Date().toISOString().slice(0, 10));
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const submit = async () => {
    if (!amount || !description.trim()) { setError("Amount and description are required."); return; }
    setSubmitting(true);
    setError("");
    try {
      await apiClient.post("/owner-ledger", {
        owner_id: ownerId, transaction_date: transactionDate, transaction_type: transactionType,
        description, debit: side === "debit" ? amount : "0", credit: side === "credit" ? amount : "0",
      });
      onSaved();
      onClose();
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Could not post this entry.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal open onClose={onClose} title="Manual Ledger Entry" footer={
      <>
        <button className="btn-secondary" onClick={onClose}>Cancel</button>
        <button className="btn-primary" onClick={submit} disabled={submitting}>
          {submitting ? <Loader2 size={16} className="animate-spin" /> : <Plus size={16} />} Post Entry
        </button>
      </>
    }>
      <div className="space-y-3">
        {error && <p className="text-xs text-rust-500">{error}</p>}
        <FormField label="Type" required>
          <select className="input" value={transactionType} onChange={(e) => setTransactionType(e.target.value)}>
            {MANUAL_ENTRY_TYPES.map((t) => <option key={t} value={t}>{LEDGER_TYPE_LABELS[t]}</option>)}
          </select>
        </FormField>
        <FormField label="Direction" required hint="Credit increases what the company owes the owner; debit decreases it.">
          <select className="input" value={side} onChange={(e) => setSide(e.target.value as "debit" | "credit")}>
            <option value="credit">Credit (in the owner's favor)</option>
            <option value="debit">Debit (reduces balance owed)</option>
          </select>
        </FormField>
        <FormField label="Amount" required>
          <input className="input" type="number" min="0" step="0.001" value={amount} onChange={(e) => setAmount(e.target.value)} />
        </FormField>
        <FormField label="Description" required>
          <input className="input" value={description} onChange={(e) => setDescription(e.target.value)} />
        </FormField>
        <FormField label="Date" required>
          <input className="input" type="date" value={transactionDate} onChange={(e) => setTransactionDate(e.target.value)} />
        </FormField>
      </div>
    </Modal>
  );
}

function ReverseEntryModal({ entry, onClose, onReversed }: { entry: OwnerLedgerEntry; onClose: () => void; onReversed: () => void }) {
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const submit = async () => {
    if (!reason.trim()) { setError("A reason is required to reverse an entry."); return; }
    setSubmitting(true);
    setError("");
    try {
      await apiClient.post(`/owner-ledger/${entry.id}/reverse`, { reason });
      onReversed();
      onClose();
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Could not reverse this entry.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal open onClose={onClose} title={`Reverse Entry — ${LEDGER_TYPE_LABELS[entry.transaction_type] || entry.transaction_type}`} footer={
      <>
        <button className="btn-secondary" onClick={onClose}>Cancel</button>
        <button className="btn-primary" onClick={submit} disabled={submitting}>
          {submitting ? <Loader2 size={16} className="animate-spin" /> : <Undo2 size={16} />} Reverse
        </button>
      </>
    }>
      <div className="space-y-3">
        <p className="text-xs text-ink-400 bg-ink-50 dark:bg-ink-800/60 rounded-md p-2">
          This never deletes or edits the original entry — it appends a new, opposite entry dated today and links the two together. Fully auditable.
        </p>
        {error && <p className="text-xs text-rust-500">{error}</p>}
        <FormField label="Original Amount">
          <p className="text-sm text-ink-700 dark:text-ink-200 py-2">{Number(entry.debit) > 0 ? `Debit ${money(entry.debit)}` : `Credit ${money(entry.credit)}`}</p>
        </FormField>
        <FormField label="Reason" required>
          <input className="input" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. Entered in error" />
        </FormField>
      </div>
    </Modal>
  );
}

function StatementModal({ ownerId, onClose }: { ownerId: number; onClose: () => void }) {
  const today = new Date();
  const [dateFrom, setDateFrom] = useState(new Date(today.getFullYear(), today.getMonth(), 1).toISOString().slice(0, 10));
  const [dateTo, setDateTo] = useState(today.toISOString().slice(0, 10));
  const [statement, setStatement] = useState<OwnerStatement | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const generate = async () => {
    setLoading(true);
    setError("");
    try {
      const { data } = await apiClient.get<OwnerStatement>(`/owner-statement/${ownerId}`, { params: { date_from: dateFrom, date_to: dateTo } });
      setStatement(data);
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Could not generate the statement.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal open onClose={onClose} title="Owner Statement" footer={<button className="btn-secondary" onClick={onClose}>Close</button>}>
      <div className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <FormField label="From"><input className="input" type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} /></FormField>
          <FormField label="To"><input className="input" type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} /></FormField>
        </div>
        <button className="btn-primary w-full justify-center" onClick={generate} disabled={loading}>
          {loading ? <Loader2 size={16} className="animate-spin" /> : <ScrollText size={16} />} Generate
        </button>
        {error && <p className="text-xs text-rust-500">{error}</p>}
        {statement && (
          <div className="space-y-1 text-sm border-t border-ink-100 dark:border-ink-800 pt-3">
            <StatementLine label="Opening Balance" value={statement.opening_balance} />
            <StatementLine label="Rental Income" value={statement.rental_income} sign="+" />
            <StatementLine label="Management Fees" value={statement.management_fees} sign="-" />
            <StatementLine label="Recoverable Expenses" value={statement.recoverable_expenses} sign="-" />
            <StatementLine label="Recovered Amounts" value={statement.recovered_amounts} sign="+" />
            <StatementLine label="Owner Payments" value={statement.owner_payments} sign="-" />
            <StatementLine label="Other Adjustments" value={statement.other_adjustments} sign="+" />
            <div className="border-t border-ink-100 dark:border-ink-800 my-1" />
            <StatementLine label="Net Movement" value={statement.net_movement} bold />
            <StatementLine label="Closing Balance" value={statement.closing_balance} bold />
          </div>
        )}
      </div>
    </Modal>
  );
}

function StatementLine({ label, value, sign, bold }: { label: string; value: string; sign?: "+" | "-"; bold?: boolean }) {
  return (
    <div className={`flex justify-between ${bold ? "font-semibold" : ""}`}>
      <span className="text-ink-600 dark:text-ink-300">{label}</span>
      <span>{sign && `${sign} `}{money(value)}</span>
    </div>
  );
}

// ==================== Property Hierarchy Tree ====================
function HierarchyTab({ ownerId }: { ownerId: number }) {
  const [tree, setTree] = useState<PropertyHierarchyTree | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    apiClient.get<PropertyHierarchyTree>(`/owners/${ownerId}/hierarchy-tree`)
      .then(({ data }) => setTree(data))
      .catch(() => setError("Could not load the property tree."))
      .finally(() => setLoading(false));
  }, [ownerId]);

  return (
    <div className="card p-4">
      <p className="text-xs text-ink-400 mb-3">Building → Floor → Unit → active tenant, for every property this owner has. Click a property or unit to open it.</p>
      {loading && <div className="flex justify-center py-10"><Loader2 className="animate-spin text-ink-400" /></div>}
      {error && <p className="text-sm text-rust-500 py-6 text-center">{error}</p>}
      {!loading && !error && tree && <PropertyHierarchyTreeView tree={tree} />}
    </div>
  );
}

// ==================== Notes ====================
function NotesTab({ ownerId }: { ownerId: number }) {
  const [notes, setNotes] = useState<any[]>([]);
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(true);
  const [posting, setPosting] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    apiClient.get("/notes", { params: { entity_type: "owner", entity_id: ownerId } })
      .then(({ data }) => setNotes(data)).finally(() => setLoading(false));
  }, [ownerId]);

  useEffect(() => { load(); }, [load]);

  const handleAdd = async () => {
    if (!content.trim()) return;
    setPosting(true);
    try {
      await apiClient.post("/notes", { entity_type: "owner", entity_id: ownerId, content, is_pinned: false });
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
function HistoryTab({ ownerId }: { ownerId: number }) {
  const [entries, setEntries] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiClient.get("/activity-logs", { params: { entity_type: "owner", entity_id: ownerId } })
      .then(({ data }) => setEntries(data)).finally(() => setLoading(false));
  }, [ownerId]);

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
