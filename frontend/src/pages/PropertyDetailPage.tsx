import { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate, useSearchParams } from "react-router-dom";
import apiClient from "@/api/client";
import { useAuth } from "@/context/AuthContext";
import { Modal, EmptyState, StatusBadge } from "@/components/ui";
import {
  Loader2, ArrowLeft, Home, Image as ImageIcon, FileText, Sparkles, Building2,
  StickyNote, History, Plus, Trash2, Star, Upload, AlertTriangle, Pin, MapPin, Layers, Pencil,
  FileSignature, UsersRound, Wrench, DoorOpen, DoorClosed, DollarSign, TrendingUp, TrendingDown, Percent,
  Archive, ArchiveRestore,
} from "lucide-react";
import { PropertyDetail, PropertyImage, PropertyDocument, Amenity, PropertyListItem, Floor, PaginatedResponse, PropertySummary, RentalContractListItem, TenantListItem, MaintenanceRequestListItem, PropertyFinancialDashboard } from "@/types";
import PropertyFormModal from "@/components/PropertyFormModal";
import TenantImportModal from "@/components/TenantImportModal";
import HierarchyBreadcrumb from "@/components/HierarchyBreadcrumb";
import PropertyHubPanel from "@/components/PropertyHubPanel";

type TabKey = "overview" | "financials" | "images" | "documents" | "amenities" | "units" | "floors" | "leases" | "tenants" | "maintenance" | "notes" | "history";

const TYPE_LABELS: Record<string, string> = {
  building: "Building", villa: "Villa", apartment: "Apartment", commercial_unit: "Commercial Unit",
  warehouse: "Warehouse", shop: "Shop", office: "Office", land: "Land", parking: "Parking", storage: "Storage",
  commercial_building: "Commercial Building", commercial_complex: "Commercial Complex", mixed_use: "Mixed Use Property",
};

// Container types whose Property Details page shows the live summary panel.
const CONTAINER_TYPES = new Set(["building", "villa", "commercial_building", "commercial_complex", "warehouse", "land", "mixed_use"]);

export default function PropertyDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { hasPermission } = useAuth();
  const [property, setProperty] = useState<PropertyDetail | null>(null);
  const [tab, setTab] = useState<TabKey>("overview");
  const [searchParams] = useSearchParams();
  const shouldAutoSetupFloors = searchParams.get("setupFloors") === "true";
  useEffect(() => { if (shouldAutoSetupFloors) setTab("floors"); }, [shouldAutoSetupFloors]);
  const [loading, setLoading] = useState(true);

  const canEdit = hasPermission("properties.edit");
  const canDelete = hasPermission("properties.delete");
  const canViewReports = hasPermission("reports.view");

  const load = useCallback(() => {
    setLoading(true);
    apiClient.get<PropertyDetail>(`/properties/${id}`).then(({ data }) => setProperty(data)).finally(() => setLoading(false));
  }, [id]);

  useEffect(() => { load(); }, [load]);

  const handleDelete = async () => {
    if (!confirm("Delete this property?")) return;
    try {
      await apiClient.delete(`/properties/${id}`);
      navigate("/properties");
    } catch (err: any) {
      alert(err?.response?.data?.detail || "Unable to delete this property.");
    }
  };

  const handleArchiveToggle = async () => {
    if (!property) return;
    const archiving = property.status !== "archived";
    if (archiving && !confirm("Archive this property? It stays fully intact and searchable — just hidden from the main list until unarchived.")) return;
    await apiClient.post(`/properties/${id}/${archiving ? "archive" : "unarchive"}`);
    load();
  };

  if (loading) return <div className="flex justify-center py-16"><Loader2 className="animate-spin text-ink-400" /></div>;
  if (!property) return <EmptyState title="Property not found" />;

  const isBuilding = property.property_type === "building";
  const tabs: { key: TabKey; label: string; icon: typeof Home }[] = [
    { key: "overview", label: "Overview", icon: Home },
    ...(canViewReports ? [{ key: "financials" as TabKey, label: "Financials", icon: DollarSign }] : []),
    { key: "images", label: "Images", icon: ImageIcon },
    { key: "documents", label: "Documents", icon: FileText },
    { key: "amenities", label: "Amenities", icon: Sparkles },
    ...(isBuilding ? [
      { key: "units" as TabKey, label: "Units", icon: Building2 },
      { key: "floors" as TabKey, label: "Floors", icon: Layers },
      { key: "leases" as TabKey, label: "Leases", icon: FileSignature },
      { key: "tenants" as TabKey, label: "Tenants", icon: UsersRound },
      { key: "maintenance" as TabKey, label: "Maintenance", icon: Wrench },
    ] : []),
    { key: "notes", label: "Notes", icon: StickyNote },
    { key: "history", label: "History", icon: History },
  ];

  return (
    <div>
      <button className="flex items-center gap-1.5 text-sm text-ink-500 hover:text-ink-800 dark:hover:text-ink-100 mb-4" onClick={() => navigate("/properties")}>
        <ArrowLeft size={15} /> Back to Properties
      </button>

      <HierarchyBreadcrumb property={property} />

      <div className="flex items-start justify-between flex-wrap gap-4 mb-6">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="font-display text-xl font-bold">{property.title}</h1>
            <StatusBadge status={property.status} />
          </div>
          <div className="flex items-center gap-2 mt-1 text-xs text-ink-500">
            <span className="font-mono">{property.property_code}</span>
            {property.internal_code && <><span>·</span><span className="font-mono">{property.internal_code}</span></>}
            <span>·</span>
            <span>{TYPE_LABELS[property.property_type] || property.property_type}</span>
            <span>·</span>
            <span>{property.owner_display_name}</span>
          </div>
        </div>
        {canEdit && (
          <button className="btn-secondary" onClick={handleArchiveToggle}>
            {property.status === "archived" ? <><ArchiveRestore size={15} /> Unarchive</> : <><Archive size={15} /> Archive</>}
          </button>
        )}
        {canDelete && (
          <button className="btn-secondary text-rust-500" onClick={handleDelete}><Trash2 size={15} /> Delete</button>
        )}
      </div>

      <PropertyHubPanel propertyId={property.id} />

      <div className="flex gap-1 border-b border-ink-100 dark:border-ink-800 mb-6 overflow-x-auto">
        {tabs.map((t) => (
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

      {tab === "overview" && <OverviewTab property={property} canEdit={canEdit} onSaved={load} />}
      {tab === "financials" && canViewReports && <FinancialsTab propertyId={property.id} />}
      {tab === "images" && <ImagesTab property={property} canEdit={canEdit} onChanged={load} />}
      {tab === "documents" && <DocumentsTab property={property} canEdit={canEdit} onChanged={load} />}
      {tab === "amenities" && <AmenitiesTab property={property} canEdit={canEdit} onChanged={load} />}
      {tab === "units" && isBuilding && <UnitsTab propertyId={property.id} ownerId={property.owner_id} canEdit={canEdit} />}
      {tab === "floors" && isBuilding && <FloorsTab buildingId={property.id} ownerId={property.owner_id} buildingTitle={property.title} canEdit={canEdit} autoOpenBulkGenerate={shouldAutoSetupFloors} />}
      {tab === "leases" && isBuilding && <BuildingLeasesTab buildingId={property.id} />}
      {tab === "tenants" && isBuilding && <BuildingTenantsTab buildingId={property.id} buildingTitle={property.title} />}
      {tab === "maintenance" && isBuilding && <BuildingMaintenanceTab buildingId={property.id} />}
      {tab === "notes" && <NotesTab propertyId={property.id} />}
      {tab === "history" && <HistoryTab propertyId={property.id} />}
    </div>
  );
}

// ==================== Overview ====================
function OverviewTab({ property, canEdit, onSaved }: { property: PropertyDetail; canEdit: boolean; onSaved: () => void }) {
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState<any>(property);
  const [saving, setSaving] = useState(false);
  const [floors, setFloors] = useState<Floor[]>([]);

  // Real Floor records for the unit's own parent building — same fix
  // as PropertyFormModal: a unit's floor is a Floors-tab-backed
  // selection, never a manually-typed internal database id.
  useEffect(() => {
    if (!property.parent_property_id) { setFloors([]); return; }
    apiClient.get<Floor[]>(`/properties/${property.parent_property_id}/floors`)
      .then(({ data }) => setFloors(data))
      .catch((err) => console.error(err));
  }, [property.parent_property_id]);

  const startEdit = () => { setForm(property); setEditing(true); };
  const handleSave = async () => {
    setSaving(true);
    try {
      await apiClient.put(`/properties/${property.id}`, form);
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
      {CONTAINER_TYPES.has(property.property_type) && property.summary && <PropertySummaryWidget summary={property.summary} />}
      <div className="card p-6 max-w-3xl">
        <div className="flex justify-end mb-2">
          {canEdit && !editing && <button className="btn-secondary" onClick={startEdit}>Edit</button>}
          {editing && (
            <div className="flex gap-2">
              <button className="btn-secondary" onClick={() => setEditing(false)}>Cancel</button>
              <button className="btn-primary" disabled={saving} onClick={handleSave}>
                {saving && <Loader2 size={14} className="animate-spin" />} Save
              </button>
            </div>
          )}
        </div>

        <h3 className="font-display font-semibold text-sm mb-3 flex items-center gap-1.5"><MapPin size={15} /> Location & GPS</h3>
        <div className="grid grid-cols-2 gap-4 mb-6">
          <Field label="Address Line 1" value={property.address_line1} name="address_line1" />
          <Field label="Address Line 2" value={property.address_line2} name="address_line2" />
          <Field label="Postal Code" value={property.postal_code} name="postal_code" />
          <div />
          <Field label="Latitude" value={property.latitude} name="latitude" type="number" />
          <Field label="Longitude" value={property.longitude} name="longitude" type="number" />
        </div>

        <h3 className="font-display font-semibold text-sm mb-3">Physical Attributes</h3>
        <div className="grid grid-cols-2 gap-4 mb-6">
          <Field label="Area (sqm)" value={property.area_sqm} name="area_sqm" type="number" />
          <Field label="Bedrooms" value={property.bedrooms} name="bedrooms" type="number" />
          <Field label="Bathrooms" value={property.bathrooms} name="bathrooms" type="number" />
          <Field label="Floor" value={property.floor_number} name="floor_number" />
          <Field label="Total Floors" value={property.total_floors} name="total_floors" type="number" />
          <Field label="Year Built" value={property.year_built} name="year_built" type="number" />
        </div>

        {["building", "commercial_building", "commercial_complex", "mixed_use"].includes(property.property_type) && (
          <>
            <h3 className="font-display font-semibold text-sm mb-3">Building Characteristics</h3>
            <div className="grid grid-cols-2 gap-4 mb-6">
              <Field label="Elevators" value={property.elevators} name="elevators" type="number" />
              <Field label="Parking Spaces" value={property.parking_spaces_count} name="parking_spaces_count" type="number" />
            </div>
          </>
        )}

        {property.property_type === "villa" && (
          <>
            <h3 className="font-display font-semibold text-sm mb-3">Villa Characteristics</h3>
            <div className="grid grid-cols-2 gap-4 mb-6">
              <Field label="Parking Spaces" value={property.parking_spaces_count} name="parking_spaces_count" type="number" />
              <div />
              {(["garden", "swimming_pool", "maid_room"] as const).map((name) => (
                <div key={name}>
                  <label className="label capitalize">{name.replace("_", " ")}</label>
                  {editing ? (
                    <label className="flex items-center gap-2 py-2">
                      <input type="checkbox" checked={!!form[name]} onChange={(e) => setForm({ ...form, [name]: e.target.checked })} />
                      <span className="text-sm text-ink-600 dark:text-ink-300">Yes</span>
                    </label>
                  ) : (
                    <p className="text-sm text-ink-700 dark:text-ink-200 py-2">{property[name] ? "Yes" : "No"}</p>
                  )}
                </div>
              ))}
            </div>
          </>
        )}

        <h3 className="font-display font-semibold text-sm mb-3">Unit Details</h3>
        <div className="grid grid-cols-2 gap-4 mb-6">
          <Field label="Unit Number" value={property.unit_number} name="unit_number" />
          <Field label="PACI Number (Kuwait address code)" value={property.paci_number} name="paci_number" />
          <Field label="Rent Price (asking)" value={property.rent_price} name="rent_price" type="number" />
          <Field label="Electricity Meter #" value={property.electricity_meter_number} name="electricity_meter_number" />
          <Field label="Water Meter #" value={property.water_meter_number} name="water_meter_number" />
          <div>
            <label className="label">Floor</label>
            {editing ? (
              <select className="input" value={form.floor_id ?? ""} onChange={(e) => setForm({ ...form, floor_id: e.target.value ? Number(e.target.value) : null })}>
                <option value="">{property.parent_property_id ? "Select a floor…" : "No parent building set"}</option>
                {floors.map((f) => <option key={f.id} value={f.id}>{f.floor_name ? `${f.floor_name} (${f.floor_number})` : f.floor_number}</option>)}
              </select>
            ) : (
              <p className="text-sm text-ink-700 dark:text-ink-200 py-2">{property.floor_label || "—"}</p>
            )}
          </div>
          <div>
            <label className="label">Assigned Parking {editing && "(Property ID)"}</label>
            {editing ? (
              <input className="input" type="number" value={form.parking_space_id ?? ""} onChange={(e) => setForm({ ...form, parking_space_id: e.target.value ? Number(e.target.value) : null })} />
            ) : (
              <p className="text-sm text-ink-700 dark:text-ink-200 py-2 font-mono">{property.parking_space_code || "—"}</p>
            )}
          </div>
          <div>
            <label className="label">Assigned Storage {editing && "(Property ID)"}</label>
            {editing ? (
              <input className="input" type="number" value={form.storage_space_id ?? ""} onChange={(e) => setForm({ ...form, storage_space_id: e.target.value ? Number(e.target.value) : null })} />
            ) : (
              <p className="text-sm text-ink-700 dark:text-ink-200 py-2 font-mono">{property.storage_space_code || "—"}</p>
            )}
          </div>
        </div>

        <h3 className="font-display font-semibold text-sm mb-3">Availability</h3>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label">Availability Status</label>
            {editing ? (
              <select className="input" value={form.availability_status} onChange={(e) => setForm({ ...form, availability_status: e.target.value })}>
                <option value="available">Available</option>
                <option value="leased">Leased</option>
                <option value="reserved">Reserved</option>
                <option value="under_maintenance">Under Maintenance</option>
                <option value="off_market">Off Market</option>
              </select>
            ) : (
              <p className="text-sm text-ink-700 dark:text-ink-200 py-2 capitalize">{property.availability_status.replace(/_/g, " ")}</p>
            )}
          </div>
        </div>

        <div className="mt-4">
          <label className="label">Notes Summary</label>
          {editing ? (
            <textarea className="input" rows={3} value={form.notes_summary ?? ""} onChange={(e) => setForm({ ...form, notes_summary: e.target.value })} />
          ) : (
            <p className="text-sm text-ink-700 dark:text-ink-200 py-2">{property.notes_summary || "—"}</p>
          )}
        </div>
      </div>

      <div className="card p-6 max-w-3xl">
        <h3 className="font-display font-semibold text-sm mb-3">Current Lease Contract</h3>
        {property.current_lease_id ? (
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-mono">{property.current_lease_contract_number}</p>
              <p className="text-xs text-ink-400 mt-0.5">Ends {property.current_lease_end_date}</p>
            </div>
            <a href={`/leases/${property.current_lease_id}`} className="btn-secondary">View Lease</a>
          </div>
        ) : (
          <p className="text-sm text-ink-400">No active lease linked to this property.</p>
        )}
      </div>
    </div>
  );
}

// ==================== Images ====================
function ImagesTab({ property, canEdit, onChanged }: { property: PropertyDetail; canEdit: boolean; onChanged: () => void }) {
  const [modalOpen, setModalOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [caption, setCaption] = useState("");
  const [isCover, setIsCover] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append("is_cover", String(isCover));
      if (caption) formData.append("caption", caption);
      formData.append("file", file);
      await apiClient.post(`/properties/${property.id}/images`, formData, { headers: { "Content-Type": "multipart/form-data" } });
      setModalOpen(false);
      setFile(null);
      setCaption("");
      setIsCover(false);
      onChanged();
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Upload failed. Only image files are accepted here.");
    } finally {
      setUploading(false);
    }
  };

  const setCover = async (img: PropertyImage) => {
    await apiClient.put(`/properties/${property.id}/images/${img.id}`, { is_cover: true });
    onChanged();
  };

  const handleDelete = async (img: PropertyImage) => {
    if (!confirm("Delete this image?")) return;
    await apiClient.delete(`/properties/${property.id}/images/${img.id}`);
    onChanged();
  };

  return (
    <div className="card">
      <div className="flex justify-between items-center px-5 py-4 border-b border-ink-100 dark:border-ink-800">
        <h3 className="font-display font-semibold text-sm">Images</h3>
        {canEdit && <button className="btn-secondary" onClick={() => setModalOpen(true)}><Upload size={14} /> Upload Image</button>}
      </div>
      {property.images.length === 0 && <EmptyState title="No images uploaded" description="Add photos to showcase this property." />}
      {property.images.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 p-5">
          {property.images.map((img) => (
            <div key={img.id} className="relative group">
              <img src={img.file_url ?? undefined} alt={img.caption || img.file_name} className="w-full h-32 object-cover rounded-md border border-ink-100 dark:border-ink-800" />
              {img.is_cover && <span className="absolute top-1.5 left-1.5 badge-active"><Star size={10} /> Cover</span>}
              {canEdit && (
                <div className="absolute inset-0 bg-ink-950/50 opacity-0 group-hover:opacity-100 transition-opacity rounded-md flex items-center justify-center gap-2">
                  {!img.is_cover && <button className="btn-secondary !px-2 !py-1" onClick={() => setCover(img)}>Set Cover</button>}
                  <button className="btn-secondary !px-2 !py-1 text-rust-500" onClick={() => handleDelete(img)}><Trash2 size={13} /></button>
                </div>
              )}
              {img.caption && <p className="text-xs text-ink-400 mt-1 truncate">{img.caption}</p>}
            </div>
          ))}
        </div>
      )}

      <Modal
        open={modalOpen} onClose={() => setModalOpen(false)} title="Upload Image"
        footer={<><button className="btn-secondary" onClick={() => setModalOpen(false)}>Cancel</button><button className="btn-primary" disabled={uploading || !file} onClick={handleUpload}>{uploading && <Loader2 size={14} className="animate-spin" />} Upload</button></>}
      >
        {error && <div className="mb-3 text-sm text-rust-500 bg-rust-50 dark:bg-rust-500/10 rounded-md px-3 py-2">{error}</div>}
        <div className="space-y-4">
          <div>
            <label className="label">Caption</label>
            <input className="input" value={caption} onChange={(e) => setCaption(e.target.value)} />
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={isCover} onChange={(e) => setIsCover(e.target.checked)} />
            Set as cover photo
          </label>
          <div>
            <label className="label">Image File *</label>
            <input className="input" type="file" accept="image/*" onChange={(e) => setFile(e.target.files?.[0] || null)} />
          </div>
        </div>
      </Modal>
    </div>
  );
}

// ==================== Documents ====================
function DocumentsTab({ property, canEdit, onChanged }: { property: PropertyDetail; canEdit: boolean; onChanged: () => void }) {
  const [modalOpen, setModalOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [documentType, setDocumentType] = useState("title_deed");
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
      await apiClient.post(`/properties/${property.id}/documents`, formData, { headers: { "Content-Type": "multipart/form-data" } });
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

  const handleDelete = async (d: PropertyDocument) => {
    if (!confirm(`Delete "${d.file_name}"?`)) return;
    await apiClient.delete(`/properties/${property.id}/documents/${d.id}`);
    onChanged();
  };

  return (
    <div className="card">
      <div className="flex justify-between items-center px-5 py-4 border-b border-ink-100 dark:border-ink-800">
        <h3 className="font-display font-semibold text-sm">Documents</h3>
        {canEdit && <button className="btn-secondary" onClick={() => setModalOpen(true)}><Upload size={14} /> Upload Document</button>}
      </div>
      {property.documents.length === 0 && <EmptyState title="No documents uploaded" description="Upload title deed, floor plan, permits, or inspection reports." />}
      <div className="divide-y divide-ink-50 dark:divide-ink-800/60">
        {property.documents.map((d) => (
          <div key={d.id} className="px-5 py-3 flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2">
                <a href={d.file_url ?? "#"} target="_blank" rel="noreferrer" className="text-sm font-medium text-brand-600 dark:text-brand-400 hover:underline">{d.file_name}</a>
                {d.is_expired && <span className="badge-warn"><AlertTriangle size={10} /> Expired</span>}
              </div>
              <p className="text-xs text-ink-400 capitalize mt-0.5">
                {d.document_type.replace(/_/g, " ")} {d.document_number ? `· ${d.document_number}` : ""} {d.expiry_date ? `· expires ${d.expiry_date}` : ""}
              </p>
            </div>
            {canEdit && <button className="btn-secondary !px-2 !py-1 text-rust-500" onClick={() => handleDelete(d)}><Trash2 size={13} /></button>}
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
              <option value="title_deed">Title Deed</option>
              <option value="floor_plan">Floor Plan</option>
              <option value="permit">Permit</option>
              <option value="inspection_report">Inspection Report</option>
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

// ==================== Amenities ====================
function AmenitiesTab({ property, canEdit, onChanged }: { property: PropertyDetail; canEdit: boolean; onChanged: () => void }) {
  const [allAmenities, setAllAmenities] = useState<Amenity[]>([]);
  const [selected, setSelected] = useState<number[]>(property.amenities.map((a) => a.id));
  const [saving, setSaving] = useState(false);
  const [newAmenityName, setNewAmenityName] = useState("");
  const [creatingAmenity, setCreatingAmenity] = useState(false);

  const loadAmenities = () => {
    apiClient.get<PaginatedResponse<Amenity>>("/amenities", { params: { page_size: 100 } }).then(({ data }) => setAllAmenities(data.items)).catch((err) => console.error(err));
  };

  useEffect(() => { loadAmenities(); }, []);
  useEffect(() => { setSelected(property.amenities.map((a) => a.id)); }, [property]);

  const toggle = (id: number) => {
    setSelected((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  };

  const handleAddAmenity = async () => {
    if (!newAmenityName.trim()) return;
    setCreatingAmenity(true);
    try {
      await apiClient.post("/amenities", { name: newAmenityName.trim() });
      setNewAmenityName("");
      loadAmenities();
    } finally {
      setCreatingAmenity(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await apiClient.put(`/properties/${property.id}`, { amenity_ids: selected });
      onChanged();
    } finally {
      setSaving(false);
    }
  };

  const grouped = allAmenities.reduce<Record<string, Amenity[]>>((acc, a) => {
    const cat = a.category || "other";
    (acc[cat] ||= []).push(a);
    return acc;
  }, {});

  return (
    <div className="card p-6">
      <div className="flex justify-between items-center mb-4">
        <h3 className="font-display font-semibold text-sm">Amenities</h3>
        {canEdit && (
          <button className="btn-primary" disabled={saving} onClick={handleSave}>
            {saving && <Loader2 size={14} className="animate-spin" />} Save
          </button>
        )}
      </div>
      <div className="space-y-4">
        {Object.entries(grouped).map(([category, items]) => (
          <div key={category}>
            <div className="text-xs font-semibold uppercase text-ink-400 mb-1.5">{category}</div>
            <div className="flex flex-wrap gap-3">
              {items.map((a) => (
                <label key={a.id} className="flex items-center gap-1.5 text-sm">
                  <input type="checkbox" disabled={!canEdit} checked={selected.includes(a.id)} onChange={() => toggle(a.id)} />
                  {a.name}
                </label>
              ))}
            </div>
          </div>
        ))}
      </div>
      {canEdit && (
        <div className="flex gap-2 mt-5 pt-4 border-t border-ink-100 dark:border-ink-800">
          <input className="input" placeholder="Add a new amenity to the catalog…" value={newAmenityName} onChange={(e) => setNewAmenityName(e.target.value)} onKeyDown={(e) => e.key === "Enter" && handleAddAmenity()} />
          <button className="btn-secondary" disabled={creatingAmenity || !newAmenityName.trim()} onClick={handleAddAmenity}>
            {creatingAmenity ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />} Add
          </button>
        </div>
      )}
    </div>
  );
}

// ==================== Units (buildings only) ====================
function UnitsTab({ propertyId, ownerId, canEdit }: { propertyId: number; ownerId: number; canEdit: boolean }) {
  const navigate = useNavigate();
  const [units, setUnits] = useState<PropertyListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    apiClient.get<PropertyListItem[]>(`/properties/${propertyId}/units`).then(({ data }) => setUnits(data)).finally(() => setLoading(false));
  }, [propertyId]);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="card">
      <div className="px-5 py-4 border-b border-ink-100 dark:border-ink-800 flex items-center justify-between">
        <h3 className="font-display font-semibold text-sm">Units</h3>
        {canEdit && (
          <button className="btn-secondary" onClick={() => setModalOpen(true)}>
            <Plus size={14} /> Add Unit
          </button>
        )}
      </div>

      {loading && <div className="flex justify-center py-10"><Loader2 className="animate-spin text-ink-400" /></div>}
      {!loading && units.length === 0 && (
        <EmptyState title="No units linked to this building" description="Use Add Unit above, or create a property elsewhere and set this building as its parent." />
      )}
      {units.length > 0 && (
        <div className="divide-y divide-ink-50 dark:divide-ink-800/60">
          {units.map((u) => (
            <div key={u.id} className="px-5 py-3 flex items-center justify-between cursor-pointer hover:bg-ink-50 dark:hover:bg-ink-800/40" onClick={() => navigate(`/properties/${u.id}`)}>
              <div>
                <p className="text-sm font-medium">{u.title} {u.unit_number ? `· Unit ${u.unit_number}` : ""}</p>
                <p className="text-xs text-ink-400 mt-0.5 font-mono">{u.property_code} {u.rent_price ? `· ${Number(u.rent_price).toLocaleString()}` : ""}</p>
              </div>
              <span className="badge-inactive capitalize">{u.availability_status.replace(/_/g, " ")}</span>
            </div>
          ))}
        </div>
      )}

      {modalOpen && (
        <PropertyFormModal
          open={modalOpen}
          onClose={() => setModalOpen(false)}
          onSaved={() => { setModalOpen(false); load(); }}
          defaultOwnerId={ownerId}
          defaultParentPropertyId={propertyId}
        />
      )}
    </div>
  );
}

// ==================== Floors ====================
function FloorsTab({ buildingId, ownerId, buildingTitle, canEdit, autoOpenBulkGenerate }: { buildingId: number; ownerId: number; buildingTitle: string; canEdit: boolean; autoOpenBulkGenerate?: boolean }) {
  const [floors, setFloors] = useState<Floor[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [bulkModalOpen, setBulkModalOpen] = useState(false);
  const [editing, setEditing] = useState<Floor | null>(null);
  const [form, setForm] = useState<any>({ floor_number: "", floor_name: "", total_units: "", description: "" });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Chained straight from "create building" (?setupFloors=true) — opens
  // the bulk generate modal immediately so setting up floors/apartments
  // reads as part of the same flow instead of a separate later trip.
  useEffect(() => { if (autoOpenBulkGenerate && canEdit) setBulkModalOpen(true); }, [autoOpenBulkGenerate, canEdit]);

  const load = useCallback(() => {
    setLoading(true);
    apiClient.get<Floor[]>(`/properties/${buildingId}/floors`).then(({ data }) => setFloors(data)).finally(() => setLoading(false));
  }, [buildingId]);

  useEffect(() => { load(); }, [load]);

  const openCreate = () => {
    setEditing(null);
    setForm({ floor_number: "", floor_name: "", total_units: "", description: "" });
    setError(null);
    setModalOpen(true);
  };
  const openEdit = (f: Floor) => {
    setEditing(f);
    setForm(f);
    setError(null);
    setModalOpen(true);
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      const payload = { ...form, total_units: form.total_units ? Number(form.total_units) : null };
      if (editing) {
        await apiClient.put(`/floors/${editing.id}`, payload);
      } else {
        await apiClient.post(`/properties/${buildingId}/floors`, payload);
      }
      setModalOpen(false);
      load();
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Unable to save this floor.");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (f: Floor) => {
    if (!confirm(`Delete floor "${f.floor_number}"?`)) return;
    try {
      await apiClient.delete(`/floors/${f.id}`);
      load();
    } catch (err: any) {
      alert(err?.response?.data?.detail || "Unable to delete this floor.");
    }
  };

  return (
    <div className="card">
      <div className="flex justify-between items-center px-5 py-4 border-b border-ink-100 dark:border-ink-800">
        <h3 className="font-display font-semibold text-sm">Floors</h3>
        {canEdit && (
          <div className="flex gap-2">
            <button className="btn-secondary" onClick={() => setBulkModalOpen(true)}><Sparkles size={14} /> Bulk Generate</button>
            <button className="btn-secondary" onClick={openCreate}><Plus size={14} /> Add Floor</button>
          </div>
        )}
      </div>
      {loading && <div className="flex justify-center py-10"><Loader2 className="animate-spin text-ink-400" /></div>}
      {!loading && floors.length === 0 && <EmptyState title="No floors defined yet" description="Add floors to organize units by level." />}
      {floors.length > 0 && (
        <div className="divide-y divide-ink-50 dark:divide-ink-800/60">
          {floors.map((f) => (
            <div key={f.id} className="px-5 py-3 flex items-center justify-between">
              <div>
                <p className="text-sm font-medium">{f.floor_name || `Floor ${f.floor_number}`}</p>
                <p className="text-xs text-ink-400 mt-0.5">Floor #{f.floor_number} · {f.unit_count} unit(s){f.total_units ? ` of ${f.total_units} planned` : ""}</p>
              </div>
              <div className="flex gap-1">
                {canEdit && (
                  <>
                    <button className="btn-secondary !px-2 !py-1" onClick={() => openEdit(f)}><Pencil size={13} /></button>
                    <button className="btn-secondary !px-2 !py-1 text-rust-500" onClick={() => handleDelete(f)}><Trash2 size={13} /></button>
                  </>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      <Modal
        open={modalOpen} onClose={() => setModalOpen(false)} title={editing ? "Edit Floor" : "Add Floor"}
        footer={<><button className="btn-secondary" onClick={() => setModalOpen(false)}>Cancel</button><button className="btn-primary" disabled={saving} onClick={handleSave}>{saving && <Loader2 size={14} className="animate-spin" />} Save</button></>}
      >
        {error && <div className="mb-3 text-sm text-rust-500 bg-rust-50 dark:bg-rust-500/10 rounded-md px-3 py-2">{error}</div>}
        <div className="space-y-4">
          <div>
            <label className="label">Floor Number *</label>
            <input className="input" required value={form.floor_number} onChange={(e) => setForm({ ...form, floor_number: e.target.value })} placeholder="e.g. 1, G, M, PH" />
          </div>
          <div>
            <label className="label">Floor Name</label>
            <input className="input" value={form.floor_name || ""} onChange={(e) => setForm({ ...form, floor_name: e.target.value })} placeholder="e.g. Ground Floor" />
          </div>
          <div>
            <label className="label">Planned Total Units</label>
            <input className="input" type="number" min="0" value={form.total_units ?? ""} onChange={(e) => setForm({ ...form, total_units: e.target.value })} />
          </div>
          <div>
            <label className="label">Description</label>
            <textarea className="input" rows={2} value={form.description || ""} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          </div>
        </div>
      </Modal>

      {bulkModalOpen && (
        <BulkGenerateUnitsModal
          buildingId={buildingId}
          ownerId={ownerId}
          buildingTitle={buildingTitle}
          onClose={() => setBulkModalOpen(false)}
          onGenerated={() => { setBulkModalOpen(false); load(); }}
        />
      )}
    </div>
  );
}

function BulkGenerateUnitsModal({
  buildingId, ownerId, buildingTitle, onClose, onGenerated,
}: { buildingId: number; ownerId: number; buildingTitle: string; onClose: () => void; onGenerated: () => void }) {
  const [floorCount, setFloorCount] = useState("5");
  const [startingFloorNumber, setStartingFloorNumber] = useState("1");
  const [unitsPerFloor, setUnitsPerFloor] = useState("4");
  const [startingUnitIndex, setStartingUnitIndex] = useState("1");
  const [numberingStyle, setNumberingStyle] = useState("floor_prefixed");
  const [customizePerFloor, setCustomizePerFloor] = useState(false);
  const [floorOverrides, setFloorOverrides] = useState<Record<number, string>>({});
  const [unitPropertyType, setUnitPropertyType] = useState("apartment");
  const [bedrooms, setBedrooms] = useState("");
  const [bathrooms, setBathrooms] = useState("");
  const [areaSqm, setAreaSqm] = useState("");
  const [rentPrice, setRentPrice] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<{ floors_created: number; floors_reused: number; units_created: number } | null>(null);

  const floorCountNum = Number(floorCount) || 0;
  const unitsPerFloorNum = Number(unitsPerFloor) || 0;
  const floorNumbers = Array.from({ length: floorCountNum }, (_, i) => (Number(startingFloorNumber) || 1) + i);
  const totalUnits = customizePerFloor
    ? floorNumbers.reduce((sum, fn) => sum + (floorOverrides[fn] !== undefined && floorOverrides[fn] !== "" ? Number(floorOverrides[fn]) : unitsPerFloorNum), 0)
    : floorCountNum * unitsPerFloorNum;

  const submit = async () => {
    setSubmitting(true);
    setError(null);
    try {
      const overridesPayload = customizePerFloor
        ? floorNumbers
            .filter((fn) => floorOverrides[fn] !== undefined && floorOverrides[fn] !== "" && Number(floorOverrides[fn]) !== unitsPerFloorNum)
            .map((fn) => ({ floor_number: fn, units_count: Number(floorOverrides[fn]) }))
        : undefined;

      const { data } = await apiClient.post(`/properties/${buildingId}/bulk-generate-units`, {
        floor_count: floorCountNum,
        starting_floor_number: Number(startingFloorNumber) || 1,
        units_per_floor: unitsPerFloorNum,
        starting_unit_index: Number(startingUnitIndex) || 1,
        numbering_style: numberingStyle,
        floor_overrides: overridesPayload && overridesPayload.length > 0 ? overridesPayload : undefined,
        unit_property_type: unitPropertyType,
        title_prefix: buildingTitle,
        owner_id: ownerId,
        bedrooms: bedrooms ? Number(bedrooms) : undefined,
        bathrooms: bathrooms ? Number(bathrooms) : undefined,
        area_sqm: areaSqm || undefined,
        rent_price: rentPrice || undefined,
      });
      setResult(data);
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Could not generate floors and units — check the numbers above.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      open
      onClose={onClose}
      title="Bulk Generate Floors & Units"
      footer={
        result ? (
          <button className="btn-primary" onClick={onGenerated}>Done</button>
        ) : (
          <>
            <button className="btn-secondary" onClick={onClose}>Cancel</button>
            <button className="btn-primary" disabled={submitting || totalUnits === 0} onClick={submit}>
              {submitting && <Loader2 size={14} className="animate-spin" />} Generate {totalUnits > 0 ? `${totalUnits} Unit(s)` : ""}
            </button>
          </>
        )
      }
    >
      {result ? (
        <p className="text-sm text-ink-600">
          Done — {result.floors_created} new floor(s) created{result.floors_reused > 0 ? ` (${result.floors_reused} existing floor(s) reused)` : ""},
          and {result.units_created} unit(s) generated. Open the Units tab to see them.
        </p>
      ) : (
        <div className="space-y-4">
          <p className="text-xs text-ink-400 bg-ink-50 dark:bg-ink-800/60 rounded-md p-2">
            Generates every floor and unit in one step instead of adding each one by hand. Floors that already exist (matched by floor number) are reused, not duplicated — safe to run again later to add more.
          </p>
          {error && <div className="text-sm text-rust-500 bg-rust-50 dark:bg-rust-500/10 rounded-md px-3 py-2">{error}</div>}

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Number of Floors *</label>
              <input className="input" type="number" min="1" max="200" value={floorCount} onChange={(e) => setFloorCount(e.target.value)} />
            </div>
            <div>
              <label className="label">Starting Floor Number</label>
              <input className="input" type="number" value={startingFloorNumber} onChange={(e) => setStartingFloorNumber(e.target.value)} />
            </div>
            <div>
              <label className="label">Units per Floor *</label>
              <input className="input" type="number" min="1" max="200" value={unitsPerFloor} onChange={(e) => setUnitsPerFloor(e.target.value)} />
            </div>
            <div>
              <label className="label">Starting Unit Number</label>
              <input className="input" type="number" min="1" value={startingUnitIndex} onChange={(e) => setStartingUnitIndex(e.target.value)} />
            </div>
          </div>

          <div>
            <label className="label">Unit Type *</label>
            <select className="input" value={unitPropertyType} onChange={(e) => setUnitPropertyType(e.target.value)}>
              <option value="apartment">Apartment</option>
              <option value="office">Office</option>
              <option value="commercial_unit">Commercial Unit</option>
              <option value="shop">Shop</option>
            </select>
          </div>

          <div>
            <label className="label">Numbering Style</label>
            <select className="input" value={numberingStyle} onChange={(e) => setNumberingStyle(e.target.value)}>
              <option value="floor_prefixed">Floor-prefixed (e.g. 101, 102 … 201, 202)</option>
              <option value="sequential">Sequential across the building (e.g. 1, 2, 3, 4, 5, 6)</option>
            </select>
          </div>

          <label className="flex items-center gap-2 text-sm text-ink-600 dark:text-ink-300">
            <input type="checkbox" checked={customizePerFloor} onChange={(e) => setCustomizePerFloor(e.target.checked)} />
            Customize units for specific floors (e.g. ground floor has fewer units)
          </label>

          {customizePerFloor && floorCountNum > 0 && (
            <div className="border border-ink-100 dark:border-ink-800 rounded-lg divide-y divide-ink-50 dark:divide-ink-800/60 max-h-48 overflow-y-auto">
              {floorNumbers.map((fn) => (
                <div key={fn} className="flex items-center justify-between px-3 py-1.5 text-sm">
                  <span>Floor {fn}</span>
                  <input
                    type="number" min="0" max="200" className="input !w-24 !py-1"
                    placeholder={String(unitsPerFloorNum)}
                    value={floorOverrides[fn] ?? ""}
                    onChange={(e) => setFloorOverrides({ ...floorOverrides, [fn]: e.target.value })}
                  />
                </div>
              ))}
            </div>
          )}

          <p className="text-xs text-ink-400">
            {numberingStyle === "sequential" ? (
              <>Units will be numbered continuously across the whole building (e.g. Floor {startingFloorNumber || 1} → Unit {startingUnitIndex || 1}, {(Number(startingUnitIndex) || 1) + 1}, … then Floor {(Number(startingFloorNumber) || 1) + 1} continues from {(Number(startingUnitIndex) || 1) + unitsPerFloorNum}).</>
            ) : (
              <>Units will be numbered automatically (e.g. Floor {startingFloorNumber || 1} → Unit {startingFloorNumber || 1}{String(Number(startingUnitIndex) || 1).padStart(2, "0")}, {startingFloorNumber || 1}{String((Number(startingUnitIndex) || 1) + 1).padStart(2, "0")}, ...).</>
            )}{" "}
            Edit any unit individually afterward for its exact details.
          </p>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Bedrooms (optional, applied to all)</label>
              <input className="input" type="number" min="0" value={bedrooms} onChange={(e) => setBedrooms(e.target.value)} />
            </div>
            <div>
              <label className="label">Bathrooms (optional, applied to all)</label>
              <input className="input" type="number" min="0" value={bathrooms} onChange={(e) => setBathrooms(e.target.value)} />
            </div>
            <div>
              <label className="label">Area sqm (optional, applied to all)</label>
              <input className="input" value={areaSqm} onChange={(e) => setAreaSqm(e.target.value)} />
            </div>
            <div>
              <label className="label">Rent Price (optional, applied to all)</label>
              <input className="input" value={rentPrice} onChange={(e) => setRentPrice(e.target.value)} />
            </div>
          </div>
        </div>
      )}
    </Modal>
  );
}

// ==================== Property Summary Widget (Phase 2.0) ====================
// Reads property.summary, already embedded in the GET /properties/{id}
// response — no separate fetch needed. Superset of the old
// BuildingSummaryWidget (same underlying numbers, see property_service.py
// get_property_summary), extended with occupancy rate, residential/
// commercial split, contracts expiring soon, and this month's revenue/
// expenses/net profit.
function PropertySummaryWidget({ summary }: { summary: PropertySummary }) {
  const money = (v: string | null | undefined) => v == null ? "—" : Number(v).toLocaleString(undefined, { minimumFractionDigits: 3 });

  const stats: { label: string; value: string | number; icon: typeof Home; tone: string }[] = [
    { label: "Floors", value: summary.total_floors, icon: Layers, tone: "text-brand-500" },
    { label: "Total Units", value: summary.total_units, icon: Building2, tone: "text-brand-500" },
    { label: "Occupied Units", value: summary.occupied_units, icon: DoorClosed, tone: "text-brand-500" },
    { label: "Vacant Units", value: summary.vacant_units, icon: DoorOpen, tone: "text-amber-500" },
    { label: "Reserved Units", value: summary.reserved_units, icon: Pin, tone: "text-amber-500" },
    { label: "Under Maintenance", value: summary.under_maintenance_units, icon: Wrench, tone: "text-ink-400" },
    { label: "Residential Units", value: summary.residential_units, icon: Home, tone: "text-brand-500" },
    { label: "Commercial Units", value: summary.commercial_units, icon: Building2, tone: "text-brand-500" },
    { label: "Occupancy Rate", value: `${summary.occupancy_rate}%`, icon: Percent, tone: "text-brand-500" },
    { label: "Active Contracts", value: summary.active_contracts, icon: FileSignature, tone: "text-brand-500" },
    { label: "Expired Contracts", value: summary.expired_contracts, icon: FileSignature, tone: "text-ink-400" },
    { label: "Expiring Soon", value: summary.contracts_expiring_soon, icon: AlertTriangle, tone: summary.contracts_expiring_soon > 0 ? "text-amber-500" : "text-ink-400" },
  ];

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {stats.map((s) => (
          <div key={s.label} className="card p-4">
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-xs font-medium text-ink-500 dark:text-ink-400">{s.label}</span>
              <s.icon size={14} className={s.tone} />
            </div>
            <div className="font-display text-xl font-bold">{s.value}</div>
          </div>
        ))}
      </div>
      <div className="grid grid-cols-3 gap-3">
        <div className="card p-4">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-xs font-medium text-ink-500 dark:text-ink-400">Monthly Revenue</span>
            <TrendingUp size={14} className="text-brand-500" />
          </div>
          <div className="font-display text-xl font-bold">{money(summary.monthly_revenue)}</div>
        </div>
        <div className="card p-4">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-xs font-medium text-ink-500 dark:text-ink-400">Monthly Expenses</span>
            <TrendingDown size={14} className="text-rust-500" />
          </div>
          <div className="font-display text-xl font-bold">{money(summary.monthly_expenses)}</div>
        </div>
        <div className="card p-4">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-xs font-medium text-ink-500 dark:text-ink-400">Net Profit</span>
            <DollarSign size={14} className="text-brand-500" />
          </div>
          <div className="font-display text-xl font-bold">{money(summary.net_profit)}</div>
        </div>
      </div>
    </div>
  );
}

// ==================== Building Leases ====================
function BuildingLeasesTab({ buildingId }: { buildingId: number }) {
  const navigate = useNavigate();
  const [statusFilter, setStatusFilter] = useState("");
  const [data, setData] = useState<PaginatedResponse<RentalContractListItem> | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    apiClient.get<PaginatedResponse<RentalContractListItem>>(`/properties/${buildingId}/leases`, {
      params: { contract_status: statusFilter || undefined, page_size: 50 },
    }).then(({ data }) => setData(data)).finally(() => setLoading(false));
  }, [buildingId, statusFilter]);

  const STATUS_TONE: Record<string, string> = { draft: "badge-inactive", active: "badge-active", expired: "badge-warn", terminated: "badge-inactive", renewed: "badge-active" };

  return (
    <div className="card">
      <div className="flex justify-between items-center px-5 py-4 border-b border-ink-100 dark:border-ink-800">
        <h3 className="font-display font-semibold text-sm">Leases (Building + Units)</h3>
        <select className="input max-w-[160px]" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="">All statuses</option>
          <option value="active">Active</option>
          <option value="expired">Expired</option>
          <option value="draft">Draft</option>
          <option value="terminated">Terminated</option>
          <option value="renewed">Renewed</option>
        </select>
      </div>
      {loading && <div className="flex justify-center py-10"><Loader2 className="animate-spin text-ink-400" /></div>}
      {!loading && data && data.items.length === 0 && <EmptyState title="No leases found" description="No rental contracts exist yet for this building or its units." />}
      {!loading && data && data.items.length > 0 && (
        <div className="divide-y divide-ink-50 dark:divide-ink-800/60">
          {data.items.map((c) => (
            <div key={c.id} className="px-5 py-3 flex items-center justify-between cursor-pointer hover:bg-ink-50 dark:hover:bg-ink-800/40" onClick={() => navigate(`/rentals/${c.id}`)}>
              <div>
                <p className="text-sm font-medium">{c.contract_number} — {c.tenant_display_name}</p>
                <p className="text-xs text-ink-400 mt-0.5">{c.property_title} · {c.start_date} to {c.end_date} · {Number(c.rent_amount).toLocaleString()}</p>
              </div>
              <span className={STATUS_TONE[c.contract_status]}>{c.contract_status}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ==================== Building Tenants ====================
function BuildingTenantsTab({ buildingId, buildingTitle }: { buildingId: number; buildingTitle: string }) {
  const navigate = useNavigate();
  const { hasPermission } = useAuth();
  const [tenants, setTenants] = useState<TenantListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [importOpen, setImportOpen] = useState(false);

  const load = () => {
    setLoading(true);
    apiClient.get<TenantListItem[]>(`/properties/${buildingId}/tenants`).then(({ data }) => setTenants(data)).finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, [buildingId]);

  return (
    <div>
      {hasPermission("tenants.create") && (
        <div className="flex justify-end mb-3">
          <button className="btn-secondary" onClick={() => setImportOpen(true)}>
            <Upload size={15} /> Import Tenants from Excel
          </button>
        </div>
      )}
      <div className="card">
      {loading && <div className="flex justify-center py-10"><Loader2 className="animate-spin text-ink-400" /></div>}
      {!loading && tenants.length === 0 && <EmptyState title="No tenants yet" description="Tenants will appear here once a rental contract is created for a unit in this building." />}
      {!loading && tenants.length > 0 && (
        <div className="divide-y divide-ink-50 dark:divide-ink-800/60">
          {tenants.map((t) => (
            <div key={t.id} className="px-5 py-3 flex items-center justify-between cursor-pointer hover:bg-ink-50 dark:hover:bg-ink-800/40" onClick={() => navigate(`/tenants/${t.id}`)}>
              <div>
                <p className="text-sm font-medium">{t.display_name}</p>
                <p className="text-xs text-ink-400 mt-0.5">{t.tenant_code} · {t.primary_email || t.primary_phone || "—"}</p>
              </div>
              {t.is_blacklisted && <span className="badge-warn">Blacklisted</span>}
            </div>
          ))}
        </div>
      )}
      </div>
      <TenantImportModal open={importOpen} onClose={() => setImportOpen(false)} buildingId={buildingId} buildingTitle={buildingTitle} onImported={load} />
    </div>
  );
}

// ==================== Building Maintenance ====================
function BuildingMaintenanceTab({ buildingId }: { buildingId: number }) {
  const navigate = useNavigate();
  const [data, setData] = useState<PaginatedResponse<MaintenanceRequestListItem> | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiClient.get<PaginatedResponse<MaintenanceRequestListItem>>(`/properties/${buildingId}/maintenance-requests`, { params: { page_size: 50 } })
      .then(({ data }) => setData(data)).finally(() => setLoading(false));
  }, [buildingId]);

  const STATUS_TONE: Record<string, string> = { reported: "badge-warn", assigned: "badge-inactive", in_progress: "badge-active", on_hold: "badge-inactive", completed: "badge-active", cancelled: "badge-inactive" };

  return (
    <div className="card">
      <div className="px-5 py-4 border-b border-ink-100 dark:border-ink-800"><h3 className="font-display font-semibold text-sm">Maintenance Requests (Building + Units)</h3></div>
      {loading && <div className="flex justify-center py-10"><Loader2 className="animate-spin text-ink-400" /></div>}
      {!loading && data && data.items.length === 0 && <EmptyState title="No maintenance requests" description="No maintenance has been reported for this building or its units." />}
      {!loading && data && data.items.length > 0 && (
        <div className="divide-y divide-ink-50 dark:divide-ink-800/60">
          {data.items.map((m) => (
            <div key={m.id} className="px-5 py-3 flex items-center justify-between cursor-pointer hover:bg-ink-50 dark:hover:bg-ink-800/40" onClick={() => navigate(`/maintenance/${m.id}`)}>
              <div>
                <p className="text-sm font-medium">{m.title}</p>
                <p className="text-xs text-ink-400 mt-0.5">{m.property_title} · {m.request_number} · reported {m.reported_date}</p>
              </div>
              <div className="flex items-center gap-2">
                {m.is_overdue && <AlertTriangle size={13} className="text-rust-500" />}
                <span className={STATUS_TONE[m.maintenance_status]}>{m.maintenance_status.replace(/_/g, " ")}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ==================== Financials (Property Profit Center) ====================
// Every Property is a financial profit center, not just Buildings — this
// tab is visible for any property type. Reuses the same
// /properties/{id}/financial-dashboard endpoint that composes Phase 10's
// accounting-grade reports and Phase 11's operational reports, scoped to
// this one property.
function FinancialsTab({ propertyId }: { propertyId: number }) {
  const [data, setData] = useState<PropertyFinancialDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    setLoading(true);
    setError(false);
    apiClient.get<PropertyFinancialDashboard>(`/properties/${propertyId}/financial-dashboard`)
      .then(({ data }) => setData(data))
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [propertyId]);

  if (loading) return <div className="flex justify-center py-10"><Loader2 className="animate-spin text-ink-400" /></div>;
  if (error || !data) return <EmptyState title="Financial data unavailable" description="This property may not have any financial activity yet." />;
  const k = data.kpis;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="card p-4">
          <div className="flex items-center justify-between mb-1.5"><span className="text-xs font-medium text-ink-500">Status</span><DoorClosed size={14} className="text-brand-500" /></div>
          <div className="font-display text-lg font-bold capitalize">{k.availability_status}</div>
        </div>
        <div className="card p-4">
          <div className="flex items-center justify-between mb-1.5"><span className="text-xs font-medium text-ink-500">Active Leases</span><FileSignature size={14} className="text-brand-500" /></div>
          <div className="font-display text-lg font-bold">{k.active_leases_count}</div>
        </div>
        <div className="card p-4">
          <div className="flex items-center justify-between mb-1.5"><span className="text-xs font-medium text-ink-500">Open Maintenance</span><Wrench size={14} className="text-amber-500" /></div>
          <div className="font-display text-lg font-bold">{k.open_maintenance_requests}</div>
        </div>
        <div className="card p-4">
          <div className="flex items-center justify-between mb-1.5"><span className="text-xs font-medium text-ink-500">Outstanding (Tenant)</span><DollarSign size={14} className="text-rust-500" /></div>
          <div className="font-display text-lg font-bold">{Number(k.total_outstanding_tenant).toLocaleString()}</div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="card p-5">
          <p className="text-xs font-semibold uppercase text-ink-400 mb-3">This Month</p>
          <div className="space-y-2">
            <div className="flex justify-between text-sm"><span className="flex items-center gap-1.5 text-ink-500"><TrendingUp size={13} className="text-brand-500" /> Income</span><span className="font-medium">{Number(k.total_income_this_month).toLocaleString()}</span></div>
            <div className="flex justify-between text-sm"><span className="flex items-center gap-1.5 text-ink-500"><TrendingDown size={13} className="text-rust-500" /> Expense</span><span className="font-medium">{Number(k.total_expense_this_month).toLocaleString()}</span></div>
            <div className="flex justify-between text-sm font-semibold border-t border-ink-100 dark:border-ink-800 pt-2 mt-2"><span>Net Profit</span><span>{Number(k.net_profit_this_month).toLocaleString()}</span></div>
          </div>
        </div>
        <div className="card p-5">
          <p className="text-xs font-semibold uppercase text-ink-400 mb-3">Year to Date</p>
          <div className="space-y-2">
            <div className="flex justify-between text-sm"><span className="flex items-center gap-1.5 text-ink-500"><TrendingUp size={13} className="text-brand-500" /> Income</span><span className="font-medium">{Number(k.total_income_ytd).toLocaleString()}</span></div>
            <div className="flex justify-between text-sm"><span className="flex items-center gap-1.5 text-ink-500"><TrendingDown size={13} className="text-rust-500" /> Expense</span><span className="font-medium">{Number(k.total_expense_ytd).toLocaleString()}</span></div>
            <div className="flex justify-between text-sm font-semibold border-t border-ink-100 dark:border-ink-800 pt-2 mt-2"><span>Net Profit</span><span>{Number(k.net_profit_ytd).toLocaleString()}</span></div>
          </div>
        </div>
      </div>

      <div className="card p-5">
        <h3 className="font-display font-semibold text-sm mb-4">6-Month Income / Expense Trend</h3>
        {data.monthly_trend.length === 0 ? <EmptyState title="No financial activity yet" /> : (
          <div className="space-y-3">
            {data.monthly_trend.map((m) => (
              <div key={m.month}>
                <div className="flex justify-between text-xs text-ink-500 mb-1"><span>{m.month}</span><span>Profit: {Number(m.profit).toLocaleString()}</span></div>
                <div className="flex gap-1 h-2">
                  <div className="bg-brand-500 rounded-full" style={{ width: `${Math.min((Number(m.income) / Math.max(Number(m.income), Number(m.expense), 1)) * 100, 100)}%` }} />
                  <div className="bg-rust-400 rounded-full" style={{ width: `${Math.min((Number(m.expense) / Math.max(Number(m.income), Number(m.expense), 1)) * 100, 100)}%` }} />
                </div>
              </div>
            ))}
          </div>
        )}
        <div className="flex gap-4 mt-3 text-xs text-ink-400">
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-brand-500 inline-block" /> Income</span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-rust-400 inline-block" /> Expense</span>
        </div>
      </div>
    </div>
  );
}

// ==================== Notes ====================
function NotesTab({ propertyId }: { propertyId: number }) {
  const [notes, setNotes] = useState<any[]>([]);
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(true);
  const [posting, setPosting] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    apiClient.get("/notes", { params: { entity_type: "property", entity_id: propertyId } })
      .then(({ data }) => setNotes(data)).finally(() => setLoading(false));
  }, [propertyId]);

  useEffect(() => { load(); }, [load]);

  const handleAdd = async () => {
    if (!content.trim()) return;
    setPosting(true);
    try {
      await apiClient.post("/notes", { entity_type: "property", entity_id: propertyId, content, is_pinned: false });
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
function HistoryTab({ propertyId }: { propertyId: number }) {
  const [entries, setEntries] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiClient.get("/activity-logs", { params: { entity_type: "property", entity_id: propertyId } })
      .then(({ data }) => setEntries(data)).finally(() => setLoading(false));
  }, [propertyId]);

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
