"""
financial_engine.py

The facade the API router calls — ties balance_service (the six ledger
views), deposit_service (the security deposit lifecycle),
refund_service, adjustment_service, allocation_service, and
ledger_sync_service together into the operations the spec's API and
DASHBOARD sections ask for.
"""
from datetime import date
from decimal import Decimal
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.models.financial import Transaction, TransactionType, TransactionStatus
from app.business_workflows.financial_engine.balance_service import BalanceService
from app.business_workflows.financial_engine.deposit_service import DepositService
from app.business_workflows.financial_engine.refund_service import RefundService
from app.business_workflows.financial_engine.adjustment_service import AdjustmentService
from app.business_workflows.financial_engine.allocation_service import AllocationService
from app.business_workflows.financial_engine.ledger_sync_service import LedgerSyncService
from app.business_workflows.financial_engine.financial_transaction_service import FinancialTransactionService
from app.business_workflows.financial_engine.financial_validator import FinancialValidator
from app.services.financial_service import FinancialService


class FinancialEngine:
    def __init__(self, db: Session):
        self.db = db
        self.balances = BalanceService(db)
        self.deposits = DepositService(db)
        self.refunds = RefundService(db)
        self.adjustments = AdjustmentService(db)
        self.allocations = AllocationService(db)
        self.sync = LedgerSyncService(db)
        self.transactions = FinancialTransactionService(db)
        self.validator = FinancialValidator(db)
        self.financial_service = FinancialService(db)

    # ---------------- GET /financial/ledgers ----------------
    def get_all_ledgers_summary(self) -> dict:
        """A quick, portfolio-wide snapshot — the Company Ledger (the
        only one of the six that doesn't need a specific owner/tenant/
        building/property/unit id to scope it to). The other five each
        have their own dedicated endpoint (GET /financial/{owners,
        tenants, buildings, properties}/{id}, GET /financial/units/{id})
        since they're inherently per-entity, not portfolio-wide."""
        return {"company": self.balances.get_company_ledger()}

    # ---------------- GET /financial/company ----------------
    def get_company_ledger(self) -> dict:
        return self.balances.get_company_ledger()

    # ---------------- GET /financial/owners ----------------
    def get_owner_ledger(self, owner_id: int) -> dict:
        return self.balances.get_owner_ledger(owner_id)

    # ---------------- GET /financial/tenants ----------------
    def get_tenant_ledger(self, tenant_id: int) -> dict:
        return self.balances.get_tenant_ledger(tenant_id)

    # ---------------- GET /financial/buildings ----------------
    def get_building_ledger(self, building_id: int) -> dict:
        return self.balances.get_building_ledger(building_id)

    # ---------------- GET /financial/properties ----------------
    def get_property_ledger(self, property_id: int) -> dict:
        return self.balances.get_property_ledger(property_id)

    def get_unit_ledger(self, unit_id: int) -> dict:
        return self.balances.get_unit_ledger(unit_id)

    # ---------------- POST /financial/adjustment ----------------
    def create_adjustment(self, scope: str, entity_id: int, amount: Decimal, description: str, actor_id: Optional[int], is_credit: bool = True, account_id: Optional[int] = None, property_id: Optional[int] = None) -> dict:
        if scope == "owner":
            entry = self.adjustments.adjust_owner_balance(entity_id, amount, description, actor_id, is_credit, property_id)
            return {"scope": "owner", "entry": entry}
        txn = self.adjustments.adjust_tenant_balance(entity_id, account_id, amount, description, actor_id, property_id=property_id)
        return {"scope": "tenant", "transaction": txn}

    # ---------------- POST /financial/refund ----------------
    def create_refund(self, refund_type: str, actor_id: Optional[int], **kwargs) -> dict:
        if refund_type == "payment":
            payment = self.refunds.refund_tenant_payment(kwargs["payment_id"], kwargs["reason"], actor_id, amount=kwargs.get("amount"))
            return {"refund_type": "payment", "payment": payment}
        entry = self.refunds.refund_security_deposit(
            kwargs["contract_type"], kwargs["contract_id"], kwargs["amount"], kwargs["account_id"],
            kwargs.get("payment_date") or date.today(), kwargs.get("reason"), actor_id, kwargs.get("reference_number"),
        )
        return {"refund_type": "deposit", **entry}

    # ---------------- POST /financial/deposit ----------------
    def create_deposit(self, contract_type: str, contract_id: int, amount: Decimal, account_id: int, payment_date: date, actor_id: Optional[int], reference_number: Optional[str] = None) -> dict:
        return self.deposits.receive_deposit(contract_type, contract_id, amount, account_id, payment_date, actor_id, reference_number)

    # ---------------- POST /financial/transfer ----------------
    def create_transfer(self, from_account_id: int, to_account_id: int, amount: Decimal, transaction_date: date, actor_id: Optional[int], description: Optional[str] = None, reference_number: Optional[str] = None) -> dict:
        """Internal Transfer — delegates entirely to
        FinancialService.create_transfer() (Phase 8, unchanged), which
        already implements this exactly, insufficient-balance check
        included. This endpoint exists in the Financial Engine's own
        API surface only because the spec explicitly lists
        POST /financial/transfer under this module — it is not a second
        implementation."""
        return self.financial_service.create_transfer({
            "from_account_id": from_account_id, "to_account_id": to_account_id, "amount": amount,
            "transaction_date": transaction_date, "description": description, "reference_number": reference_number,
        }, actor_id=actor_id)

    # ---------------- Dashboard ----------------
    def get_dashboard(self) -> dict:
        """Spec: Company Cash, Owner Outstanding, Tenant Outstanding,
        Security Deposits, Recoverable Expenses, Recovered Amounts,
        Today's Collections, Monthly Collections — every figure reuses
        an existing aggregation rather than a new one:
        FinancialService.dashboard() already computes cash/bank totals,
        monthly income, and tenant/owner outstanding (Phase 8);
        OwnerLedgerRepository.portfolio_recoverable_totals() and
        DepositLedgerRepository.total_held() are the two small additive
        portfolio-wide rollups this phase needed (see their own
        docstrings). Only "today's collections" had no existing
        aggregation anywhere (the existing dashboard only has a
        *monthly* income figure) — a small, direct query, same shape as
        every other single-day sum already in this codebase (e.g.
        PaymentRepository.sum_collected_between)."""
        from app.repositories.owner_ledger_repository import OwnerLedgerRepository
        from app.repositories.deposit_repository import DepositLedgerRepository

        existing_dashboard = self.financial_service.dashboard()
        recoverable = OwnerLedgerRepository(self.db).portfolio_recoverable_totals()
        deposits_held = DepositLedgerRepository(self.db).total_held()

        today = date.today()
        todays_collections_stmt = select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            Transaction.transaction_date == today, Transaction.transaction_type == TransactionType.TENANT_PAYMENT,
            Transaction.transaction_status == TransactionStatus.COMPLETED, Transaction.deleted_at.is_(None),
        )
        todays_collections = self.db.execute(todays_collections_stmt).scalar_one() or Decimal("0")

        return {
            "company_cash": existing_dashboard["total_cash_balance"] + existing_dashboard["total_bank_balance"],
            "owner_outstanding": existing_dashboard["total_owner_outstanding"],
            "tenant_outstanding": existing_dashboard["total_tenant_outstanding"],
            "security_deposits_held": deposits_held,
            "recoverable_expenses_outstanding": recoverable["outstanding"],
            "recovered_amounts_total": recoverable["total_recovered_amounts"],
            "todays_collections": todays_collections,
            "monthly_collections": existing_dashboard["total_income_this_month"],
        }
