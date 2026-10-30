from datetime import datetime, date
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.orm import Session, selectinload
from app.repositories.base import BaseRepository
from app.models.occupancy import UnitOccupancyOverride, OccupancyStatusHistory
from app.models.rental import RentalContract, RentalContractStatus
from app.models.maintenance import MaintenanceRequest, MaintenanceRequestStatus

OPEN_MAINTENANCE_STATUSES = [
    MaintenanceRequestStatus.REPORTED, MaintenanceRequestStatus.ASSIGNED,
    MaintenanceRequestStatus.IN_PROGRESS, MaintenanceRequestStatus.ON_HOLD,
]


class OccupancyOverrideRepository(BaseRepository[UnitOccupancyOverride]):
    def __init__(self, db: Session):
        super().__init__(UnitOccupancyOverride, db)

    def get_active_for_unit(self, property_id: int) -> Optional[UnitOccupancyOverride]:
        """The one override that matters for computing status right now
        — most recent, not cleared. Expiry is checked in Python via
        .is_active (see model) since it depends on "now", which SQLite's
        test DB and Postgres don't need to agree on identically."""
        stmt = (
            select(UnitOccupancyOverride)
            .where(UnitOccupancyOverride.property_id == property_id, UnitOccupancyOverride.cleared_at.is_(None), UnitOccupancyOverride.deleted_at.is_(None))
            .order_by(UnitOccupancyOverride.id.desc())
            .limit(1)
        )
        override = self.db.execute(stmt).scalar_one_or_none()
        return override if (override and override.is_active) else None

    def get_active_for_units(self, property_ids: list[int]) -> dict[int, UnitOccupancyOverride]:
        """Bulk version of get_active_for_unit — one query for a whole
        building's worth of units instead of N, used by the dashboard/
        building-summary/units-list endpoints."""
        if not property_ids:
            return {}
        stmt = (
            select(UnitOccupancyOverride)
            .where(UnitOccupancyOverride.property_id.in_(property_ids), UnitOccupancyOverride.cleared_at.is_(None), UnitOccupancyOverride.deleted_at.is_(None))
            .order_by(UnitOccupancyOverride.id.desc())
        )
        result: dict[int, UnitOccupancyOverride] = {}
        for override in self.db.execute(stmt).scalars().all():
            if override.property_id not in result and override.is_active:
                result[override.property_id] = override
        return result

    def get_detail(self, override_id: int) -> Optional[UnitOccupancyOverride]:
        stmt = select(UnitOccupancyOverride).options(selectinload(UnitOccupancyOverride.property_ref)).where(
            UnitOccupancyOverride.id == override_id, UnitOccupancyOverride.deleted_at.is_(None),
        )
        return self.db.execute(stmt).scalar_one_or_none()


class OccupancyHistoryRepository(BaseRepository[OccupancyStatusHistory]):
    def __init__(self, db: Session):
        super().__init__(OccupancyStatusHistory, db)

    def get_last_status(self, property_id: int) -> Optional[str]:
        stmt = (
            select(OccupancyStatusHistory.new_status)
            .where(OccupancyStatusHistory.property_id == property_id)
            .order_by(OccupancyStatusHistory.id.desc())
            .limit(1)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list_for_unit(self, property_id: int, limit: int = 50) -> list[OccupancyStatusHistory]:
        stmt = (
            select(OccupancyStatusHistory)
            .where(OccupancyStatusHistory.property_id == property_id)
            .order_by(OccupancyStatusHistory.id.desc())
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())


class OccupancyDataRepository:
    """Read-only access to the actual source-of-truth tables the engine
    computes status from (RentalContract, MaintenanceRequest) — kept
    separate from OccupancyOverrideRepository/OccupancyHistoryRepository
    since this one owns no table of its own, it only queries tables
    that belong to the Rentals/Maintenance modules."""

    def __init__(self, db: Session):
        self.db = db

    def get_active_contract(self, property_id: int) -> Optional[RentalContract]:
        stmt = (
            select(RentalContract)
            .where(RentalContract.property_id == property_id, RentalContract.contract_status == RentalContractStatus.ACTIVE, RentalContract.deleted_at.is_(None))
            .order_by(RentalContract.id.desc())
            .limit(1)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_active_contracts_for_units(self, property_ids: list[int]) -> dict[int, RentalContract]:
        if not property_ids:
            return {}
        stmt = select(RentalContract).where(
            RentalContract.property_id.in_(property_ids), RentalContract.contract_status == RentalContractStatus.ACTIVE, RentalContract.deleted_at.is_(None),
        )
        return {c.property_id: c for c in self.db.execute(stmt).scalars().all()}

    def has_open_maintenance(self, property_id: int) -> bool:
        stmt = select(func.count()).select_from(MaintenanceRequest).where(
            MaintenanceRequest.property_id == property_id, MaintenanceRequest.maintenance_status.in_(OPEN_MAINTENANCE_STATUSES), MaintenanceRequest.deleted_at.is_(None),
        )
        return (self.db.execute(stmt).scalar_one() or 0) > 0

    def open_maintenance_unit_ids(self, property_ids: list[int]) -> set[int]:
        if not property_ids:
            return set()
        stmt = select(MaintenanceRequest.property_id).where(
            MaintenanceRequest.property_id.in_(property_ids), MaintenanceRequest.maintenance_status.in_(OPEN_MAINTENANCE_STATUSES), MaintenanceRequest.deleted_at.is_(None),
        ).distinct()
        return {row[0] for row in self.db.execute(stmt).all()}

    def count_other_active_contracts(self, property_id: int, exclude_contract_id: Optional[int] = None) -> int:
        """Used by the 'prevent multiple active leases on the same unit'
        validation — counts ACTIVE contracts on this unit other than the
        one being activated (so re-checking an already-active contract
        doesn't count itself)."""
        stmt = select(func.count()).select_from(RentalContract).where(
            RentalContract.property_id == property_id, RentalContract.contract_status == RentalContractStatus.ACTIVE, RentalContract.deleted_at.is_(None),
        )
        if exclude_contract_id:
            stmt = stmt.where(RentalContract.id != exclude_contract_id)
        return self.db.execute(stmt).scalar_one() or 0
