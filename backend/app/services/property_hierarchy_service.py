"""
Property Hierarchy Tree — read-only view over the existing structure
(Owner -> Property/Building -> Floor -> Unit -> active RentalContract/
Tenant). No new tables, no new relationships — this composes entirely
from repository methods that already exist for other features
(bulk_generate_units, the Occupancy Engine's bulk active-contract
lookup, Floor listing), the same "reuse, don't duplicate" rule the
rest of this codebase already follows.

Purely additive and read-only: nothing here writes anything, so it
cannot affect existing data or behavior no matter how it's used.
"""
from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.property import Property
from app.models.tenant import Tenant
from app.repositories.owner_repository import OwnerRepository
from app.repositories.property_repository import PropertyRepository
from app.repositories.occupancy_repository import OccupancyDataRepository
from app.services.property_service import FloorService

UNIT_TYPE_LABELS = {
    "apartment": "Apartment", "office": "Office", "shop": "Shop", "commercial_unit": "Commercial Unit",
    "parking": "Parking", "storage": "Storage",
}


class PropertyHierarchyService:
    def __init__(self, db: Session):
        self.db = db
        self.owner_repo = OwnerRepository(db)
        self.property_repo = PropertyRepository(db)
        self.occupancy_data = OccupancyDataRepository(db)
        self.floor_service = FloorService(db)

    def get_owner_tree(self, owner_id: int) -> dict:
        owner = self.owner_repo.get(owner_id)
        if not owner:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Owner not found")

        top_level_stmt = select(Property).where(
            Property.owner_id == owner_id, Property.parent_property_id.is_(None), Property.deleted_at.is_(None),
        ).order_by(Property.title)
        top_level_properties = list(self.db.execute(top_level_stmt).scalars().all())

        return {
            "owner": {"id": owner.id, "owner_code": owner.owner_code, "display_name": owner.display_name},
            "properties": [self._build_property_node(p) for p in top_level_properties],
        }

    def _build_property_node(self, prop: Property) -> dict:
        node = {
            "id": prop.id, "title": prop.title, "property_code": prop.property_code,
            "property_type": prop.property_type, "floors": [], "active_contract": None,
        }

        unit_ids = self.property_repo.get_unit_ids(prop.id)
        if unit_ids:
            # Has child units (a building-type container) — group them by floor.
            floors = self.floor_service.list_for_building(prop.id)
            units = self.property_repo.get_many_with_parent(unit_ids)
            active_contracts = self.occupancy_data.get_active_contracts_for_units(unit_ids)
            tenant_names = self._bulk_tenant_names([c.tenant_id for c in active_contracts.values()])

            units_by_floor: dict[Optional[int], list[Property]] = {}
            for u in units:
                units_by_floor.setdefault(u.floor_id, []).append(u)

            for floor in floors:
                floor_units = sorted(units_by_floor.pop(floor.id, []), key=lambda u: u.unit_number or "")
                node["floors"].append({
                    "id": floor.id, "floor_number": floor.floor_number, "floor_name": floor.floor_name,
                    "units": [self._build_unit_node(u, active_contracts.get(u.id), tenant_names) for u in floor_units],
                })

            # Units with no floor assigned yet (floor_id is nullable) — still
            # shown, grouped under a synthetic "Unassigned Floor" bucket
            # rather than silently dropped.
            leftover = units_by_floor.pop(None, [])
            if leftover:
                node["floors"].append({
                    "id": None, "floor_number": None, "floor_name": "Unassigned",
                    "units": [self._build_unit_node(u, active_contracts.get(u.id), tenant_names) for u in sorted(leftover, key=lambda u: u.unit_number or "")],
                })
        else:
            # No child units — this property (villa, standalone land, etc.)
            # is itself the leasable thing; look up its own active contract.
            contract = self.occupancy_data.get_active_contract(prop.id)
            if contract:
                tenant_names = self._bulk_tenant_names([contract.tenant_id])
                node["active_contract"] = self._contract_summary(contract, tenant_names)

        return node

    def _build_unit_node(self, unit: Property, contract, tenant_names: dict) -> dict:
        return {
            "id": unit.id, "unit_number": unit.unit_number,
            "unit_type": UNIT_TYPE_LABELS.get(unit.property_type, unit.property_type),
            "availability_status": unit.availability_status,
            "active_contract": self._contract_summary(contract, tenant_names) if contract else None,
        }

    def _contract_summary(self, contract, tenant_names: dict) -> dict:
        return {
            "id": contract.id, "contract_number": contract.contract_number,
            "tenant_id": contract.tenant_id, "tenant_name": tenant_names.get(contract.tenant_id, f"Tenant #{contract.tenant_id}"),
            "rent_amount": str(contract.rent_amount), "end_date": contract.end_date.isoformat(),
        }

    def _bulk_tenant_names(self, tenant_ids: list[int]) -> dict:
        ids = [i for i in set(tenant_ids) if i]
        if not ids:
            return {}
        rows = self.db.execute(select(Tenant).where(Tenant.id.in_(ids))).scalars().all()
        return {t.id: t.display_name for t in rows}
