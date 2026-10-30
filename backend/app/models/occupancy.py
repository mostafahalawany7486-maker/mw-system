"""
Occupancy & Unit Lifecycle Engine (Phase 18).

Pre-implementation analysis (full write-up in
docs/occupancy-engine.md) found that `Property.availability_status`
already exists but is exactly the anti-pattern the spec asks to
replace: a plain stored column, set imperatively in two places
(RentalService.activate_contract/terminate_contract) and read via a
GROUP BY count in PropertyRepository.unit_availability_counts — i.e.
"occupied" currently means "whatever this column says", not "what is
actually true right now". That column is left in place, untouched, for
backward compatibility (existing reads still work), but the new engine
in business_workflows/occupancy/ never reads or writes it — it computes
a unit's status live from the actual source-of-truth tables
(RentalContract, MaintenanceRequest) every time, plus the two new
tables below for the handful of statuses that had no source of truth
in this codebase at all.

OccupancyStatus is intentionally NOT a database column anywhere. It is
a computed value (see occupancy_engine.py) — the two models below exist
for the two supporting concerns that computation alone can't provide:
an explicit administrative override, and an audit trail of computed
changes over time.
"""
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, ForeignKey, DateTime, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel


class OccupancyStatus:
    """The 11 statuses the spec asks for. Not a DB enum/check constraint
    anywhere (plain string columns throughout this codebase, validated
    at the Pydantic layer only — same convention as every other status
    enum here, e.g. PropertyType, RentalContractStatus)."""
    AVAILABLE = "available"
    RESERVED = "reserved"
    OCCUPIED = "occupied"
    NOTICE_PERIOD = "notice_period"
    VACATING_SOON = "vacating_soon"
    UNDER_MAINTENANCE = "under_maintenance"
    CLEANING = "cleaning"
    INSPECTION = "inspection"
    BLOCKED = "blocked"
    RENOVATION = "renovation"
    INACTIVE = "inactive"

    ALL = [
        AVAILABLE, RESERVED, OCCUPIED, NOTICE_PERIOD, VACATING_SOON, UNDER_MAINTENANCE,
        CLEANING, INSPECTION, BLOCKED, RENOVATION, INACTIVE,
    ]
    # Statuses settable only via an explicit administrative override
    # (see UnitOccupancyOverride) — the six with no other event source
    # anywhere in this codebase. OCCUPIED, NOTICE_PERIOD, VACATING_SOON,
    # and UNDER_MAINTENANCE are never set this way — they're always
    # derived live from RentalContract/MaintenanceRequest (see
    # occupancy_engine.py); AVAILABLE is the default/fallback, also
    # never set directly.
    OVERRIDABLE = [RESERVED, CLEANING, INSPECTION, BLOCKED, RENOVATION, INACTIVE]


class UnitOccupancyOverride(BaseModel):
    """An explicit administrative decision that a unit is in one of the
    six OVERRIDABLE statuses above, right now — e.g. staff marking a
    unit 'Blocked' pending a legal matter, or 'Cleaning' between
    tenants. Overrides always win over whatever the engine would
    otherwise compute (see occupancy_engine.py's priority order).

    Append-only in spirit: "clearing" an override sets cleared_at/
    cleared_by/clear_reason on the same row rather than deleting it, so
    the full history of what was overridden, by whom, and why is never
    lost — the same "never delete, only supersede" pattern already
    established elsewhere in this codebase (OwnerLedgerEntry reversals,
    JournalEntry reversals).
    """
    __tablename__ = "unit_occupancy_overrides"

    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id"), nullable=False, index=True)
    override_status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    set_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    set_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cleared_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cleared_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    clear_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    property_ref: Mapped["Property"] = relationship(foreign_keys=[property_id])  # noqa: F821

    @property
    def is_active(self) -> bool:
        if self.cleared_at is not None:
            return False
        if self.expires_at is not None and self.expires_at <= datetime.now(timezone.utc):
            return False
        return True


class OccupancyStatusHistory(BaseModel):
    """One row per *change* in a unit's computed occupancy status — not
    one row per recalculation. Populated by
    OccupancyEngine.recalculate_and_log() (see occupancy_engine.py's
    module docstring for why comparison-against-last-snapshot, rather
    than a direct write hook, is how this stays populated without the
    engine ever depending on a stored status column)."""
    __tablename__ = "occupancy_status_history"

    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id"), nullable=False, index=True)
    previous_status: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    new_status: Mapped[str] = mapped_column(String(30), nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    triggered_by: Mapped[str] = mapped_column(String(30), default="recalculate")
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    property_ref: Mapped["Property"] = relationship(foreign_keys=[property_id])  # noqa: F821
