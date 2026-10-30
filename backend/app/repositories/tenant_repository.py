from typing import Optional
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session, selectinload
from app.models.tenant import Tenant, TenantContact, TenantEmergencyContact, TenantDocument, TenantRating
from app.repositories.base import BaseRepository


class TenantRepository(BaseRepository[Tenant]):
    def __init__(self, db: Session):
        super().__init__(Tenant, db)

    def get_many(self, tenant_ids: list[int]) -> list[Tenant]:
        if not tenant_ids:
            return []
        stmt = select(Tenant).where(Tenant.id.in_(tenant_ids), Tenant.deleted_at.is_(None))
        return list(self.db.execute(stmt).scalars().all())

    def get_detail(self, tenant_id: int) -> Optional[Tenant]:
        stmt = (
            select(Tenant)
            .options(
                selectinload(Tenant.contacts),
                selectinload(Tenant.emergency_contacts),
                selectinload(Tenant.documents),
                selectinload(Tenant.ratings),
            )
            .where(Tenant.id == tenant_id, Tenant.deleted_at.is_(None))
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def next_tenant_code(self) -> str:
        stmt = select(func.count()).select_from(Tenant)
        count = self.db.execute(stmt).scalar_one()
        return f"TNT-{count + 1:06d}"

    def average_rating(self, tenant_id: int) -> Optional[float]:
        stmt = select(func.avg(TenantRating.rating_value)).where(
            TenantRating.tenant_id == tenant_id, TenantRating.deleted_at.is_(None)
        )
        result = self.db.execute(stmt).scalar_one()
        return round(float(result), 2) if result is not None else None

    def rating_count(self, tenant_id: int) -> int:
        stmt = select(func.count()).select_from(TenantRating).where(
            TenantRating.tenant_id == tenant_id, TenantRating.deleted_at.is_(None)
        )
        return self.db.execute(stmt).scalar_one()

    def list_tenants(
        self, page: int, page_size: int, search: Optional[str], tenant_type: Optional[str],
        is_blacklisted: Optional[bool], branch_id: Optional[int], building_id: Optional[int],
        sort_by: Optional[str], sort_dir: str,
    ) -> tuple[list[Tenant], int]:
        stmt = select(Tenant).where(Tenant.deleted_at.is_(None))

        if tenant_type:
            stmt = stmt.where(Tenant.tenant_type == tenant_type)
        if is_blacklisted is not None:
            stmt = stmt.where(Tenant.is_blacklisted.is_(is_blacklisted))
        if branch_id:
            stmt = stmt.where(Tenant.branch_id == branch_id)
        if building_id:
            # Confirmed directly: as more buildings/tenants get added,
            # picking a building first to narrow the tenant list down is
            # faster than searching every tenant in the whole portfolio
            # by name. A tenant "belongs to" a building through their
            # (active) RentalContract's unit, which is itself either
            # directly under the building (parent_property_id) or IS
            # the building itself (the "whole building"/"whole floor"
            # contract options — property_id == building_id, or the
            # unit's own parent chain leads there).
            from app.models.rental import RentalContract, RentalContractStatus
            from app.models.property import Property as PropertyModel
            stmt = stmt.where(Tenant.id.in_(
                select(RentalContract.tenant_id)
                .join(PropertyModel, PropertyModel.id == RentalContract.property_id)
                .where(
                    RentalContract.deleted_at.is_(None), RentalContract.contract_status == RentalContractStatus.ACTIVE,
                    or_(PropertyModel.id == building_id, PropertyModel.parent_property_id == building_id),
                )
            ))
        if search:
            like = f"%{search}%"
            stmt = stmt.where(or_(
                Tenant.tenant_code.ilike(like),
                Tenant.first_name.ilike(like),
                Tenant.last_name.ilike(like),
                Tenant.company_name.ilike(like),
                Tenant.primary_email.ilike(like),
                Tenant.primary_phone.ilike(like),
                Tenant.national_id.ilike(like),
                Tenant.passport_number.ilike(like),
                Tenant.commercial_registration_number.ilike(like),
            ))

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = self.db.execute(count_stmt).scalar_one()

        sort_column_map = {
            "created_at": Tenant.created_at,
            "tenant_code": Tenant.tenant_code,
            "company_name": Tenant.company_name,
            "last_name": Tenant.last_name,
        }
        column = sort_column_map.get(sort_by, Tenant.created_at)
        stmt = stmt.order_by(column.desc() if sort_dir == "desc" else column.asc())

        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        items = list(self.db.execute(stmt).scalars().all())
        return items, total

    def dashboard_counts(self) -> dict:
        base = select(func.count()).select_from(Tenant).where(Tenant.deleted_at.is_(None))
        total = self.db.execute(base).scalar_one()

        individual = self.db.execute(base.where(Tenant.tenant_type == "individual")).scalar_one()
        company = self.db.execute(base.where(Tenant.tenant_type == "company")).scalar_one()
        active = self.db.execute(base.where(Tenant.status == "active")).scalar_one()
        blacklisted = self.db.execute(base.where(Tenant.is_blacklisted.is_(True))).scalar_one()

        avg_stmt = select(func.avg(TenantRating.rating_value)).where(TenantRating.deleted_at.is_(None))
        avg_result = self.db.execute(avg_stmt).scalar_one()

        recent_stmt = (
            select(Tenant)
            .where(Tenant.deleted_at.is_(None))
            .order_by(Tenant.created_at.desc())
            .limit(5)
        )
        recent = list(self.db.execute(recent_stmt).scalars().all())

        return {
            "total_tenants": total,
            "individual_tenants": individual,
            "company_tenants": company,
            "active_tenants": active,
            "blacklisted_tenants": blacklisted,
            "average_rating_overall": round(float(avg_result), 2) if avg_result is not None else None,
            "recently_added": recent,
        }


class TenantContactRepository(BaseRepository[TenantContact]):
    def __init__(self, db: Session):
        super().__init__(TenantContact, db)

    def unset_other_primaries(self, tenant_id: int, exclude_id: Optional[int] = None):
        stmt = select(TenantContact).where(TenantContact.tenant_id == tenant_id, TenantContact.is_primary.is_(True))
        if exclude_id:
            stmt = stmt.where(TenantContact.id != exclude_id)
        for c in self.db.execute(stmt).scalars().all():
            c.is_primary = False


class TenantEmergencyContactRepository(BaseRepository[TenantEmergencyContact]):
    def __init__(self, db: Session):
        super().__init__(TenantEmergencyContact, db)

    def unset_other_primaries(self, tenant_id: int, exclude_id: Optional[int] = None):
        stmt = select(TenantEmergencyContact).where(TenantEmergencyContact.tenant_id == tenant_id, TenantEmergencyContact.is_primary.is_(True))
        if exclude_id:
            stmt = stmt.where(TenantEmergencyContact.id != exclude_id)
        for c in self.db.execute(stmt).scalars().all():
            c.is_primary = False


class TenantDocumentRepository(BaseRepository[TenantDocument]):
    def __init__(self, db: Session):
        super().__init__(TenantDocument, db)


class TenantRatingRepository(BaseRepository[TenantRating]):
    def __init__(self, db: Session):
        super().__init__(TenantRating, db)

    def list_for_tenant(self, tenant_id: int) -> list[TenantRating]:
        stmt = select(TenantRating).where(
            TenantRating.tenant_id == tenant_id, TenantRating.deleted_at.is_(None)
        ).order_by(TenantRating.created_at.desc())
        return list(self.db.execute(stmt).scalars().all())
