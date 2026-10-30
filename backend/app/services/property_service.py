from typing import Optional
from fastapi import HTTPException, status, UploadFile
from sqlalchemy.orm import Session

from app.repositories.property_repository import (
    PropertyRepository, AmenityRepository, PropertyImageRepository, PropertyDocumentRepository, FloorRepository,
)
from app.repositories.owner_repository import OwnerRepository
from app.models.property import Property, PropertyType
from app.schemas.common import PaginationParams
from app.services.audit_service import AuditService
from app.services.file_storage_service import FileUploadService

ENTITY_TYPE = "property"


class PropertyService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = PropertyRepository(db)
        self.amenity_repo = AmenityRepository(db)
        self.image_repo = PropertyImageRepository(db)
        self.document_repo = PropertyDocumentRepository(db)
        self.floor_repo = FloorRepository(db)
        self.owner_repo = OwnerRepository(db)
        self.audit = AuditService(db)
        self.uploader = FileUploadService()

    def _attach_current_lease(self, property_: Property) -> Property:
        """Attaches computed fields as plain attributes so the Pydantic
        response schema (from_attributes) can pick them up without requiring
        extra reverse relationships on the model."""
        lease = self.repo.get_current_lease(property_.id)
        property_.current_lease_id = lease.id if lease else None
        property_.current_lease_contract_number = lease.contract_number if lease else None
        property_.current_lease_end_date = lease.end_date if lease else None

        floor = getattr(property_, "floor", None)
        property_.floor_label = (f"{floor.floor_name} ({floor.floor_number})" if floor and floor.floor_name else floor.floor_number) if floor else None

        parking = getattr(property_, "parking_space", None)
        property_.parking_space_code = parking.property_code if parking else None

        storage = getattr(property_, "storage_space", None)
        property_.storage_space_code = storage.property_code if storage else None

        return property_

    def _validate_unit_references(self, data: dict) -> None:
        """Validates floor_id belongs to a building, and parking/storage
        space IDs point to properties of the matching type."""
        if data.get("floor_id"):
            floor = self.floor_repo.get(data["floor_id"])
            if not floor:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid floor_id")

        if data.get("parking_space_id"):
            parking = self.repo.get(data["parking_space_id"])
            if not parking or parking.property_type != "parking":
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="parking_space_id must reference an existing property of type 'parking'")

        if data.get("storage_space_id"):
            storage = self.repo.get(data["storage_space_id"])
            if not storage or storage.property_type != "storage":
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="storage_space_id must reference an existing property of type 'storage'")

    # ---------------- CRUD ----------------
    def list_properties(self, params: PaginationParams, property_type, availability_status, owner_id, branch_id, city_id, parent_property_id, floor_id=None, include_archived: bool = False, top_level_only: bool = False):
        items, total = self.repo.list_properties(
            page=params.page, page_size=params.page_size, search=params.search,
            property_type=property_type, availability_status=availability_status,
            owner_id=owner_id, branch_id=branch_id, city_id=city_id, parent_property_id=parent_property_id,
            floor_id=floor_id, sort_by=params.sort_by, sort_dir=params.sort_dir or "desc",
            include_archived=include_archived, top_level_only=top_level_only,
        )
        items = [self._attach_current_lease(p) for p in items]
        return items, total

    def get_property(self, property_id: int) -> Property:
        prop = self.repo.get_detail(property_id)
        if not prop:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
        prop = self._attach_current_lease(prop)
        prop.summary = self.get_property_summary(prop) if prop.property_type in PropertyType.CONTAINER_TYPES else None
        return prop

    def create_property(self, data: dict, actor_id: Optional[int]) -> Property:
        owner = self.owner_repo.get(data["owner_id"])
        if not owner:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid owner_id")

        if data.get("parent_property_id"):
            parent = self.repo.get(data["parent_property_id"])
            if not parent:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid parent_property_id")

        self._validate_unit_references(data)

        amenity_ids = data.pop("amenity_ids", [])
        payload = dict(data)
        payload["property_code"] = self.repo.next_property_code()
        prop = self.repo.create(payload, actor_id=actor_id)
        if amenity_ids:
            prop.amenities = self.amenity_repo.get_by_ids(amenity_ids)

        self.audit.log_activity(ENTITY_TYPE, prop.id, "created", f"Property {prop.property_code} ({prop.title}) created", actor_id)
        self.audit.log_audit(ENTITY_TYPE, prop.id, "created", None, actor_id)
        self.db.commit()
        return self.get_property(prop.id)

    def get_or_create_floor_unit(self, floor_id: int, actor_id: Optional[int]) -> Property:
        """Get-or-create the single Property row (property_type=FLOOR)
        that represents "this floor, rented as one whole" — the backing
        mechanism for the "whole floor" contract option confirmed
        directly. Idempotent: calling this again for the same floor
        returns the same row rather than creating duplicates, the same
        way a unit only ever gets created once."""
        from app.models.property import Floor, PropertyType

        floor = self.db.get(Floor, floor_id)
        if not floor:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Floor not found")

        existing = self.db.query(Property).filter(
            Property.floor_id == floor_id, Property.property_type == PropertyType.FLOOR, Property.deleted_at.is_(None),
        ).first()
        if existing:
            return existing

        building = self.repo.get(floor.building_id)
        payload = {
            "owner_id": building.owner_id,
            "parent_property_id": building.id,
            "floor_id": floor.id,
            "property_type": PropertyType.FLOOR,
            "title": f"{building.title} — {floor.floor_name or f'Floor {floor.floor_number}'} (Whole Floor)",
            "country_id": building.country_id,
            "city_id": building.city_id,
            "address_line1": building.address_line1,
        }
        payload["property_code"] = self.repo.next_property_code()
        prop = self.repo.create(payload, actor_id=actor_id)
        self.audit.log_activity(ENTITY_TYPE, prop.id, "created", f"Whole-floor unit {prop.property_code} created for {floor.floor_name or floor.floor_number}", actor_id)
        self.db.commit()
        return prop

    def bulk_generate_units(self, building_id: int, data: dict, actor_id: Optional[int]) -> dict:
        """Generates floor_count floors (skipping any that already exist
        for this building, matched by floor_number — never duplicated)
        and units_per_floor units on each, in one call. Pure composition
        over FloorService.create() and this class's own create_property()
        — no new creation logic, just the loop a person would otherwise
        have to do by hand one property at a time. See
        docs/property-structure.md."""
        building = self.repo.get(building_id)
        if not building:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Building not found")
        if building.property_type not in FloorService.FLOOR_CAPABLE_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Bulk generation is only available for {FloorService.FLOOR_CAPABLE_TYPES}",
            )

        floor_service = FloorService(self.db)
        floor_count = data["floor_count"]
        starting_floor_number = data.get("starting_floor_number") or 1
        units_per_floor = data["units_per_floor"]
        unit_property_type = data["unit_property_type"]
        starting_unit_index = data.get("starting_unit_index") or 1
        numbering_style = data.get("numbering_style") or "floor_prefixed"
        floor_overrides = {fo["floor_number"]: fo["units_count"] for fo in (data.get("floor_overrides") or [])}
        title_prefix = data.get("title_prefix") or building.title
        owner_id = data.get("owner_id") or building.owner_id
        unit_defaults = {k: data[k] for k in ("bedrooms", "bathrooms", "area_sqm", "rent_price") if data.get(k) is not None}

        existing_floors = {f.floor_number: f for f in floor_service.list_for_building(building_id)}
        floors_created = 0
        created_units = []
        sequential_counter = starting_unit_index  # only advances across floors when numbering_style == "sequential"

        for i in range(floor_count):
            floor_number_value = starting_floor_number + i
            floor_number_str = str(floor_number_value)
            floor = existing_floors.get(floor_number_str)
            if not floor:
                floor = floor_service.create(building_id, {"floor_number": floor_number_str}, actor_id=actor_id)
                existing_floors[floor_number_str] = floor
                floors_created += 1

            # A floor listed in floor_overrides uses its own unit count
            # instead of the uniform units_per_floor — e.g. a ground
            # floor with fewer/more units than the rest of the building.
            this_floor_unit_count = floor_overrides.get(floor_number_value, units_per_floor)

            for j in range(this_floor_unit_count):
                if numbering_style == "sequential":
                    # Runs continuously across the whole building — Floor
                    # 1 -> 1, 2, 3 / Floor 2 -> 4, 5, 6 — rather than
                    # resetting per floor.
                    unit_number = str(sequential_counter)
                    sequential_counter += 1
                else:
                    unit_index = starting_unit_index + j
                    # e.g. floor 3, unit 1 -> "301" — matches the convention
                    # already visible on existing seeded units in this system.
                    unit_number = f"{floor_number_value}{unit_index:02d}"
                unit_payload = {
                    "property_type": unit_property_type,
                    "title": f"{title_prefix} — Floor {floor_number_str} — Unit {unit_number}",
                    "owner_id": owner_id,
                    "parent_property_id": building_id,
                    "floor_id": floor.id,
                    "unit_number": unit_number,
                    **unit_defaults,
                }
                created_units.append(self.create_property(unit_payload, actor_id=actor_id))

        return {
            "building_id": building_id,
            "floors_created": floors_created,
            "floors_reused": floor_count - floors_created,
            "units_created": len(created_units),
            "units": created_units,
        }

    def update_property(self, property_id: int, data: dict, actor_id: Optional[int]) -> Property:
        prop = self.repo.get(property_id)
        if not prop:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")

        amenity_ids = data.pop("amenity_ids", None)
        self._validate_unit_references(data)
        if data.get("parking_space_id") == prop.id or data.get("storage_space_id") == prop.id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A property cannot reference itself as its own parking or storage space")
        before = {k: getattr(prop, k) for k in data.keys()}
        self.repo.update(prop, data, actor_id=actor_id)
        after = {k: getattr(prop, k) for k in data.keys()}
        if amenity_ids is not None:
            prop.amenities = self.amenity_repo.get_by_ids(amenity_ids)

        changes = self.audit.diff(before, after)
        if changes:
            self.audit.log_activity(ENTITY_TYPE, prop.id, "updated", f"Property {prop.property_code} updated", actor_id)
            self.audit.log_audit(ENTITY_TYPE, prop.id, "updated", changes, actor_id)
        self.db.commit()
        return self.get_property(prop.id)

    def list_vacant_missing_price(self) -> list[dict]:
        """Backing list for the "Set Vacant Unit Prices" bulk screen —
        reuses OccupancyService.get_units() exactly as the Dashboard's
        Vacant Units Value card already does, filtered down to the ones
        with no rent_price at all (the ones the dashboard card can't
        count and flags with its "+N with no price" note)."""
        from app.business_workflows.occupancy.occupancy_service import OccupancyService
        items, _ = OccupancyService(self.db).get_units(None, "vacant", 1, 100000)
        return [u for u in items if not u.get("rent_amount")]

    def bulk_set_rent_prices(self, updates: list[dict], actor_id: Optional[int]) -> int:
        """updates: [{"property_id": int, "rent_price": Decimal}, ...].
        One commit at the end rather than per-row — this is a "fill in
        the blanks" bulk action a person does once, not a high-frequency
        write path, so a single query per row plus one shared commit is
        the right tradeoff over a more complex batched UPDATE."""
        updated = 0
        for row in updates:
            prop = self.repo.get(row["property_id"])
            if not prop:
                continue
            prop.rent_price = row["rent_price"]
            updated += 1
        if updated:
            self.audit.log_activity(ENTITY_TYPE, 0, "bulk_rent_price_set", f"{updated} vacant unit(s) had their rent price set in bulk", actor_id)
            self.db.commit()
        return updated

    def delete_property(self, property_id: int, actor_id: Optional[int]) -> None:
        prop = self.repo.get(property_id)
        if not prop:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
        # Same reasoning as the other delete guards added alongside this
        # one: a building/unit that still has child units, an active
        # Master Lease, or an active tenant contract shouldn't be able
        # to silently vanish while those things still point at it.
        unit_ids = self.repo.get_unit_ids(property_id)
        if unit_ids:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot delete: this property still has {len(unit_ids)} unit(s). Delete those first.",
            )
        from app.models.lease import LeaseAgreement, LeaseStatus
        from app.models.rental import RentalContract, RentalContractStatus
        active_lease = self.db.query(LeaseAgreement).filter(
            LeaseAgreement.property_id == property_id, LeaseAgreement.deleted_at.is_(None), LeaseAgreement.contract_status == LeaseStatus.ACTIVE,
        ).count()
        if active_lease > 0:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cannot delete: this property has an active Master Lease. Terminate it first.")
        active_contracts = self.db.query(RentalContract).filter(
            RentalContract.property_id == property_id, RentalContract.deleted_at.is_(None), RentalContract.contract_status == RentalContractStatus.ACTIVE,
        ).count()
        if active_contracts > 0:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Cannot delete: {active_contracts} active tenant contract(s) still reference this property. Terminate those first.")
        self.repo.soft_delete(prop, actor_id=actor_id)
        self.audit.log_activity(ENTITY_TYPE, prop.id, "deleted", f"Property {prop.property_code} deleted", actor_id)
        self.db.commit()

    def archive_property(self, property_id: int, actor_id: Optional[int]) -> Property:
        """Distinct from delete: stays a fully normal, visible-on-lookup
        record — just tagged out of the default list view. See
        BaseRepository.archive()."""
        prop = self.repo.get(property_id)
        if not prop:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
        self.repo.archive(prop, actor_id=actor_id)
        self.audit.log_activity(ENTITY_TYPE, prop.id, "archived", f"Property {prop.property_code} archived", actor_id)
        self.db.commit()
        return prop

    def unarchive_property(self, property_id: int, actor_id: Optional[int]) -> Property:
        prop = self.repo.get(property_id)
        if not prop:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
        self.repo.unarchive(prop, actor_id=actor_id)
        self.audit.log_activity(ENTITY_TYPE, prop.id, "unarchived", f"Property {prop.property_code} restored from archive", actor_id)
        self.db.commit()
        return prop

    def list_units(self, property_id: int) -> list[Property]:
        """Child properties (e.g. apartments/offices/shops within a building)."""
        self.get_property(property_id)
        stmt_items, _ = self.repo.list_properties(
            page=1, page_size=500, search=None, property_type=None, availability_status=None,
            owner_id=None, branch_id=None, city_id=None, parent_property_id=property_id,
            sort_by="title", sort_dir="asc",
        )
        return [self._attach_current_lease(p) for p in stmt_items]

    # ---------------- Dashboard ----------------
    def dashboard(self) -> dict:
        return self.repo.dashboard_counts()

    # ---------------- Images ----------------
    def upload_image(self, property_id: int, file: UploadFile, caption: Optional[str], is_cover: bool, actor_id: Optional[int]):
        self.get_property(property_id)
        meta = self.uploader.upload(file, "property_image", property_id)
        if not meta["mime_type"].startswith("image/"):
            self.uploader.delete(meta["file_path"])
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only image files are allowed here (use Documents for other file types)")
        meta.update({"property_id": property_id, "caption": caption, "is_cover": is_cover})
        if is_cover:
            self.image_repo.unset_other_covers(property_id)
        image = self.image_repo.create(meta, actor_id=actor_id)
        self.audit.log_activity(ENTITY_TYPE, property_id, "image_added", f"Image '{image.file_name}' uploaded", actor_id)
        self.db.commit()
        return image

    def update_image(self, property_id: int, image_id: int, data: dict, actor_id: Optional[int]):
        image = self.image_repo.get(image_id)
        if not image or image.property_id != property_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")
        if data.get("is_cover"):
            self.image_repo.unset_other_covers(property_id, exclude_id=image_id)
        self.image_repo.update(image, data, actor_id=actor_id)
        self.db.commit()
        return image

    def delete_image(self, property_id: int, image_id: int, actor_id: Optional[int]):
        image = self.image_repo.get(image_id)
        if not image or image.property_id != property_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")
        self.uploader.delete(image.file_path)
        self.image_repo.soft_delete(image, actor_id=actor_id)
        self.audit.log_activity(ENTITY_TYPE, property_id, "image_removed", f"Image '{image.file_name}' removed", actor_id)
        self.db.commit()

    # ---------------- Documents ----------------
    def upload_document(
        self, property_id: int, file: UploadFile, document_type: str, document_number: Optional[str],
        issue_date, expiry_date, description: Optional[str], actor_id: Optional[int],
    ):
        self.get_property(property_id)
        meta = self.uploader.upload(file, "property_document", property_id)
        meta.update({
            "property_id": property_id, "document_type": document_type, "document_number": document_number,
            "issue_date": issue_date, "expiry_date": expiry_date, "description": description,
        })
        doc = self.document_repo.create(meta, actor_id=actor_id)
        self.audit.log_activity(ENTITY_TYPE, property_id, "document_added", f"Document '{doc.file_name}' ({document_type}) uploaded", actor_id)
        self.db.commit()
        return doc

    def update_document(self, property_id: int, document_id: int, data: dict, actor_id: Optional[int]):
        doc = self.document_repo.get(document_id)
        if not doc or doc.property_id != property_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
        self.document_repo.update(doc, data, actor_id=actor_id)
        self.db.commit()
        return doc

    def delete_document(self, property_id: int, document_id: int, actor_id: Optional[int]):
        doc = self.document_repo.get(document_id)
        if not doc or doc.property_id != property_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
        self.uploader.delete(doc.file_path)
        self.document_repo.soft_delete(doc, actor_id=actor_id)
        self.audit.log_activity(ENTITY_TYPE, property_id, "document_removed", f"Document '{doc.file_name}' removed", actor_id)
        self.db.commit()

    # ---------------- Building Management ----------------
    # A Property with property_type="building" already IS the Building
    # entity (Phase 4/5) — these methods aggregate its existing children
    # (Units via parent_property_id, Floors) together with Rental
    # Contracts / Tenants / Maintenance Requests scoped to the building
    # and its units. No new tables; everything reuses Phases 5/7/9's own
    # repositories and list schemas.
    def _building_and_unit_ids(self, building_id: int) -> tuple[Property, list[int]]:
        building = self.repo.get(building_id)
        if not building:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Building not found")
        unit_ids = self.repo.get_unit_ids(building_id)
        return building, unit_ids

    def _aggregate_container(self, building_id: int) -> dict:
        """Shared computation behind both get_building_summary (existing
        endpoint, kept for backward compatibility) and get_property_summary
        (Phase 2.0's richer Property Details summary) — one place doing the
        actual counting so the two can never disagree."""
        from app.repositories.rental_repository import RentalContractRepository
        from app.repositories.maintenance_repository import MaintenanceRequestRepository
        from app.models.rental import RentalContractStatus

        building, unit_ids = self._building_and_unit_ids(building_id)
        all_ids = [building_id] + unit_ids
        availability = self.repo.unit_availability_counts(unit_ids)
        unit_types = self.repo.unit_type_counts(unit_ids)

        rental_repo = RentalContractRepository(self.db)
        maintenance_repo = MaintenanceRequestRepository(self.db)
        unit_count = len(unit_ids)
        occupied = availability["occupied"]
        return {
            "building": building,
            "floor_count": self.repo.floor_count(building_id),
            "unit_count": unit_count,
            "occupied_units": occupied,
            "vacant_units": availability["vacant"],
            "reserved_units": availability["reserved"],
            "under_maintenance_units": availability["under_maintenance"],
            "other_units": availability["other"],
            "residential_units": unit_types["residential"],
            "commercial_units": unit_types["commercial"],
            "occupancy_rate": round((occupied / unit_count * 100), 2) if unit_count else 0.0,
            "active_leases_count": rental_repo.count_by_property_ids_and_status(all_ids, RentalContractStatus.ACTIVE),
            "expired_leases_count": rental_repo.count_by_property_ids_and_status(all_ids, RentalContractStatus.EXPIRED),
            "contracts_expiring_soon": rental_repo.count_expiring_soon_by_property_ids(all_ids),
            "tenant_count": len(rental_repo.distinct_tenant_ids_by_property_ids(all_ids)),
            "open_maintenance_requests_count": maintenance_repo.count_open_by_property_ids(all_ids),
        }

    def get_building_summary(self, building_id: int) -> dict:
        agg = self._aggregate_container(building_id)
        return {
            "floor_count": agg["floor_count"],
            "unit_count": agg["unit_count"],
            "occupied_units": agg["occupied_units"],
            "vacant_units": agg["vacant_units"],
            "other_units": agg["other_units"],
            "residential_units": agg["residential_units"],
            "commercial_units": agg["commercial_units"],
            "occupancy_rate": agg["occupancy_rate"],
            "active_leases_count": agg["active_leases_count"],
            "expired_leases_count": agg["expired_leases_count"],
            "contracts_expiring_soon": agg["contracts_expiring_soon"],
            "tenant_count": agg["tenant_count"],
            "open_maintenance_requests_count": agg["open_maintenance_requests_count"],
        }

    def get_property_summary(self, prop: Property) -> dict:
        """Phase 2.0 "Property Summary" — embedded automatically into
        PropertyDetailOut for any container-type property (see
        get_property above). Financial figures reuse
        ReportsService.property_financial_dashboard's existing
        income/expense aggregation for this property's own transactions
        (see that method's docstring) rather than duplicating GL-query
        logic; note this counts revenue/expenses posted directly against
        the building/villa row itself, not re-summed from every child
        unit's own transactions, since those are already visible on each
        unit's own Property Details page."""
        from app.services.reports_service import ReportsService

        agg = self._aggregate_container(prop.id)
        financial = ReportsService(self.db).property_financial_dashboard(prop.id)["kpis"]
        return {
            "property_type": prop.property_type,
            "total_floors": agg["floor_count"],
            "total_units": agg["unit_count"],
            "occupied_units": agg["occupied_units"],
            "vacant_units": agg["vacant_units"],
            "reserved_units": agg["reserved_units"],
            "under_maintenance_units": agg["under_maintenance_units"],
            "residential_units": agg["residential_units"],
            "commercial_units": agg["commercial_units"],
            "occupancy_rate": agg["occupancy_rate"],
            "active_contracts": agg["active_leases_count"],
            "expired_contracts": agg["expired_leases_count"],
            "contracts_expiring_soon": agg["contracts_expiring_soon"],
            "monthly_revenue": financial["total_income_this_month"],
            "monthly_expenses": financial["total_expense_this_month"],
            "net_profit": financial["net_profit_this_month"],
            "last_updated": prop.updated_at.date() if getattr(prop, "updated_at", None) else None,
        }

    def get_building_leases(self, building_id: int, contract_status: Optional[str], params: PaginationParams):
        from app.repositories.rental_repository import RentalContractRepository
        _, unit_ids = self._building_and_unit_ids(building_id)
        all_ids = [building_id] + unit_ids
        items, total = RentalContractRepository(self.db).list_by_property_ids(all_ids, contract_status, params.page, params.page_size)
        for c in items:
            c.tenant_is_blacklisted = bool(c.tenant.is_blacklisted) if c.tenant else False
        return items, total

    def get_building_tenants(self, building_id: int):
        from app.repositories.rental_repository import RentalContractRepository
        from app.repositories.tenant_repository import TenantRepository
        _, unit_ids = self._building_and_unit_ids(building_id)
        all_ids = [building_id] + unit_ids
        tenant_ids = RentalContractRepository(self.db).distinct_tenant_ids_by_property_ids(all_ids)
        return TenantRepository(self.db).get_many(tenant_ids)

    def get_building_maintenance_requests(self, building_id: int, params: PaginationParams):
        from app.repositories.maintenance_repository import MaintenanceRequestRepository
        _, unit_ids = self._building_and_unit_ids(building_id)
        all_ids = [building_id] + unit_ids
        items, total = MaintenanceRequestRepository(self.db).list_by_property_ids(all_ids, params.page, params.page_size)
        return items, total


class FloorService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = FloorRepository(db)
        self.property_repo = PropertyRepository(db)
        self.audit = AuditService(db)

    FLOOR_CAPABLE_TYPES = [PropertyType.BUILDING, PropertyType.COMMERCIAL_BUILDING, PropertyType.COMMERCIAL_COMPLEX, PropertyType.MIXED_USE]

    def _get_building(self, building_id: int) -> Property:
        building = self.property_repo.get(building_id)
        if not building:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Building not found")
        if building.property_type not in self.FLOOR_CAPABLE_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Floors can only be added to a property of type {self.FLOOR_CAPABLE_TYPES}",
            )
        return building

    def list_for_building(self, building_id: int):
        self._get_building(building_id)
        floors = self.repo.list_for_building(building_id)
        for f in floors:
            f.unit_count = self.repo.unit_count(f.id)
        return floors

    def create(self, building_id: int, data: dict, actor_id: Optional[int]):
        self._get_building(building_id)
        data["building_id"] = building_id
        floor = self.repo.create(data, actor_id=actor_id)
        self.audit.log_activity("property", building_id, "floor_added", f"Floor '{floor.floor_number}' added", actor_id)
        self.db.commit()
        floor.unit_count = 0
        return floor

    def update(self, floor_id: int, data: dict, actor_id: Optional[int]):
        floor = self.repo.get(floor_id)
        if not floor:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Floor not found")
        self.repo.update(floor, data, actor_id=actor_id)
        self.db.commit()
        floor.unit_count = self.repo.unit_count(floor.id)
        return floor

    def delete(self, floor_id: int, actor_id: Optional[int]):
        floor = self.repo.get(floor_id)
        if not floor:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Floor not found")
        if self.repo.unit_count(floor_id) > 0:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cannot delete a floor that still has units assigned to it")
        self.repo.soft_delete(floor, actor_id=actor_id)
        self.audit.log_activity("property", floor.building_id, "floor_removed", f"Floor '{floor.floor_number}' removed", actor_id)
        self.db.commit()


class AmenityService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = AmenityRepository(db)
        self.audit = AuditService(db)

    def list(self, params: PaginationParams):
        return self.repo.list(
            page=params.page, page_size=params.page_size, search=params.search,
            search_fields=["name", "category"], sort_by=params.sort_by or "name", sort_dir=params.sort_dir,
        )

    def create(self, name: str, category: Optional[str], actor_id: Optional[int]):
        if self.repo.get_by_name(name):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An amenity with this name already exists")
        amenity = self.repo.create({"name": name, "category": category}, actor_id=actor_id)
        self.db.commit()
        return amenity

    def update(self, amenity_id: int, data: dict, actor_id: Optional[int]):
        amenity = self.repo.get(amenity_id)
        if not amenity:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Amenity not found")
        self.repo.update(amenity, data, actor_id=actor_id)
        self.db.commit()
        return amenity

    def delete(self, amenity_id: int, actor_id: Optional[int]):
        amenity = self.repo.get(amenity_id)
        if not amenity:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Amenity not found")
        self.repo.soft_delete(amenity, actor_id=actor_id)
        self.db.commit()
