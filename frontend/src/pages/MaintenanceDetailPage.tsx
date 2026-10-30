import { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import apiClient from "@/api/client";
import { useAuth } from "@/context/AuthContext";
import { Modal, EmptyState } from "@/components/ui";
import {
  Loader2, ArrowLeft, FileText, Wrench, Camera, History, Plus, Trash2,
  CheckCircle2, XCircle, PauseCircle, PlayCircle, UserCog, AlertTriangle, Upload,
} from "lucide-react";
import { MaintenanceRequestDetail, Contractor, Technician, PaginatedResponse } from "@/types";

type TabKey = "overview" | "costs" | "photos" | "history";

const TABS: { key: TabKey; label: string; icon: typeof FileText }[] = [
  { key: "overview", label: "Overview", icon: FileText },
  { key: "costs", label: "Materials & Labor", icon: Wrench },
  { key: "photos", label: "Before / After Photos", icon: Camera },
  { key: "history", label: "History", icon: History },
];

const STATUS_TONE: Record<string, string> = {
  reported: "badge-inactive", assigned: "badge-warn", in_progress: "badge-warn",
  on_hold: "badge-warn", completed: "badge-active", cancelled: "badge-inactive",
};

export default function MaintenanceDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { hasPermission } = useAuth();
  const [req, setReq] = useState<MaintenanceRequestDetail | null>(null);
  const [tab, setTab] = useState<TabKey>("overview");
  const [loading, setLoading] = useState(true);
  const [actionModal, setActionModal] = useState<"assign" | "hold" | "cancel" | "complete" | null>(null);

  const canEdit = hasPermission("maintenance.edit");
  const canDelete = hasPermission("maintenance.delete");

  const load = useCallback(() => {
    setLoading(true);
    apiClient.get<MaintenanceRequestDetail>(`/maintenance/requests/${id}`).then(({ data }) => setReq(data)).finally(() => setLoading(false));
  }, [id]);

  useEffect(() => { load(); }, [load]);

  const handleStart = async () => { await apiClient.post(`/maintenance/requests/${id}/start`); load(); };
  const handleResume = async () => { await apiClient.post(`/maintenance/requests/${id}/resume`); load(); };
  const handleDelete = async () => {
    if (!confirm("Delete this maintenance request?")) return;
    await apiClient.delete(`/maintenance/requests/${id}`);
    navigate("/maintenance");
  };

  if (loading) return <div className="flex justify-center py-16"><Loader2 className="animate-spin text-ink-400" /></div>;
  if (!req) return <EmptyState title="Maintenance request not found" />;

  return (
    <div>
      <button className="flex items-center gap-1.5 text-sm text-ink-500 hover:text-ink-800 dark:hover:text-ink-100 mb-4" onClick={() => navigate("/maintenance")}>
        <ArrowLeft size={15} /> Back to Maintenance
      </button>

      <div className="flex items-start justify-between flex-wrap gap-4 mb-6">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="font-display text-xl font-bold font-mono">{req.request_number}</h1>
            <span className={STATUS_TONE[req.maintenance_status] || "badge-inactive"}>{req.maintenance_status.replace(/_/g, " ")}</span>
            {req.is_overdue && <span className="badge-warn"><AlertTriangle size={10} /> Overdue</span>}
          </div>
          <p className="text-sm text-ink-500 mt-1">{req.title} · {req.property_title}</p>
        </div>
        <div className="flex gap-2 flex-wrap">
          {canEdit && (req.maintenance_status === "reported" || req.maintenance_status === "assigned" || req.maintenance_status === "on_hold") && (
            <button className="btn-secondary" onClick={() => setActionModal("assign")}><UserCog size={15} /> {req.maintenance_status === "reported" ? "Assign" : "Reassign"}</button>
          )}
          {canEdit && req.maintenance_status === "assigned" && (
            <button className="btn-primary" onClick={handleStart}><PlayCircle size={15} /> Start Work</button>
          )}
          {canEdit && req.maintenance_status === "on_hold" && (
            <button className="btn-primary" onClick={handleResume}><PlayCircle size={15} /> Resume</button>
          )}
          {canEdit && req.maintenance_status === "in_progress" && (
            <>
              <button className="btn-secondary" onClick={() => setActionModal("hold")}><PauseCircle size={15} /> Hold</button>
              <button className="btn-primary" onClick={() => setActionModal("complete")}><CheckCircle2 size={15} /> Complete</button>
            </>
          )}
          {canEdit && !["completed", "cancelled"].includes(req.maintenance_status) && (
            <button className="btn-secondary text-rust-500" onClick={() => setActionModal("cancel")}><XCircle size={15} /> Cancel</button>
          )}
          {canDelete && <button className="btn-secondary text-rust-500" onClick={handleDelete}><Trash2 size={15} /></button>}
        </div>
      </div>

      <div className="flex gap-1 border-b border-ink-100 dark:border-ink-800 mb-6 overflow-x-auto">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`flex items-center gap-1.5 px-3.5 py-2.5 text-sm font-medium border-b-2 whitespace-nowrap transition-colors ${
              tab === t.key ? "border-brand-500 text-brand-600 dark:text-brand-400" : "border-transparent text-ink-500 hover:text-ink-800 dark:hover:text-ink-100"
            }`}
          >
            <t.icon size={15} /> {t.label}
          </button>
        ))}
      </div>

      {tab === "overview" && <OverviewTab req={req} canEdit={canEdit} onSaved={load} />}
      {tab === "costs" && <CostsTab req={req} canEdit={canEdit} onChanged={load} />}
      {tab === "photos" && <PhotosTab req={req} canEdit={canEdit} onChanged={load} />}
      {tab === "history" && <HistoryTab requestId={req.id} />}

      {actionModal === "assign" && <AssignModal req={req} onClose={() => setActionModal(null)} onDone={() => { setActionModal(null); load(); }} />}
      {actionModal === "hold" && <HoldModal req={req} onClose={() => setActionModal(null)} onDone={() => { setActionModal(null); load(); }} />}
      {actionModal === "cancel" && <CancelModal req={req} onClose={() => setActionModal(null)} onDone={() => { setActionModal(null); load(); }} />}
      {actionModal === "complete" && <CompleteModal req={req} onClose={() => setActionModal(null)} onDone={() => { setActionModal(null); load(); }} />}
    </div>
  );
}

// ==================== Overview ====================
function OverviewTab({ req, canEdit, onSaved }: { req: MaintenanceRequestDetail; canEdit: boolean; onSaved: () => void }) {
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState<any>(req);
  const [saving, setSaving] = useState(false);
  const editable = req.maintenance_status !== "completed" && req.maintenance_status !== "cancelled";

  const startEdit = () => { setForm(req); setEditing(true); };
  const handleSave = async () => {
    setSaving(true);
    try {
      await apiClient.put(`/maintenance/requests/${req.id}`, {
        title: form.title, description: form.description, category: form.category || undefined,
        priority: form.priority, scheduled_date: form.scheduled_date || undefined,
        estimated_cost: form.estimated_cost || undefined, notes: form.notes,
      });
      setEditing(false);
      onSaved();
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="card p-6 max-w-3xl">
      {editable && canEdit && (
        <div className="flex justify-end mb-2">
          {!editing ? (
            <button className="btn-secondary" onClick={startEdit}>Edit</button>
          ) : (
            <div className="flex gap-2">
              <button className="btn-secondary" onClick={() => setEditing(false)}>Cancel</button>
              <button className="btn-primary" disabled={saving} onClick={handleSave}>{saving && <Loader2 size={14} className="animate-spin" />} Save</button>
            </div>
          )}
        </div>
      )}

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="label">Title</label>
          {editing ? <input className="input" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /> : <p className="text-sm text-ink-700 dark:text-ink-200 py-2">{req.title}</p>}
        </div>
        <div>
          <label className="label">Category</label>
          <p className="text-sm text-ink-700 dark:text-ink-200 py-2 capitalize">{req.category?.replace(/_/g, " ") || "—"}</p>
        </div>
        <div>
          <label className="label">Priority</label>
          {editing ? (
            <select className="input" value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value })}>
              <option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option><option value="urgent">Urgent</option>
            </select>
          ) : <p className="text-sm text-ink-700 dark:text-ink-200 py-2 capitalize">{req.priority}</p>}
        </div>
        <div>
          <label className="label">Reported Date</label>
          <p className="text-sm text-ink-700 dark:text-ink-200 py-2">{req.reported_date}</p>
        </div>
        <div>
          <label className="label">Scheduled Date</label>
          {editing ? <input className="input" type="date" value={form.scheduled_date || ""} onChange={(e) => setForm({ ...form, scheduled_date: e.target.value })} /> : <p className="text-sm text-ink-700 dark:text-ink-200 py-2">{req.scheduled_date || "—"}</p>}
        </div>
        <div>
          <label className="label">Completed Date</label>
          <p className="text-sm text-ink-700 dark:text-ink-200 py-2">{req.completed_date || "—"}</p>
        </div>
        <div>
          <label className="label">Contractor</label>
          <p className="text-sm text-ink-700 dark:text-ink-200 py-2">{req.contractor_name || "—"}</p>
        </div>
        <div>
          <label className="label">Technician</label>
          <p className="text-sm text-ink-700 dark:text-ink-200 py-2">{req.technician_name || "—"}</p>
        </div>
        <div>
          <label className="label">Estimated Cost</label>
          {editing ? <input className="input" type="number" min="0" step="0.001" value={form.estimated_cost || ""} onChange={(e) => setForm({ ...form, estimated_cost: e.target.value })} /> : <p className="text-sm text-ink-700 dark:text-ink-200 py-2">{req.estimated_cost ? Number(req.estimated_cost).toLocaleString() : "—"}</p>}
        </div>
        <div>
          <label className="label">Actual Cost (Materials + Labor)</label>
          <p className="text-sm font-medium text-ink-700 dark:text-ink-200 py-2">{Number(req.total_actual_cost).toLocaleString()}</p>
        </div>
      </div>

      <div className="mt-4">
        <label className="label">Description</label>
        {editing ? <textarea className="input" rows={3} value={form.description || ""} onChange={(e) => setForm({ ...form, description: e.target.value })} /> : <p className="text-sm text-ink-700 dark:text-ink-200 py-2">{req.description || "—"}</p>}
      </div>

      {req.on_hold_reason && (
        <div className="mt-4 p-3 rounded-md bg-amber-50 dark:bg-amber-500/10">
          <p className="text-sm font-medium text-amber-600">On hold</p>
          <p className="text-sm text-ink-500 mt-1">{req.on_hold_reason}</p>
        </div>
      )}
      {req.cancellation_reason && (
        <div className="mt-4 p-3 rounded-md bg-rust-50 dark:bg-rust-500/10">
          <p className="text-sm font-medium text-rust-600">Cancelled</p>
          <p className="text-sm text-ink-500 mt-1">{req.cancellation_reason}</p>
        </div>
      )}
    </div>
  );
}

// ==================== Materials & Labor ====================
function CostsTab({ req, canEdit, onChanged }: { req: MaintenanceRequestDetail; canEdit: boolean; onChanged: () => void }) {
  const [materialModalOpen, setMaterialModalOpen] = useState(false);
  const [laborModalOpen, setLaborModalOpen] = useState(false);
  const [materialForm, setMaterialForm] = useState({ name: "", quantity: "1", unit_cost: "0", supplier: "" });
  const [laborForm, setLaborForm] = useState({ technician_id: "", work_date: new Date().toISOString().slice(0, 10), hours: "", hourly_rate: "", description: "" });
  const [technicians, setTechnicians] = useState<Technician[]>([]);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (laborModalOpen) {
      apiClient.get<PaginatedResponse<Technician>>("/maintenance/technicians", { params: { page_size: 100 } }).then(({ data }) => setTechnicians(data.items));
    }
  }, [laborModalOpen]);

  const handleAddMaterial = async () => {
    setSaving(true);
    try {
      await apiClient.post(`/maintenance/requests/${req.id}/materials`, materialForm);
      setMaterialModalOpen(false);
      setMaterialForm({ name: "", quantity: "1", unit_cost: "0", supplier: "" });
      onChanged();
    } finally {
      setSaving(false);
    }
  };

  const handleAddLabor = async () => {
    setSaving(true);
    try {
      const payload: any = { ...laborForm };
      if (payload.technician_id) payload.technician_id = Number(payload.technician_id); else delete payload.technician_id;
      await apiClient.post(`/maintenance/requests/${req.id}/labor`, payload);
      setLaborModalOpen(false);
      setLaborForm({ technician_id: "", work_date: new Date().toISOString().slice(0, 10), hours: "", hourly_rate: "", description: "" });
      onChanged();
    } finally {
      setSaving(false);
    }
  };

  const deleteMaterial = async (materialId: number) => {
    if (!confirm("Remove this material?")) return;
    await apiClient.delete(`/maintenance/requests/${req.id}/materials/${materialId}`);
    onChanged();
  };

  const deleteLabor = async (laborId: number) => {
    if (!confirm("Remove this labor cost entry?")) return;
    await apiClient.delete(`/maintenance/requests/${req.id}/labor/${laborId}`);
    onChanged();
  };

  return (
    <div className="space-y-6">
      <div className="card">
        <div className="flex justify-between items-center px-5 py-4 border-b border-ink-100 dark:border-ink-800">
          <h3 className="font-display font-semibold text-sm">Materials</h3>
          {canEdit && <button className="btn-secondary" onClick={() => setMaterialModalOpen(true)}><Plus size={14} /> Add Material</button>}
        </div>
        {req.materials.length === 0 && <EmptyState title="No materials logged yet" />}
        {req.materials.length > 0 && (
          <div className="overflow-x-auto">
            <table className="table-shell">
              <thead><tr><th>Name</th><th>Qty</th><th>Unit Cost</th><th>Supplier</th><th>Total</th>{canEdit && <th></th>}</tr></thead>
              <tbody>
                {req.materials.map((m) => (
                  <tr key={m.id}>
                    <td className="font-medium">{m.name}</td>
                    <td>{m.quantity}</td>
                    <td>{Number(m.unit_cost).toLocaleString()}</td>
                    <td className="text-ink-500">{m.supplier || "—"}</td>
                    <td className="font-medium">{Number(m.total_cost).toLocaleString()}</td>
                    {canEdit && <td className="text-right"><button className="btn-secondary !px-2 !py-1 text-rust-500" onClick={() => deleteMaterial(m.id)}><Trash2 size={13} /></button></td>}
                  </tr>
                ))}
              </tbody>
              <tfoot><tr><td colSpan={4} className="text-right font-medium">Total Materials</td><td className="font-semibold">{Number(req.total_material_cost).toLocaleString()}</td>{canEdit && <td></td>}</tr></tfoot>
            </table>
          </div>
        )}
      </div>

      <div className="card">
        <div className="flex justify-between items-center px-5 py-4 border-b border-ink-100 dark:border-ink-800">
          <h3 className="font-display font-semibold text-sm">Labor Cost</h3>
          {canEdit && <button className="btn-secondary" onClick={() => setLaborModalOpen(true)}><Plus size={14} /> Add Labor Entry</button>}
        </div>
        {req.labor_entries.length === 0 && <EmptyState title="No labor cost entries yet" />}
        {req.labor_entries.length > 0 && (
          <div className="overflow-x-auto">
            <table className="table-shell">
              <thead><tr><th>Date</th><th>Technician</th><th>Hours</th><th>Rate</th><th>Notes</th><th>Total</th>{canEdit && <th></th>}</tr></thead>
              <tbody>
                {req.labor_entries.map((l) => (
                  <tr key={l.id}>
                    <td className="text-ink-500">{l.work_date}</td>
                    <td className="font-medium">{l.technician_name || "—"}</td>
                    <td>{l.hours}</td>
                    <td>{Number(l.hourly_rate).toLocaleString()}</td>
                    <td className="text-ink-500 max-w-[200px] truncate">{l.description || "—"}</td>
                    <td className="font-medium">{Number(l.total_cost).toLocaleString()}</td>
                    {canEdit && <td className="text-right"><button className="btn-secondary !px-2 !py-1 text-rust-500" onClick={() => deleteLabor(l.id)}><Trash2 size={13} /></button></td>}
                  </tr>
                ))}
              </tbody>
              <tfoot><tr><td colSpan={5} className="text-right font-medium">Total Labor</td><td className="font-semibold">{Number(req.total_labor_cost).toLocaleString()}</td>{canEdit && <td></td>}</tr></tfoot>
            </table>
          </div>
        )}
      </div>

      <Modal
        open={materialModalOpen} onClose={() => setMaterialModalOpen(false)} title="Add Material"
        footer={<><button className="btn-secondary" onClick={() => setMaterialModalOpen(false)}>Cancel</button><button className="btn-primary" disabled={saving || !materialForm.name} onClick={handleAddMaterial}>{saving && <Loader2 size={14} className="animate-spin" />} Save</button></>}
      >
        <div className="space-y-4">
          <div><label className="label">Name *</label><input className="input" required value={materialForm.name} onChange={(e) => setMaterialForm({ ...materialForm, name: e.target.value })} /></div>
          <div className="grid grid-cols-2 gap-4">
            <div><label className="label">Quantity</label><input className="input" type="number" min="0" step="0.01" value={materialForm.quantity} onChange={(e) => setMaterialForm({ ...materialForm, quantity: e.target.value })} /></div>
            <div><label className="label">Unit Cost</label><input className="input" type="number" min="0" step="0.001" value={materialForm.unit_cost} onChange={(e) => setMaterialForm({ ...materialForm, unit_cost: e.target.value })} /></div>
          </div>
          <div><label className="label">Supplier</label><input className="input" value={materialForm.supplier} onChange={(e) => setMaterialForm({ ...materialForm, supplier: e.target.value })} /></div>
        </div>
      </Modal>

      <Modal
        open={laborModalOpen} onClose={() => setLaborModalOpen(false)} title="Add Labor Entry"
        footer={<><button className="btn-secondary" onClick={() => setLaborModalOpen(false)}>Cancel</button><button className="btn-primary" disabled={saving || !laborForm.hours || !laborForm.hourly_rate} onClick={handleAddLabor}>{saving && <Loader2 size={14} className="animate-spin" />} Save</button></>}
      >
        <div className="space-y-4">
          <div>
            <label className="label">Technician</label>
            <select className="input" value={laborForm.technician_id} onChange={(e) => setLaborForm({ ...laborForm, technician_id: e.target.value })}>
              <option value="">—</option>
              {technicians.map((t) => <option key={t.id} value={t.id}>{t.technician_code} — {t.full_name}</option>)}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div><label className="label">Work Date *</label><input className="input" type="date" required value={laborForm.work_date} onChange={(e) => setLaborForm({ ...laborForm, work_date: e.target.value })} /></div>
            <div><label className="label">Hours *</label><input className="input" type="number" min="0" step="0.25" required value={laborForm.hours} onChange={(e) => setLaborForm({ ...laborForm, hours: e.target.value })} /></div>
          </div>
          <div><label className="label">Hourly Rate *</label><input className="input" type="number" min="0" step="0.001" required value={laborForm.hourly_rate} onChange={(e) => setLaborForm({ ...laborForm, hourly_rate: e.target.value })} /></div>
          <div><label className="label">Notes</label><input className="input" value={laborForm.description} onChange={(e) => setLaborForm({ ...laborForm, description: e.target.value })} /></div>
        </div>
      </Modal>
    </div>
  );
}

// ==================== Photos ====================
function PhotosTab({ req, canEdit, onChanged }: { req: MaintenanceRequestDetail; canEdit: boolean; onChanged: () => void }) {
  const [modalOpen, setModalOpen] = useState(false);
  const [photoType, setPhotoType] = useState<"before" | "after">("before");
  const [caption, setCaption] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);

  const beforePhotos = req.photos.filter((p) => p.photo_type === "before");
  const afterPhotos = req.photos.filter((p) => p.photo_type === "after");

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append("photo_type", photoType);
      if (caption) formData.append("caption", caption);
      formData.append("file", file);
      await apiClient.post(`/maintenance/requests/${req.id}/photos`, formData, { headers: { "Content-Type": "multipart/form-data" } });
      setModalOpen(false);
      setFile(null);
      setCaption("");
      onChanged();
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (photoId: number) => {
    if (!confirm("Delete this photo?")) return;
    await apiClient.delete(`/maintenance/requests/${req.id}/photos/${photoId}`);
    onChanged();
  };

  const PhotoGrid = ({ photos }: { photos: typeof req.photos }) => (
    <div className="grid grid-cols-2 md:grid-cols-3 gap-3 p-5">
      {photos.map((p) => (
        <div key={p.id} className="relative group rounded-md overflow-hidden border border-ink-100 dark:border-ink-800">
          <img src={p.file_url ?? undefined} alt={p.caption || p.file_name} className="w-full h-32 object-cover" />
          {p.caption && <p className="text-xs text-ink-500 px-2 py-1 truncate">{p.caption}</p>}
          {canEdit && (
            <button className="absolute top-1 right-1 bg-ink-950/60 text-white rounded-full p-1 opacity-0 group-hover:opacity-100 transition-opacity" onClick={() => handleDelete(p.id)}>
              <Trash2 size={12} />
            </button>
          )}
        </div>
      ))}
    </div>
  );

  return (
    <div className="space-y-6">
      {canEdit && (
        <div className="flex justify-end">
          <button className="btn-primary" onClick={() => setModalOpen(true)}><Upload size={14} /> Upload Photo</button>
        </div>
      )}
      <div className="card">
        <div className="px-5 py-4 border-b border-ink-100 dark:border-ink-800">
          <h3 className="font-display font-semibold text-sm">Before</h3>
        </div>
        {beforePhotos.length === 0 ? <EmptyState title="No before photos yet" /> : <PhotoGrid photos={beforePhotos} />}
      </div>
      <div className="card">
        <div className="px-5 py-4 border-b border-ink-100 dark:border-ink-800">
          <h3 className="font-display font-semibold text-sm">After</h3>
        </div>
        {afterPhotos.length === 0 ? <EmptyState title="No after photos yet" /> : <PhotoGrid photos={afterPhotos} />}
      </div>

      <Modal
        open={modalOpen} onClose={() => setModalOpen(false)} title="Upload Photo"
        footer={<><button className="btn-secondary" onClick={() => setModalOpen(false)}>Cancel</button><button className="btn-primary" disabled={uploading || !file} onClick={handleUpload}>{uploading && <Loader2 size={14} className="animate-spin" />} Upload</button></>}
      >
        <div className="space-y-4">
          <div>
            <label className="label">Photo Type *</label>
            <div className="flex gap-2">
              <button type="button" className={photoType === "before" ? "btn-primary flex-1" : "btn-secondary flex-1"} onClick={() => setPhotoType("before")}>Before</button>
              <button type="button" className={photoType === "after" ? "btn-primary flex-1" : "btn-secondary flex-1"} onClick={() => setPhotoType("after")}>After</button>
            </div>
          </div>
          <div><label className="label">Caption</label><input className="input" value={caption} onChange={(e) => setCaption(e.target.value)} /></div>
          <div><label className="label">File *</label><input className="input" type="file" accept="image/*" onChange={(e) => setFile(e.target.files?.[0] || null)} /></div>
        </div>
      </Modal>
    </div>
  );
}

// ==================== History ====================
function HistoryTab({ requestId }: { requestId: number }) {
  const [entries, setEntries] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiClient.get("/activity-logs", { params: { entity_type: "maintenance_request", entity_id: requestId } })
      .then(({ data }) => setEntries(data)).finally(() => setLoading(false));
  }, [requestId]);

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

// ==================== Action Modals ====================
function AssignModal({ req, onClose, onDone }: { req: MaintenanceRequestDetail; onClose: () => void; onDone: () => void }) {
  const [contractors, setContractors] = useState<Contractor[]>([]);
  const [technicians, setTechnicians] = useState<Technician[]>([]);
  const [contractorId, setContractorId] = useState<string>(req.assigned_contractor_id ? String(req.assigned_contractor_id) : "");
  const [technicianId, setTechnicianId] = useState<string>(req.assigned_technician_id ? String(req.assigned_technician_id) : "");
  const [scheduledDate, setScheduledDate] = useState(req.scheduled_date || "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiClient.get<PaginatedResponse<Contractor>>("/maintenance/contractors", { params: { page_size: 100 } }).then(({ data }) => setContractors(data.items));
    apiClient.get<PaginatedResponse<Technician>>("/maintenance/technicians", { params: { page_size: 100 } }).then(({ data }) => setTechnicians(data.items));
  }, []);

  const handleSubmit = async () => {
    setSaving(true);
    setError(null);
    try {
      await apiClient.post(`/maintenance/requests/${req.id}/assign`, {
        assigned_contractor_id: contractorId ? Number(contractorId) : undefined,
        assigned_technician_id: technicianId ? Number(technicianId) : undefined,
        scheduled_date: scheduledDate || undefined,
      });
      onDone();
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Unable to assign this request.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open onClose={onClose} title="Assign Contractor / Technician"
      footer={<><button className="btn-secondary" onClick={onClose}>Cancel</button><button className="btn-primary" disabled={saving || (!contractorId && !technicianId)} onClick={handleSubmit}>{saving && <Loader2 size={14} className="animate-spin" />} Assign</button></>}
    >
      {error && <div className="mb-3 text-sm text-rust-500 bg-rust-50 dark:bg-rust-500/10 rounded-md px-3 py-2">{error}</div>}
      <div className="space-y-4">
        <div>
          <label className="label">Contractor</label>
          <select className="input" value={contractorId} onChange={(e) => setContractorId(e.target.value)}>
            <option value="">—</option>
            {contractors.map((c) => <option key={c.id} value={c.id}>{c.contractor_code} — {c.company_name}</option>)}
          </select>
        </div>
        <div>
          <label className="label">Technician</label>
          <select className="input" value={technicianId} onChange={(e) => setTechnicianId(e.target.value)}>
            <option value="">—</option>
            {technicians.map((t) => <option key={t.id} value={t.id}>{t.technician_code} — {t.full_name}</option>)}
          </select>
        </div>
        <div>
          <label className="label">Scheduled Date</label>
          <input className="input" type="date" value={scheduledDate} onChange={(e) => setScheduledDate(e.target.value)} />
        </div>
      </div>
    </Modal>
  );
}

function HoldModal({ req, onClose, onDone }: { req: MaintenanceRequestDetail; onClose: () => void; onDone: () => void }) {
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);

  const handleSubmit = async () => {
    setSaving(true);
    try {
      await apiClient.post(`/maintenance/requests/${req.id}/hold`, { on_hold_reason: reason });
      onDone();
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal open onClose={onClose} title="Put On Hold" footer={<><button className="btn-secondary" onClick={onClose}>Cancel</button><button className="btn-primary" disabled={saving || !reason} onClick={handleSubmit}>{saving && <Loader2 size={14} className="animate-spin" />} Confirm</button></>}>
      <div>
        <label className="label">Reason *</label>
        <textarea className="input" rows={3} required value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. Waiting on replacement parts" />
      </div>
    </Modal>
  );
}

function CancelModal({ req, onClose, onDone }: { req: MaintenanceRequestDetail; onClose: () => void; onDone: () => void }) {
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);

  const handleSubmit = async () => {
    setSaving(true);
    try {
      await apiClient.post(`/maintenance/requests/${req.id}/cancel`, { cancellation_reason: reason });
      onDone();
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal open onClose={onClose} title="Cancel Request" footer={<><button className="btn-secondary" onClick={onClose}>Cancel</button><button className="btn-danger" disabled={saving || !reason} onClick={handleSubmit}>{saving && <Loader2 size={14} className="animate-spin" />} Confirm Cancel</button></>}>
      <div>
        <label className="label">Reason *</label>
        <textarea className="input" rows={3} required value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. Duplicate request" />
      </div>
    </Modal>
  );
}

function CompleteModal({ req, onClose, onDone }: { req: MaintenanceRequestDetail; onClose: () => void; onDone: () => void }) {
  const [completedDate, setCompletedDate] = useState(new Date().toISOString().slice(0, 10));
  const [saving, setSaving] = useState(false);

  const handleSubmit = async () => {
    setSaving(true);
    try {
      await apiClient.post(`/maintenance/requests/${req.id}/complete`, { completed_date: completedDate });
      onDone();
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal open onClose={onClose} title="Mark as Completed" footer={<><button className="btn-secondary" onClick={onClose}>Cancel</button><button className="btn-primary" disabled={saving} onClick={handleSubmit}>{saving && <Loader2 size={14} className="animate-spin" />} Complete</button></>}>
      <div className="space-y-4">
        <p className="text-sm text-ink-500">Total actual cost so far: <span className="font-medium">{Number(req.total_actual_cost).toLocaleString()}</span> (materials + labor logged on the Materials & Labor tab)</p>
        <div>
          <label className="label">Completed Date *</label>
          <input className="input" type="date" required value={completedDate} onChange={(e) => setCompletedDate(e.target.value)} />
        </div>
      </div>
    </Modal>
  );
}
