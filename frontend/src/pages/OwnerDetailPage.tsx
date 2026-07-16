import { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import apiClient from "@/api/client";
import { useAuth } from "@/context/AuthContext";
import { StatusBadge, Modal, EmptyState } from "@/components/ui";
import {
  Loader2, ArrowLeft, User, Building2, MapPin, Landmark, Contact2, FileText,
  StickyNote, History, Plus, Trash2, Pencil, Star, Upload, AlertTriangle, Pin,
} from "lucide-react";
import { OwnerDetail, OwnerAddress, OwnerBankAccount, OwnerContact, OwnerDocument } from "@/types";

type TabKey = "overview" | "addresses" | "bank" | "contacts" | "documents" | "notes" | "history";

const TABS: { key: TabKey; label: string; icon: typeof User }[] = [
  { key: "overview", label: "Overview", icon: User },
  { key: "addresses", label: "Addresses", icon: MapPin },
  { key: "bank", label: "Bank Accounts", icon: Landmark },
  { key: "contacts", label: "Contacts", icon: Contact2 },
  { key: "documents", label: "Documents", icon: FileText },
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
    await apiClient.delete(`/owners/${id}`);
    navigate("/owners");
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
