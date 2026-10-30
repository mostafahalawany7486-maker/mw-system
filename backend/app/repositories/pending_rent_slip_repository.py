from datetime import date
from typing import Optional
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session, selectinload
from app.models.pending_rent_slip import PendingRentSlip, PendingRentSlipStatus
from app.repositories.base import BaseRepository


def _display_load_options():
    return [selectinload(PendingRentSlip.tenant), selectinload(PendingRentSlip.property_ref)]


class PendingRentSlipRepository(BaseRepository[PendingRentSlip]):
    def __init__(self, db: Session):
        super().__init__(PendingRentSlip, db)

    def next_slip_number(self) -> str:
        count = self.db.execute(select(func.count()).select_from(PendingRentSlip)).scalar_one()
        return f"PRS-{count + 1:06d}"

    def get_by_barcode(self, barcode_value: str) -> Optional[PendingRentSlip]:
        stmt = select(PendingRentSlip).options(*_display_load_options()).where(
            PendingRentSlip.barcode_value == barcode_value, PendingRentSlip.deleted_at.is_(None)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_tenant_property_month_copy(self, tenant_id: int, property_id: int, rental_month: date, copy_type: str) -> Optional[PendingRentSlip]:
        stmt = select(PendingRentSlip).where(
            PendingRentSlip.tenant_id == tenant_id, PendingRentSlip.property_id == property_id,
            PendingRentSlip.rental_month == rental_month, PendingRentSlip.copy_type == copy_type,
            PendingRentSlip.deleted_at.is_(None),
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_detail(self, slip_id: int) -> Optional[PendingRentSlip]:
        stmt = select(PendingRentSlip).options(*_display_load_options()).where(
            PendingRentSlip.id == slip_id, PendingRentSlip.deleted_at.is_(None)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list_by_ids(self, slip_ids: list[int]) -> list[PendingRentSlip]:
        stmt = select(PendingRentSlip).options(*_display_load_options()).where(
            PendingRentSlip.id.in_(slip_ids), PendingRentSlip.deleted_at.is_(None)
        )
        rows = {s.id: s for s in self.db.execute(stmt).scalars().all()}
        return [rows[i] for i in slip_ids if i in rows]

    def list_slips(
        self, page: int, page_size: int, search: Optional[str], rental_month: Optional[date],
        slip_status: Optional[str], property_id: Optional[int], building_id: Optional[int],
    ) -> tuple[list[PendingRentSlip], int]:
        from app.models.property import Property
        from app.models.tenant import Tenant

        stmt = select(PendingRentSlip).options(*_display_load_options()).where(PendingRentSlip.deleted_at.is_(None))
        if rental_month:
            stmt = stmt.where(PendingRentSlip.rental_month == rental_month)
        if slip_status:
            stmt = stmt.where(PendingRentSlip.slip_status == slip_status)
        if property_id:
            stmt = stmt.where(PendingRentSlip.property_id == property_id)
        if building_id:
            unit_ids_subq = select(Property.id).where(Property.parent_property_id == building_id)
            stmt = stmt.where(or_(PendingRentSlip.property_id == building_id, PendingRentSlip.property_id.in_(unit_ids_subq)))
        if search:
            like = f"%{search}%"
            stmt = (
                stmt.join(Tenant, Tenant.id == PendingRentSlip.tenant_id, isouter=True)
                .where(or_(PendingRentSlip.slip_number.ilike(like), Tenant.first_name.ilike(like), Tenant.last_name.ilike(like), Tenant.company_name.ilike(like)))
            )

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = self.db.execute(count_stmt).scalar_one()

        stmt = stmt.order_by(PendingRentSlip.id.desc()).offset((page - 1) * page_size).limit(page_size)
        items = list(self.db.execute(stmt).scalars().all())
        return items, total

    def dashboard_counts(self) -> dict:
        base = select(func.count()).select_from(PendingRentSlip).where(PendingRentSlip.deleted_at.is_(None))
        total = self.db.execute(base).scalar_one()

        def count_status(s):
            return self.db.execute(base.where(PendingRentSlip.slip_status == s)).scalar_one()

        return {
            "total_slips": total,
            "pending_count": count_status(PendingRentSlipStatus.PENDING),
            "collected_count": count_status(PendingRentSlipStatus.COLLECTED),
            "cancelled_count": count_status(PendingRentSlipStatus.CANCELLED),
        }
