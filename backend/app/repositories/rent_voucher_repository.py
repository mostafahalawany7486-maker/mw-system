from datetime import date
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.orm import Session, selectinload
from app.repositories.base import BaseRepository
from app.models.rent_voucher import RentVoucher
from app.models.financial import Transaction
from app.models.property import Property


def _display_load_options():
    """Full attribute chains needed by RentVoucher's display properties
    (tenant_name, building_name, unit_number, property_address,
    payment_method_label_*) — same repeated-full-path pattern as
    RentCycleRepository (Phase 14)."""
    return (
        selectinload(RentVoucher.transaction).selectinload(Transaction.tenant),
        selectinload(RentVoucher.transaction).selectinload(Transaction.property_ref).selectinload(Property.parent),
    )


class RentVoucherRepository(BaseRepository[RentVoucher]):
    def __init__(self, db: Session):
        super().__init__(RentVoucher, db)

    def get_detail(self, voucher_id: int) -> Optional[RentVoucher]:
        stmt = (
            select(RentVoucher)
            .options(*_display_load_options())
            .where(RentVoucher.id == voucher_id, RentVoucher.deleted_at.is_(None))
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_barcode(self, barcode_value: str) -> Optional[RentVoucher]:
        stmt = (
            select(RentVoucher)
            .options(*_display_load_options())
            .where(RentVoucher.barcode_value == barcode_value, RentVoucher.deleted_at.is_(None))
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_transaction_and_copy(self, transaction_id: int, copy_type: str) -> Optional[RentVoucher]:
        stmt = select(RentVoucher).where(
            RentVoucher.transaction_id == transaction_id, RentVoucher.copy_type == copy_type,
            RentVoucher.deleted_at.is_(None),
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list_by_ids(self, voucher_ids: list[int]) -> list[RentVoucher]:
        stmt = (
            select(RentVoucher)
            .options(*_display_load_options())
            .where(RentVoucher.id.in_(voucher_ids), RentVoucher.deleted_at.is_(None))
        )
        # Preserve caller-requested order (e.g. "voucher 1, 2, 3, 4" print
        # sequencing) rather than whatever order the DB happens to return.
        rows = {v.id: v for v in self.db.execute(stmt).scalars().all()}
        return [rows[i] for i in voucher_ids if i in rows]

    def next_voucher_number(self) -> str:
        stmt = select(func.count()).select_from(RentVoucher)
        count = self.db.execute(stmt).scalar_one()
        return f"RV-{count + 1:06d}"

    def list_vouchers(
        self, page: int, page_size: int, rental_month: Optional[date], copy_type: Optional[str],
        transaction_id: Optional[int], sort_by: Optional[str], sort_dir: str,
    ) -> tuple[list[RentVoucher], int]:
        base_stmt = select(RentVoucher).where(RentVoucher.deleted_at.is_(None))
        if rental_month:
            base_stmt = base_stmt.where(RentVoucher.rental_month == rental_month)
        if copy_type:
            base_stmt = base_stmt.where(RentVoucher.copy_type == copy_type)
        if transaction_id:
            base_stmt = base_stmt.where(RentVoucher.transaction_id == transaction_id)

        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total = self.db.execute(count_stmt).scalar_one()

        stmt = base_stmt.options(*_display_load_options())
        if sort_by and hasattr(RentVoucher, sort_by):
            column = getattr(RentVoucher, sort_by)
            stmt = stmt.order_by(column.desc() if sort_dir == "desc" else column.asc())
        else:
            stmt = stmt.order_by(RentVoucher.id.desc())

        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        items = list(self.db.execute(stmt).scalars().all())
        return items, total
