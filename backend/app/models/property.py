"""
Property Management module (Phase 4).

All ten requested property kinds (Building, Villa, Apartment, Commercial
Unit, Warehouse, Shop, Office, Land, Parking, Storage) are modeled as a
single `Property` table with a `property_type` discriminator, following
the same reasoning as Owner (Phase 2): the variants share the overwhelming
majority of fields (location, GPS, images, documents, amenities,
ownership, leasing) and only differ in a few physical attributes, which
are kept as nullable common columns rather than per-type tables.

A Building can be the PARENT of many units (apartments, offices, shops,
etc. within it) via `parent_property_id` — a simple, common real-estate
hierarchy, not a new concept requiring its own table.

Lease linkage: a property can have many leases over its lifetime (renewed,
expired, terminated ones), so the FK lives on LeaseAgreement
(`property_id`, added in this same migration) rather than a single
lease_id on Property. Property exposes a computed "current lease" via the
repository (most recent ACTIVE lease for that property) to satisfy the
"Lease Contract" field from the spec without forcing a 1:1 that doesn't
match reality.
"""
from datetime import date
from decimal import Decimal
from typing import Optional
from sqlalchemy import String, ForeignKey, Boolean, Numeric, Integer, Text, Date, Table, Column
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel, Base


class PropertyType:
    BUILDING = "building"
    VILLA = "villa"
    APARTMENT = "apartment"
    COMMERCIAL_UNIT = "commercial_unit"
    WAREHOUSE = "warehouse"
    SHOP = "shop"
    OFFICE = "office"
    LAND = "land"
    PARKING = "parking"
    STORAGE = "storage"
    # --- Phase 2.0: additional container types (own Owner->Property->Units
    # hierarchy roots, same as BUILDING/VILLA — not unit types, so they're
    # not added to UNIT_TYPES below) ---
    COMMERCIAL_BUILDING = "commercial_building"
    COMMERCIAL_COMPLEX = "commercial_complex"
    MIXED_USE = "mixed_use"

    # Confirmed directly: a tenant can rent an entire floor (all its
    # units together) as one contract, with one rent voucher listing
    # every unit number on it. Modeled as its own Property row (a
    # "virtual" unit representing the floor as a whole) rather than
    # a schema change to RentalContract (which only ever points at one
    # property_id) — every downstream system that already works off
    # property_id (installments, vouchers, Collect Rent, reports)
    # needs zero changes. Deliberately NOT added to CONTAINER_TYPES or
    # either UNIT_TYPES list below — the occupancy engine's normal
    # unit-counting (which iterates those lists) ignores it completely,
    # so it can never double-count against its own child units. See
    # RentalService._create_floor_wide_side_effects() for how the
    # child units get marked unavailable instead.
    FLOOR = "floor"

    ALL = [
        BUILDING, VILLA, APARTMENT, COMMERCIAL_UNIT, WAREHOUSE, SHOP, OFFICE, LAND, PARKING, STORAGE,
        COMMERCIAL_BUILDING, COMMERCIAL_COMPLEX, MIXED_USE, FLOOR,
    ]

    # Types that can act as a parent/container in the hierarchy (can own
    # Floors and child Units via parent_property_id) — used to validate
    # Floor creation and to compute dashboard roll-ups like "Total
    # Buildings" without hardcoding the list in five different places.
    CONTAINER_TYPES = [BUILDING, VILLA, COMMERCIAL_BUILDING, COMMERCIAL_COMPLEX, WAREHOUSE, LAND, MIXED_USE]

    # Unit-level types (the "Units" layer of Owner -> Property -> Floors ->
    # Units), split residential vs commercial per Phase 2.0's dashboard
    # requirements. PARKING/STORAGE are neither — they're auxiliary spaces
    # referenced by other units (see parking_space_id/storage_space_id).
    RESIDENTIAL_UNIT_TYPES = [APARTMENT]
    COMMERCIAL_UNIT_TYPES = [COMMERCIAL_UNIT, SHOP, OFFICE]


class AvailabilityStatus:
    AVAILABLE = "available"
    LEASED = "leased"
    RESERVED = "reserved"
    UNDER_MAINTENANCE = "under_maintenance"
    OFF_MARKET = "off_market"

    ALL = [AVAILABLE, LEASED, RESERVED, UNDER_MAINTENANCE, OFF_MARKET]


class FurnishingStatus:
    FURNISHED = "furnished"
    SEMI_FURNISHED = "semi_furnished"
    UNFURNISHED = "unfurnished"

    ALL = [FURNISHED, SEMI_FURNISHED, UNFURNISHED]


property_amenities = Table(
    "property_amenities",
    Base.metadata,
    Column("property_id", ForeignKey("properties.id", ondelete="CASCADE"), primary_key=True),
    Column("amenity_id", ForeignKey("amenities.id", ondelete="CASCADE"), primary_key=True),
)


class Amenity(BaseModel):
    __tablename__ = "amenities"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # e.g. safety, comfort, utility

    properties: Mapped[list["Property"]] = relationship(secondary=property_amenities, back_populates="amenities")


class Floor(BaseModel):
    """A physical floor within a Building. Units (Property rows with
    property_type in the 'unit-like' set) reference a Floor via floor_id
    instead of a free-text string, so floors can be managed as first-class
    records (e.g. listing every unit on Floor 3)."""
    __tablename__ = "floors"

    building_id: Mapped[int] = mapped_column(ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    floor_number: Mapped[str] = mapped_column(String(20), nullable=False)  # e.g. "1", "G", "M", "PH"
    floor_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # e.g. "Ground Floor"
    total_units: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    building: Mapped["Property"] = relationship(foreign_keys=[building_id])


class Property(BaseModel):
    __tablename__ = "properties"

    property_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    internal_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    property_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)

    parent_property_id: Mapped[Optional[int]] = mapped_column(ForeignKey("properties.id"), nullable=True, index=True)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    owner_id: Mapped[int] = mapped_column(ForeignKey("owners.id"), nullable=False, index=True)
    branch_id: Mapped[Optional[int]] = mapped_column(ForeignKey("branches.id"), nullable=True, index=True)

    # --- Location ---
    address_line1: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    address_line2: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    city_id: Mapped[Optional[int]] = mapped_column(ForeignKey("cities.id"), nullable=True, index=True)
    country_id: Mapped[Optional[int]] = mapped_column(ForeignKey("countries.id"), nullable=True)
    postal_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # --- GPS ---
    latitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(9, 6), nullable=True)
    longitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(9, 6), nullable=True)

    # --- Physical attributes (nullable; relevance varies by property_type) ---
    area_sqm: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    bedrooms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    bathrooms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    floor_number: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    total_floors: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    year_built: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    furnishing_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    availability_status: Mapped[str] = mapped_column(String(20), default=AvailabilityStatus.AVAILABLE, index=True)
    notes_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # --- Phase 2.0: Building/Villa-specific characteristics ---
    # Nullable common columns on the same shared Property table, following
    # this file's existing pattern (see module docstring) rather than
    # per-type tables. Only meaningful when property_type is a container
    # type (building/villa/commercial_building/commercial_complex/mixed_use)
    # but kept ungated at the DB level like every other physical attribute
    # here (bedrooms, bathrooms, etc. are equally "not applicable" to some
    # types and nobody enforces that in the schema either).
    elevators: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Building
    # Physical parking capacity of the building/villa itself — distinct
    # from individual child Property rows of property_type='parking',
    # which represent specific assignable parking units already tracked
    # via parking_space_id. A building can have a parking capacity number
    # without every space being individually modeled.
    parking_spaces_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Building / Villa
    garden: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)  # Villa
    swimming_pool: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)  # Villa
    maid_room: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)  # Villa (optional)

    # --- Unit Management (Phase 5) ---
    floor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("floors.id"), nullable=True, index=True)
    unit_number: Mapped[Optional[str]] = mapped_column(String(30), nullable=True, index=True)
    rent_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 3), nullable=True)  # asking/listed price, distinct from a signed lease's actual rent_amount
    electricity_meter_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    water_meter_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    # Kuwait PACI (Public Authority for Civil Information) address
    # number — a per-unit/per-property official address code, not a
    # personal ID. Corrects an earlier mistake: the Rent Voucher print
    # template briefly showed "PACI Number" under the tenant's own
    # info, sourced from Tenant.national_id — PACI numbers identify the
    # unit's physical address, not the person, so this belongs here
    # instead. See docs/paci-number-correction.md.
    paci_number: Mapped[Optional[str]] = mapped_column(String(30), nullable=True, index=True)
    parking_space_id: Mapped[Optional[int]] = mapped_column(ForeignKey("properties.id"), nullable=True)
    storage_space_id: Mapped[Optional[int]] = mapped_column(ForeignKey("properties.id"), nullable=True)

    owner: Mapped["Owner"] = relationship(foreign_keys=[owner_id])  # noqa: F821
    parent: Mapped[Optional["Property"]] = relationship(remote_side="Property.id", foreign_keys=[parent_property_id])
    floor: Mapped[Optional["Floor"]] = relationship(foreign_keys=[floor_id])
    parking_space: Mapped[Optional["Property"]] = relationship(remote_side="Property.id", foreign_keys=[parking_space_id])
    storage_space: Mapped[Optional["Property"]] = relationship(remote_side="Property.id", foreign_keys=[storage_space_id])
    amenities: Mapped[list["Amenity"]] = relationship(secondary=property_amenities, back_populates="properties")
    images: Mapped[list["PropertyImage"]] = relationship(back_populates="property_ref", cascade="all, delete-orphan", order_by="PropertyImage.sort_order")
    documents: Mapped[list["PropertyDocument"]] = relationship(back_populates="property_ref", cascade="all, delete-orphan")

    @property
    def display_location(self) -> Optional[str]:
        parts = [p for p in [self.address_line1, self.address_line2] if p]
        return ", ".join(parts) if parts else None


class PropertyImage(BaseModel):
    __tablename__ = "property_images"

    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(150), nullable=False)
    storage_backend: Mapped[str] = mapped_column(String(20), default="local")
    caption: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_cover: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    property_ref: Mapped["Property"] = relationship(back_populates="images", foreign_keys=[property_id])


class PropertyDocument(BaseModel):
    """Structured legal/technical documents (title deed, floor plan, permit,
    inspection report, ...) — mirrors OwnerDocument's shape (Phase 2)."""
    __tablename__ = "property_documents"

    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    document_type: Mapped[str] = mapped_column(String(50), nullable=False)  # title_deed|floor_plan|permit|inspection_report|other
    document_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    issue_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(150), nullable=False)
    storage_backend: Mapped[str] = mapped_column(String(20), default="local")
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    property_ref: Mapped["Property"] = relationship(back_populates="documents", foreign_keys=[property_id])

    @property
    def is_expired(self) -> bool:
        return bool(self.expiry_date and self.expiry_date < date.today())
