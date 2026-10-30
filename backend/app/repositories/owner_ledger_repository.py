from datetime import date
from decimal import Decimal
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.orm import Session, selectinload
from app.repositories.base import BaseRepository
from app.models.owner_ledger import OwnerLedgerEntry, OwnerLedgerEntryStatus, OwnerLedgerTransactionType
from app.models.property import Property


def _display_load_options():
    return (
        selectinload(OwnerLedgerEntry.owner),
        selectinload(OwnerLedgerEntry.property_ref).selectinload(Property.parent),
    )


class OwnerLedgerRepository(BaseRepository[OwnerLedgerEntry]):
    def __init__(self, db: Session):
        super().__init__(OwnerLedgerEntry, db)

    def get_detail(self, entry_id: int) -> Optional[OwnerLedgerEntry]:
        stmt = (
            select(OwnerLedgerEntry)
            .options(*_display_load_options())
            .where(OwnerLedgerEntry.id == entry_id, OwnerLedgerEntry.deleted_at.is_(None))
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_last_entry(self, owner_id: int) -> Optional[OwnerLedgerEntry]:
        """The most recent entry for an owner — its `balance` IS the
        owner's current balance (see owner_balance_service.py)."""
        stmt = (
            select(OwnerLedgerEntry)
            .where(OwnerLedgerEntry.owner_id == owner_id, OwnerLedgerEntry.deleted_at.is_(None))
            .order_by(OwnerLedgerEntry.id.desc())
            .limit(1)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list_for_owner(
        self, owner_id: int, page: int, page_size: int, transaction_type: Optional[str],
        date_from: Optional[date], date_to: Optional[date], sort_dir: str,
    ) -> tuple[list[OwnerLedgerEntry], int]:
        base_stmt = select(OwnerLedgerEntry).where(
            OwnerLedgerEntry.owner_id == owner_id, OwnerLedgerEntry.deleted_at.is_(None),
        )
        if transaction_type:
            base_stmt = base_stmt.where(OwnerLedgerEntry.transaction_type == transaction_type)
        if date_from:
            base_stmt = base_stmt.where(OwnerLedgerEntry.transaction_date >= date_from)
        if date_to:
            base_stmt = base_stmt.where(OwnerLedgerEntry.transaction_date <= date_to)

        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total = self.db.execute(count_stmt).scalar_one()

        stmt = base_stmt.options(*_display_load_options())
        stmt = stmt.order_by(OwnerLedgerEntry.id.desc() if sort_dir == "desc" else OwnerLedgerEntry.id.asc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        items = list(self.db.execute(stmt).scalars().all())
        return items, total

    def list_all(
        self, page: int, page_size: int, owner_id: Optional[int], transaction_type: Optional[str],
        date_from: Optional[date], date_to: Optional[date],
    ) -> tuple[list[OwnerLedgerEntry], int]:
        base_stmt = select(OwnerLedgerEntry).where(OwnerLedgerEntry.deleted_at.is_(None))
        if owner_id:
            base_stmt = base_stmt.where(OwnerLedgerEntry.owner_id == owner_id)
        if transaction_type:
            base_stmt = base_stmt.where(OwnerLedgerEntry.transaction_type == transaction_type)
        if date_from:
            base_stmt = base_stmt.where(OwnerLedgerEntry.transaction_date >= date_from)
        if date_to:
            base_stmt = base_stmt.where(OwnerLedgerEntry.transaction_date <= date_to)

        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total = self.db.execute(count_stmt).scalar_one()

        stmt = base_stmt.options(*_display_load_options()).order_by(OwnerLedgerEntry.id.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        items = list(self.db.execute(stmt).scalars().all())
        return items, total

    def list_in_range(self, owner_id: int, date_from: date, date_to: date) -> list[OwnerLedgerEntry]:
        """Every entry in [date_from, date_to] for statement generation,
        oldest first."""
        stmt = (
            select(OwnerLedgerEntry)
            .where(
                OwnerLedgerEntry.owner_id == owner_id, OwnerLedgerEntry.deleted_at.is_(None),
                OwnerLedgerEntry.transaction_date >= date_from, OwnerLedgerEntry.transaction_date <= date_to,
            )
            .order_by(OwnerLedgerEntry.transaction_date.asc(), OwnerLedgerEntry.id.asc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def balance_before(self, owner_id: int, as_of: date) -> Decimal:
        """The owner's balance strictly before `as_of` — i.e. the
        opening balance for a statement period starting on `as_of`."""
        stmt = (
            select(OwnerLedgerEntry.balance)
            .where(
                OwnerLedgerEntry.owner_id == owner_id, OwnerLedgerEntry.deleted_at.is_(None),
                OwnerLedgerEntry.transaction_date < as_of,
            )
            .order_by(OwnerLedgerEntry.transaction_date.desc(), OwnerLedgerEntry.id.desc())
            .limit(1)
        )
        result = self.db.execute(stmt).scalar_one_or_none()
        return result if result is not None else Decimal("0")

    def sum_outstanding_recoverable(self, owner_id: int) -> Decimal:
        """Net not-yet-recovered amount: total RECOVERABLE_EXPENSE
        debits minus total RECOVERED_AMOUNT credits, for this owner,
        across active (non-reversed) entries."""
        expense_stmt = select(func.coalesce(func.sum(OwnerLedgerEntry.debit), 0)).where(
            OwnerLedgerEntry.owner_id == owner_id, OwnerLedgerEntry.deleted_at.is_(None),
            OwnerLedgerEntry.transaction_type == OwnerLedgerTransactionType.RECOVERABLE_EXPENSE,
            OwnerLedgerEntry.entry_status != OwnerLedgerEntryStatus.REVERSED,
        )
        recovered_stmt = select(func.coalesce(func.sum(OwnerLedgerEntry.credit), 0)).where(
            OwnerLedgerEntry.owner_id == owner_id, OwnerLedgerEntry.deleted_at.is_(None),
            OwnerLedgerEntry.transaction_type == OwnerLedgerTransactionType.RECOVERED_AMOUNT,
            OwnerLedgerEntry.entry_status != OwnerLedgerEntryStatus.REVERSED,
        )
        expenses = self.db.execute(expense_stmt).scalar_one() or Decimal("0")
        recovered = self.db.execute(recovered_stmt).scalar_one() or Decimal("0")
        return expenses - recovered

    def portfolio_recoverable_totals(self) -> dict:
        """Same computation as sum_outstanding_recoverable, without the
        owner_id filter — used by the Financial Engine dashboard
        (business_workflows/financial_engine/) for the portfolio-wide
        'Recoverable Expenses' / 'Recovered Amounts' figures."""
        expense_stmt = select(func.coalesce(func.sum(OwnerLedgerEntry.debit), 0)).where(
            OwnerLedgerEntry.deleted_at.is_(None), OwnerLedgerEntry.transaction_type == OwnerLedgerTransactionType.RECOVERABLE_EXPENSE,
            OwnerLedgerEntry.entry_status != OwnerLedgerEntryStatus.REVERSED,
        )
        recovered_stmt = select(func.coalesce(func.sum(OwnerLedgerEntry.credit), 0)).where(
            OwnerLedgerEntry.deleted_at.is_(None), OwnerLedgerEntry.transaction_type == OwnerLedgerTransactionType.RECOVERED_AMOUNT,
            OwnerLedgerEntry.entry_status != OwnerLedgerEntryStatus.REVERSED,
        )
        total_expenses = self.db.execute(expense_stmt).scalar_one() or Decimal("0")
        total_recovered = self.db.execute(recovered_stmt).scalar_one() or Decimal("0")
        return {"total_recoverable_expenses": total_expenses, "total_recovered_amounts": total_recovered, "outstanding": total_expenses - total_recovered}

    def sum_by_type_in_range(self, owner_id: int, transaction_type: str, date_from: date, date_to: date) -> dict:
        stmt = select(
            func.coalesce(func.sum(OwnerLedgerEntry.debit), 0), func.coalesce(func.sum(OwnerLedgerEntry.credit), 0),
        ).where(
            OwnerLedgerEntry.owner_id == owner_id, OwnerLedgerEntry.deleted_at.is_(None),
            OwnerLedgerEntry.transaction_type == transaction_type,
            OwnerLedgerEntry.transaction_date >= date_from, OwnerLedgerEntry.transaction_date <= date_to,
        )
        debit, credit = self.db.execute(stmt).one()
        return {"debit": debit or Decimal("0"), "credit": credit or Decimal("0")}
