import { useEffect, useState } from "react";
import apiClient from "@/api/client";
import { Modal } from "@/components/ui";
import { Loader2, Plus } from "lucide-react";
import { PropertyDetail, OwnerListItem, PropertyListItem, PaginatedResponse, Floor } from "@/types";

// Split in two, per the confirmed business model ("we only ever rent
// whole buildings from owners, never individual apartments/offices/
// parking/commercial floors directly") — BUILDING_TYPES is shown when
// adding a property from the top-level Properties tab (no parent), and
// UNIT_TYPES is shown only when adding a unit *inside* an existing
// building (opened with defaultParentPropertyId already set — the
// "Add Unit" button on a building's own Units tab). Nothing was
// deleted from the backend or the data model — PropertyType still
// supports every one of these values; this only changes which ones
// this one form offers, and when.
const BUILDING_TYPES: { value: string; label: string }[] = [
  { value: "building", label: "Residential Building" },
  { value: "villa", label: "Villa" },
  { value: "commercial_building", label: "Commercial Building" },
  { value: "commercial_complex", label: "Commercial Complex" },
  { value: "warehouse", label: "Warehouse" },
  { value: "land", label: "Land" },
  { value: "mixed_use", label: "Mixed Use Property" },
];
const UNIT_TYPES: { value: string; label: string }[] = [
  { value: "apartment", label: "Apartment" },
  { value: "commercial_unit", label: "Commercial Unit" },
  { value: "shop", label: "Shop" },
  { value: "office", label: "Office" },
  { value: "parking", label: "Parking" },
  { value: "storage", label: "Storage" },
];

const HAS_ROOMS = new Set(["villa", "apartment"]);
const HAS_FLOOR = new Set(["apartment", "office", "commercial_unit", "shop"]);
// Container types (Owner -> Property -> Floors -> Units hierarchy roots),
// mirrors PropertyType.CONTAINER_TYPES on the backend.
const CONTAINER_TYPES = new Set(["building", "villa", "commercial_building", "commercial_complex", "warehouse", "land", "mixed_use"]);
const HAS_VILLA_FEATURES = new Set(["villa"]);
const HAS_BUILDING_FEATURES = new Set(["building", "commercial_building", "commercial_complex", "mixed_use"]);

const emptyForm = {
  property_type: "apartment",
  title: "",
  owner_id: "" as number | "",
  internal_code: "",
  parent_property_id: "" as number | "",
  address_line1: "",
  area_sqm: "",
  bedrooms: "",
  bathrooms: "",
  floor_id: "" as number | "",
  unit_number: "",
  rent_price: "",
  elevators: "",
  parking_spaces_count: "",
  garden: false,
  swimming_pool: false,
  maid_room: false,
};

export default function PropertyFormModal({
  open, onClose, onSaved, defaultOwnerId, defaultParentPropertyId,
}: { open: boolean; onClose: () => void; onSaved: (p: PropertyDetail) => void; defaultOwnerId?: number; defaultParentPropertyId?: number }) {
  const [form, setForm] = useState<any>(emptyForm);
  const [owners, setOwners] = useState<OwnerListItem[]>([]);
  const [buildings, setBuildings] = useState<PropertyListItem[]>([]);
  const [floors, setFloors] = useState<Floor[]>([]);
  const [loadingFloors, setLoadingFloors] = useState(false);
  const [addingFloor, setAddingFloor] = useState(false);
  const [newFloorNumber, setNewFloorNumber] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    apiClient.get<PaginatedResponse<OwnerListItem>>("/owners", { params: { page_size: 100 } }).then(({ data }) => setOwners(data.items)).catch((err) => console.error(err));
    // Every container type can be a parent (a villa or commercial
    // building can hold units too, not just "building") — fetched
    // without a property_type filter and narrowed client-side, since
    // the list endpoint only supports one exact type per call.
    apiClient.get<PaginatedResponse<PropertyListItem>>("/properties", { params: { page_size: 200 } })
      .then(({ data }) => setBuildings(data.items.filter((p) => CONTAINER_TYPES.has(p.property_type))))
      .catch((err) => console.error(err));
    setForm({
      ...emptyForm,
      // Default type matches whichever list this open() is about to
      // show: a whole building type when adding a top-level property,
      // an apartment when adding a unit inside one.
      property_type: defaultParentPropertyId ? "apartment" : "building",
      owner_id: defaultOwnerId ?? "",
      parent_property_id: defaultParentPropertyId ?? "",
    });
    setFloors([]);
    setError(null);
  }, [open, defaultOwnerId, defaultParentPropertyId]);

  // Real Floor records for whichever building is selected as the
  // parent — this is what makes the "Floor" field below an actual
  // Floors-tab-backed selection instead of unrelated free text. Reset
  // the chosen floor whenever the building changes, since a floor_id
  // from a different building would be meaningless.
  useEffect(() => {
    if (!form.parent_property_id) { setFloors([]); return; }
    setLoadingFloors(true);
    apiClient.get<Floor[]>(`/properties/${form.parent_property_id}/floors`)
      .then(({ data }) => setFloors(data))
      .catch((err) => console.error(err))
      .finally(() => setLoadingFloors(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [form.parent_property_id]);

  const addFloorInline = async () => {
    if (!newFloorNumber.trim() || !form.parent_property_id) return;
    try {
      const { data } = await apiClient.post<Floor>(`/properties/${form.parent_property_id}/floors`, { floor_number: newFloorNumber.trim() });
      setFloors((prev) => [...prev, data]);
      setForm((f: any) => ({ ...f, floor_id: data.id }));
      setNewFloorNumber("");
      setAddingFloor(false);
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Could not add that floor.");
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      const payload: any = {
        ...form,
        owner_id: Number(form.owner_id),
        parent_property_id: form.parent_property_id ? Number(form.parent_property_id) : null,
        area_sqm: form.area_sqm || null,
        bedrooms: form.bedrooms ? Number(form.bedrooms) : null,
        bathrooms: form.bathrooms ? Number(form.bathrooms) : null,
        floor_id: form.floor_id ? Number(form.floor_id) : null,
        unit_number: form.unit_number || null,
        rent_price: form.rent_price || null,
        elevators: form.elevators ? Number(form.elevators) : null,
        parking_spaces_count: form.parking_spaces_count ? Number(form.parking_spaces_count) : null,
        garden: HAS_VILLA_FEATURES.has(form.property_type) ? form.garden : null,
        swimming_pool: HAS_VILLA_FEATURES.has(form.property_type) ? form.swimming_pool : null,
        maid_room: HAS_VILLA_FEATURES.has(form.property_type) ? form.maid_room : null,
      };
      const { data } = await apiClient.post<PropertyDetail>("/properties", payload);
      onSaved(data);
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "Unable to create this property. Please check the form.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Add Property"
      footer={
        <>
          <button className="btn-secondary" onClick={onClose}>Cancel</button>
          <button className="btn-primary" disabled={saving} onClick={handleSave}>
            {saving && <Loader2 size={14} className="animate-spin" />} Create Property
          </button>
        </>
      }
    >
      {error && <div className="mb-3 text-sm text-rust-500 bg-rust-50 dark:bg-rust-500/10 rounded-md px-3 py-2">{error}</div>}
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label">Property Type *</label>
            <select className="input" value={form.property_type} onChange={(e) => setForm({ ...form, property_type: e.target.value })}>
              {(defaultParentPropertyId ? UNIT_TYPES : BUILDING_TYPES).map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
            </select>
          </div>
          <div>
            <label className="label">Owner *</label>
            <select className="input" required value={form.owner_id} onChange={(e) => setForm({ ...form, owner_id: e.target.value })}>
              <option value="">Select an owner…</option>
              {owners.map((o) => <option key={o.id} value={o.id}>{o.owner_code} — {o.display_name}</option>)}
            </select>
          </div>
        </div>
        <div>
          <label className="label">Title *</label>
          <input className="input" required value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="e.g. Sunset Villa, Unit 4B" />
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label">Internal Code</label>
            <input className="input" value={form.internal_code} onChange={(e) => setForm({ ...form, internal_code: e.target.value })} placeholder="Your own reference code" />
          </div>
          {/* "Parent Building" only makes sense while adding a unit
              *inside* a specific building (defaultParentPropertyId is
              already fixed by that context) — hidden entirely for the
              top-level "Add Property" flow, since Property Type there
              is now restricted to whole-building types only, and a
              building doesn't have a parent building in this business
              model ("we only ever rent whole buildings from owners"). */}
          {defaultParentPropertyId && (
            <div>
              <label className="label">Building</label>
              <select className="input" value={form.parent_property_id} disabled>
                {buildings.filter((b) => b.id === defaultParentPropertyId).map((b) => <option key={b.id} value={b.id}>{b.property_code} — {b.title}</option>)}
              </select>
            </div>
          )}
        </div>
        <div>
          <label className="label">Address</label>
          <input className="input" value={form.address_line1} onChange={(e) => setForm({ ...form, address_line1: e.target.value })} />
        </div>
        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className="label">Area (sqm)</label>
            <input className="input" type="number" min="0" step="0.01" value={form.area_sqm} onChange={(e) => setForm({ ...form, area_sqm: e.target.value })} />
          </div>
          {HAS_ROOMS.has(form.property_type) && (
            <>
              <div>
                <label className="label">Bedrooms</label>
                <input className="input" type="number" min="0" value={form.bedrooms} onChange={(e) => setForm({ ...form, bedrooms: e.target.value })} />
              </div>
              <div>
                <label className="label">Bathrooms</label>
                <input className="input" type="number" min="0" value={form.bathrooms} onChange={(e) => setForm({ ...form, bathrooms: e.target.value })} />
              </div>
            </>
          )}
          {HAS_FLOOR.has(form.property_type) && (
            <div>
              <label className="label">Floor</label>
              {!form.parent_property_id ? (
                <p className="text-xs text-ink-400 pt-2">Select a Parent Building above to choose its floor.</p>
              ) : addingFloor ? (
                <div className="flex gap-1.5">
                  <input
                    className="input" autoFocus placeholder="e.g. 1, G, PH"
                    value={newFloorNumber} onChange={(e) => setNewFloorNumber(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addFloorInline(); } }}
                  />
                  <button type="button" className="btn-secondary !px-2.5" onClick={addFloorInline}>Add</button>
                  <button type="button" className="btn-secondary !px-2.5" onClick={() => setAddingFloor(false)}>×</button>
                </div>
              ) : (
                <div className="flex gap-1.5">
                  <select
                    className="input" value={form.floor_id} disabled={loadingFloors}
                    onChange={(e) => setForm({ ...form, floor_id: e.target.value })}
                  >
                    <option value="">{loadingFloors ? "Loading floors…" : "Select a floor…"}</option>
                    {floors.map((f) => <option key={f.id} value={f.id}>{f.floor_name ? `${f.floor_name} (${f.floor_number})` : f.floor_number}</option>)}
                  </select>
                  <button type="button" className="btn-secondary !px-2.5" title="Add a new floor to this building" onClick={() => setAddingFloor(true)}>
                    <Plus size={14} />
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
        {HAS_BUILDING_FEATURES.has(form.property_type) && (
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label">Elevators</label>
              <input className="input" type="number" min="0" value={form.elevators} onChange={(e) => setForm({ ...form, elevators: e.target.value })} />
            </div>
            <div>
              <label className="label">Parking Spaces</label>
              <input className="input" type="number" min="0" value={form.parking_spaces_count} onChange={(e) => setForm({ ...form, parking_spaces_count: e.target.value })} />
            </div>
          </div>
        )}
        {HAS_VILLA_FEATURES.has(form.property_type) && (
          <div className="grid grid-cols-4 gap-4 items-end">
            <div>
              <label className="label">Parking Spaces</label>
              <input className="input" type="number" min="0" value={form.parking_spaces_count} onChange={(e) => setForm({ ...form, parking_spaces_count: e.target.value })} />
            </div>
            <label className="flex items-center gap-2 text-sm text-ink-600 pb-2">
              <input type="checkbox" checked={form.garden} onChange={(e) => setForm({ ...form, garden: e.target.checked })} /> Garden
            </label>
            <label className="flex items-center gap-2 text-sm text-ink-600 pb-2">
              <input type="checkbox" checked={form.swimming_pool} onChange={(e) => setForm({ ...form, swimming_pool: e.target.checked })} /> Swimming Pool
            </label>
            <label className="flex items-center gap-2 text-sm text-ink-600 pb-2">
              <input type="checkbox" checked={form.maid_room} onChange={(e) => setForm({ ...form, maid_room: e.target.checked })} /> Maid Room
            </label>
          </div>
        )}
        {!CONTAINER_TYPES.has(form.property_type) && (
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label">Unit Number</label>
              <input className="input" value={form.unit_number} onChange={(e) => setForm({ ...form, unit_number: e.target.value })} placeholder="e.g. 4B, 201" />
            </div>
            <div>
              <label className="label">Rent Price (asking)</label>
              <input className="input" type="number" min="0" step="0.001" value={form.rent_price} onChange={(e) => setForm({ ...form, rent_price: e.target.value })} />
            </div>
          </div>
        )}
        <p className="text-xs text-ink-400">You can add GPS coordinates, images, documents, and amenities after creating the property.</p>
      </div>
    </Modal>
  );
}
