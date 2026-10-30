from datetime import date
from decimal import Decimal
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.orm import Session, selectinload
from app.repositories.base import BaseRepository
from app.models.payment import Payment, PaymentAllocation
from app.models.financial import Transaction, TransactionType, TransactionStatus
from app.models.property import Property


def _display_load_options():
    """Full attribute chains for Payment's display properties — same
    repeated-full-path pattern as RentCycleRepository (Phase 14) /
    RentVoucherRepository (Phase 15)."""
    return (
        selectinload(Payment.tenant),
        selectinload(Payment.property_ref).selectinload(Property.parent),
        selectinload(Payment.property_ref).selectinload(Property.owner),
        selectinload(Payment.allocations).selectinload(PaymentAllocation.invoice),
    )


class PaymentRepository(BaseRepository[Payment]):
    def __init__(self, db: Session):
        super().__init__(Payment, db)

    def get_detail(self, payment_id: int) -> Optional[Payment]:
        stmt = (
            select(Payment)
            .options(*_display_load_options())
            .where(Payment.id == payment_id, Payment.deleted_at.is_(None))
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_reference_number(self, reference_number: str) -> Optional[Payment]:
        stmt = select(Payment).where(Payment.reference_number == reference_number, Payment.deleted_at.is_(None))
        return self.db.execute(stmt).scalar_one_or_none()

    def next_payment_number(self) -> str:
        stmt = select(func.count()).select_from(Payment)
        count = self.db.execute(stmt).scalar_one()
        return f"PAY-{count + 1:06d}"

    def list_payments(
        self, page: int, page_size: int, tenant_id: Optional[int], payment_status: Optional[str],
        payment_method: Optional[str], date_from: Optional[date], date_to: Optional[date],
        sort_by: Optional[str], sort_dir: str, search: Optional[str] = None,
    ) -> tuple[list[Payment], int]:
        base_stmt = select(Payment).where(Payment.deleted_at.is_(None))
        if tenant_id:
            base_stmt = base_stmt.where(Payment.tenant_id == tenant_id)
        if payment_status:
            base_stmt = base_stmt.where(Payment.payment_status == payment_status)
        if payment_method:
            base_stmt = base_stmt.where(Payment.payment_method == payment_method)
        if date_from:
            base_stmt = base_stmt.where(Payment.payment_date >= date_from)
        if date_to:
            base_stmt = base_stmt.where(Payment.payment_date <= date_to)
        if search:
            like = f"%{search}%"
            base_stmt = base_stmt.where(
                (Payment.payment_number.ilike(like)) | (Payment.reference_number.ilike(like))
            )

        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total = self.db.execute(count_stmt).scalar_one()

        stmt = base_stmt.options(*_display_load_options())
        if sort_by and hasattr(Payment, sort_by):
            column = getattr(Payment, sort_by)
            stmt = stmt.order_by(column.desc() if sort_dir == "desc" else column.asc())
        else:
            stmt = stmt.order_by(Payment.id.desc())

        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        items = list(self.db.execute(stmt).scalars().all())
        return items, total

    # ---------------- Collection dashboard ----------------
    def sum_collected_between(self, date_from: date, date_to: date) -> Decimal:
        """Sum of successfully posted tenant-payment collections in a
        date range — reads the existing Transaction ledger directly
        (the single source of truth for what was actually collected),
        not the Payment.amount column (which can include not-yet-
        verified/cancelled amounts)."""
        stmt = select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            Transaction.transaction_type == TransactionType.TENANT_PAYMENT,
            Transaction.transaction_status == TransactionStatus.COMPLETED,
            Transaction.transaction_date >= date_from, Transaction.transaction_date <= date_to,
            Transaction.deleted_at.is_(None),
        )
        return self.db.execute(stmt).scalar_one() or Decimal("0")

    def count_by_status(self) -> dict:
        rows = self.db.execute(
            select(Payment.payment_status, func.count()).where(Payment.deleted_at.is_(None)).group_by(Payment.payment_status)
        ).all()
        return {status: count for status, count in rows}

    def sum_overdue_invoice_balance(self) -> Decimal:
        """Reads the existing Invoice.invoice_status == 'overdue' rows
        (set by FinancialService.maintenance_sweep's existing
        mark_overdue_sweep — unchanged) and sums their outstanding
        balance. Read-only; does not compute or assign overdue status
        itself, so there is exactly one place that decides what
        'overdue' means."""
        from app.models.financial import Invoice, InvoiceStatus
        stmt = select(func.coalesce(func.sum(Invoice.amount - Invoice.amount_paid), 0)).where(
            Invoice.invoice_status == InvoiceStatus.OVERDUE, Invoice.deleted_at.is_(None),
        )
        return self.db.execute(stmt).scalar_one() or Decimal("0")


class PaymentAllocationRepository(BaseRepository[PaymentAllocation]):
    def __init__(self, db: Session):
        super().__init__(PaymentAllocation, db)

    def list_for_payment(self, payment_id: int) -> list[PaymentAllocation]:
        stmt = (
            select(PaymentAllocation)
            .options(selectinload(PaymentAllocation.invoice))
            .where(PaymentAllocation.payment_id == payment_id, PaymentAllocation.deleted_at.is_(None))
        )
        return list(self.db.execute(stmt).scalars().all())
