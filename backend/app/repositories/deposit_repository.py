from decimal import Decimal
from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.repositories.base import BaseRepository
from app.models.financial_engine import DepositLedgerEntry


class DepositLedgerRepository(BaseRepository[DepositLedgerEntry]):
    def __init__(self, db: Session):
        super().__init__(DepositLedgerEntry, db)

    def list_for_contract(self, contract_type: str, contract_id: int) -> list[DepositLedgerEntry]:
        stmt = (
            select(DepositLedgerEntry)
            .where(DepositLedgerEntry.contract_type == contract_type, DepositLedgerEntry.contract_id == contract_id, DepositLedgerEntry.deleted_at.is_(None))
            .order_by(DepositLedgerEntry.id.asc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_last_entry(self, contract_type: str, contract_id: int) -> Optional[DepositLedgerEntry]:
        stmt = (
            select(DepositLedgerEntry)
            .where(DepositLedgerEntry.contract_type == contract_type, DepositLedgerEntry.contract_id == contract_id, DepositLedgerEntry.deleted_at.is_(None))
            .order_by(DepositLedgerEntry.id.desc())
            .limit(1)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def has_any_entry(self, contract_type: str, contract_id: int) -> bool:
        return self.get_last_entry(contract_type, contract_id) is not None

    def total_held(self) -> Decimal:
        """Sum of the *current remaining* balance across every deposit
        that has ever had an entry — i.e. the latest balance_after per
        (contract_type, contract_id), not the original received amount,
        so a partially-refunded/deducted deposit is only counted for
        what's actually still held. Used by the Financial Engine
        dashboard's 'Security Deposits' figure."""
        from sqlalchemy import func as sa_func
        latest_ids_stmt = (
            select(sa_func.max(DepositLedgerEntry.id))
            .where(DepositLedgerEntry.deleted_at.is_(None))
            .group_by(DepositLedgerEntry.contract_type, DepositLedgerEntry.contract_id)
        )
        latest_ids = [row[0] for row in self.db.execute(latest_ids_stmt).all()]
        if not latest_ids:
            return Decimal("0")
        stmt = select(sa_func.coalesce(sa_func.sum(DepositLedgerEntry.balance_after), 0)).where(DepositLedgerEntry.id.in_(latest_ids))
        return self.db.execute(stmt).scalar_one() or Decimal("0")
