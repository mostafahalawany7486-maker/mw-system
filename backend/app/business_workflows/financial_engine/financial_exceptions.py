"""
financial_exceptions.py

Every exception the Financial Engine raises. Subclasses HTTPException
directly — same convention as every other business workflow module in
this codebase (owner_ledger, payment, occupancy).
"""
from fastapi import HTTPException, status


class FinancialEngineError(HTTPException):
    """Base class for every Financial Engine exception."""


class InvalidLedgerScopeError(FinancialEngineError):
    def __init__(self, ledger_type: str):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown ledger type: {ledger_type}")


class EntityNotFoundError(FinancialEngineError):
    def __init__(self, entity_type: str, entity_id: int):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=f"{entity_type} {entity_id} not found")


class DuplicateTransactionError(FinancialEngineError):
    def __init__(self, reference_number: str):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A transaction with reference number '{reference_number}' already exists",
        )


class DuplicateDepositError(FinancialEngineError):
    def __init__(self, contract_type: str, contract_id: int):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{contract_type} {contract_id} already has a security deposit on record — use an adjustment, not a second deposit",
        )


class NegativeDepositError(FinancialEngineError):
    def __init__(self):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail="Deposit amount must be greater than zero")


class OverRefundError(FinancialEngineError):
    def __init__(self, requested: str, available: str):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Refund amount {requested} exceeds the available balance {available}",
        )


class InvalidDepositTransitionError(FinancialEngineError):
    def __init__(self, current_status: str, action: str):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot {action} a security deposit that is currently '{current_status}'",
        )


class InvalidAllocationError(FinancialEngineError):
    def __init__(self, detail: str):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class LedgerImbalanceError(FinancialEngineError):
    def __init__(self, detail: str):
        super().__init__(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Ledger imbalance detected: {detail}")


class NegativeBalanceNotAllowedError(FinancialEngineError):
    def __init__(self, ledger_type: str, entity_id: int):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"This action would drive the {ledger_type} balance for entity {entity_id} negative, which isn't allowed here",
        )
