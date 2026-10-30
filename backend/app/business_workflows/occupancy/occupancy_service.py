"""
occupancy_service.py

The facade the API router calls — ties occupancy_engine (computation),
occupancy_statistics (aggregation), occupancy_events (writes), and
occupancy_scheduler (the recalculate sweep) together into the handful
of operations the spec's API section asks for, plus the override/notice
actions needed to make six of the eleven statuses actually reachable.
"""
from datetime import date, datetime
from typing import Optional
from sqlalchemy.orm import Session

from app.repositories.property_repository import PropertyRepository
from app.business_workflows.occupancy.occupancy_engine import OccupancyEngine
from app.business_workflows.occupancy.occupancy_statistics import OccupancyStatisticsService
from app.business_workflows.occupancy.occupancy_events import OccupancyEventsService
from app.business_workflows.occupancy.occupancy_scheduler import OccupancyScheduler
from app.business_workflows.occupancy.occupancy_validator import OccupancyValidator
from app.repositories.rental_repository import RentalContractRepository


class OccupancyService:
    def __init__(self, db: Session):
        self.db = db
        self.engine = OccupancyEngine(db)
        self.stats = OccupancyStatisticsService(db)
        self.events = OccupancyEventsService(db)
        self.scheduler = OccupancyScheduler(db)
        self.validator = OccupancyValidator(db)
        self.property_repo = PropertyRepository(db)
        self.rental_repo = RentalContractRepository(db)

    # ---------------- GET /occupancy ----------------
    def get_dashboard(self) -> dict:
        return self.stats.get_dashboard()

    # ---------------- GET /occupancy/buildings ----------------
    def get_buildings(self, building_id: Optional[int] = None) -> list[dict]:
        if building_id is not None:
            self.validator.validate_building_exists(building_id)
            return [self.stats.get_building_summary(building_id)]
        return self.stats.get_all_buildings_summary()

    # ---------------- GET /occupancy/units ----------------
    def get_units(self, building_id: Optional[int], occupancy_status: Optional[str], page: int, page_size: int) -> tuple[list[dict], int]:
        if building_id is not None:
            self.validator.validate_building_exists(building_id)
            unit_ids = self.property_repo.get_unit_ids(building_id)
        else:
            unit_ids = self.stats._all_unit_ids()

        statuses = self.engine.compute_bulk(unit_ids)
        if occupancy_status:
            unit_ids = [uid for uid in unit_ids if statuses.get(uid, (None, None))[0] == occupancy_status]

        total = len(unit_ids)
        page_ids = unit_ids[(page - 1) * page_size: (page - 1) * page_size + page_size]

        units = self.property_repo.get_many_with_parent(page_ids) if page_ids else []
        contracts = {c.property_id: c for c in self.rental_repo.list_active_by_property_ids(page_ids)} if page_ids else {}

        # Raised directly: a unit blocked because it's part of a
        # whole-floor contract (see RentalService._sync_floor_wide_overrides)
        # has no contract directly on IT — the contract is on the
        # floor-level Property instead — so it showed no tenant name,
        # no rent, nothing, and reasonably looked "just empty" even
        # though it's genuinely occupied. Looks up each blocked unit's
        # floor-level contract (if any) and inherits tenant/end-date
        # from it instead of leaving those blank.
        from app.models.property import PropertyType, Property
        floor_ids = {u.floor_id for u in units if u.floor_id and not contracts.get(u.id)}
        floor_unit_ids = []
        if floor_ids:
            floor_unit_rows = self.db.query(Property.id, Property.floor_id).filter(
                Property.floor_id.in_(floor_ids), Property.property_type == PropertyType.FLOOR, Property.deleted_at.is_(None),
            ).all()
            floor_unit_ids = [r.id for r in floor_unit_rows]
            floor_unit_by_floor = {r.floor_id: r.id for r in floor_unit_rows}
        else:
            floor_unit_by_floor = {}
        floor_contracts = {c.property_id: c for c in self.rental_repo.list_active_by_property_ids(floor_unit_ids)} if floor_unit_ids else {}

        items = []
        for unit in units:
            occ_status, reason = statuses.get(unit.id, self.engine.compute_unit_status(unit.id))
            contract = contracts.get(unit.id)
            whole_floor_contract = None
            if not contract and unit.floor_id in floor_unit_by_floor:
                whole_floor_contract = floor_contracts.get(floor_unit_by_floor[unit.floor_id])
            source_contract = contract or whole_floor_contract
            items.append({
                "property_id": unit.id,
                "property_title": unit.title,
                "property_code": unit.property_code,
                "unit_number": unit.unit_number,
                "building_id": unit.parent_property_id,
                "building_title": unit.parent.title if unit.parent else None,
                "occupancy_status": occ_status,
                "status_reason": f"Part of whole-floor contract {whole_floor_contract.contract_number}" if whole_floor_contract else reason,
                "tenant_display_name": source_contract.tenant_display_name if source_contract else None,
                "rental_contract_id": contract.id if contract else None,
                "whole_floor_contract_id": whole_floor_contract.id if whole_floor_contract else None,
                "contract_end_date": source_contract.end_date if source_contract else None,
                "rent_amount": contract.rent_amount if contract else unit.rent_price,
            })
        return items, total

    # ---------------- POST /occupancy/recalculate ----------------
    def recalculate(self, building_id: Optional[int], actor_id: Optional[int]) -> dict:
        return self.scheduler.run_sweep(building_id, actor_id)

    # ---------------- Overrides & notice (supporting endpoints) ----------------
    def set_override(self, property_id: int, override_status: str, reason: Optional[str], expires_at: Optional[datetime], actor_id: Optional[int]):
        return self.events.set_override(property_id, override_status, reason, expires_at, actor_id)

    def clear_override(self, override_id: int, reason: Optional[str], actor_id: Optional[int]):
        return self.events.clear_override(override_id, reason, actor_id)

    def set_move_out_notice(self, contract_id: int, notice_date: date, actor_id: Optional[int]):
        return self.events.set_move_out_notice(contract_id, notice_date, actor_id)

    def get_unit_history(self, property_id: int, limit: int = 50):
        self.validator.validate_unit_exists(property_id)
        from app.repositories.occupancy_repository import OccupancyHistoryRepository
        return OccupancyHistoryRepository(self.db).list_for_unit(property_id, limit)
