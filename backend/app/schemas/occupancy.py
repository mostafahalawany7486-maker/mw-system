from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, field_validator
from app.models.occupancy import OccupancyStatus

VALID_OVERRIDE_STATUSES = set(OccupancyStatus.OVERRIDABLE)


class SetOverrideRequest(BaseModel):
    override_status: str
    reason: Optional[str] = None
    expires_at: Optional[datetime] = None

    @field_validator("override_status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in VALID_OVERRIDE_STATUSES:
            raise ValueError(f"override_status must be one of {sorted(VALID_OVERRIDE_STATUSES)}")
        return v


class ClearOverrideRequest(BaseModel):
    reason: Optional[str] = None


class SetNoticeRequest(BaseModel):
    move_out_notice_date: date


class UnitOccupancyOut(BaseModel):
    property_id: int
    property_title: str
    property_code: str
    unit_number: Optional[str] = None
    building_id: Optional[int] = None
    building_title: Optional[str] = None
    occupancy_status: str
    status_reason: str
    tenant_display_name: Optional[str] = None
    rental_contract_id: Optional[int] = None
    contract_end_date: Optional[date] = None
    rent_amount: Optional[Decimal] = None


class OccupancyDashboardOut(BaseModel):
    total_units: int
    occupied_units: int
    vacant_units: int
    reserved_units: int
    maintenance_units: int
    notice_period_units: int
    vacating_soon_units: int
    other_units: int
    occupancy_percentage: Decimal
    vacancy_percentage: Decimal
    by_status: dict


class BuildingOccupancySummaryOut(BaseModel):
    building_id: int
    building_title: str
    building_code: str
    unit_count: int
    occupied_units: int
    vacant_units: int
    occupancy_percentage: Decimal
    vacancy_percentage: Decimal
    average_rent: Decimal
    active_contracts: int
    expiring_contracts: int
    maintenance_count: int


class OccupancyOverrideOut(BaseModel):
    id: int
    property_id: int
    override_status: str
    reason: Optional[str] = None
    set_by: Optional[int] = None
    set_at: datetime
    expires_at: Optional[datetime] = None
    cleared_at: Optional[datetime] = None
    cleared_by: Optional[int] = None
    clear_reason: Optional[str] = None


class OccupancyHistoryItemOut(BaseModel):
    id: int
    property_id: int
    previous_status: Optional[str] = None
    new_status: str
    reason: Optional[str] = None
    triggered_by: str
    changed_at: datetime


class RecalculateResultOut(BaseModel):
    units_checked: int
    units_changed: int
    changes: List[OccupancyHistoryItemOut] = []
