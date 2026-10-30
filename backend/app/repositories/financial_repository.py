from datetime import date
from decimal import Decimal
from typing import Optional
from sqlalchemy import select, func, or_, case
from sqlalchemy.orm import Session, selectinload
from app.models.financial import FinancialAccount, Transaction, TransactionType, TransactionStatus, Receipt, Invoice, InvoiceStatus
from app.models.tenant import Tenant
from app.models.owner import Owner
from app.models.rental import RentalContract, RentalPaymentInstallment, RentalInstallmentStatus
from app.models.lease import LeaseAgreement, LeasePaymentInstallment, InstallmentStatus
from app.repositories.base import BaseRepository


class FinancialAccountRepository(BaseRepository[FinancialAccount]):
    def __init__(self, db: Session):
        super().__init__(FinancialAccount, db)

    def next_account_code(self) -> str:
        count = self.db.execute(select(func.count()).select_from(FinancialAccount)).scalar_one()
        return f"ACC-{count + 1:06d}"

    def current_balance(self, account_id: int) -> Decimal:
        account = self.get(account_id)
        if not account:
            return Decimal("0")
        inflow_stmt = select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            Transaction.account_id == account_id, Transaction.direction == "in",
            Transaction.transaction_status == TransactionStatus.COMPLETED, Transaction.deleted_at.is_(None),
        )
        outflow_stmt = select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            Transaction.account_id == account_id, Transaction.direction == "out",
            Transaction.transaction_status == TransactionStatus.COMPLETED, Transaction.deleted_at.is_(None),
        )
        inflow = self.db.execute(inflow_stmt).scalar_one()
        outflow = self.db.execute(outflow_stmt).scalar_one()
        return account.opening_balance + inflow - outflow

    def list_active(self) -> list[FinancialAccount]:
        stmt = select(FinancialAccount).where(FinancialAccount.deleted_at.is_(None)).order_by(FinancialAccount.name)
        return list(self.db.execute(stmt).scalars().all())


class TransactionRepository(BaseRepository[Transaction]):
    def __init__(self, db: Session):
        super().__init__(Transaction, db)

    def get_by_reference_number(self, reference_number: str) -> Optional[Transaction]:
        """Used by the Financial Engine's duplicate-transaction check
        (business_workflows/financial_engine/financial_validator.py) —
        mirrors PaymentRepository.get_by_reference_number's exact
        pattern (Phase 16), one query added for the one table that
        didn't already have it."""
        stmt = select(Transaction).where(Transaction.reference_number == reference_number, Transaction.deleted_at.is_(None))
        return self.db.execute(stmt).scalar_one_or_none()

    def get_detail(self, transaction_id: int) -> Optional[Transaction]:
        stmt = (
            select(Transaction)
            .options(selectinload(Transaction.account), selectinload(Transaction.tenant), selectinload(Transaction.owner), selectinload(Transaction.receipt), selectinload(Transaction.property_ref))
            .where(Transaction.id == transaction_id, Transaction.deleted_at.is_(None))
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_rental_installment(self, installment_id: int) -> Optional[Transaction]:
        """Backs the Rental Receipt's Bank Name field — a receipt has no
        payment_method field of its own (payment_status stays whatever
        it was; printing never changes it), and payment_method/
        reference_number are already synced onto the installment itself
        by create_transaction() above, so the receipt reads those two
        directly off the installment. bank_name, however, lives on
        FinancialAccount (not Transaction — Transaction has no bank_name
        column), so this is the one lookup still needed: find the
        Transaction this installment's payment created, to reach its
        linked account.bank_name. Returns None if not yet paid — the
        receipt's payment section is correctly blank in that case."""
        stmt = select(Transaction).options(selectinload(Transaction.account)).where(
            Transaction.rental_installment_id == installment_id, Transaction.deleted_at.is_(None),
        ).order_by(Transaction.created_at.desc())
        return self.db.execute(stmt).scalars().first()

    def next_transaction_number(self) -> str:
        count = self.db.execute(select(func.count()).select_from(Transaction)).scalar_one()
        return f"TXN-{count + 1:06d}"

    def list_transactions(
        self, page: int, page_size: int, search: Optional[str], transaction_type: Optional[str],
        account_id: Optional[int], tenant_id: Optional[int], owner_id: Optional[int],
        date_from: Optional[date], date_to: Optional[date], sort_dir: str, property_id: Optional[int] = None,
        property_ids: Optional[list[int]] = None,
    ) -> tuple[list[Transaction], int]:
        stmt = (
            select(Transaction)
            .options(selectinload(Transaction.account), selectinload(Transaction.tenant), selectinload(Transaction.owner), selectinload(Transaction.receipt), selectinload(Transaction.property_ref))
            .where(Transaction.deleted_at.is_(None))
        )
        if transaction_type:
            stmt = stmt.where(Transaction.transaction_type == transaction_type)
        if account_id:
            stmt = stmt.where(Transaction.account_id == account_id)
        if tenant_id:
            stmt = stmt.where(Transaction.tenant_id == tenant_id)
        if owner_id:
            stmt = stmt.where(Transaction.owner_id == owner_id)
        if property_id:
            stmt = stmt.where(Transaction.property_id == property_id)
        if property_ids:
            # Building-scoped filter (see the router's building_id param)
            # — every transaction for the building itself plus every one
            # of its units, same [building_id] + unit_ids shape already
            # used by OccupancyStatisticsService/BalanceService.
            stmt = stmt.where(Transaction.property_id.in_(property_ids))
        if date_from:
            stmt = stmt.where(Transaction.transaction_date >= date_from)
        if date_to:
            stmt = stmt.where(Transaction.transaction_date <= date_to)
        if search:
            like = f"%{search}%"
            stmt = (
                stmt.join(Tenant, Tenant.id == Transaction.tenant_id, isouter=True)
                .join(Owner, Owner.id == Transaction.owner_id, isouter=True)
                .where(or_(
                    Transaction.transaction_number.ilike(like),
                    Transaction.reference_number.ilike(like),
                    Transaction.description.ilike(like),
                    Tenant.first_name.ilike(like), Tenant.last_name.ilike(like), Tenant.company_name.ilike(like),
                    Owner.first_name.ilike(like), Owner.last_name.ilike(like), Owner.company_name.ilike(like),
                ))
            )

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = self.db.execute(count_stmt).scalar_one()

        column = Transaction.transaction_date
        stmt = stmt.order_by(column.desc() if sort_dir == "desc" else column.asc(), Transaction.id.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        items = list(self.db.execute(stmt).scalars().all())
        return items, total

    def monthly_totals(self, year: int, month: int) -> tuple[Decimal, Decimal]:
        income_stmt = select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            Transaction.transaction_type.in_([TransactionType.TENANT_PAYMENT, TransactionType.INCOME]),
            Transaction.transaction_status == TransactionStatus.COMPLETED,
            Transaction.deleted_at.is_(None),
            func.extract("year", Transaction.transaction_date) == year,
            func.extract("month", Transaction.transaction_date) == month,
        )
        expense_stmt = select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            Transaction.transaction_type.in_([TransactionType.OWNER_PAYMENT, TransactionType.EXPENSE]),
            Transaction.transaction_status == TransactionStatus.COMPLETED,
            Transaction.deleted_at.is_(None),
            func.extract("year", Transaction.transaction_date) == year,
            func.extract("month", Transaction.transaction_date) == month,
        )
        income = self.db.execute(income_stmt).scalar_one()
        expense = self.db.execute(expense_stmt).scalar_one()
        return income, expense


class ReceiptRepository(BaseRepository[Receipt]):
    def __init__(self, db: Session):
        super().__init__(Receipt, db)

    def next_receipt_number(self) -> str:
        count = self.db.execute(select(func.count()).select_from(Receipt)).scalar_one()
        return f"RCP-{count + 1:06d}"

    def get_by_transaction(self, transaction_id: int) -> Optional[Receipt]:
        stmt = select(Receipt).where(Receipt.transaction_id == transaction_id, Receipt.deleted_at.is_(None))
        return self.db.execute(stmt).scalar_one_or_none()

    def get_detail(self, receipt_id: int) -> Optional[Receipt]:
        stmt = (
            select(Receipt)
            .options(selectinload(Receipt.transaction).selectinload(Transaction.account),
                      selectinload(Receipt.transaction).selectinload(Transaction.tenant),
                      selectinload(Receipt.transaction).selectinload(Transaction.owner))
            .where(Receipt.id == receipt_id, Receipt.deleted_at.is_(None))
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list_all(self, page: int, page_size: int) -> tuple[list[Receipt], int]:
        stmt = (
            select(Receipt)
            .options(selectinload(Receipt.transaction).selectinload(Transaction.account),
                      selectinload(Receipt.transaction).selectinload(Transaction.tenant),
                      selectinload(Receipt.transaction).selectinload(Transaction.owner))
            .where(Receipt.deleted_at.is_(None))
            .order_by(Receipt.issued_date.desc())
        )
        total = self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        items = list(self.db.execute(stmt).scalars().all())
        return items, total


class InvoiceRepository(BaseRepository[Invoice]):
    def __init__(self, db: Session):
        super().__init__(Invoice, db)

    def next_invoice_number(self) -> str:
        count = self.db.execute(select(func.count()).select_from(Invoice)).scalar_one()
        return f"INV-{count + 1:06d}"

    def get_detail(self, invoice_id: int) -> Optional[Invoice]:
        stmt = select(Invoice).options(selectinload(Invoice.tenant)).where(Invoice.id == invoice_id, Invoice.deleted_at.is_(None))
        return self.db.execute(stmt).scalar_one_or_none()

    def list_invoices(self, page: int, page_size: int, search: Optional[str], invoice_status: Optional[str], tenant_id: Optional[int]) -> tuple[list[Invoice], int]:
        stmt = select(Invoice).options(selectinload(Invoice.tenant)).where(Invoice.deleted_at.is_(None))
        if invoice_status:
            stmt = stmt.where(Invoice.invoice_status == invoice_status)
        if tenant_id:
            stmt = stmt.where(Invoice.tenant_id == tenant_id)
        if search:
            like = f"%{search}%"
            stmt = stmt.join(Tenant, Tenant.id == Invoice.tenant_id, isouter=True).where(or_(
                Invoice.invoice_number.ilike(like), Tenant.first_name.ilike(like), Tenant.last_name.ilike(like), Tenant.company_name.ilike(like),
            ))
        total = self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        stmt = stmt.order_by(Invoice.due_date.asc()).offset((page - 1) * page_size).limit(page_size)
        items = list(self.db.execute(stmt).scalars().all())
        return items, total

    def mark_overdue_sweep(self) -> int:
        stmt = select(Invoice).where(
            Invoice.deleted_at.is_(None), Invoice.invoice_status.in_([InvoiceStatus.SENT, InvoiceStatus.PARTIALLY_PAID]), Invoice.due_date < date.today(),
        )
        invoices = list(self.db.execute(stmt).scalars().all())
        for inv in invoices:
            inv.invoice_status = InvoiceStatus.OVERDUE
        return len(invoices)

    # ---------------- Rent Billing Engine ----------------
    def exists_for_period(self, rental_contract_id: int, billing_period_start: date) -> bool:
        """Duplicate-check for bulk generation: never generate two
        invoices for the same contract covering the same billing period,
        no matter how many times a generation run is triggered."""
        stmt = select(func.count()).select_from(Invoice).where(
            Invoice.deleted_at.is_(None), Invoice.rental_contract_id == rental_contract_id,
            Invoice.billing_period_start == billing_period_start, Invoice.invoice_status != InvoiceStatus.VOID,
        )
        return self.db.execute(stmt).scalar_one() > 0

    def get_by_qr_token(self, qr_token: str) -> Optional[Invoice]:
        stmt = select(Invoice).options(selectinload(Invoice.tenant), selectinload(Invoice.property_ref)).where(Invoice.qr_token == qr_token, Invoice.deleted_at.is_(None))
        return self.db.execute(stmt).scalar_one_or_none()

    def get_many_for_print(self, invoice_ids: list[int]) -> list[Invoice]:
        stmt = (
            select(Invoice)
            .options(selectinload(Invoice.tenant), selectinload(Invoice.property_ref))
            .where(Invoice.id.in_(invoice_ids), Invoice.deleted_at.is_(None))
        )
        return list(self.db.execute(stmt).scalars().all())

    def search(
        self, page: int, page_size: int, invoice_number: Optional[str], tenant_id: Optional[int], property_id: Optional[int],
        owner_id: Optional[int], rental_contract_id: Optional[int], phone: Optional[str], civil_id: Optional[str],
        invoice_status: Optional[str], date_from: Optional[date], date_to: Optional[date],
    ) -> tuple[list[Invoice], int]:
        from app.models.property import Property

        stmt = (
            select(Invoice)
            .options(selectinload(Invoice.tenant), selectinload(Invoice.property_ref))
            .where(Invoice.deleted_at.is_(None))
        )
        if invoice_number:
            stmt = stmt.where(Invoice.invoice_number.ilike(f"%{invoice_number}%"))
        if tenant_id:
            stmt = stmt.where(Invoice.tenant_id == tenant_id)
        if property_id:
            stmt = stmt.where(Invoice.property_id == property_id)
        if rental_contract_id:
            stmt = stmt.where(Invoice.rental_contract_id == rental_contract_id)
        if invoice_status:
            stmt = stmt.where(Invoice.invoice_status == invoice_status)
        if date_from:
            stmt = stmt.where(Invoice.issue_date >= date_from)
        if date_to:
            stmt = stmt.where(Invoice.issue_date <= date_to)
        if owner_id:
            stmt = stmt.join(Property, Property.id == Invoice.property_id).where(Property.owner_id == owner_id)
        if civil_id:
            stmt = stmt.join(Tenant, Tenant.id == Invoice.tenant_id).where(Tenant.national_id.ilike(f"%{civil_id}%"))
        if phone:
            stmt = stmt.join(Tenant, Tenant.id == Invoice.tenant_id, isouter=(civil_id is None)).where(
                or_(Tenant.primary_phone.ilike(f"%{phone}%"), Tenant.secondary_phone.ilike(f"%{phone}%"))
            )

        total = self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        stmt = stmt.order_by(Invoice.issue_date.desc()).offset((page - 1) * page_size).limit(page_size)
        items = list(self.db.execute(stmt).scalars().all())
        return items, total


class OutstandingBalanceRepository:
    def __init__(self, db: Session):
        self.db = db

    def tenant_outstanding(self) -> list[dict]:
        stmt = (
            select(
                Tenant.id, Tenant.first_name, Tenant.last_name, Tenant.company_name, Tenant.tenant_type,
                func.coalesce(func.sum(
                    RentalPaymentInstallment.amount - RentalPaymentInstallment.discount_amount
                    + RentalPaymentInstallment.tax_amount + RentalPaymentInstallment.late_fee_amount
                ), 0).label("outstanding"),
                func.sum(case((RentalPaymentInstallment.payment_status == RentalInstallmentStatus.OVERDUE, 1), else_=0)).label("overdue_count"),
                func.sum(case((RentalPaymentInstallment.payment_status == RentalInstallmentStatus.PENDING, 1), else_=0)).label("pending_count"),
            )
            .join(RentalContract, RentalContract.tenant_id == Tenant.id)
            .join(RentalPaymentInstallment, RentalPaymentInstallment.contract_id == RentalContract.id)
            .where(
                RentalPaymentInstallment.payment_status.in_([RentalInstallmentStatus.PENDING, RentalInstallmentStatus.OVERDUE]),
                RentalPaymentInstallment.due_date <= date.today(),
                RentalPaymentInstallment.deleted_at.is_(None),
                Tenant.deleted_at.is_(None),
            )
            .group_by(Tenant.id, Tenant.first_name, Tenant.last_name, Tenant.company_name, Tenant.tenant_type)
            .having(func.coalesce(func.sum(
                RentalPaymentInstallment.amount - RentalPaymentInstallment.discount_amount
                + RentalPaymentInstallment.tax_amount + RentalPaymentInstallment.late_fee_amount
            ), 0) > 0)
        )
        rows = self.db.execute(stmt).all()
        results = []
        for r in rows:
            display_name = r.company_name if r.tenant_type == "company" else f"{r.first_name or ''} {r.last_name or ''}".strip()
            results.append({
                "id": r.id, "display_name": display_name or f"Tenant #{r.id}",
                "outstanding_amount": r.outstanding, "overdue_count": r.overdue_count, "pending_count": r.pending_count,
            })
        return results

    def owner_outstanding(self) -> list[dict]:
        stmt = (
            select(
                Owner.id, Owner.first_name, Owner.last_name, Owner.company_name, Owner.owner_type,
                func.coalesce(func.sum(LeasePaymentInstallment.amount), 0).label("outstanding"),
                func.sum(case((LeasePaymentInstallment.payment_status == InstallmentStatus.OVERDUE, 1), else_=0)).label("overdue_count"),
                func.sum(case((LeasePaymentInstallment.payment_status == InstallmentStatus.PENDING, 1), else_=0)).label("pending_count"),
            )
            .join(LeaseAgreement, LeaseAgreement.owner_id == Owner.id)
            .join(LeasePaymentInstallment, LeasePaymentInstallment.lease_id == LeaseAgreement.id)
            .where(
                LeasePaymentInstallment.payment_status.in_([InstallmentStatus.PENDING, InstallmentStatus.OVERDUE]),
                LeasePaymentInstallment.due_date <= date.today(),
                LeasePaymentInstallment.deleted_at.is_(None),
                Owner.deleted_at.is_(None),
            )
            .group_by(Owner.id, Owner.first_name, Owner.last_name, Owner.company_name, Owner.owner_type)
            .having(func.coalesce(func.sum(LeasePaymentInstallment.amount), 0) > 0)
        )
        rows = self.db.execute(stmt).all()
        results = []
        for r in rows:
            display_name = r.company_name if r.owner_type == "company" else f"{r.first_name or ''} {r.last_name or ''}".strip()
            results.append({
                "id": r.id, "display_name": display_name or f"Owner #{r.id}",
                "outstanding_amount": r.outstanding, "overdue_count": r.overdue_count, "pending_count": r.pending_count,
            })
        return results
