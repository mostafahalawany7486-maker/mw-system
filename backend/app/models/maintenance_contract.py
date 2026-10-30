"""
Maintenance Contracts (extension on top of Phase 9 — Maintenance).

Phase 9 already models *reactive* maintenance ("something broke, file a
ticket"). This adds the missing *proactive* concept: a recurring/annual
service contract with a Contractor (elevator maintenance, HVAC/AC
service, generator servicing, fire-safety inspection, pest control,
etc.) that covers a Property for a fixed period, with its own
draft -> active -> (expired | terminated | renewed) status machine —
deliberately the exact same shape as LeaseAgreement (Phase 3) /
RentalContract (Phase 7) / MaintenanceRequest (Phase 9), since this
codebase already has three working examples of that pattern and a
fourth entity should not invent a new one.

Renewal reuses the Phase 3 LeaseAgreement approach: renewing creates a
NEW contract row (so the old contract's history/requests stay intact)
and marks the old one RENEWED, linked via renewed_from_contract_id.
Renewal reminders reuse the exact same on-demand sweep pattern as
Phase 3/7 (no background scheduler exists in this stack yet — see
docs/phase3-renewal-reminders.md, which already documents how to wire
any of these sweeps to a real cron/Azure Function timer trigger).

MaintenanceRequest (Phase 9) gets one new nullable, purely additive
column — `maintenance_contract_id` — so a work order can optionally be
linked back to "this was covered under contract MTC-000004" instead of
being a one-off. No existing Phase 9 column, relationship, or behavior
is touched; every existing maintenance request (contract_id = NULL)
is unaffected.
"""
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional
from sqlalchemy import String, ForeignKey, Boolean, Date, Text, Numeric, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel


class MaintenanceContractStatus:
    DRAFT = "draft"
    ACTIVE = "active"
    EXPIRED = "expired"
    TERMINATED = "terminated"
    RENEWED = "renewed"


class ContractVisitFrequency:
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    SEMI_ANNUAL = "semi_annual"
    ANNUAL = "annual"
    CUSTOM = "custom"


class MaintenanceContract(BaseModel):
    __tablename__ = "maintenance_contracts"

    contract_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)

    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id"), nullable=False, index=True)
    contractor_id: Mapped[int] = mapped_column(ForeignKey("contractors.id"), nullable=False, index=True)

    # Reuses the exact same category vocabulary as MaintenanceRequest.category
    # (see app/schemas/maintenance.py VALID_CATEGORIES) — "elevator" and
    # "hvac" are already first-class values there, so no new taxonomy.
    service_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    signed_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    visit_frequency: Mapped[str] = mapped_column(String(20), default=ContractVisitFrequency.QUARTERLY)
    visits_per_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    next_service_due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    annual_cost: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    currency_id: Mapped[Optional[int]] = mapped_column(ForeignKey("currencies.id"), nullable=True)

    is_renewable: Mapped[bool] = mapped_column(Boolean, default=True)
    renewal_notice_days: Mapped[int] = mapped_column(Integer, default=30)
    renewal_reminder_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    renewed_from_contract_id: Mapped[Optional[int]] = mapped_column(ForeignKey("maintenance_contracts.id"), nullable=True)

    contract_status: Mapped[str] = mapped_column(String(20), default=MaintenanceContractStatus.DRAFT, index=True)
    terminated_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    termination_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    property_ref: Mapped["Property"] = relationship(foreign_keys=[property_id])  # noqa: F821
    contractor: Mapped["Contractor"] = relationship(foreign_keys=[contractor_id])  # noqa: F821
    renewed_from: Mapped[Optional["MaintenanceContract"]] = relationship(
        remote_side="MaintenanceContract.id", foreign_keys=[renewed_from_contract_id]
    )

    @property
    def property_title(self) -> Optional[str]:
        return self.property_ref.title if self.property_ref else None

    @property
    def contractor_name(self) -> Optional[str]:
        return self.contractor.company_name if self.contractor else None

    @property
    def is_expiring_soon(self) -> bool:
        if self.contract_status != MaintenanceContractStatus.ACTIVE:
            return False
        days_remaining = (self.end_date - date.today()).days
        return 0 <= days_remaining <= self.renewal_notice_days

    @property
    def days_until_expiry(self) -> int:
        return (self.end_date - date.today()).days

    @property
    def is_service_due_soon(self) -> bool:
        """Distinct from contract expiry: the next scheduled visit (e.g. the
        quarterly elevator inspection) is within 14 days, regardless of how
        much of the overall contract term remains."""
        if self.contract_status != MaintenanceContractStatus.ACTIVE or not self.next_service_due_date:
            return False
        days_remaining = (self.next_service_due_date - date.today()).days
        return 0 <= days_remaining <= 14

    @property
    def is_service_overdue(self) -> bool:
        if self.contract_status != MaintenanceContractStatus.ACTIVE or not self.next_service_due_date:
            return False
        return self.next_service_due_date < date.today()
