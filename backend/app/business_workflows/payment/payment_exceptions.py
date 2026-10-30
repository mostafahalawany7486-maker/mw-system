"""
payment_exceptions.py

Custom exception types for the Payment & Collection Engine — every one
subclasses `fastapi.HTTPException` directly, exactly like
rent_cycle_exceptions.py (Phase 14), so they stay fully compatible with
FastAPI's existing exception handling without introducing a second
error-handling convention.
"""
from fastapi import HTTPException, status


class PaymentError(HTTPException):
    """Base class for every Payment & Collection Engine exception."""


class PaymentNotFoundError(PaymentError):
    def __init__(self, payment_id: int):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=f"Payment {payment_id} not found")


class NegativePaymentAmountError(PaymentError):
    def __init__(self):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail="Payment amount must be greater than zero")


class DuplicateReferenceNumberError(PaymentError):
    def __init__(self, reference_number: str, existing_payment_number: str):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Reference number '{reference_number}' is already used by payment {existing_payment_number}",
        )


class PaymentExceedsOutstandingError(PaymentError):
    def __init__(self, invoice_number: str, requested: object, outstanding: object):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Allocation of {requested} to invoice {invoice_number} exceeds its outstanding balance ({outstanding})",
        )


class PaymentOnCancelledReceiptError(PaymentError):
    def __init__(self, invoice_number: str, invoice_status: str):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot allocate a payment to invoice {invoice_number} — it is {invoice_status}",
        )


class InvalidPaymentStatusTransitionError(PaymentError):
    def __init__(self, current_status: str, attempted_action: str):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot {attempted_action} a payment that is '{current_status}'",
        )


class DuplicateReversalError(PaymentError):
    def __init__(self):
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail="This payment has already been reversed")


class InvalidAllocationError(PaymentError):
    def __init__(self, detail: str):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)
