import { useEffect, useState, useCallback } from "react";
import apiClient from "@/api/client";
import { Loader2, AlertTriangle, CheckCircle2 } from "lucide-react";
import { OwnerListItem, PropertyListItem, Floor, UnitOccupancySummary, PaginatedResponse } from "@/types";

/**
 * Cascading Owner -> Property -> Floor -> Apartment/Unit selector.
 *
 * Composed entirely from existing, already-working endpoints — no new
 * backend code:
 *   GET /owners                          (owner list)
 *   GET /properties?owner_id=X           (that owner's properties,
 *                                          filtered client-side to
 *                                          top-level only, since the
 *                                          list endpoint has no
 *                                          "no parent" filter of its own)
 *   GET /properties/{id}/floors          (Phase 5, already existed)
 *   GET /properties?parent_property_id=X&floor_id=Y  (units on that floor,
 *                                          already-supported filters)
 *   GET /occupancy/units?building_id=X   (Phase 18 Occupancy Engine —
 *                                          cross-referenced to flag
 *                                          which units already have an
 *                                          active tenant contract; if
 *                                          the signed-in user lacks
 *                                          occupancy.view, this degrades
 *                                          silently to "no badges shown"
 *                                          rather than blocking the form)
 *
 * Handles three shapes automatically, no configuration needed:
 *  - Property has no child units at all (villa, standalone unit) -> it
 *    IS the selectable unit; selection finalizes immediately.
 *  - Property has units but no Floor records -> skips the floor step,
 *    goes straight to a flat Apartment/Unit dropdown.
 *  - Property has units grouped under floors -> full 4-level cascade.
 * Units with no floor_id assigned are still reachable via a synthetic
 * "Unassigned" floor entry, never silently dropped.
 */

interface Props {
  ownerId: number | "";
  onOwnerChange: (id: number | "") => void;
  onUnitSelect: (unit: PropertyListItem | null) => void;
  showOwnerSelector?: boolean;
  disabled?: boolean;
  // When true, selecting a Property finalizes the selection right
  // there — no Floor/Apartment step is ever offered, even if the
  // building already has floors and units generated. For Master
  // Leases (Owner -> Company): the whole building is what's being
  // leased, never one specific unit within it, so drilling further
  // would be asking a question that doesn't apply to this contract
  // type. Tenant contracts (which DO lease one specific unit) leave
  // this false/default, keeping the full cascade.
  buildingLevelOnly?: boolean;
  // When true, offers "the whole building" as an EXTRA choice
  // alongside the normal floor/unit drill-down, instead of forcing
  // one or the other — for expenses that sometimes belong to one
  // apartment (painting a unit) and sometimes to the building as a
  // whole (a guard's salary, the shared pool, building-wide
  // electricity/water) from the very same form. Different from
  // buildingLevelOnly, which removes the unit option entirely; this
  // adds the building option without removing anything.
  allowWholeBuildingChoice?: boolean;
  // When true, offers "this whole floor" as an EXTRA choice once a
  // specific floor is picked, alongside the normal unit dropdown —
  // confirmed directly: a tenant renting an entire floor (all its
  // units together) as one contract, with one rent voucher listing
  // every unit number on it. Backed by
  // POST /floors/{floor_id}/whole-floor-unit (get-or-creates a single
  // Property row representing the floor as a whole — see
  // PropertyService.get_or_create_floor_unit), so everything
  // downstream that already works off property_id (installments,
  // vouchers, Collect Rent) needs zero changes.
  allowWholeFloorChoice?: boolean;
}

const OCCUPANCY_TONE: Record<string, string> = {
  occupied: "text-rust-500", notice_period: "text-amber-500", vacating_soon: "text-amber-500",
  under_maintenance: "text-amber-500", vacant: "text-emerald-600",
};

export default function PropertyHierarchySelector({ ownerId, onOwnerChange, onUnitSelect, showOwnerSelector = true, disabled, buildingLevelOnly = false, allowWholeBuildingChoice = false, allowWholeFloorChoice = false }: Props) {
  const [owners, setOwners] = useState<OwnerListItem[]>([]);
  const [properties, setProperties] = useState<PropertyListItem[]>([]);
  const [propertyId, setPropertyId] = useState<number | "">("");
  const [floors, setFloors] = useState<Floor[]>([]);
  const [floorKey, setFloorKey] = useState<string>(""); // floor.id as string, or "unassigned"
  const [units, setUnits] = useState<PropertyListItem[]>([]);
  const [unitId, setUnitId] = useState<number | "">("");
  const [occupancy, setOccupancy] = useState<Record<number, UnitOccupancySummary>>({});
  const [loadingLevel, setLoadingLevel] = useState<"" | "properties" | "structure" | "units">("");
  const [directUnit, setDirectUnit] = useState(false); // true when the selected property IS the unit (no children)
  // Only used when allowWholeBuildingChoice is true — see the Props
  // comment for the distinction from buildingLevelOnly.
  const [wholeBuildingSelected, setWholeBuildingSelected] = useState(false);
  const [wholeFloorSelected, setWholeFloorSelected] = useState(false);
  const [loadingWholeFloor, setLoadingWholeFloor] = useState(false);

  useEffect(() => {
    if (showOwnerSelector) {
      apiClient.get<PaginatedResponse<OwnerListItem>>("/owners", { params: { page_size: 200 } }).then(({ data }) => setOwners(data.items)).catch(() => {});
    }
  }, [showOwnerSelector]);

  // Owner -> top-level Properties
  useEffect(() => {
    setPropertyId(""); setFloors([]); setFloorKey(""); setUnits([]); setUnitId(""); setDirectUnit(false);
    setWholeBuildingSelected(false);
    setWholeFloorSelected(false);
    onUnitSelect(null);
    if (!ownerId) { setProperties([]); return; }
    setLoadingLevel("properties");
    apiClient.get<PaginatedResponse<PropertyListItem>>("/properties", { params: { owner_id: ownerId, top_level_only: true, page_size: 200 } })
      .then(({ data }) => setProperties(data.items))
      .finally(() => setLoadingLevel(""));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ownerId]);

  const loadOccupancy = useCallback((buildingId: number) => {
    apiClient.get<PaginatedResponse<UnitOccupancySummary>>("/occupancy/units", { params: { building_id: buildingId, page_size: 200 } })
      .then(({ data }) => {
        const map: Record<number, UnitOccupancySummary> = {};
        data.items.forEach((u) => { map[u.property_id] = u; });
        setOccupancy(map);
      })
      .catch(() => setOccupancy({})); // no occupancy.view permission, or module unavailable — degrade silently
  }, []);

  // Property -> Floors + Units
  useEffect(() => {
    setFloors([]); setFloorKey(""); setUnits([]); setUnitId(""); setDirectUnit(false); setOccupancy({});
    setWholeBuildingSelected(false);
    setWholeFloorSelected(false);
    onUnitSelect(null);
    if (!propertyId) return;
    const selected = properties.find((p) => p.id === propertyId) || null;

    if (buildingLevelOnly) {
      // The whole building IS the leasable thing here — never drill
      // into its floors/units, even if it already has some generated.
      setDirectUnit(true);
      onUnitSelect(selected);
      return;
    }

    setLoadingLevel("structure");
    Promise.all([
      apiClient.get<Floor[]>(`/properties/${propertyId}/floors`).catch(() => ({ data: [] as Floor[] })),
      apiClient.get<PaginatedResponse<PropertyListItem>>("/properties", { params: { parent_property_id: propertyId, page_size: 200 } }).catch(() => ({ data: { items: [] } as any })),
    ])
      .then(([floorsRes, unitsRes]) => {
        const allUnits: PropertyListItem[] = unitsRes.data.items || [];
        if (allUnits.length === 0) {
          // No child units — the property itself is the leasable thing.
          setDirectUnit(true);
          onUnitSelect(selected);
        } else {
          setFloors(floorsRes.data || []);
          setUnits(allUnits);
          loadOccupancy(propertyId);
        }
      })
      .finally(() => setLoadingLevel(""));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [propertyId]);

  // Floor -> filtered units list
  const unitsForFloor = floorKey
    ? units.filter((u) => (floorKey === "unassigned" ? !u.floor_id : String(u.floor_id) === floorKey))
    : (floors.length === 0 ? units : []);

  useEffect(() => {
    setUnitId("");
    onUnitSelect(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [floorKey]);

  const handleUnitPick = (id: number | "") => {
    setUnitId(id);
    const unit = units.find((u) => u.id === id) || null;
    onUnitSelect(unit);
  };

  const occupancyBadge = (unitPropertyId: number) => {
    const occ = occupancy[unitPropertyId];
    if (!occ) return null;
    if (occ.occupancy_status === "vacant" || occ.occupancy_status === "available") return null;
    return ` — ${occ.occupancy_status.replace("_", " ")}${occ.tenant_display_name ? ` (${occ.tenant_display_name})` : ""}`;
  };

  const selectedUnitOccupancy = unitId ? occupancy[unitId] : (directUnit && propertyId ? occupancy[propertyId] : null);
  const hasActiveConflict = !!selectedUnitOccupancy && !["vacant", "available"].includes(selectedUnitOccupancy.occupancy_status);

  return (
    <div className="space-y-4">
      {showOwnerSelector && (
        <div>
          <label className="label">Owner *</label>
          <select className="input" required disabled={disabled} value={ownerId} onChange={(e) => onOwnerChange(e.target.value ? Number(e.target.value) : "")}>
            <option value="">Select an owner…</option>
            {owners.map((o) => <option key={o.id} value={o.id}>{o.owner_code} — {o.display_name}</option>)}
          </select>
        </div>
      )}

      <div>
        <label className="label">Property *</label>
        <select className="input" required disabled={disabled || !ownerId} value={propertyId} onChange={(e) => setPropertyId(e.target.value ? Number(e.target.value) : "")}>
          <option value="">{!ownerId ? "Select an owner first…" : "Select a property…"}</option>
          {properties.map((p) => <option key={p.id} value={p.id}>{p.property_code} — {p.title}</option>)}
        </select>
        {loadingLevel === "properties" && <div className="text-xs text-ink-400 mt-1 flex items-center gap-1"><Loader2 size={11} className="animate-spin" /> Loading properties…</div>}
      </div>

      {loadingLevel === "structure" && (
        <div className="text-xs text-ink-400 flex items-center gap-1"><Loader2 size={11} className="animate-spin" /> Checking for floors/units…</div>
      )}

      {allowWholeBuildingChoice && !directUnit && propertyId && !loadingLevel && (units.length > 0 || floors.length > 0) && (
        <label className="flex items-start gap-2 text-sm cursor-pointer">
          <input
            type="checkbox"
            className="mt-0.5"
            checked={wholeBuildingSelected}
            onChange={(e) => {
              setWholeBuildingSelected(e.target.checked);
              setFloorKey(""); setUnitId("");
              if (e.target.checked) {
                const building = properties.find((p) => p.id === propertyId) || null;
                onUnitSelect(building);
              } else {
                onUnitSelect(null);
              }
            }}
          />
          <span>
            For the whole building — not one specific unit (e.g. a guard's salary, the shared pool, building-wide electricity/water)
          </span>
        </label>
      )}

      {!wholeBuildingSelected && !directUnit && propertyId && floors.length > 0 && (
        <div>
          <label className="label">Floor *</label>
          <select className="input" required disabled={disabled} value={floorKey} onChange={(e) => { setFloorKey(e.target.value); setWholeFloorSelected(false); setUnitId(""); onUnitSelect(null); }}>
            <option value="">Select a floor…</option>
            {floors.map((f) => <option key={f.id} value={f.id}>{f.floor_name || `Floor ${f.floor_number}`} ({f.unit_count} unit{f.unit_count === 1 ? "" : "s"})</option>)}
            {units.some((u) => !u.floor_id) && <option value="unassigned">Unassigned units</option>}
          </select>
        </div>
      )}

      {allowWholeFloorChoice && !wholeBuildingSelected && !directUnit && floorKey && floorKey !== "unassigned" && (
        <label className="flex items-start gap-2 text-sm cursor-pointer">
          <input
            type="checkbox"
            className="mt-0.5"
            checked={wholeFloorSelected}
            disabled={loadingWholeFloor}
            onChange={async (e) => {
              setWholeFloorSelected(e.target.checked);
              setUnitId("");
              if (!e.target.checked) { onUnitSelect(null); return; }
              setLoadingWholeFloor(true);
              try {
                const { data: floorUnit } = await apiClient.post(`/floors/${floorKey}/whole-floor-unit`);
                onUnitSelect(floorUnit);
              } finally {
                setLoadingWholeFloor(false);
              }
            }}
          />
          <span>
            The whole floor — not one specific unit (one contract, one rent voucher listing every unit number on this floor)
            {loadingWholeFloor && <Loader2 size={12} className="inline animate-spin ml-1" />}
          </span>
        </label>
      )}

      {!wholeFloorSelected && !wholeBuildingSelected && !directUnit && propertyId && (floors.length === 0 ? units.length > 0 : floorKey) && (
        <div>
          <label className="label">Apartment / Unit *</label>
          <select className="input" required disabled={disabled} value={unitId} onChange={(e) => handleUnitPick(e.target.value ? Number(e.target.value) : "")}>
            <option value="">Select a unit…</option>
            {unitsForFloor.map((u) => (
              <option key={u.id} value={u.id}>
                {u.unit_number ? `Unit ${u.unit_number}` : u.title}{occupancyBadge(u.id)}
              </option>
            ))}
          </select>
        </div>
      )}

      {directUnit && propertyId && (
        <p className="text-xs text-ink-400">
          {buildingLevelOnly
            ? "Selected as the whole building for this lease — its floors and units aren't part of this contract."
            : "This property has no separate floors/units recorded — it's selected as the contract's property directly."}
        </p>
      )}

      {selectedUnitOccupancy && (
        hasActiveConflict ? (
          <div className="flex items-start gap-2 text-sm text-rust-600 bg-rust-50 dark:bg-rust-500/10 rounded-md px-3 py-2">
            <AlertTriangle size={15} className="shrink-0 mt-0.5" />
            <span>
              This unit is currently <strong>{selectedUnitOccupancy.occupancy_status.replace("_", " ")}</strong>
              {selectedUnitOccupancy.tenant_display_name ? ` by ${selectedUnitOccupancy.tenant_display_name}` : ""}
              {selectedUnitOccupancy.contract_end_date ? ` (contract ends ${selectedUnitOccupancy.contract_end_date})` : ""}.
              You can still proceed, but the system will block activation while that contract stays active.
            </span>
          </div>
        ) : (
          <div className="flex items-center gap-2 text-sm text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-500/10 rounded-md px-3 py-2">
            <CheckCircle2 size={15} /> This unit is vacant.
          </div>
        )
      )}
    </div>
  );
}
