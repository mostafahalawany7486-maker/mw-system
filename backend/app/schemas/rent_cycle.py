from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, field_validator
from app.schemas.common import AuditFieldsOut

VALID_CYCLE_STATUSES = {
    "draft", "generated", "printed", "distributed", "collecting",
    "partially_collected", "completed", "closed", "cancelled",
}


class RentCycleCreate(BaseModel):
    month: int
    year: int
    start_date: Optional[date] = None
    due_date: Optional[date] = None
    property_ids: Optional[List[int]] = None
    notes: Optional[str] = None

    @field_validator("month")
    @classmethod
    def validate_month(cls, v: int) -> int:
        if not 1 <= v <= 12:
            raise ValueError("month must be between 1 and 12")
        return v

    @field_validator("year")
    @classmethod
    def validate_year(cls, v: int) -> int:
        if v < 2000 or v > 2200:
            raise ValueError("year is out of a plausible range")
        return v


class GenerateCycleRequest(BaseModel):
    force: bool = False


class CloseCycleRequest(BaseModel):
    notes: Optional[str] = None


class CancelCycleRequest(BaseModel):
    reason: str


class RentCycleRecordOut(AuditFieldsOut):
    cycle_id: int
    rental_contract_id: int
    invoice_id: Optional[int] = None
    installment_id: Optional[int] = None
    amount: Decimal
    due_date: date
    record_status: str
    skip_reason: Optional[str] = None

    tenant_display_name: Optional[str] = None
    property_title: Optional[str] = None
    building_title: Optional[str] = None
    unit_number: Optional[str] = None
    invoice_number: Optional[str] = None
    invoice_status: Optional[str] = None
    receipt_number: Optional[str] = None


class RentCycleListItemOut(AuditFieldsOut):
    cycle_number: str
    month: int
    year: int
    start_date: date
    due_date: date
    closing_date: Optional[date] = None
    cycle_status: str
    generated_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None


class RentCycleDetailOut(RentCycleListItemOut):
    property_ids: Optional[List[int]] = None
    notes: Optional[str] = None
    cancellation_reason: Optional[str] = None
    records: List[RentCycleRecordOut] = []


class RentCycleDashboardOut(BaseModel):
    total_cycles: int
    open_cycles: int
    cycles_by_status: dict

    # Current-cycle collection snapshot (the cycle for "today", if one exists)
    current_cycle_number: Optional[str] = None
    total_receipts: int = 0
    total_expected_income: Decimal = Decimal("0")
    total_collected_income: Decimal = Decimal("0")
    active_lease_count: int = 0
    generated_receipt_count: int = 0
    collection_progress_percent: Decimal = Decimal("0")


class RentCycleGenerateResultOut(BaseModel):
    cycle: RentCycleDetailOut
    invoices_generated: int
    receipts_generated: int
    leases_skipped: int
    message: str
