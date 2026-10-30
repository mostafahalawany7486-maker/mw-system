import { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import apiClient from "@/api/client";
import { useAuth } from "@/context/AuthContext";
import { StatusBadge, Modal, EmptyState } from "@/components/ui";
import {
  Loader2, ArrowLeft, User, Building2, Contact2, HeartPulse, FileText,
  StickyNote, History, Plus, Trash2, Pencil, Star, Upload, AlertTriangle, Pin, ShieldBan, ShieldCheck,
} from "lucide-react";
import { TenantDetail, TenantContact, TenantEmergencyContact, TenantDocument, TenantRating } from "@/types";

type TabKey = "overview" | "contacts" | "emergency" | "documents" | "ratings" | "notes" | "history";

const TABS: { key: TabKey; label: string; icon: typeof User }[] = [
  { key: "overview", label: "Overview", icon: User },
  { key: "contacts", label: "Contacts", icon: Contact2 },
  { key: "emergency", label: "Emergency Contact", icon: HeartPulse },
  { key: "documents", label: "Documents", icon: FileText },
  { key: "ratings", label: "Rating", icon: Star },
  { key: "notes", label: "Notes", icon: StickyNote },
  { key: "history", label: "History", icon: History },
];

export default function TenantDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { hasPermission } = useAuth();
  const [tenant, setTenant] = useState<TenantDetail | null>(null);
  const [tab, setTab] = useState<TabKey>("overview");
  const [loading, setLoading] = useState(true);
  const [blacklistModalOpen, setBlacklistModalOpen] = useState(false);

  const canEdit = hasPermission("tenants.edit");
  const canDelete = hasPermission("tenants.delete");

  const load = useCallback(() => {
    setLoading(true);
    apiClient.get<TenantDetail>(`/tenants/${id}`).then(({ data }) => setTenant(data)).finally(() => setLoading(false));
  }, [id]);

  useEffect(() => { load(); }, [load]);

  const handleDeleteTenant = async () => {
    if (!confirm("Delete this tenant? This can be reversed by an administrator.")) return;
    try {
      await apiClient.delete(`/tenants/${id}`);
      navigate("/tenants");
    } catch (err: any) {
      alert(err?.response?.data?.detail || "Unable to delete this tenant.");
    }
  };

  const handleUnblacklist = async () => {
    if (!confirm("Remove this tenant from the blacklist?")) return;
    await apiClient.post(`/tenants/${id}/unblacklist`);
    load();
  };

  if (loading) return <div className="flex justify-center py-16"><Loader2 className="animate-spin text-ink-400" /></div>;
  if (!tenant) return <EmptyState title="Tenant not found" />;

  return (
    <div>
      <button className="flex items-center gap-1.5 text-sm text-ink-500 hover:text-ink-800 dark:hover:text-ink-100 mb-4" onClick={() => navigate("/tenants")}>
        <ArrowLeft size={15} /> Back to Tenants
      </button>

      <div className="flex items-start justify-between flex-wrap gap-4 mb-6">
        <div className="flex items-center gap-3">
          <div className={`w-12 h-12 rounded-full text-white flex items-center justify-center ${tenant.is_blacklisted ? "bg-rust-500" : "bg-brand-600"}`}>
            {tenant.tenant_type === "company" ? <Building2 size={20} /> : <User size={20} />}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="font-display text-xl font-bold">{tenant.display_name}</h1>
              {tenant.is_blacklisted && <span className="badge-warn"><ShieldBan size={11} /> Blacklisted</span>}
            </div>
            <div className="flex items-center gap-2 mt-1 text-xs text-ink-500">
              <span className="font-mono">{tenant.tenant_code}</span>
              <span>·</span>
              <span className="capitalize">{tenant.tenant_type}</span>
              <span>·</span>
              <StatusBadge status={tenant.status} />
              {tenant.average_rating != null && <><span>·</span><span>{tenant.average_rating}/5 ({tenant.rating_count})</span></>}
            </div>
          </div>
        </div>
        <div className="flex gap-2">
          {canEdit && !tenant.is_blacklisted && (
            <button className="btn-secondary text-rust-500" onClick={() => setBlacklistModalOpen(true)}><ShieldBan size={15} /> Blacklist</button>
          )}
          {canEdit && tenant.is_blacklisted && (
            <button className="btn-secondary text-brand-600" onClick={handleUnblacklist}><ShieldCheck size={15} /> Remove from Blacklist</button>
          )}
          {canDelete && (
            <button className="btn-secondary text-rust-500" onClick={handleDeleteTenant}><Trash2 size={15} /></button>
          )}
        </div>
      </div>

      {tenant.is_blacklisted && (
        <div className="card p-4 mb-6 border-rust-200 dark:border-rust-500/30 bg-rust-50 dark:bg-rust-500/5">
          <div className="flex items-center gap-2 mb-1">
            <AlertTriangle size={15} className="text-rust-500" />
            <h3 className="font-display font-semibold text-sm text-rust-600">Blacklisted</h3>
          </div>
          <p className="text-sm text-ink-600 dark:text-ink-300">{tenant.blacklist_reason}</p>
          {tenant.blacklisted_at && <p className="text-xs text-ink-400 mt-1">Since {new Date(tenant.blacklisted_at).toLocaleDateString()}</p>}
        </div>
      )}

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

      {tab === "overview" && <OverviewTab tenant={tenant} canEdit={canEdit} onSaved={load} />}
      {tab === "contacts" && <ContactsTab tenant={tenant} canEdit={canEdit} onChanged={load} />}
      {tab === "emergency" && <EmergencyTab tenant={tenant} canEdit={canEdit} onChanged={load} />}
      {tab === "documents" && <DocumentsTab tenant={tenant} canEdit={canEdit} onChanged={load} />}
      {tab === "ratings" && <RatingsTab tenant={tenant} canEdit={canEdit} onChanged={load} />}
      {tab === "notes" && <NotesTab tenantId={tenant.id} />}
      {tab === "history" && <HistoryTab tenantId={tenant.id} />}

      {blacklistModalOpen && (
        <BlacklistModal tenant={tenant} onClose={() => setBlacklistModalOpen(false)} onDone={() => { setBlacklistModalOpen(false); load(); }} />
      )}
    </div>
  );
}

// ==================== Overview ====================
function OverviewTab({ tenant, canEdit, onSaved }: { tenant: TenantDetail; canEdit: boolean; onSaved: () => void }) {
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState<any>(tenant);
  const [saving, setSaving] = useState(false);

  const startEdit = () => { setForm(tenant); setEditing(true); };
  const handleSave = async () => {
    setSaving(true);
    try {
      await apiClient.put(`/tenants/${tenant.id}`, form);
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
        {tenant.tenant_type === "individual" ? (
          <>
            <Field label="First Name" value={tenant.first_name} name="first_name" />
            <Field label="Last Name" value={tenant.last_name} name="last_name" />
            <Field label="National ID" value={tenant.national_id} name="national_id" />
            <Field label="Passport Number" value={tenant.passport_number} name="passport_number" />
            <Field label="Date of Birth" value={tenant.date_of_birth} name="date_of_birth" type="date" />
          </>
        ) : (
          <>
            <Field label="Company Name" value={tenant.company_name} name="company_name" />
            <Field label="Commercial Registration #" value={tenant.commercial_registration_number} name="commercial_registration_number" />
            <Field label="Tax Number" value={tenant.tax_number} name="tax_number" />
            <Field label="Contact Person" value={tenant.contact_person_name} name="contact_person_name" />
          </>
        )}
        <Field label="Primary Email" value={tenant.primary_email} name="primary_email" type="email" />
        <Field label="Primary Phone" value={tenant.primary_phone} name="primary_phone" />
        <Field label="Secondary Phone" value={tenant.secondary_phone} name="secondary_phone" />
        <Field label="Website" value={tenant.website} name="website" />
        <Field label="Address (printed on rental receipts)" value={tenant.address} name="address" />
      </div>
      <div className="mt-4">
        <label className="label">Notes Summary</label>
        {editing ? (
          <textarea className="input" rows={3} value={form.notes_summary ?? ""} onChange={(e) => setForm({ ...form, notes_summary: e.target.value })} />
        ) : (
          <p className="text-sm text-ink-700 dark:text-ink-200 py-2">{tenant.notes_summary || "—"}</p>
        )}
      </div>
    </div>
  );
}

// ==================== Contacts ====================
function ContactsTab({ tenant, canEdit, onChanged }: { tenant: TenantDetail; canEdit: boolean; onChanged: () => void }) {
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<TenantContact | null>(null);
  const [form, setForm] = useState<any>({ full_name: "", designation: "", email: "", phone: "", is_primary: false });
  const [saving, setSaving] = useState(false);

  const openCreate = () => { setEditing(null); setForm({ full_name: "", designation: "", email: "", phone: "", is_primary: false }); setModalOpen(true); };
  const openEdit = (c: TenantContact) => { setEditing(c); setForm(c); setModalOpen(true); };

  const handleSave = async () => {
    setSaving(true);
    try {
      if (editing) {
        await apiClient.put(`/tenants/${tenant.id}/contacts/${editing.id}`, form);
      } else {
        await apiClient.post(`/tenants/${tenant.id}/contacts`, form);
      }
      setModalOpen(false);
      onChanged();
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (c: TenantContact) => {
    if (!confirm("Delete this contact?")) return;
    await apiClient.delete(`/tenants/${tenant.id}/contacts/${c.id}`);
    onChanged();
  };

  return (
    <div className="card">
      <div className="flex justify-between items-center px-5 py-4 border-b border-ink-100 dark:border-ink-800">
        <h3 className="font-display font-semibold text-sm">Contacts</h3>
        {canEdit && <button className="btn-secondary" onClick={openCreate}><Plus size={14} /> Add Contact</button>}
      </div>
      {tenant.contacts.length === 0 && <EmptyState title="No additional contacts" />}
      <div className="divide-y divide-ink-50 dark:divide-ink-800/60">
        {tenant.contacts.map((c) => (
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

// ==================== Emergency Contact ====================
function EmergencyTab({ tenant, canEdit, onChanged }: { tenant: TenantDetail; canEdit: boolean; onChanged: () => void }) {
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<TenantEmergencyContact | null>(null);
  const [form, setForm] = useState<any>({ full_name: "", relationship_type: "", phone: "", email: "", address: "", is_primary: false });
  const [saving, setSaving] = useState(false);

  const openCreate = () => { setEditing(null); setForm({ full_name: "", relationship_type: "", phone: "", email: "", address: "", is_primary: false }); setModalOpen(true); };
  const openEdit = (c: TenantEmergencyContact) => { setEditing(c); setForm(c); setModalOpen(true); };

  const handleSave = async () => {
    setSaving(true);
    try {
      if (editing) {
        await apiClient.put(`/tenants/${tenant.id}/emergency-contacts/${editing.id}`, form);
      } else {
        await apiClient.post(`/tenants/${tenant.id}/emergency-contacts`, form);
      }
      setModalOpen(false);
      onChanged();
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (c: TenantEmergencyContact) => {
    if (!confirm("Delete this emergency contact?")) return;
    await apiClient.delete(`/tenants/${tenant.id}/emergency-contacts/${c.id}`);
    onChanged();
  };

  return (
    <div className="card">
      <div className="flex justify-between items-center px-5 py-4 border-b border-ink-100 dark:border-ink-800">
        <h3 className="font-display font-semibold text-sm">Emergency Contacts</h3>
        {canEdit && <button className="btn-secondary" onClick={openCreate}><Plus size={14} /> Add Emergency Contact</button>}
      </div>
      {tenant.emergency_contacts.length === 0 && <EmptyState title="No emergency contacts on file" />}
      <div className="divide-y divide-ink-50 dark:divide-ink-800/60">
        {tenant.emergency_contacts.map((c) => (
          <div key={c.id} className="px-5 py-3 flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium">{c.full_name}</span>
                {c.is_primary && <span className="badge-active"><Star size={10} /> Primary</span>}
              </div>
              <p className="text-xs text-ink-400 capitalize">{c.relationship_type || "—"}</p>
              <p className="text-sm text-ink-500 mt-0.5">{c.phone} {c.email ? `· ${c.email}` : ""}</p>
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
        open={modalOpen} onClose={() => setModalOpen(false)} title={editing ? "Edit Emergency Contact" : "Add Emergency Contact"}
        footer={<><button className="btn-secondary" onClick={() => setModalOpen(false)}>Cancel</button><button className="btn-primary" disabled={saving} onClick={handleSave}>{saving && <Loader2 size={14} className="animate-spin" />} Save</button></>}
      >
        <div className="space-y-4">
          <div>
            <label className="label">Full Name *</label>
            <input className="input" required value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
          </div>
          <div>
            <label className="label">Relationship</label>
            <input className="input" value={form.relationship_type || ""} onChange={(e) => setForm({ ...form, relationship_type: e.target.value })} placeholder="e.g. spouse, parent, sibling" />
          </div>
          <div>
            <label className="label">Phone *</label>
            <input className="input" required value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
          </div>
          <div>
            <label className="label">Email</label>
            <input className="input" type="email" value={form.email || ""} onChange={(e) => setForm({ ...form, email: e.target.value })} />
          </div>
          <div>
            <label className="label">Address</label>
            <input className="input" value={form.address || ""} onChange={(e) => setForm({ ...form, address: e.target.value })} />
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={!!form.is_primary} onChange={(e) => setForm({ ...form, is_primary: e.target.checked })} />
            Set as primary emergency contact
          </label>
        </div>
      </Modal>
    </div>
  );
}

// ==================== Documents ====================
function DocumentsTab({ tenant, canEdit, onChanged }: { tenant: TenantDetail; canEdit: boolean; onChanged: () => void }) {
  const [modalOpen, setModalOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [documentType, setDocumentType] = useState("national_id");
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
      await apiClient.post(`/tenants/${tenant.id}/documents`, formData, { headers: { "Content-Type": "multipart/form-data" } });
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

  const handleDelete = async (d: TenantDocument) => {
    if (!confirm(`Delete "${d.file_name}"?`)) return;
    await apiClient.delete(`/tenants/${tenant.id}/documents/${d.id}`);
    onChanged();
  };

  return (
    <div className="card">
      <div className="flex justify-between items-center px-5 py-4 border-b border-ink-100 dark:border-ink-800">
        <h3 className="font-display font-semibold text-sm">Documents</h3>
        {canEdit && <button className="btn-secondary" onClick={() => setModalOpen(true)}><Upload size={14} /> Upload Document</button>}
      </div>
      {tenant.documents.length === 0 && <EmptyState title="No documents uploaded" description="Upload national ID, passport, or commercial registration scans." />}
      <div className="divide-y divide-ink-50 dark:divide-ink-800/60">
        {tenant.documents.map((d) => (
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
              <option value="national_id">National ID</option>
              <option value="passport">Passport</option>
              <option value="commercial_registration">Commercial Registration</option>
              <option value="visa">Visa</option>
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
          </div>
        </div>
      </Modal>
    </div>
  );
}

// ==================== Ratings ====================
function RatingsTab({ tenant, canEdit, onChanged }: { tenant: TenantDetail; canEdit: boolean; onChanged: () => void }) {
  const [modalOpen, setModalOpen] = useState(false);
  const [ratingValue, setRatingValue] = useState(5);
  const [comment, setComment] = useState("");
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    setSaving(true);
    try {
      await apiClient.post(`/tenants/${tenant.id}/ratings`, { rating_value: ratingValue, comment: comment || undefined });
      setModalOpen(false);
      setComment("");
      setRatingValue(5);
      onChanged();
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (r: TenantRating) => {
    if (!confirm("Delete this rating?")) return;
    await apiClient.delete(`/tenants/${tenant.id}/ratings/${r.id}`);
    onChanged();
  };

  return (
    <div className="card">
      <div className="flex justify-between items-center px-5 py-4 border-b border-ink-100 dark:border-ink-800">
        <div>
          <h3 className="font-display font-semibold text-sm">Rating</h3>
          <p className="text-xs text-ink-400 mt-0.5">
            {tenant.average_rating != null ? `Average: ${tenant.average_rating} / 5 (${tenant.rating_count} rating${tenant.rating_count === 1 ? "" : "s"})` : "No ratings yet"}
          </p>
        </div>
        {canEdit && <button className="btn-secondary" onClick={() => setModalOpen(true)}><Plus size={14} /> Add Rating</button>}
      </div>
      {tenant.ratings.length === 0 && <EmptyState title="No ratings yet" description="Rate this tenant based on payment reliability, property care, etc." />}
      <div className="divide-y divide-ink-50 dark:divide-ink-800/60">
        {tenant.ratings.map((r) => (
          <div key={r.id} className="px-5 py-3 flex items-start justify-between gap-3">
            <div className="flex-1">
              <div className="flex items-center gap-1">
                {[1, 2, 3, 4, 5].map((n) => (
                  <Star key={n} size={14} className={n <= r.rating_value ? "text-amber-500 fill-amber-500" : "text-ink-200 dark:text-ink-700"} />
                ))}
              </div>
              {r.comment && <p className="text-sm text-ink-600 dark:text-ink-300 mt-1">{r.comment}</p>}
              <p className="text-xs text-ink-400 mt-1">{new Date(r.created_at).toLocaleDateString()}</p>
            </div>
            {canEdit && <button className="btn-secondary !px-2 !py-1 text-rust-500" onClick={() => handleDelete(r)}><Trash2 size={13} /></button>}
          </div>
        ))}
      </div>

      <Modal
        open={modalOpen} onClose={() => setModalOpen(false)} title="Add Rating"
        footer={<><button className="btn-secondary" onClick={() => setModalOpen(false)}>Cancel</button><button className="btn-primary" disabled={saving} onClick={handleSave}>{saving && <Loader2 size={14} className="animate-spin" />} Save</button></>}
      >
        <div className="space-y-4">
          <div>
            <label className="label">Rating *</label>
            <div className="flex gap-1">
              {[1, 2, 3, 4, 5].map((n) => (
                <button key={n} type="button" onClick={() => setRatingValue(n)}>
                  <Star size={24} className={n <= ratingValue ? "text-amber-500 fill-amber-500" : "text-ink-200 dark:text-ink-700"} />
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="label">Comment</label>
            <textarea className="input" rows={3} value={comment} onChange={(e) => setComment(e.target.value)} placeholder="e.g. Always paid on time, kept the unit in great condition" />
          </div>
        </div>
      </Modal>
    </div>
  );
}

// ==================== Notes ====================
function NotesTab({ tenantId }: { tenantId: number }) {
  const [notes, setNotes] = useState<any[]>([]);
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(true);
  const [posting, setPosting] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    apiClient.get("/notes", { params: { entity_type: "tenant", entity_id: tenantId } })
      .then(({ data }) => setNotes(data)).finally(() => setLoading(false));
  }, [tenantId]);

  useEffect(() => { load(); }, [load]);

  const handleAdd = async () => {
    if (!content.trim()) return;
    setPosting(true);
    try {
      await apiClient.post("/notes", { entity_type: "tenant", entity_id: tenantId, content, is_pinned: false });
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
function HistoryTab({ tenantId }: { tenantId: number }) {
  const [entries, setEntries] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiClient.get("/activity-logs", { params: { entity_type: "tenant", entity_id: tenantId } })
      .then(({ data }) => setEntries(data)).finally(() => setLoading(false));
  }, [tenantId]);

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

// ==================== Blacklist Modal ====================
function BlacklistModal({ tenant, onClose, onDone }: { tenant: TenantDetail; onClose: () => void; onDone: () => void }) {
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    setSaving(true);
    setError(null);
    try {
      await apiClient.post(`/tenants/${tenant.id}/blacklist`, { reason });
      onDone();
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Unable to blacklist this tenant.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open onClose={onClose} title="Blacklist Tenant"
      footer={<><button className="btn-secondary" onClick={onClose}>Cancel</button><button className="btn-danger" disabled={saving || !reason.trim()} onClick={handleSubmit}>{saving && <Loader2 size={14} className="animate-spin" />} Blacklist</button></>}
    >
      {error && <div className="mb-3 text-sm text-rust-500 bg-rust-50 dark:bg-rust-500/10 rounded-md px-3 py-2">{error}</div>}
      <div className="space-y-4">
        <p className="text-sm text-ink-500">This flags {tenant.display_name} across the system. Staff will see a clear warning before entering any future sublease agreement with this tenant.</p>
        <div>
          <label className="label">Reason *</label>
          <textarea className="input" rows={3} required value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. Repeated late payments, property damage" />
        </div>
      </div>
    </Modal>
  );
}
