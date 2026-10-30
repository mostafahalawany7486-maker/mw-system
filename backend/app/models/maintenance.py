"""
Maintenance module (Phase 9).

MaintenanceRequest is the central entity (mirrors the RentalContract/
LeaseAgreement status-machine pattern from Phases 3/7): reported -> assigned
-> in_progress -> completed, with on_hold and cancelled as side branches.

Contractors and Technicians are lightweight directory entities — a
Technician may optionally belong to a Contractor (contracted labor) or
have no contractor_id (in-house staff). Materials and Labor Cost are
per-request line items so "actual cost" is always an accurate sum rather
than a single guessed number, and Before/After Photos get first-class
fields (photo_type discriminator) rather than being folded into the
generic Phase 1 Attachment table, since "before vs. after" is a specific,
structured concept worth its own column rather than free-text description
parsing.

History reuses the generic Phase 1 ActivityLog (entity_type=
"maintenance_request") — no new table needed, consistent with every prior
phase.
"""
from datetime import date
from decimal import Decimal
from typing import Optional
from sqlalchemy import String, ForeignKey, Date, Text, Numeric, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel


class MaintenancePriority:
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class MaintenanceRequestStatus:
    REPORTED = "reported"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class PhotoType:
    BEFORE = "before"
    AFTER = "after"


class Contractor(BaseModel):
    __tablename__ = "contractors"

    contractor_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    company_name: Mapped[str] = mapped_column(String(150), nullable=False)
    contact_person: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    specialty: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    hourly_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 3), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    technicians: Mapped[list["Technician"]] = relationship(back_populates="contractor")


class Technician(BaseModel):
    __tablename__ = "technicians"

    technician_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    specialty: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    contractor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("contractors.id"), nullable=True, index=True)
    hourly_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 3), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    contractor: Mapped[Optional["Contractor"]] = relationship(back_populates="technicians", foreign_keys=[contractor_id])

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def is_in_house(self) -> bool:
        return self.contractor_id is None


class MaintenanceRequest(BaseModel):
    __tablename__ = "maintenance_requests"

    request_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id"), nullable=False, index=True)
    rental_contract_id: Mapped[Optional[int]] = mapped_column(ForeignKey("rental_contracts.id"), nullable=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tenants.id"), nullable=True, index=True)
    # Additive (Maintenance Contracts extension): optional link back to the
    # recurring service contract this work order was performed under (e.g.
    # a quarterly elevator inspection visit). NULL for every existing and
    # future ad-hoc/reactive request — nothing about the reactive workflow
    # changes when this is unset.
    maintenance_contract_id: Mapped[Optional[int]] = mapped_column(ForeignKey("maintenance_contracts.id"), nullable=True, index=True)

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    priority: Mapped[str] = mapped_column(String(20), default=MaintenancePriority.MEDIUM, index=True)
    maintenance_status: Mapped[str] = mapped_column(String(20), default=MaintenanceRequestStatus.REPORTED, index=True)

    reported_date: Mapped[date] = mapped_column(Date, nullable=False)
    scheduled_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    completed_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    assigned_contractor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("contractors.id"), nullable=True)
    assigned_technician_id: Mapped[Optional[int]] = mapped_column(ForeignKey("technicians.id"), nullable=True)

    estimated_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 3), nullable=True)
    on_hold_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cancellation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    property_ref: Mapped["Property"] = relationship(foreign_keys=[property_id])  # noqa: F821
    rental_contract: Mapped[Optional["RentalContract"]] = relationship(foreign_keys=[rental_contract_id])  # noqa: F821
    tenant: Mapped[Optional["Tenant"]] = relationship(foreign_keys=[tenant_id])  # noqa: F821
    assigned_contractor: Mapped[Optional["Contractor"]] = relationship(foreign_keys=[assigned_contractor_id])
    assigned_technician: Mapped[Optional["Technician"]] = relationship(foreign_keys=[assigned_technician_id])
    maintenance_contract: Mapped[Optional["MaintenanceContract"]] = relationship(foreign_keys=[maintenance_contract_id])  # noqa: F821

    materials: Mapped[list["MaintenanceMaterial"]] = relationship(back_populates="request", cascade="all, delete-orphan")
    labor_entries: Mapped[list["MaintenanceLaborCost"]] = relationship(back_populates="request", cascade="all, delete-orphan")
    photos: Mapped[list["MaintenancePhoto"]] = relationship(back_populates="request", cascade="all, delete-orphan")

    @property
    def property_title(self) -> Optional[str]:
        return self.property_ref.title if self.property_ref else None

    @property
    def tenant_display_name(self) -> Optional[str]:
        return self.tenant.display_name if self.tenant else None

    @property
    def contractor_name(self) -> Optional[str]:
        return self.assigned_contractor.company_name if self.assigned_contractor else None

    @property
    def technician_name(self) -> Optional[str]:
        return self.assigned_technician.full_name if self.assigned_technician else None

    @property
    def total_material_cost(self) -> Decimal:
        return sum((m.total_cost for m in self.materials), Decimal("0"))

    @property
    def total_labor_cost(self) -> Decimal:
        return sum((l.total_cost for l in self.labor_entries), Decimal("0"))

    @property
    def total_actual_cost(self) -> Decimal:
        return self.total_material_cost + self.total_labor_cost

    @property
    def is_overdue(self) -> bool:
        if self.maintenance_status in (MaintenanceRequestStatus.COMPLETED, MaintenanceRequestStatus.CANCELLED):
            return False
        return bool(self.scheduled_date) and self.scheduled_date < date.today()


class MaintenanceMaterial(BaseModel):
    __tablename__ = "maintenance_materials"

    request_id: Mapped[int] = mapped_column(ForeignKey("maintenance_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 3), default=1)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(10, 3), default=0)
    supplier: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)

    request: Mapped["MaintenanceRequest"] = relationship(back_populates="materials", foreign_keys=[request_id])

    @property
    def total_cost(self) -> Decimal:
        return self.quantity * self.unit_cost


class MaintenanceLaborCost(BaseModel):
    __tablename__ = "maintenance_labor_costs"

    request_id: Mapped[int] = mapped_column(ForeignKey("maintenance_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    technician_id: Mapped[Optional[int]] = mapped_column(ForeignKey("technicians.id"), nullable=True)
    contractor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("contractors.id"), nullable=True)
    work_date: Mapped[date] = mapped_column(Date, nullable=False)
    hours: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=0)
    hourly_rate: Mapped[Decimal] = mapped_column(Numeric(10, 3), default=0)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    request: Mapped["MaintenanceRequest"] = relationship(back_populates="labor_entries", foreign_keys=[request_id])
    technician: Mapped[Optional["Technician"]] = relationship(foreign_keys=[technician_id])
    contractor: Mapped[Optional["Contractor"]] = relationship(foreign_keys=[contractor_id])

    @property
    def total_cost(self) -> Decimal:
        return self.hours * self.hourly_rate

    @property
    def technician_name(self) -> Optional[str]:
        return self.technician.full_name if self.technician else None


class MaintenancePhoto(BaseModel):
    __tablename__ = "maintenance_photos"

    request_id: Mapped[int] = mapped_column(ForeignKey("maintenance_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    photo_type: Mapped[str] = mapped_column(String(10), nullable=False, index=True)  # before | after
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(150), nullable=False)
    storage_backend: Mapped[str] = mapped_column(String(20), default="local")
    caption: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    request: Mapped["MaintenanceRequest"] = relationship(back_populates="photos", foreign_keys=[request_id])
