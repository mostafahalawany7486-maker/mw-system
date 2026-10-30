from typing import Optional
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session, selectinload
from app.models.property import Property, Amenity, PropertyImage, PropertyDocument, Floor, PropertyType
from app.models.owner import Owner
from app.models.lease import LeaseAgreement, LeaseStatus
from app.models.base import RecordStatus
from app.repositories.base import BaseRepository


class PropertyRepository(BaseRepository[Property]):
    def __init__(self, db: Session):
        super().__init__(Property, db)

    def get_unit_ids(self, building_id: int) -> list[int]:
        """Real leasable units directly under a building — excludes the
        FLOOR type's virtual "whole floor" Property row (see
        PropertyService.get_or_create_floor_unit), which is also a child
        of the building but isn't a real unit; its own child units are
        already included here individually."""
        stmt = select(Property.id).where(
            Property.parent_property_id == building_id, Property.deleted_at.is_(None),
            Property.property_type != PropertyType.FLOOR,
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_many_with_parent(self, property_ids: list[int]) -> list[Property]:
        """Bulk fetch with `.parent` eager-loaded — used by the
        Occupancy Engine's unit listing (business_workflows/occupancy/)
        to show each unit's building title without an N+1 lazy-load per
        row."""
        if not property_ids:
            return []
        stmt = select(Property).options(selectinload(Property.parent)).where(Property.id.in_(property_ids), Property.deleted_at.is_(None))
        return list(self.db.execute(stmt).scalars().all())

    def floor_count(self, building_id: int) -> int:
        stmt = select(func.count()).select_from(Floor).where(Floor.building_id == building_id, Floor.deleted_at.is_(None))
        return self.db.execute(stmt).scalar_one()

    def unit_availability_counts(self, unit_ids: list[int]) -> dict:
        if not unit_ids:
            return {"occupied": 0, "vacant": 0, "reserved": 0, "under_maintenance": 0, "other": 0}
        stmt = select(Property.availability_status, func.count()).where(
            Property.id.in_(unit_ids), Property.deleted_at.is_(None)
        ).group_by(Property.availability_status)
        rows = dict(self.db.execute(stmt).all())
        occupied = rows.get("leased", 0)
        vacant = rows.get("available", 0)
        reserved = rows.get("reserved", 0)
        under_maintenance = rows.get("under_maintenance", 0)
        other = sum(rows.values()) - occupied - vacant - reserved - under_maintenance
        return {"occupied": occupied, "vacant": vacant, "reserved": reserved, "under_maintenance": under_maintenance, "other": other}

    def unit_type_counts(self, unit_ids: list[int]) -> dict:
        """Residential vs. commercial split of a building/villa's child
        units (Phase 2.0's "Residential Units" / "Commercial Units"),
        computed from property_type rather than stored, so it can never
        drift out of sync with the actual units."""
        if not unit_ids:
            return {"residential": 0, "commercial": 0}
        stmt = select(Property.property_type, func.count()).where(
            Property.id.in_(unit_ids), Property.deleted_at.is_(None)
        ).group_by(Property.property_type)
        rows = dict(self.db.execute(stmt).all())
        residential = sum(rows.get(t, 0) for t in PropertyType.RESIDENTIAL_UNIT_TYPES)
        commercial = sum(rows.get(t, 0) for t in PropertyType.COMMERCIAL_UNIT_TYPES)
        return {"residential": residential, "commercial": commercial}

    def get_detail(self, property_id: int) -> Optional[Property]:
        stmt = (
            select(Property)
            .options(
                selectinload(Property.owner),
                selectinload(Property.amenities),
                selectinload(Property.images),
                selectinload(Property.documents),
                selectinload(Property.floor),
                selectinload(Property.parking_space),
                selectinload(Property.storage_space),
            )
            .where(Property.id == property_id, Property.deleted_at.is_(None))
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_current_lease(self, property_id: int) -> Optional[LeaseAgreement]:
        stmt = (
            select(LeaseAgreement)
            .where(
                LeaseAgreement.property_id == property_id,
                LeaseAgreement.deleted_at.is_(None),
                LeaseAgreement.contract_status == LeaseStatus.ACTIVE,
            )
            .order_by(LeaseAgreement.start_date.desc())
            .limit(1)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def next_property_code(self) -> str:
        stmt = select(func.count()).select_from(Property)
        count = self.db.execute(stmt).scalar_one()
        return f"PRP-{count + 1:06d}"

    def list_properties(
        self, page: int, page_size: int, search: Optional[str], property_type: Optional[str],
        availability_status: Optional[str], owner_id: Optional[int], branch_id: Optional[int],
        city_id: Optional[int], parent_property_id: Optional[int], sort_by: Optional[str], sort_dir: str, floor_id: Optional[int] = None,
        include_archived: bool = False, top_level_only: bool = False,
    ) -> tuple[list[Property], int]:
        stmt = (
            select(Property)
            .options(selectinload(Property.owner), selectinload(Property.floor))
            .where(Property.deleted_at.is_(None))
        )
        # Archive extension: excluded by default, same as every other list
        # endpoint in this codebase already excludes deleted_at — this is
        # additive (no existing property has status='archived' yet, since
        # that value was previously only ever reached via soft_delete,
        # which already hides it via deleted_at regardless).
        if not include_archived:
            stmt = stmt.where(Property.status != RecordStatus.ARCHIVED)
        # Cascading Property Selector extension: "give me only
        # Buildings/Villas/standalone properties, not their child Units" —
        # distinct from the existing parent_property_id filter below,
        # which asks for children of ONE specific parent instead.
        if top_level_only:
            stmt = stmt.where(Property.parent_property_id.is_(None))

        if property_type:
            stmt = stmt.where(Property.property_type == property_type)
        if availability_status:
            stmt = stmt.where(Property.availability_status == availability_status)
        if owner_id:
            stmt = stmt.where(Property.owner_id == owner_id)
        if branch_id:
            stmt = stmt.where(Property.branch_id == branch_id)
        if city_id:
            stmt = stmt.where(Property.city_id == city_id)
        if parent_property_id is not None:
            stmt = stmt.where(Property.parent_property_id == parent_property_id)
        if floor_id is not None:
            stmt = stmt.where(Property.floor_id == floor_id)
        if search:
            like = f"%{search}%"
            stmt = stmt.join(Owner, Owner.id == Property.owner_id, isouter=True).where(or_(
                Property.property_code.ilike(like),
                Property.internal_code.ilike(like),
                Property.title.ilike(like),
                Property.address_line1.ilike(like),
                Property.unit_number.ilike(like),
                Owner.first_name.ilike(like),
                Owner.last_name.ilike(like),
                Owner.company_name.ilike(like),
            ))

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = self.db.execute(count_stmt).scalar_one()

        sort_column_map = {
            "created_at": Property.created_at,
            "property_code": Property.property_code,
            "title": Property.title,
        }
        column = sort_column_map.get(sort_by, Property.created_at)
        stmt = stmt.order_by(column.desc() if sort_dir == "desc" else column.asc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)

        items = list(self.db.execute(stmt).scalars().all())
        return items, total

    def dashboard_counts(self) -> dict:
        base = select(func.count()).select_from(Property).where(Property.deleted_at.is_(None))

        # FLOOR-type rows are excluded from the headline "Total Properties"
        # count for the same reason they're excluded from Total Units below:
        # they're an internal linking record for "this whole floor, leased
        # as one contract" (see PropertyService.get_or_create_floor_unit),
        # not a distinct property/unit a person added to the portfolio.
        # Without this, Total Properties silently didn't match
        # Buildings + Villas + ... + Total Units (e.g. 30 vs. 1 + 28 = 29)
        # whenever any floor had ever been rented out as a whole. `base`
        # itself stays unfiltered so by_type below still reports an
        # accurate (if unused today) count for PropertyType.FLOOR too.
        total = self.db.execute(base.where(Property.property_type != PropertyType.FLOOR)).scalar_one()

        by_type = {}
        for ptype in PropertyType.ALL:
            by_type[ptype] = self.db.execute(base.where(Property.property_type == ptype)).scalar_one()

        by_availability = {}
        for status_ in ["available", "leased", "reserved", "under_maintenance", "off_market"]:
            by_availability[status_] = self.db.execute(base.where(Property.availability_status == status_)).scalar_one()

        recent_stmt = (
            select(Property)
            .options(selectinload(Property.owner))
            .where(Property.deleted_at.is_(None))
            .order_by(Property.created_at.desc())
            .limit(5)
        )
        recent = list(self.db.execute(recent_stmt).scalars().all())

        # --- Phase 2.0 rolled-up widgets ---
        # "Total Units" = every leaf property, i.e. anything with a parent
        # (a child unit within a building/villa) OR a unit-like type that
        # can also stand alone (an apartment/shop/etc. not inside a
        # building). Container types themselves (building/villa/...) are
        # never counted as a "unit" — and neither is the FLOOR type: it's
        # a virtual Property row representing "this whole floor, leased
        # as one contract" (see RentalService._create_floor_wide_side_effects),
        # not a physical unit. Its own child units are already counted
        # individually, so including it too silently inflated Total
        # Units/Total Apartments by 1 for every floor-wide rental — bug
        # found via a mismatch between units actually added and the
        # dashboard count after renting a full floor.
        commercial_types = [PropertyType.COMMERCIAL_BUILDING, PropertyType.COMMERCIAL_COMPLEX] + PropertyType.COMMERCIAL_UNIT_TYPES
        non_unit_types = PropertyType.CONTAINER_TYPES + [PropertyType.FLOOR]
        total_units_stmt = base.where(Property.property_type.notin_(non_unit_types))
        total_units = self.db.execute(total_units_stmt).scalar_one()
        occupied_units = self.db.execute(total_units_stmt.where(Property.availability_status == "leased")).scalar_one()
        vacant_units = self.db.execute(total_units_stmt.where(Property.availability_status == "available")).scalar_one()

        return {
            "total_properties": total,
            "by_type": by_type,
            "by_availability": by_availability,
            "recently_added": recent,
            "total_buildings": by_type.get(PropertyType.BUILDING, 0),
            "total_villas": by_type.get(PropertyType.VILLA, 0),
            "total_commercial_properties": sum(by_type.get(t, 0) for t in commercial_types),
            "total_warehouses": by_type.get(PropertyType.WAREHOUSE, 0),
            "total_lands": by_type.get(PropertyType.LAND, 0),
            "total_units": total_units,
            "occupied_units": occupied_units,
            "vacant_units": vacant_units,
            "occupancy_rate": round((occupied_units / total_units * 100), 2) if total_units else 0.0,
        }


class AmenityRepository(BaseRepository[Amenity]):
    def __init__(self, db: Session):
        super().__init__(Amenity, db)

    def get_by_ids(self, ids: list[int]) -> list[Amenity]:
        if not ids:
            return []
        stmt = select(Amenity).where(Amenity.id.in_(ids))
        return list(self.db.execute(stmt).scalars().all())

    def get_by_name(self, name: str) -> Optional[Amenity]:
        stmt = select(Amenity).where(Amenity.name == name, Amenity.deleted_at.is_(None))
        return self.db.execute(stmt).scalar_one_or_none()


class PropertyImageRepository(BaseRepository[PropertyImage]):
    def __init__(self, db: Session):
        super().__init__(PropertyImage, db)

    def list_for_property(self, property_id: int) -> list[PropertyImage]:
        stmt = select(PropertyImage).where(
            PropertyImage.property_id == property_id, PropertyImage.deleted_at.is_(None)
        ).order_by(PropertyImage.sort_order.asc(), PropertyImage.created_at.asc())
        return list(self.db.execute(stmt).scalars().all())

    def unset_other_covers(self, property_id: int, exclude_id: Optional[int] = None):
        stmt = select(PropertyImage).where(PropertyImage.property_id == property_id, PropertyImage.is_cover.is_(True))
        if exclude_id:
            stmt = stmt.where(PropertyImage.id != exclude_id)
        for img in self.db.execute(stmt).scalars().all():
            img.is_cover = False


class FloorRepository(BaseRepository[Floor]):
    def __init__(self, db: Session):
        super().__init__(Floor, db)

    def list_for_building(self, building_id: int) -> list[Floor]:
        stmt = select(Floor).where(
            Floor.building_id == building_id, Floor.deleted_at.is_(None)
        ).order_by(Floor.floor_number.asc())
        return list(self.db.execute(stmt).scalars().all())

    def unit_count(self, floor_id: int) -> int:
        """Real units on a floor — excludes the FLOOR type's own virtual
        "whole floor" Property row (see PropertyService.get_or_create_floor_unit),
        which also carries this floor_id but isn't a real unit. Without
        this exclusion, a floor that had ever been rented out "as a
        whole" would show one extra unit that doesn't actually exist —
        same bug class as PropertyRepository.get_dashboard_stats /
        OccupancyStatisticsService._all_unit_ids."""
        stmt = select(func.count()).select_from(Property).where(
            Property.floor_id == floor_id, Property.deleted_at.is_(None),
            Property.property_type != PropertyType.FLOOR,
        )
        return self.db.execute(stmt).scalar_one()


class PropertyDocumentRepository(BaseRepository[PropertyDocument]):
    def __init__(self, db: Session):
        super().__init__(PropertyDocument, db)

    def list_for_property(self, property_id: int) -> list[PropertyDocument]:
        stmt = select(PropertyDocument).where(
            PropertyDocument.property_id == property_id, PropertyDocument.deleted_at.is_(None)
        ).order_by(PropertyDocument.created_at.desc())
        return list(self.db.execute(stmt).scalars().all())
