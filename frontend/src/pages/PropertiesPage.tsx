import { useEffect, useState, useCallback } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import apiClient from "@/api/client";
import { useAuth } from "@/context/AuthContext";
import { PageHeader, Pagination, StatusBadge, EmptyState, ToolbarSearch, Skeleton } from "@/components/ui";
import { Plus, Home, MapPin, Building2, DoorOpen, DoorClosed, TreePine, Warehouse, Map as MapIcon, LayoutGrid, PieChart } from "lucide-react";
import { PropertyListItem, PropertyDashboard, PaginatedResponse, Floor } from "@/types";
import PropertyFormModal from "@/components/PropertyFormModal";

const TYPE_KEYS = [
  "building", "villa", "commercial_building", "commercial_complex", "warehouse", "land", "mixed_use",
  "apartment", "commercial_unit", "shop", "office", "parking", "storage",
];

// Matches UNIT_TYPES in PropertyFormModal.tsx — used below to decide
// when the default "buildings only" view should switch off (someone
// explicitly searching for a unit type across every building, not
// browsing the portfolio structurally).
const UNIT_TYPE_VALUES = new Set(["apartment", "commercial_unit", "shop", "office", "parking", "storage"]);

// Types that can own Floors (see backend FloorService.FLOOR_CAPABLE_TYPES) —
// only these show the cascading Floor filter once selected.
const FLOOR_CAPABLE_TYPES = new Set(["building", "commercial_building", "commercial_complex", "mixed_use"]);

const AVAILABILITY_TONE: Record<string, string> = {
  available: "badge-active", leased: "badge-warn", reserved: "badge-warn",
  under_maintenance: "badge-inactive", off_market: "badge-inactive",
};

export default function PropertiesPage() {
  const { hasPermission } = useAuth();
  const { t } = useTranslation("properties");
  const navigate = useNavigate();
  const [data, setData] = useState<PaginatedResponse<PropertyListItem> | null>(null);
  const [dashboard, setDashboard] = useState<PropertyDashboard | null>(null);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [propertyType, setPropertyType] = useState("");
  const [availabilityStatus, setAvailabilityStatus] = useState("");
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [searchParams] = useSearchParams();
  useEffect(() => { if (searchParams.get("new") === "true") setModalOpen(true); }, [searchParams]);

  // Phase 2.0: Building/Villa + Floor filters
  const [containers, setContainers] = useState<PropertyListItem[]>([]);
  const [parentPropertyId, setParentPropertyId] = useState("");
  const [floors, setFloors] = useState<Floor[]>([]);
  const [floorId, setFloorId] = useState("");
  const [includeArchived, setIncludeArchived] = useState(false);

  const canCreate = hasPermission("properties.create");

  const load = useCallback(() => {
    setLoading(true);
    // Defaults to buildings/villas only — a unit is only ever shown
    // here if someone explicitly drilled into a specific building
    // (parentPropertyId set) or explicitly searched for a unit type
    // across every building (propertyType is one of UNIT_TYPE_VALUES).
    // Otherwise the list used to mix every building and every one of
    // its units together in one flat table with no visual structure.
    const topLevelOnly = !parentPropertyId && !UNIT_TYPE_VALUES.has(propertyType) && !search;
    apiClient
      .get<PaginatedResponse<PropertyListItem>>("/properties", {
        params: {
          page, page_size: 10, search: search || undefined,
          property_type: propertyType || undefined, availability_status: availabilityStatus || undefined,
          parent_property_id: parentPropertyId || undefined, floor_id: floorId || undefined,
          include_archived: includeArchived || undefined, top_level_only: topLevelOnly || undefined,
        },
      })
      .then(({ data }) => setData(data))
      .finally(() => setLoading(false));
  }, [page, search, propertyType, availabilityStatus, parentPropertyId, floorId, includeArchived]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    apiClient.get<PropertyDashboard>("/properties/dashboard/summary").then(({ data }) => setDashboard(data));
  }, [data]);

  // Populate the Building/Villa filter dropdown once — buildings and
  // villas are the two container types the Phase 2.0 spec names
  // explicitly for this filter.
  useEffect(() => {
    Promise.all([
      apiClient.get<PaginatedResponse<PropertyListItem>>("/properties", { params: { property_type: "building", page_size: 200 } }),
      apiClient.get<PaginatedResponse<PropertyListItem>>("/properties", { params: { property_type: "villa", page_size: 200 } }),
    ]).then(([buildings, villas]) => {
      setContainers([...buildings.data.items, ...villas.data.items].sort((a, b) => a.title.localeCompare(b.title)));
    });
  }, []);

  // Cascade: once a floor-capable building is chosen, load its floors for the Floor filter.
  useEffect(() => {
    if (!parentPropertyId) { setFloors([]); setFloorId(""); return; }
    const selected = containers.find((c) => c.id === Number(parentPropertyId));
    if (!selected || !FLOOR_CAPABLE_TYPES.has(selected.property_type)) { setFloors([]); setFloorId(""); return; }
    apiClient.get<Floor[]>(`/properties/${parentPropertyId}/floors`).then(({ data }) => setFloors(data));
    setFloorId("");
  }, [parentPropertyId, containers]);

  return (
    <div>
      <PageHeader
        title={t("title")}
        description={t("description")}
        action={canCreate && (
          <button className="btn-primary" onClick={() => setModalOpen(true)}>
            <Plus size={16} /> {t("addProperty")}
          </button>
        )}
      />

      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-3">
        <div className="card p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-ink-500 dark:text-ink-400">{t("totalProperties")}</span>
            <Home size={16} className="text-ink-400" />
          </div>
          <div className="font-display text-2xl font-bold">{dashboard ? dashboard.total_properties : "—"}</div>
        </div>
        <div className="card p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-ink-500 dark:text-ink-400">{t("buildings")}</span>
            <Building2 size={16} className="text-ink-400" />
          </div>
          <div className="font-display text-2xl font-bold">{dashboard ? dashboard.total_buildings : "—"}</div>
        </div>
        <div className="card p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-ink-500 dark:text-ink-400">{t("totalVillas")}</span>
            <TreePine size={16} className="text-ink-400" />
          </div>
          <div className="font-display text-2xl font-bold">{dashboard ? dashboard.total_villas : "—"}</div>
        </div>
        <div className="card p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-ink-500 dark:text-ink-400">{t("totalCommercial")}</span>
            <LayoutGrid size={16} className="text-ink-400" />
          </div>
          <div className="font-display text-2xl font-bold">{dashboard ? dashboard.total_commercial_properties : "—"}</div>
        </div>
        <div className="card p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-ink-500 dark:text-ink-400">{t("totalWarehouses")}</span>
            <Warehouse size={16} className="text-ink-400" />
          </div>
          <div className="font-display text-2xl font-bold">{dashboard ? dashboard.total_warehouses : "—"}</div>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
        <div className="card p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-ink-500 dark:text-ink-400">{t("totalLands")}</span>
            <MapIcon size={16} className="text-ink-400" />
          </div>
          <div className="font-display text-2xl font-bold">{dashboard ? dashboard.total_lands : "—"}</div>
        </div>
        <div className="card p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-ink-500 dark:text-ink-400">{t("totalUnits")}</span>
            <MapPin size={16} className="text-ink-400" />
          </div>
          <div className="font-display text-2xl font-bold">{dashboard ? dashboard.total_units : "—"}</div>
        </div>
        <div className="card p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-ink-500 dark:text-ink-400">{t("occupiedUnits")}</span>
            <DoorClosed size={16} className="text-brand-500" />
          </div>
          <div className="font-display text-2xl font-bold">{dashboard ? dashboard.occupied_units : "—"}</div>
        </div>
        <div className="card p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-ink-500 dark:text-ink-400">{t("vacantUnits")}</span>
            <DoorOpen size={16} className="text-amber-500" />
          </div>
          <div className="font-display text-2xl font-bold">{dashboard ? dashboard.vacant_units : "—"}</div>
        </div>
        <div className="card p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-ink-500 dark:text-ink-400">{t("occupancyRate")}</span>
            <PieChart size={16} className="text-ink-400" />
          </div>
          <div className="font-display text-2xl font-bold">{dashboard ? `${dashboard.occupancy_rate}%` : "—"}</div>
        </div>
      </div>

      <div className="card">
        <div className="p-4 border-b border-ink-100 dark:border-ink-800 flex flex-wrap gap-3 items-center">
          <ToolbarSearch value={search} onChange={(v) => { setSearch(v); setPage(1); }} placeholder={t("searchPlaceholder")} />
          <select className="input max-w-[180px]" value={propertyType} onChange={(e) => { setPropertyType(e.target.value); setPage(1); }}>
            <option value="">{t("allTypes")}</option>
            {TYPE_KEYS.map((v) => <option key={v} value={v}>{t(`types.${v}`)}</option>)}
          </select>
          <select className="input max-w-[160px]" value={availabilityStatus} onChange={(e) => { setAvailabilityStatus(e.target.value); setPage(1); }}>
            <option value="">{t("allAvailability")}</option>
            <option value="available">{t("availability.available")}</option>
            <option value="leased">{t("availability.leased")}</option>
            <option value="reserved">{t("availability.reserved")}</option>
            <option value="under_maintenance">{t("availability.under_maintenance")}</option>
            <option value="off_market">{t("availability.off_market")}</option>
          </select>
          <select className="input max-w-[200px]" value={parentPropertyId} onChange={(e) => { setParentPropertyId(e.target.value); setPage(1); }}>
            <option value="">{t("allBuildingsVillas")}</option>
            {containers.map((c) => <option key={c.id} value={c.id}>{c.title} ({t(`types.${c.property_type}`, c.property_type)})</option>)}
          </select>
          {floors.length > 0 && (
            <select className="input max-w-[160px]" value={floorId} onChange={(e) => { setFloorId(e.target.value); setPage(1); }}>
              <option value="">{t("allFloors")}</option>
              {floors.map((f) => <option key={f.id} value={f.id}>{f.floor_name || `Floor ${f.floor_number}`}</option>)}
            </select>
          )}
          <label className="flex items-center gap-1.5 text-sm text-ink-500 whitespace-nowrap px-1">
            <input type="checkbox" checked={includeArchived} onChange={(e) => { setIncludeArchived(e.target.checked); setPage(1); }} />
            Show Archived
          </label>
        </div>

        {!loading && !parentPropertyId && !UNIT_TYPE_VALUES.has(propertyType) && !search && (
          <p className="text-xs text-ink-400 px-4 pb-1">
            Showing buildings, villas, and other whole properties only. Open one to see its floors and units, or pick it from "All buildings & villas" above to list its units here.
          </p>
        )}

        {loading && (
          <div className="p-4 space-y-3" aria-busy="true" aria-label="Loading properties">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="flex gap-6 items-center">
                <Skeleton className="h-3.5 w-16" />
                <Skeleton className="h-3.5 w-32" />
                <Skeleton className="h-3.5 w-20" />
                <Skeleton className="h-3.5 w-24" />
                <Skeleton className="h-3.5 w-20" />
                <Skeleton className="h-5 w-16 rounded-full" />
              </div>
            ))}
          </div>
        )}

        {!loading && data && data.items.length === 0 && (
          <EmptyState title={t("noPropertiesYet")} description={t("addFirstProperty")} />
        )}

        {!loading && data && data.items.length > 0 && (
          <div className="overflow-x-auto">
            <table className="table-shell">
              <thead>
                <tr>
                  <th>{t("table.code")}</th><th>{t("table.title")}</th><th>{t("table.type")}</th><th>{t("table.owner")}</th><th>{t("table.currentLease")}</th><th>{t("table.availability")}</th><th>{t("table.status")}</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((p) => (
                  <tr key={p.id} className="cursor-pointer" onClick={() => navigate(`/properties/${p.id}`)}>
                    <td className="font-mono text-xs">{p.property_code}</td>
                    <td className="font-medium">{p.title}</td>
                    <td>{t(`types.${p.property_type}`, p.property_type)}</td>
                    <td className="text-ink-500">{p.owner_display_name || `#${p.owner_id}`}</td>
                    <td className="text-ink-500 font-mono text-xs">{p.current_lease_contract_number || "—"}</td>
                    <td><span className={AVAILABILITY_TONE[p.availability_status] || "badge-inactive"}>{t(`availability.${p.availability_status}`, p.availability_status.replace(/_/g, " "))}</span></td>
                    <td><StatusBadge status={p.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {data && <Pagination page={data.page} totalPages={data.total_pages} onChange={setPage} />}
      </div>

      <PropertyFormModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onSaved={(created) => {
          setModalOpen(false);
          // Chains straight into floor/unit setup for buildings, so it
          // reads as one flow ("create the building, then its floors
          // and apartments") instead of a separate trip back later —
          // see PropertyDetailPage's handling of ?setupFloors=true.
          // Scoped to "building" specifically to match the Floors tab's
          // own existing isBuilding check there.
          const suffix = created.property_type === "building" ? "?setupFloors=true" : "";
          navigate(`/properties/${created.id}${suffix}`);
        }}
      />
    </div>
  );
}
