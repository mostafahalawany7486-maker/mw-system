"""
occupancy_validator.py

Every business rule the spec's VALIDATIONS section asks for, plus this
package's exceptions — same "rules + exceptions together, separate from
orchestration" split as owner_ledger_validator.py.
"""
from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repositories.property_repository import PropertyRepository
from app.repositories.occupancy_repository import OccupancyOverrideRepository, OccupancyDataRepository
from app.models.occupancy import OccupancyStatus


class OccupancyError(HTTPException):
    """Base class for every Occupancy Engine exception."""


class UnitNotFoundError(OccupancyError):
    def __init__(self, property_id: int):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unit {property_id} not found")


class BuildingNotFoundError(OccupancyError):
    def __init__(self, building_id: int):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=f"Building {building_id} not found")


class ReservationConflictError(OccupancyError):
    def __init__(self, property_id: int, current_status: str):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Unit {property_id} cannot be reserved — it is currently {current_status}",
        )


class MaintenanceConflictError(OccupancyError):
    def __init__(self, property_id: int):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Unit {property_id} has an open maintenance request — resolve it before applying this override",
        )


class DuplicateOccupancyStateError(OccupancyError):
    def __init__(self, property_id: int, override_status: str):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Unit {property_id} already has an active '{override_status}' override — clear it first or let it expire",
        )


class OverrideNotFoundError(OccupancyError):
    def __init__(self, override_id: int):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=f"Occupancy override {override_id} not found")


class OverrideAlreadyClearedError(OccupancyError):
    def __init__(self, override_id: int):
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=f"Occupancy override {override_id} was already cleared")


class MultipleActiveLeasesError(OccupancyError):
    def __init__(self, property_id: int):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Unit {property_id} already has another active rental contract — a unit can only have one active lease at a time",
        )


class OccupancyValidator:
    def __init__(self, db: Session):
        self.db = db
        self.property_repo = PropertyRepository(db)
        self.override_repo = OccupancyOverrideRepository(db)
        self.data_repo = OccupancyDataRepository(db)

    def validate_unit_exists(self, property_id: int):
        unit = self.property_repo.get(property_id)
        if not unit:
            raise UnitNotFoundError(property_id)
        return unit

    def validate_building_exists(self, building_id: int):
        building = self.property_repo.get(building_id)
        if not building:
            raise BuildingNotFoundError(building_id)
        return building

    def validate_can_set_override(self, property_id: int, override_status: str, computed_status: str):
        """Spec: 'Prevent Reservation conflict, Maintenance conflict,
        Duplicate occupancy state.'"""
        # Duplicate occupancy state — an active override for this exact
        # status already exists.
        existing = self.override_repo.get_active_for_unit(property_id)
        if existing and existing.override_status == override_status:
            raise DuplicateOccupancyStateError(property_id, override_status)

        # Reservation conflict — can't reserve a unit that's actually
        # occupied (or already under notice) right now.
        if override_status == OccupancyStatus.RESERVED and computed_status in (OccupancyStatus.OCCUPIED, OccupancyStatus.NOTICE_PERIOD):
            raise ReservationConflictError(property_id, computed_status)

        # Maintenance conflict — an open MaintenanceRequest already
        # governs this unit's status; an override would silently mask
        # it rather than resolve it, so require closing the request
        # first before applying most overrides.
        if override_status in (OccupancyStatus.RESERVED, OccupancyStatus.CLEANING, OccupancyStatus.INSPECTION) and self.data_repo.has_open_maintenance(property_id):
            raise MaintenanceConflictError(property_id)

    def validate_can_clear_override(self, override) -> None:
        if override.cleared_at is not None:
            raise OverrideAlreadyClearedError(override.id)

    def validate_no_other_active_lease(self, property_id: int, exclude_contract_id: Optional[int] = None):
        """Spec: 'Prevent multiple active leases on same unit.' Reused
        by RentalService.activate_contract (see that file's own call
        site) as well as this module's own endpoints — a single source
        of truth for the rule instead of two implementations that could
        drift apart."""
        count = self.data_repo.count_other_active_contracts(property_id, exclude_contract_id)
        if count > 0:
            raise MultipleActiveLeasesError(property_id)
