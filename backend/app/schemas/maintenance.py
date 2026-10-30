from datetime import date
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, field_validator, model_validator
from app.schemas.common import AuditFieldsOut

VALID_PRIORITIES = {"low", "medium", "high", "urgent"}
VALID_STATUSES = {"reported", "assigned", "in_progress", "on_hold", "completed", "cancelled"}
VALID_CATEGORIES = {
    "plumbing", "electrical", "hvac", "appliance", "structural",
    "pest_control", "painting", "cleaning", "security", "elevator", "landscaping", "other",
}
VALID_SPECIALTIES = VALID_CATEGORIES | {"general"}
VALID_PHOTO_TYPES = {"before", "after"}


# ---------------- Contractor ----------------
class ContractorCreate(BaseModel):
    company_name: str
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    specialty: Optional[str] = None
    hourly_rate: Optional[Decimal] = None
    notes: Optional[str] = None

    @field_validator("specialty")
    @classmethod
    def validate_specialty(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_SPECIALTIES:
            raise ValueError(f"specialty must be one of {sorted(VALID_SPECIALTIES)}")
        return v


class ContractorUpdate(BaseModel):
    company_name: Optional[str] = None
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    specialty: Optional[str] = None
    hourly_rate: Optional[Decimal] = None
    notes: Optional[str] = None
    status: Optional[str] = None

    @field_validator("specialty")
    @classmethod
    def validate_specialty(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_SPECIALTIES:
            raise ValueError(f"specialty must be one of {sorted(VALID_SPECIALTIES)}")
        return v


class ContractorOut(AuditFieldsOut):
    contractor_code: str
    company_name: str
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    specialty: Optional[str] = None
    hourly_rate: Optional[Decimal] = None
    notes: Optional[str] = None
    technician_count: int = 0


# ---------------- Technician ----------------
class TechnicianCreate(BaseModel):
    first_name: str
    last_name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    specialty: Optional[str] = None
    contractor_id: Optional[int] = None
    hourly_rate: Optional[Decimal] = None
    notes: Optional[str] = None

    @field_validator("specialty")
    @classmethod
    def validate_specialty(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_SPECIALTIES:
            raise ValueError(f"specialty must be one of {sorted(VALID_SPECIALTIES)}")
        return v


class TechnicianUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    specialty: Optional[str] = None
    contractor_id: Optional[int] = None
    hourly_rate: Optional[Decimal] = None
    notes: Optional[str] = None
    status: Optional[str] = None

    @field_validator("specialty")
    @classmethod
    def validate_specialty(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_SPECIALTIES:
            raise ValueError(f"specialty must be one of {sorted(VALID_SPECIALTIES)}")
        return v


class TechnicianOut(AuditFieldsOut):
    technician_code: str
    first_name: str
    last_name: str
    full_name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    specialty: Optional[str] = None
    contractor_id: Optional[int] = None
    contractor_name: Optional[str] = None
    hourly_rate: Optional[Decimal] = None
    notes: Optional[str] = None
    is_in_house: bool = True


# ---------------- Materials & Labor ----------------
class MaterialCreate(BaseModel):
    name: str
    quantity: Decimal = Decimal("1")
    unit_cost: Decimal = Decimal("0")
    supplier: Optional[str] = None

    @field_validator("quantity", "unit_cost")
    @classmethod
    def validate_non_negative(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("Value cannot be negative")
        return v


class MaterialOut(AuditFieldsOut):
    request_id: int
    name: str
    quantity: Decimal
    unit_cost: Decimal
    supplier: Optional[str] = None
    total_cost: Decimal


class LaborCostCreate(BaseModel):
    technician_id: Optional[int] = None
    contractor_id: Optional[int] = None
    work_date: date
    hours: Decimal
    hourly_rate: Decimal
    description: Optional[str] = None

    @field_validator("hours", "hourly_rate")
    @classmethod
    def validate_non_negative(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("Value cannot be negative")
        return v


class LaborCostOut(AuditFieldsOut):
    request_id: int
    technician_id: Optional[int] = None
    technician_name: Optional[str] = None
    contractor_id: Optional[int] = None
    work_date: date
    hours: Decimal
    hourly_rate: Decimal
    description: Optional[str] = None
    total_cost: Decimal


class PhotoOut(AuditFieldsOut):
    request_id: int
    photo_type: str
    file_name: str
    file_url: Optional[str] = None
    file_size_bytes: int
    mime_type: str
    caption: Optional[str] = None


# ---------------- Maintenance Request ----------------
class MaintenanceRequestCreate(BaseModel):
    property_id: int
    rental_contract_id: Optional[int] = None
    tenant_id: Optional[int] = None
    # Additive (Maintenance Contracts extension): optionally link this work
    # order to the recurring service contract it's being performed under.
    maintenance_contract_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    category: Optional[str] = None
    priority: str = "medium"
    reported_date: date
    scheduled_date: Optional[date] = None
    estimated_cost: Optional[Decimal] = None
    notes: Optional[str] = None

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: str) -> str:
        if v not in VALID_PRIORITIES:
            raise ValueError(f"priority must be one of {sorted(VALID_PRIORITIES)}")
        return v

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_CATEGORIES:
            raise ValueError(f"category must be one of {sorted(VALID_CATEGORIES)}")
        return v

    @model_validator(mode="after")
    def validate_scheduled_date(self):
        if self.scheduled_date and self.scheduled_date < self.reported_date:
            raise ValueError("scheduled_date cannot be before reported_date")
        return self


class MaintenanceRequestUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[str] = None
    scheduled_date: Optional[date] = None
    estimated_cost: Optional[Decimal] = None
    maintenance_contract_id: Optional[int] = None
    notes: Optional[str] = None

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_PRIORITIES:
            raise ValueError(f"priority must be one of {sorted(VALID_PRIORITIES)}")
        return v

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_CATEGORIES:
            raise ValueError(f"category must be one of {sorted(VALID_CATEGORIES)}")
        return v


class AssignRequest(BaseModel):
    assigned_contractor_id: Optional[int] = None
    assigned_technician_id: Optional[int] = None
    scheduled_date: Optional[date] = None

    @model_validator(mode="after")
    def validate_at_least_one(self):
        if not self.assigned_contractor_id and not self.assigned_technician_id:
            raise ValueError("Assign at least a contractor or a technician")
        return self


class HoldRequest(BaseModel):
    on_hold_reason: str


class CancelRequest(BaseModel):
    cancellation_reason: str


class CompleteRequest(BaseModel):
    completed_date: date


class MaintenanceRequestListItemOut(AuditFieldsOut):
    request_number: str
    property_id: int
    property_title: Optional[str] = None
    tenant_id: Optional[int] = None
    tenant_display_name: Optional[str] = None
    title: str
    category: Optional[str] = None
    priority: str
    maintenance_status: str
    reported_date: date
    scheduled_date: Optional[date] = None
    completed_date: Optional[date] = None
    contractor_name: Optional[str] = None
    technician_name: Optional[str] = None
    total_actual_cost: Decimal = Decimal("0")
    is_overdue: bool = False


class MaintenanceRequestDetailOut(AuditFieldsOut):
    request_number: str
    property_id: int
    property_title: Optional[str] = None
    rental_contract_id: Optional[int] = None
    tenant_id: Optional[int] = None
    tenant_display_name: Optional[str] = None
    maintenance_contract_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    category: Optional[str] = None
    priority: str
    maintenance_status: str
    reported_date: date
    scheduled_date: Optional[date] = None
    completed_date: Optional[date] = None
    assigned_contractor_id: Optional[int] = None
    contractor_name: Optional[str] = None
    assigned_technician_id: Optional[int] = None
    technician_name: Optional[str] = None
    estimated_cost: Optional[Decimal] = None
    on_hold_reason: Optional[str] = None
    cancellation_reason: Optional[str] = None
    notes: Optional[str] = None
    is_overdue: bool = False
    total_material_cost: Decimal = Decimal("0")
    total_labor_cost: Decimal = Decimal("0")
    total_actual_cost: Decimal = Decimal("0")
    materials: List[MaterialOut] = []
    labor_entries: List[LaborCostOut] = []
    photos: List[PhotoOut] = []


class MaintenanceDashboardOut(BaseModel):
    total_requests: int
    reported_count: int
    assigned_count: int
    in_progress_count: int
    on_hold_count: int
    completed_count: int
    cancelled_count: int
    overdue_count: int
    urgent_open_count: int
    total_actual_cost_this_month: Decimal
