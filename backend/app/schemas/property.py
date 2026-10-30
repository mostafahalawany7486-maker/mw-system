from datetime import date
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, field_validator
from app.schemas.common import AuditFieldsOut

VALID_PROPERTY_TYPES = {
    "building", "villa", "apartment", "commercial_unit", "warehouse",
    "shop", "office", "land", "parking", "storage",
    "commercial_building", "commercial_complex", "mixed_use",
}
VALID_AVAILABILITY_STATUSES = {"available", "leased", "reserved", "under_maintenance", "off_market"}
VALID_FURNISHING_STATUSES = {"furnished", "semi_furnished", "unfurnished"}


# ---------------- Floor ----------------
class FloorCreate(BaseModel):
    floor_number: str
    floor_name: Optional[str] = None
    total_units: Optional[int] = None
    description: Optional[str] = None


class FloorUnitOverride(BaseModel):
    """Overrides units_per_floor for one specific floor — e.g. the ground
    floor has 2 units instead of the building's usual 4."""
    floor_number: int
    units_count: int

    @field_validator("units_count")
    @classmethod
    def validate_units_count(cls, v: int) -> int:
        if v < 0:
            raise ValueError("units_count cannot be negative")
        if v > 200:
            raise ValueError("units_count must be 200 or fewer")
        return v


class BulkGenerateUnitsRequest(BaseModel):
    """Generates an entire building's floors + units in one request
    instead of adding each one by hand — see docs/property-structure.md
    (Bulk Unit Generation section) for the full reasoning. Floors that
    already exist (matched by floor_number) are reused, not duplicated,
    so this is also safe to run again later to add more floors to an
    existing building."""
    floor_count: int
    starting_floor_number: int = 1
    units_per_floor: int
    unit_property_type: str
    starting_unit_index: int = 1
    # "floor_prefixed" (default): Floor 3 -> 301, 302, 303 — matches the
    # convention already visible on existing seeded units. "sequential":
    # numbers run continuously across the whole building regardless of
    # floor (Floor 1 -> 1, 2, 3 / Floor 2 -> 4, 5, 6...), for buildings
    # that don't use floor-prefixed addressing.
    numbering_style: str = "floor_prefixed"
    # Per-floor customization: any floor listed here uses its own
    # units_count instead of the uniform units_per_floor above — e.g. a
    # ground floor with fewer/more units than the rest of the building.
    floor_overrides: Optional[List[FloorUnitOverride]] = None
    title_prefix: Optional[str] = None
    owner_id: Optional[int] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    area_sqm: Optional[Decimal] = None
    rent_price: Optional[Decimal] = None

    @field_validator("floor_count", "units_per_floor")
    @classmethod
    def validate_positive_counts(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("must be greater than zero")
        if v > 200:
            raise ValueError("must be 200 or fewer per request")
        return v

    @field_validator("numbering_style")
    @classmethod
    def validate_numbering_style(cls, v: str) -> str:
        if v not in ("floor_prefixed", "sequential"):
            raise ValueError("numbering_style must be 'floor_prefixed' or 'sequential'")
        return v


class FloorUpdate(BaseModel):
    floor_number: Optional[str] = None
    floor_name: Optional[str] = None
    total_units: Optional[int] = None
    description: Optional[str] = None
    status: Optional[str] = None


class FloorOut(AuditFieldsOut):
    building_id: int
    floor_number: str
    floor_name: Optional[str] = None
    total_units: Optional[int] = None
    description: Optional[str] = None
    unit_count: int = 0


# ---------------- Amenity ----------------
class AmenityCreate(BaseModel):
    name: str
    category: Optional[str] = None


class AmenityUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    status: Optional[str] = None


class AmenityOut(AuditFieldsOut):
    name: str
    category: Optional[str] = None


# ---------------- Property Image ----------------
class PropertyImageUpdate(BaseModel):
    caption: Optional[str] = None
    is_cover: Optional[bool] = None
    sort_order: Optional[int] = None


class PropertyImageOut(AuditFieldsOut):
    property_id: int
    file_name: str
    file_url: Optional[str] = None
    file_size_bytes: int
    mime_type: str
    caption: Optional[str] = None
    is_cover: bool
    sort_order: int


# ---------------- Property Document ----------------
class PropertyDocumentUpdate(BaseModel):
    document_type: Optional[str] = None
    document_number: Optional[str] = None
    issue_date: Optional[date] = None
    expiry_date: Optional[date] = None
    description: Optional[str] = None


class PropertyDocumentOut(AuditFieldsOut):
    property_id: int
    document_type: str
    document_number: Optional[str] = None
    issue_date: Optional[date] = None
    expiry_date: Optional[date] = None
    file_name: str
    file_url: Optional[str] = None
    file_size_bytes: int
    mime_type: str
    description: Optional[str] = None
    is_expired: bool = False


# ---------------- Property ----------------
class PropertyCreate(BaseModel):
    property_type: str
    internal_code: Optional[str] = None
    parent_property_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    owner_id: int
    branch_id: Optional[int] = None

    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city_id: Optional[int] = None
    country_id: Optional[int] = None
    postal_code: Optional[str] = None

    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None

    area_sqm: Optional[Decimal] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    floor_number: Optional[str] = None
    total_floors: Optional[int] = None
    year_built: Optional[int] = None
    furnishing_status: Optional[str] = None

    availability_status: str = "available"
    notes_summary: Optional[str] = None
    amenity_ids: List[int] = []

    # --- Unit Management (Phase 5) ---
    floor_id: Optional[int] = None
    unit_number: Optional[str] = None
    rent_price: Optional[Decimal] = None
    electricity_meter_number: Optional[str] = None
    water_meter_number: Optional[str] = None
    paci_number: Optional[str] = None
    parking_space_id: Optional[int] = None
    storage_space_id: Optional[int] = None

    # --- Building/Villa characteristics (Phase 2.0) ---
    elevators: Optional[int] = None
    parking_spaces_count: Optional[int] = None
    garden: Optional[bool] = None
    swimming_pool: Optional[bool] = None
    maid_room: Optional[bool] = None

    @field_validator("property_type")
    @classmethod
    def validate_property_type(cls, v: str) -> str:
        if v not in VALID_PROPERTY_TYPES:
            raise ValueError(f"property_type must be one of {sorted(VALID_PROPERTY_TYPES)}")
        return v

    @field_validator("availability_status")
    @classmethod
    def validate_availability(cls, v: str) -> str:
        if v not in VALID_AVAILABILITY_STATUSES:
            raise ValueError(f"availability_status must be one of {sorted(VALID_AVAILABILITY_STATUSES)}")
        return v

    @field_validator("furnishing_status")
    @classmethod
    def validate_furnishing(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_FURNISHING_STATUSES:
            raise ValueError(f"furnishing_status must be one of {sorted(VALID_FURNISHING_STATUSES)}")
        return v

    @field_validator("latitude")
    @classmethod
    def validate_latitude(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and not (-90 <= v <= 90):
            raise ValueError("latitude must be between -90 and 90")
        return v

    @field_validator("longitude")
    @classmethod
    def validate_longitude(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and not (-180 <= v <= 180):
            raise ValueError("longitude must be between -180 and 180")
        return v

    @field_validator("rent_price")
    @classmethod
    def validate_rent_price(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v < 0:
            raise ValueError("rent_price cannot be negative")
        return v


class PropertyUpdate(BaseModel):
    internal_code: Optional[str] = None
    parent_property_id: Optional[int] = None
    title: Optional[str] = None
    description: Optional[str] = None
    branch_id: Optional[int] = None

    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city_id: Optional[int] = None
    country_id: Optional[int] = None
    postal_code: Optional[str] = None

    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None

    area_sqm: Optional[Decimal] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    floor_number: Optional[str] = None
    total_floors: Optional[int] = None
    year_built: Optional[int] = None
    furnishing_status: Optional[str] = None

    availability_status: Optional[str] = None
    notes_summary: Optional[str] = None
    status: Optional[str] = None
    amenity_ids: Optional[List[int]] = None

    # --- Unit Management (Phase 5) ---
    floor_id: Optional[int] = None
    unit_number: Optional[str] = None
    rent_price: Optional[Decimal] = None
    electricity_meter_number: Optional[str] = None
    water_meter_number: Optional[str] = None
    paci_number: Optional[str] = None
    parking_space_id: Optional[int] = None
    storage_space_id: Optional[int] = None

    # --- Building/Villa characteristics (Phase 2.0) ---
    elevators: Optional[int] = None
    parking_spaces_count: Optional[int] = None
    garden: Optional[bool] = None
    swimming_pool: Optional[bool] = None
    maid_room: Optional[bool] = None

    @field_validator("availability_status")
    @classmethod
    def validate_availability(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_AVAILABILITY_STATUSES:
            raise ValueError(f"availability_status must be one of {sorted(VALID_AVAILABILITY_STATUSES)}")
        return v


class PropertyListItemOut(AuditFieldsOut):
    property_code: str
    internal_code: Optional[str] = None
    property_type: str
    title: str
    owner_id: int
    owner_display_name: Optional[str] = None
    city_id: Optional[int] = None
    availability_status: str
    area_sqm: Optional[Decimal] = None
    bedrooms: Optional[int] = None
    current_lease_contract_number: Optional[str] = None
    unit_number: Optional[str] = None
    rent_price: Optional[Decimal] = None
    floor_id: Optional[int] = None
    floor_label: Optional[str] = None
    # Additive (Cascading Property Selector extension): lets API
    # consumers tell a top-level Building/Villa apart from a child Unit
    # without a second round trip. Already existed on every Property row
    # — was just never exposed on the list serializer before.
    parent_property_id: Optional[int] = None


class BulkGenerateUnitsResultOut(BaseModel):
    building_id: int
    floors_created: int
    floors_reused: int
    units_created: int
    units: List[PropertyListItemOut]


class PropertyDetailOut(AuditFieldsOut):
    property_code: str
    internal_code: Optional[str] = None
    property_type: str
    parent_property_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    owner_id: int
    owner_display_name: Optional[str] = None
    branch_id: Optional[int] = None

    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city_id: Optional[int] = None
    country_id: Optional[int] = None
    postal_code: Optional[str] = None
    display_location: Optional[str] = None

    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None

    area_sqm: Optional[Decimal] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    floor_number: Optional[str] = None
    total_floors: Optional[int] = None
    year_built: Optional[int] = None
    furnishing_status: Optional[str] = None

    availability_status: str
    notes_summary: Optional[str] = None

    amenities: List[AmenityOut] = []
    images: List[PropertyImageOut] = []
    documents: List[PropertyDocumentOut] = []

    current_lease_id: Optional[int] = None
    current_lease_contract_number: Optional[str] = None
    current_lease_end_date: Optional[date] = None

    # --- Unit Management (Phase 5) ---
    floor_id: Optional[int] = None
    floor_label: Optional[str] = None
    unit_number: Optional[str] = None
    rent_price: Optional[Decimal] = None
    electricity_meter_number: Optional[str] = None
    water_meter_number: Optional[str] = None
    paci_number: Optional[str] = None
    parking_space_id: Optional[int] = None
    parking_space_code: Optional[str] = None
    storage_space_id: Optional[int] = None
    storage_space_code: Optional[str] = None

    # --- Building/Villa characteristics (Phase 2.0) ---
    elevators: Optional[int] = None
    parking_spaces_count: Optional[int] = None
    garden: Optional[bool] = None
    swimming_pool: Optional[bool] = None
    maid_room: Optional[bool] = None

    # Populated only for container types (building/villa/commercial_building/
    # commercial_complex/warehouse/land/mixed_use) — the "Property Details
    # page" summary Phase 2.0 asks for. None for plain units, since a unit
    # has no children to summarize. See PropertyType.CONTAINER_TYPES.
    summary: Optional["PropertySummaryOut"] = None


class PropertyDashboardOut(BaseModel):
    total_properties: int
    by_type: dict
    by_availability: dict
    # --- Phase 2.0 rolled-up dashboard widgets ---
    total_buildings: int = 0
    total_villas: int = 0
    total_commercial_properties: int = 0
    total_warehouses: int = 0
    total_lands: int = 0
    total_units: int = 0
    occupied_units: int = 0
    vacant_units: int = 0
    occupancy_rate: float = 0.0
    recently_added: List[PropertyListItemOut] = []


class PropertySummaryOut(BaseModel):
    """Live, computed-on-read summary for a container property's Details
    page (Phase 2.0) — everything here is derived from child Units /
    Floors / Rental Contracts / Transactions, never stored, per the
    spec's "must be dynamic and never entered manually" requirement.
    Superset of BuildingSummaryOut (same underlying computation) with the
    additional fields Phase 2.0's "Property Summary" section asks for."""
    property_type: str
    total_floors: int
    total_units: int
    occupied_units: int
    vacant_units: int
    reserved_units: int
    under_maintenance_units: int
    residential_units: int
    commercial_units: int
    occupancy_rate: float
    active_contracts: int
    expired_contracts: int
    contracts_expiring_soon: int
    monthly_revenue: Decimal = Decimal("0")
    monthly_expenses: Decimal = Decimal("0")
    net_profit: Optional[Decimal] = None
    last_updated: Optional[date] = None


PropertyDetailOut.model_rebuild()


class BuildingSummaryOut(BaseModel):
    """Phase 4/5's Property (property_type='building') already IS the
    Building entity — this is a read-only aggregation over its existing
    child Units (parent_property_id), Floors, Rental Contracts, and
    Maintenance Requests, not a new stored concept.

    Kept as-is (own endpoint/shape) for backward compatibility with
    existing callers of GET /properties/{id}/building-summary; the newer,
    richer PropertySummaryOut above (embedded in PropertyDetailOut) is the
    Phase 2.0 "Property Summary" — both read from the same repository
    methods so the numbers always agree."""
    floor_count: int
    unit_count: int
    occupied_units: int
    vacant_units: int
    other_units: int
    residential_units: int = 0
    commercial_units: int = 0
    occupancy_rate: float = 0.0
    active_leases_count: int
    expired_leases_count: int
    contracts_expiring_soon: int = 0
    tenant_count: int
    open_maintenance_requests_count: int
    recently_added: List[PropertyListItemOut] = []
