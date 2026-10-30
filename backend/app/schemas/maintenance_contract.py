from datetime import date
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, field_validator
from app.schemas.common import AuditFieldsOut
from app.schemas.maintenance import VALID_CATEGORIES

# Reuses the exact same service/category vocabulary as MaintenanceRequest
# (elevator, hvac, ... already exist there) — no separate taxonomy.
VALID_SERVICE_TYPES = VALID_CATEGORIES
VALID_CONTRACT_STATUSES = {"draft", "active", "expired", "terminated", "renewed"}
VALID_VISIT_FREQUENCIES = {"monthly", "quarterly", "semi_annual", "annual", "custom"}


class MaintenanceContractCreate(BaseModel):
    property_id: int
    contractor_id: int
    service_type: str
    title: str
    description: Optional[str] = None
    start_date: date
    end_date: date
    signed_date: Optional[date] = None
    visit_frequency: str = "quarterly"
    visits_per_year: Optional[int] = None
    next_service_due_date: Optional[date] = None
    annual_cost: Decimal
    currency_id: Optional[int] = None
    is_renewable: bool = True
    renewal_notice_days: int = 30
    notes: Optional[str] = None

    @field_validator("service_type")
    @classmethod
    def validate_service_type(cls, v: str) -> str:
        if v not in VALID_SERVICE_TYPES:
            raise ValueError(f"service_type must be one of {sorted(VALID_SERVICE_TYPES)}")
        return v

    @field_validator("visit_frequency")
    @classmethod
    def validate_visit_frequency(cls, v: str) -> str:
        if v not in VALID_VISIT_FREQUENCIES:
            raise ValueError(f"visit_frequency must be one of {sorted(VALID_VISIT_FREQUENCIES)}")
        return v


class MaintenanceContractUpdate(BaseModel):
    contractor_id: Optional[int] = None
    service_type: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    signed_date: Optional[date] = None
    visit_frequency: Optional[str] = None
    visits_per_year: Optional[int] = None
    next_service_due_date: Optional[date] = None
    annual_cost: Optional[Decimal] = None
    currency_id: Optional[int] = None
    is_renewable: Optional[bool] = None
    renewal_notice_days: Optional[int] = None
    notes: Optional[str] = None

    @field_validator("service_type")
    @classmethod
    def validate_service_type(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_SERVICE_TYPES:
            raise ValueError(f"service_type must be one of {sorted(VALID_SERVICE_TYPES)}")
        return v

    @field_validator("visit_frequency")
    @classmethod
    def validate_visit_frequency(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_VISIT_FREQUENCIES:
            raise ValueError(f"visit_frequency must be one of {sorted(VALID_VISIT_FREQUENCIES)}")
        return v


class TerminateMaintenanceContractRequest(BaseModel):
    terminated_date: date
    termination_reason: str


class RenewMaintenanceContractRequest(BaseModel):
    new_end_date: date
    new_start_date: Optional[date] = None  # defaults to old end_date + 1 day if omitted
    annual_cost: Optional[Decimal] = None  # allows adjusting cost on renewal
    notes: Optional[str] = None


class LogServiceVisitRequest(BaseModel):
    """Records that the scheduled visit happened and advances
    next_service_due_date by one visit_frequency step — the operational
    action behind "did the elevator/AC technician actually show up this
    quarter"."""
    visit_date: date
    notes: Optional[str] = None


class MaintenanceContractListItemOut(AuditFieldsOut):
    contract_number: str
    property_id: int
    property_title: Optional[str] = None
    contractor_id: int
    contractor_name: Optional[str] = None
    service_type: str
    title: str
    start_date: date
    end_date: date
    visit_frequency: str
    next_service_due_date: Optional[date] = None
    annual_cost: Decimal
    currency_id: Optional[int] = None
    contract_status: str
    is_expiring_soon: bool = False
    is_service_due_soon: bool = False
    is_service_overdue: bool = False
    days_until_expiry: int = 0


class MaintenanceContractDetailOut(AuditFieldsOut):
    contract_number: str
    property_id: int
    property_title: Optional[str] = None
    contractor_id: int
    contractor_name: Optional[str] = None
    service_type: str
    title: str
    description: Optional[str] = None
    start_date: date
    end_date: date
    signed_date: Optional[date] = None
    visit_frequency: str
    visits_per_year: Optional[int] = None
    next_service_due_date: Optional[date] = None
    annual_cost: Decimal
    currency_id: Optional[int] = None
    is_renewable: bool
    renewal_notice_days: int
    renewal_reminder_sent: bool
    renewed_from_contract_id: Optional[int] = None
    contract_status: str
    terminated_date: Optional[date] = None
    termination_reason: Optional[str] = None
    notes: Optional[str] = None
    is_expiring_soon: bool = False
    is_service_due_soon: bool = False
    is_service_overdue: bool = False
    days_until_expiry: int = 0


class MaintenanceContractDashboardOut(BaseModel):
    total_contracts: int
    active_contracts: int
    draft_contracts: int
    expiring_soon: int
    service_due_soon: int
    terminated_contracts: int
    upcoming: List[MaintenanceContractListItemOut] = []
