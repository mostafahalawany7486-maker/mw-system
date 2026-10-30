"""
balance_service.py

The core of the Financial Engine's design decision (see
docs/financial-engine.md's "Conflicts found" section): there is no
`CompanyLedger`/`OwnerLedger`/`TenantLedger`/`BuildingLedger`/
`PropertyLedger`/`UnitLedger` table anywhere. Six *views*, computed
live, over the tables that already are the source of truth:

  - Company Ledger    -> FinancialAccount balances (Phase 8, unchanged)
  - Owner Ledger       -> OwnerBalanceService (Phase 17, reused directly
                          — this module doesn't re-implement it)
  - Tenant Ledger      -> Transaction + the existing outstanding-balance
                          query, scoped by tenant_id
  - Building Ledger    -> Transaction, scoped by [building_id] + its unit ids
                          (same aggregation shape PropertyService/
                          OccupancyStatisticsService already use)
  - Property Ledger    -> Transaction, scoped by one property_id
  - Unit Ledger        -> identical query to Property Ledger; "unit" and
                          "property" are the same table in this codebase
                          (a unit *is* a Property row — Phase 4/5 design),
                          kept as a separate method only because the
                          spec names them separately, not because the
                          underlying query differs at all.

"Balances must always be calculated automatically" and "Never allow
negative balances unless explicitly allowed" are satisfied by
construction: since nothing here is stored, there's no stale value to
go wrong, and negative-balance prevention is enforced at the point
money actually moves (see financial_validator.py / deposit_service.py),
not by clamping a computed number after the fact.
"""
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.models.financial import Transaction, TransactionStatus, TransactionType
from app.repositories.financial_repository import FinancialAccountRepository, TransactionRepository, OutstandingBalanceRepository
from app.repositories.property_repository import PropertyRepository
from app.business_workflows.owner_ledger.owner_balance_service import OwnerBalanceService
from app.business_workflows.financial_engine.financial_exceptions import EntityNotFoundError


class BalanceService:
    def __init__(self, db: Session):
        self.db = db
        self.account_repo = FinancialAccountRepository(db)
        self.txn_repo = TransactionRepository(db)
        self.outstanding_repo = OutstandingBalanceRepository(db)
        self.property_repo = PropertyRepository(db)
        self.owner_balance = OwnerBalanceService(db)

    # ---------------- Company Ledger ----------------
    def get_company_ledger(self) -> dict:
        accounts = self.account_repo.list_active()
        cash_total = Decimal("0")
        bank_total = Decimal("0")
        account_balances = []
        for a in accounts:
            balance = self.account_repo.current_balance(a.id)
            account_balances.append({"account_id": a.id, "account_name": a.name, "account_type": a.account_type, "balance": balance})
            if a.account_type == "cash":
                cash_total += balance
            else:
                bank_total += balance
        return {
            "cash_total": cash_total,
            "bank_total": bank_total,
            "total_balance": cash_total + bank_total,
            "accounts": account_balances,
        }

    # ---------------- Owner Ledger ----------------
    def get_owner_ledger(self, owner_id: int) -> dict:
        return self.owner_balance.get_owner_balance_summary(owner_id)

    # ---------------- Tenant Ledger ----------------
    def get_tenant_ledger(self, tenant_id: int) -> dict:
        def _sum(transaction_type):
            stmt = select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                Transaction.tenant_id == tenant_id, Transaction.transaction_type == transaction_type,
                Transaction.transaction_status == TransactionStatus.COMPLETED, Transaction.deleted_at.is_(None),
            )
            return self.db.execute(stmt).scalar_one() or Decimal("0")

        total_paid = _sum(TransactionType.TENANT_PAYMENT)
        total_refunded = _sum(TransactionType.REFUND)
        total_deposited = _sum(TransactionType.DEPOSIT_RECEIVED)
        total_deposit_refunded = _sum(TransactionType.DEPOSIT_REFUND)

        outstanding_amount = Decimal("0")
        for row in self.outstanding_repo.tenant_outstanding():
            if row["id"] == tenant_id:
                outstanding_amount = row["outstanding_amount"]
                break

        return {
            "tenant_id": tenant_id,
            "total_paid": total_paid,
            "total_refunded": total_refunded,
            "total_deposited": total_deposited,
            "total_deposit_refunded": total_deposit_refunded,
            "outstanding_rent": outstanding_amount,
        }

    # ---------------- Building / Property / Unit Ledger ----------------
    def get_building_ledger(self, building_id: int) -> dict:
        building = self.property_repo.get(building_id)
        if not building:
            raise EntityNotFoundError("Building", building_id)
        unit_ids = self.property_repo.get_unit_ids(building_id)
        all_ids = [building_id] + unit_ids
        return self._ledger_for_property_ids(all_ids, scope_id=building_id, scope_label="building")

    def get_property_ledger(self, property_id: int) -> dict:
        prop = self.property_repo.get(property_id)
        if not prop:
            raise EntityNotFoundError("Property", property_id)
        return self._ledger_for_property_ids([property_id], scope_id=property_id, scope_label="property")

    def get_unit_ledger(self, unit_id: int) -> dict:
        """Same query as get_property_ledger — a unit is a Property row
        (Phase 4/5) — kept as its own method only because the spec asks
        for Unit Ledger as a named concept, not because the computation
        differs."""
        unit = self.property_repo.get(unit_id)
        if not unit:
            raise EntityNotFoundError("Unit", unit_id)
        return self._ledger_for_property_ids([unit_id], scope_id=unit_id, scope_label="unit")

    def _ledger_for_property_ids(self, property_ids: list[int], scope_id: int, scope_label: str) -> dict:
        def _sum(types):
            stmt = select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                Transaction.property_id.in_(property_ids), Transaction.transaction_type.in_(types),
                Transaction.transaction_status == TransactionStatus.COMPLETED, Transaction.deleted_at.is_(None),
            )
            return self.db.execute(stmt).scalar_one() or Decimal("0")

        rental_income = _sum((TransactionType.TENANT_PAYMENT, TransactionType.INCOME))
        # Maintenance cost isn't its own TransactionType (maintenance
        # spend is recorded as a normal EXPENSE — see
        # MaintenanceWorkflowService.complete_and_settle, Phase 12,
        # unchanged) — reported as a subtotal of total_expenses rather
        # than invented as a distinct figure this module can't actually
        # distinguish from any other operating expense at the
        # Transaction level.
        total_expenses = _sum((TransactionType.EXPENSE,))
        owner_expenses = _sum((TransactionType.RECOVERABLE_EXPENSE,))

        return {
            f"{scope_label}_id": scope_id,
            "rental_income": rental_income,
            "operating_expenses": total_expenses,
            "owner_expenses": owner_expenses,
            "net_income": rental_income - total_expenses - owner_expenses,
        }
