"""
financial_transaction_service.py

Spec: "Every financial movement must generate a financial transaction."
This is a thin wrapper around FinancialService.create_transaction()
(Phase 8, unchanged) — not a second transaction table. Its only added
value is the duplicate-transaction check (financial_validator.py)
before delegating, so every Financial Engine write path goes through
one place that enforces it rather than repeating the check in every
service (deposit_service.py, refund_service.py, adjustment_service.py
all call this instead of FinancialService directly).
"""
from datetime import date
from decimal import Decimal
from typing import Optional
from sqlalchemy.orm import Session

from app.services.financial_service import FinancialService
from app.business_workflows.financial_engine.financial_validator import FinancialValidator


class FinancialTransactionService:
    def __init__(self, db: Session):
        self.db = db
        self.financial_service = FinancialService(db)
        self.validator = FinancialValidator(db)

    def record(self, transaction_type: str, amount: Decimal, account_id: int, transaction_date: date, actor_id: Optional[int], **extra):
        """Returns the created Transaction (app.models.financial.Transaction)."""
        reference_number = extra.get("reference_number")
        self.validator.validate_no_duplicate_transaction(reference_number)
        return self.financial_service.create_transaction({
            "transaction_type": transaction_type, "amount": amount, "account_id": account_id,
            "transaction_date": transaction_date, **extra,
        }, actor_id=actor_id)
