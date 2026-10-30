from datetime import date
from decimal import Decimal
from typing import Optional
from sqlalchemy import select, func, or_, case
from sqlalchemy.orm import Session, selectinload
from app.models.accounting import (
    ChartOfAccount, CostCenter, VatRate, PostingRule, JournalEntry, JournalEntryLine,
    AccountType, EntryStatus,
)
from app.repositories.base import BaseRepository


class ChartOfAccountRepository(BaseRepository[ChartOfAccount]):
    def __init__(self, db: Session):
        super().__init__(ChartOfAccount, db)

    def get_by_code(self, account_code: str) -> Optional[ChartOfAccount]:
        stmt = select(ChartOfAccount).where(ChartOfAccount.account_code == account_code, ChartOfAccount.deleted_at.is_(None))
        return self.db.execute(stmt).scalar_one_or_none()

    def list_all(self, account_type: Optional[str] = None) -> list[ChartOfAccount]:
        stmt = select(ChartOfAccount).where(ChartOfAccount.deleted_at.is_(None))
        if account_type:
            stmt = stmt.where(ChartOfAccount.account_type == account_type)
        stmt = stmt.order_by(ChartOfAccount.account_code)
        return list(self.db.execute(stmt).scalars().all())

    def has_children(self, account_id: int) -> bool:
        stmt = select(func.count()).select_from(ChartOfAccount).where(
            ChartOfAccount.parent_account_id == account_id, ChartOfAccount.deleted_at.is_(None)
        )
        return self.db.execute(stmt).scalar_one() > 0

    def has_journal_lines(self, account_id: int) -> bool:
        stmt = select(func.count()).select_from(JournalEntryLine).where(
            JournalEntryLine.account_id == account_id, JournalEntryLine.deleted_at.is_(None)
        )
        return self.db.execute(stmt).scalar_one() > 0

    def account_balance(self, account_id: int, as_of_date: Optional[date] = None) -> Decimal:
        account = self.get(account_id)
        if not account:
            return Decimal("0")
        stmt = (
            select(
                func.coalesce(func.sum(JournalEntryLine.debit_amount), 0),
                func.coalesce(func.sum(JournalEntryLine.credit_amount), 0),
            )
            .select_from(JournalEntryLine)
            .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
            .where(
                JournalEntryLine.account_id == account_id,
                JournalEntryLine.deleted_at.is_(None),
                JournalEntry.entry_status == EntryStatus.POSTED,
            )
        )
        if as_of_date:
            stmt = stmt.where(JournalEntry.entry_date <= as_of_date)
        debit, credit = self.db.execute(stmt).one()
        return (debit - credit) if account.account_type in AccountType.DEBIT_NORMAL else (credit - debit)


class CostCenterRepository(BaseRepository[CostCenter]):
    def __init__(self, db: Session):
        super().__init__(CostCenter, db)

    def get_detail(self, cost_center_id: int) -> Optional[CostCenter]:
        stmt = select(CostCenter).options(selectinload(CostCenter.property_ref)).where(
            CostCenter.id == cost_center_id, CostCenter.deleted_at.is_(None)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list_active(self) -> list[CostCenter]:
        stmt = select(CostCenter).options(selectinload(CostCenter.property_ref)).where(CostCenter.deleted_at.is_(None)).order_by(CostCenter.name)
        return list(self.db.execute(stmt).scalars().all())


class VatRateRepository(BaseRepository[VatRate]):
    def __init__(self, db: Session):
        super().__init__(VatRate, db)

    def list_active(self) -> list[VatRate]:
        stmt = select(VatRate).options(selectinload(VatRate.gl_account)).where(VatRate.deleted_at.is_(None)).order_by(VatRate.code)
        return list(self.db.execute(stmt).scalars().all())


class PostingRuleRepository(BaseRepository[PostingRule]):
    def __init__(self, db: Session):
        super().__init__(PostingRule, db)

    def find_rule(self, transaction_type: str, category: Optional[str]) -> Optional[PostingRule]:
        # Prefer an exact (type, category) match, then fall back to (type, None).
        if category:
            stmt = select(PostingRule).where(
                PostingRule.transaction_type == transaction_type, PostingRule.category == category, PostingRule.deleted_at.is_(None)
            )
            rule = self.db.execute(stmt).scalar_one_or_none()
            if rule:
                return rule
        stmt = select(PostingRule).where(
            PostingRule.transaction_type == transaction_type, PostingRule.category.is_(None), PostingRule.deleted_at.is_(None)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def exists_for(self, transaction_type: str, category: Optional[str], exclude_id: Optional[int] = None) -> bool:
        stmt = select(func.count()).select_from(PostingRule).where(
            PostingRule.transaction_type == transaction_type, PostingRule.deleted_at.is_(None)
        )
        stmt = stmt.where(PostingRule.category == category) if category else stmt.where(PostingRule.category.is_(None))
        if exclude_id:
            stmt = stmt.where(PostingRule.id != exclude_id)
        return self.db.execute(stmt).scalar_one() > 0

    def list_all(self) -> list[PostingRule]:
        stmt = select(PostingRule).options(selectinload(PostingRule.offset_account)).where(PostingRule.deleted_at.is_(None)).order_by(PostingRule.transaction_type)
        return list(self.db.execute(stmt).scalars().all())


class JournalEntryRepository(BaseRepository[JournalEntry]):
    def __init__(self, db: Session):
        super().__init__(JournalEntry, db)

    def get_detail(self, entry_id: int) -> Optional[JournalEntry]:
        stmt = (
            select(JournalEntry)
            .options(selectinload(JournalEntry.lines).selectinload(JournalEntryLine.account), selectinload(JournalEntry.lines).selectinload(JournalEntryLine.property_ref))
            .where(JournalEntry.id == entry_id, JournalEntry.deleted_at.is_(None))
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def next_entry_number(self) -> str:
        count = self.db.execute(select(func.count()).select_from(JournalEntry)).scalar_one()
        return f"JE-{count + 1:06d}"

    def list_entries(
        self, page: int, page_size: int, search: Optional[str], entry_status: Optional[str],
        source_type: Optional[str], date_from: Optional[date], date_to: Optional[date], sort_dir: str,
    ) -> tuple[list[JournalEntry], int]:
        stmt = select(JournalEntry).options(selectinload(JournalEntry.lines)).where(JournalEntry.deleted_at.is_(None))
        if entry_status:
            stmt = stmt.where(JournalEntry.entry_status == entry_status)
        if source_type:
            stmt = stmt.where(JournalEntry.source_type == source_type)
        if date_from:
            stmt = stmt.where(JournalEntry.entry_date >= date_from)
        if date_to:
            stmt = stmt.where(JournalEntry.entry_date <= date_to)
        if search:
            like = f"%{search}%"
            stmt = stmt.where(or_(JournalEntry.entry_number.ilike(like), JournalEntry.description.ilike(like), JournalEntry.reference_number.ilike(like)))

        total = self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        column = JournalEntry.entry_date
        stmt = stmt.order_by(column.desc() if sort_dir == "desc" else column.asc(), JournalEntry.id.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        items = list(self.db.execute(stmt).scalars().all())
        return items, total


class AccountingReportRepository:
    """Read-only aggregation queries for Trial Balance, General Ledger,
    Balance Sheet, Income Statement, Cash Flow, and VAT — all computed
    live from posted JournalEntryLine rows, never stored."""

    def __init__(self, db: Session):
        self.db = db

    def trial_balance(self, as_of_date: date) -> list[dict]:
        stmt = (
            select(
                ChartOfAccount.id, ChartOfAccount.account_code, ChartOfAccount.account_name, ChartOfAccount.account_type,
                func.coalesce(func.sum(JournalEntryLine.debit_amount), 0).label("debit"),
                func.coalesce(func.sum(JournalEntryLine.credit_amount), 0).label("credit"),
            )
            .select_from(ChartOfAccount)
            .join(JournalEntryLine, JournalEntryLine.account_id == ChartOfAccount.id)
            .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
            .where(
                ChartOfAccount.deleted_at.is_(None), JournalEntryLine.deleted_at.is_(None),
                JournalEntry.entry_status == EntryStatus.POSTED, JournalEntry.entry_date <= as_of_date,
            )
            .group_by(ChartOfAccount.id, ChartOfAccount.account_code, ChartOfAccount.account_name, ChartOfAccount.account_type)
            .order_by(ChartOfAccount.account_code)
        )
        rows = self.db.execute(stmt).all()
        results = []
        for r in rows:
            is_debit_normal = r.account_type in AccountType.DEBIT_NORMAL
            net = (r.debit - r.credit) if is_debit_normal else (r.credit - r.debit)
            if net == 0:
                continue
            if is_debit_normal:
                debit_balance = net if net > 0 else Decimal("0")
                credit_balance = -net if net < 0 else Decimal("0")
            else:
                credit_balance = net if net > 0 else Decimal("0")
                debit_balance = -net if net < 0 else Decimal("0")
            results.append({
                "account_id": r.id, "account_code": r.account_code, "account_name": r.account_name,
                "account_type": r.account_type, "debit_balance": debit_balance, "credit_balance": credit_balance,
            })
        return results

    def property_balance_summary(self, property_id: int, as_of_date: date) -> list[dict]:
        """Like trial_balance, but scoped to a single Property's own
        JournalEntryLine.property_id — a subset of the full ledger, so
        (unlike trial_balance) it isn't expected to net to zero on its
        own; it shows what each account's balance looks like from this
        one property's point of view."""
        stmt = (
            select(
                ChartOfAccount.id, ChartOfAccount.account_code, ChartOfAccount.account_name, ChartOfAccount.account_type,
                func.coalesce(func.sum(JournalEntryLine.debit_amount), 0).label("debit"),
                func.coalesce(func.sum(JournalEntryLine.credit_amount), 0).label("credit"),
            )
            .select_from(ChartOfAccount)
            .join(JournalEntryLine, JournalEntryLine.account_id == ChartOfAccount.id)
            .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
            .where(
                ChartOfAccount.deleted_at.is_(None), JournalEntryLine.deleted_at.is_(None),
                JournalEntryLine.property_id == property_id,
                JournalEntry.entry_status == EntryStatus.POSTED, JournalEntry.entry_date <= as_of_date,
            )
            .group_by(ChartOfAccount.id, ChartOfAccount.account_code, ChartOfAccount.account_name, ChartOfAccount.account_type)
            .order_by(ChartOfAccount.account_code)
        )
        rows = self.db.execute(stmt).all()
        results = []
        for r in rows:
            is_debit_normal = r.account_type in AccountType.DEBIT_NORMAL
            net = (r.debit - r.credit) if is_debit_normal else (r.credit - r.debit)
            if net == 0:
                continue
            if is_debit_normal:
                debit_balance = net if net > 0 else Decimal("0")
                credit_balance = -net if net < 0 else Decimal("0")
            else:
                credit_balance = net if net > 0 else Decimal("0")
                debit_balance = -net if net < 0 else Decimal("0")
            results.append({
                "account_id": r.id, "account_code": r.account_code, "account_name": r.account_name,
                "account_type": r.account_type, "debit_balance": debit_balance, "credit_balance": credit_balance,
            })
        return results

    def property_ledger_lines(self, property_id: int, date_from: Optional[date], date_to: Optional[date]) -> list[JournalEntryLine]:
        """Every posted GL line tagged to this Property, across every
        account it touched — a per-property sub-ledger, chronological."""
        stmt = (
            select(JournalEntryLine)
            .options(selectinload(JournalEntryLine.journal_entry), selectinload(JournalEntryLine.account))
            .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
            .where(
                JournalEntryLine.property_id == property_id, JournalEntryLine.deleted_at.is_(None),
                JournalEntry.entry_status == EntryStatus.POSTED,
            )
        )
        if date_from:
            stmt = stmt.where(JournalEntry.entry_date >= date_from)
        if date_to:
            stmt = stmt.where(JournalEntry.entry_date <= date_to)
        stmt = stmt.order_by(JournalEntry.entry_date.asc(), JournalEntryLine.id.asc())
        return list(self.db.execute(stmt).scalars().all())

    def general_ledger_lines(self, account_id: int, date_from: Optional[date], date_to: Optional[date]) -> list[JournalEntryLine]:
        stmt = (
            select(JournalEntryLine)
            .options(selectinload(JournalEntryLine.journal_entry))
            .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
            .where(
                JournalEntryLine.account_id == account_id, JournalEntryLine.deleted_at.is_(None),
                JournalEntry.entry_status == EntryStatus.POSTED,
            )
        )
        if date_from:
            stmt = stmt.where(JournalEntry.entry_date >= date_from)
        if date_to:
            stmt = stmt.where(JournalEntry.entry_date <= date_to)
        stmt = stmt.order_by(JournalEntry.entry_date.asc(), JournalEntryLine.id.asc())
        return list(self.db.execute(stmt).scalars().all())

    def opening_balance(self, account_id: int, before_date: date, normal_debit: bool) -> Decimal:
        stmt = (
            select(
                func.coalesce(func.sum(JournalEntryLine.debit_amount), 0),
                func.coalesce(func.sum(JournalEntryLine.credit_amount), 0),
            )
            .select_from(JournalEntryLine)
            .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
            .where(
                JournalEntryLine.account_id == account_id, JournalEntryLine.deleted_at.is_(None),
                JournalEntry.entry_status == EntryStatus.POSTED, JournalEntry.entry_date < before_date,
            )
        )
        debit, credit = self.db.execute(stmt).one()
        return (debit - credit) if normal_debit else (credit - debit)

    def section_balances(self, account_type: str, date_from: Optional[date], date_to: date, property_id: Optional[int] = None) -> list[dict]:
        stmt = (
            select(
                ChartOfAccount.id, ChartOfAccount.account_code, ChartOfAccount.account_name,
                func.coalesce(func.sum(JournalEntryLine.debit_amount), 0).label("debit"),
                func.coalesce(func.sum(JournalEntryLine.credit_amount), 0).label("credit"),
            )
            .select_from(ChartOfAccount)
            .join(JournalEntryLine, JournalEntryLine.account_id == ChartOfAccount.id)
            .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
            .where(
                ChartOfAccount.deleted_at.is_(None), ChartOfAccount.account_type == account_type,
                JournalEntryLine.deleted_at.is_(None), JournalEntry.entry_status == EntryStatus.POSTED,
                JournalEntry.entry_date <= date_to,
            )
        )
        if property_id:
            stmt = stmt.where(JournalEntryLine.property_id == property_id)
        if date_from:
            stmt = stmt.where(JournalEntry.entry_date >= date_from)
        stmt = stmt.group_by(ChartOfAccount.id, ChartOfAccount.account_code, ChartOfAccount.account_name).order_by(ChartOfAccount.account_code)
        rows = self.db.execute(stmt).all()
        is_debit_normal = account_type in AccountType.DEBIT_NORMAL
        results = []
        for r in rows:
            net = r.debit - r.credit
            balance = net if is_debit_normal else -net
            if balance != 0:
                results.append({"account_id": r.id, "account_code": r.account_code, "account_name": r.account_name, "balance": balance})
        return results

    def cash_flow_by_transaction_type(self, date_from: date, date_to: date, property_id: Optional[int] = None) -> list[dict]:
        from app.models.financial import Transaction, TransactionType, TransactionStatus
        from app.models.rental import RentalContract
        if property_id:
            resolved_property_id = func.coalesce(Transaction.property_id, RentalContract.property_id)
            stmt = (
                select(
                    Transaction.transaction_type,
                    func.coalesce(func.sum(
                        case((Transaction.direction == "in", Transaction.amount), else_=-Transaction.amount)
                    ), 0).label("net_amount"),
                )
                .select_from(Transaction)
                .outerjoin(RentalContract, RentalContract.id == Transaction.rental_contract_id)
                .where(
                    Transaction.deleted_at.is_(None), Transaction.transaction_status == TransactionStatus.COMPLETED,
                    Transaction.transaction_date >= date_from, Transaction.transaction_date <= date_to,
                    Transaction.transaction_type.notin_([TransactionType.TRANSFER_IN, TransactionType.TRANSFER_OUT]),
                    resolved_property_id == property_id,
                )
                .group_by(Transaction.transaction_type)
                .order_by(Transaction.transaction_type)
            )
        else:
            stmt = (
                select(
                    Transaction.transaction_type,
                    func.coalesce(func.sum(
                        case((Transaction.direction == "in", Transaction.amount), else_=-Transaction.amount)
                    ), 0).label("net_amount"),
                )
                .where(
                    Transaction.deleted_at.is_(None), Transaction.transaction_status == TransactionStatus.COMPLETED,
                    Transaction.transaction_date >= date_from, Transaction.transaction_date <= date_to,
                    Transaction.transaction_type.notin_([TransactionType.TRANSFER_IN, TransactionType.TRANSFER_OUT]),
                )
                .group_by(Transaction.transaction_type)
                .order_by(Transaction.transaction_type)
            )
        rows = self.db.execute(stmt).all()
        return [{"transaction_type": r.transaction_type, "total_amount": r.net_amount} for r in rows]

    def cash_balance_as_of(self, as_of_date: date) -> Decimal:
        from app.models.financial import FinancialAccount, Transaction, TransactionStatus
        opening_stmt = select(func.coalesce(func.sum(FinancialAccount.opening_balance), 0)).where(FinancialAccount.deleted_at.is_(None))
        opening = self.db.execute(opening_stmt).scalar_one()
        inflow_stmt = select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            Transaction.direction == "in", Transaction.transaction_status == TransactionStatus.COMPLETED,
            Transaction.deleted_at.is_(None), Transaction.transaction_date <= as_of_date,
        )
        outflow_stmt = select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            Transaction.direction == "out", Transaction.transaction_status == TransactionStatus.COMPLETED,
            Transaction.deleted_at.is_(None), Transaction.transaction_date <= as_of_date,
        )
        inflow = self.db.execute(inflow_stmt).scalar_one()
        outflow = self.db.execute(outflow_stmt).scalar_one()
        return opening + inflow - outflow

    def vat_report(self, date_from: date, date_to: date) -> list[dict]:
        stmt = (
            select(
                VatRate.id, VatRate.code, VatRate.name, VatRate.rate_percentage,
                func.coalesce(func.sum(case((JournalEntryLine.credit_amount > 0, JournalEntryLine.vat_amount), else_=0)), 0).label("output_vat"),
                func.coalesce(func.sum(case((JournalEntryLine.debit_amount > 0, JournalEntryLine.vat_amount), else_=0)), 0).label("input_vat"),
            )
            .select_from(VatRate)
            .join(JournalEntryLine, JournalEntryLine.vat_rate_id == VatRate.id)
            .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
            .where(
                VatRate.deleted_at.is_(None), JournalEntryLine.deleted_at.is_(None),
                JournalEntry.entry_status == EntryStatus.POSTED,
                JournalEntry.entry_date >= date_from, JournalEntry.entry_date <= date_to,
            )
            .group_by(VatRate.id, VatRate.code, VatRate.name, VatRate.rate_percentage)
            .order_by(VatRate.code)
        )
        rows = self.db.execute(stmt).all()
        return [{
            "vat_rate_id": r.id, "vat_code": r.code, "vat_name": r.name, "rate_percentage": r.rate_percentage,
            "output_vat": r.output_vat, "input_vat": r.input_vat, "net_vat": r.output_vat - r.input_vat,
        } for r in rows]
