"""
occupancy_statistics.py

Aggregation on top of OccupancyEngine.compute_bulk() — the spec's
OCCUPANCY DASHBOARD and BUILDING SUMMARY sections. Reuses existing
repository methods for everything that isn't itself an occupancy-status
question (active/expiring contract counts, maintenance counts) rather
than re-deriving them — the same "one place counts, multiple callers"
principle PropertyService._aggregate_container already established for
the pre-existing building summary, applied here for the new
status-aware version.
"""
from decimal import Decimal
from typing import Optional
from sqlalchemy.orm import Session

from app.models.property import Property, PropertyType
from app.models.occupancy import OccupancyStatus
from app.repositories.property_repository import PropertyRepository
from app.repositories.rental_repository import RentalContractRepository
from app.repositories.maintenance_repository import MaintenanceRequestRepository
from app.business_workflows.occupancy.occupancy_engine import OccupancyEngine
from app.models.rental import RentalContractStatus
from sqlalchemy import select, func


def _percentage(part: int, whole: int) -> Decimal:
    if not whole:
        return Decimal("0.00")
    return Decimal(round((part / whole) * 100, 2))


class OccupancyStatisticsService:
    def __init__(self, db: Session):
        self.db = db
        self.property_repo = PropertyRepository(db)
        self.rental_repo = RentalContractRepository(db)
        self.maintenance_repo = MaintenanceRequestRepository(db)
        self.engine = OccupancyEngine(db)

    def _all_unit_ids(self, building_id: Optional[int] = None) -> list[int]:
        """Every leasable unit (non-container property types) — portfolio-
        wide if building_id is None, scoped to one building otherwise.
        Buildings/villas/etc. themselves are containers, not units, and
        are excluded — same exclusion PropertyService/ReportsService
        already apply everywhere occupancy is computed. FLOOR is also
        excluded: it's a virtual Property row standing in for "this whole
        floor, leased as one contract" (see
        RentalService._create_floor_wide_side_effects), not a real unit —
        its own child units are already counted individually, so
        including it too double-counted occupancy for every floor-wide
        rental (same bug as PropertyRepository.get_dashboard_stats)."""
        non_unit_types = PropertyType.CONTAINER_TYPES + [PropertyType.FLOOR]
        if building_id is not None:
            return self.property_repo.get_unit_ids(building_id)
        stmt = select(Property.id).where(
            Property.deleted_at.is_(None), ~Property.property_type.in_(non_unit_types),
        )
        return [row[0] for row in self.db.execute(stmt).all()]

    def get_dashboard(self) -> dict:
        unit_ids = self._all_unit_ids()
        statuses = self.engine.compute_bulk(unit_ids)
        return self._summarize(statuses, unit_ids)

    def _summarize(self, statuses: dict[int, tuple[str, str]], unit_ids: list[int]) -> dict:
        by_status: dict[str, int] = {s: 0 for s in OccupancyStatus.ALL}
        for status_value, _ in statuses.values():
            by_status[status_value] = by_status.get(status_value, 0) + 1

        total = len(unit_ids)
        occupied = by_status[OccupancyStatus.OCCUPIED]
        vacant = by_status[OccupancyStatus.AVAILABLE]
        reserved = by_status[OccupancyStatus.RESERVED]
        maintenance = by_status[OccupancyStatus.UNDER_MAINTENANCE]
        notice = by_status[OccupancyStatus.NOTICE_PERIOD]
        vacating = by_status[OccupancyStatus.VACATING_SOON]
        other = total - occupied - vacant - reserved - maintenance - notice - vacating

        return {
            "total_units": total,
            "occupied_units": occupied,
            "vacant_units": vacant,
            "reserved_units": reserved,
            "maintenance_units": maintenance,
            "notice_period_units": notice,
            "vacating_soon_units": vacating,
            "other_units": other,
            "occupancy_percentage": _percentage(occupied, total),
            "vacancy_percentage": _percentage(vacant, total),
            "by_status": by_status,
        }

    def get_building_summary(self, building_id: int) -> dict:
        building = self.property_repo.get(building_id)
        unit_ids = self._all_unit_ids(building_id)
        statuses = self.engine.compute_bulk(unit_ids)
        occ = self._summarize(statuses, unit_ids)

        all_ids = [building_id] + unit_ids
        average_rent = self._average_active_rent(unit_ids)

        return {
            "building_id": building_id,
            "building_title": building.title,
            "building_code": building.property_code,
            "unit_count": occ["total_units"],
            "occupied_units": occ["occupied_units"],
            "vacant_units": occ["vacant_units"],
            "occupancy_percentage": occ["occupancy_percentage"],
            "vacancy_percentage": occ["vacancy_percentage"],
            "average_rent": average_rent,
            "active_contracts": self.rental_repo.count_by_property_ids_and_status(all_ids, RentalContractStatus.ACTIVE),
            "expiring_contracts": self.rental_repo.count_expiring_soon_by_property_ids(all_ids),
            "maintenance_count": self.maintenance_repo.count_open_by_property_ids(all_ids),
        }

    def get_all_buildings_summary(self) -> list[dict]:
        stmt = select(Property.id).where(Property.deleted_at.is_(None), Property.property_type.in_(PropertyType.CONTAINER_TYPES))
        building_ids = [row[0] for row in self.db.execute(stmt).all()]
        return [self.get_building_summary(bid) for bid in building_ids]

    def _average_active_rent(self, unit_ids: list[int]) -> Decimal:
        """Actual signed rent on active contracts for these units — more
        meaningful for a leasing summary than the asking price on
        vacant units (Property.rent_price), which most of a building's
        currently-occupied units won't even have set."""
        if not unit_ids:
            return Decimal("0.00")
        from app.models.rental import RentalContract
        stmt = select(func.avg(RentalContract.rent_amount)).where(
            RentalContract.property_id.in_(unit_ids), RentalContract.contract_status == RentalContractStatus.ACTIVE, RentalContract.deleted_at.is_(None),
        )
        avg = self.db.execute(stmt).scalar_one()
        return Decimal(round(avg, 2)) if avg is not None else Decimal("0.00")
