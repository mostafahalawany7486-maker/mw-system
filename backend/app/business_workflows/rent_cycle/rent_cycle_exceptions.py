"""
rent_cycle_exceptions.py

Custom exception types for the Rent Cycle Engine. Every exception here
subclasses `fastapi.HTTPException` directly rather than introducing a
parallel error hierarchy — this keeps them exactly as compatible with
FastAPI's existing exception handling as every `HTTPException` already
raised throughout `app/services/*`. The point of naming them (instead of
raising bare `HTTPException(status_code=..., detail=...)` inline, as the
rest of this codebase does) is purely for this module's own internal
clarity and testability: `except DuplicateCycleError` reads better than
`except HTTPException` at the call sites in rent_cycle_service.py, and
tests can assert on the specific type instead of parsing `detail`
strings.
"""
from fastapi import HTTPException, status


class RentCycleError(HTTPException):
    """Base class for every Rent Cycle Engine exception."""


class CycleNotFoundError(RentCycleError):
    def __init__(self, cycle_id: int):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=f"Rent cycle {cycle_id} not found")


class DuplicateCycleError(RentCycleError):
    def __init__(self, year: int, month: int, existing_cycle_number: str):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A rent cycle for {year}-{month:02d} already exists ({existing_cycle_number})",
        )


class InvalidCycleStatusTransitionError(RentCycleError):
    def __init__(self, current_status: str, attempted_action: str):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot {attempted_action} a rent cycle that is '{current_status}'",
        )


class RegenerationNotAuthorizedError(RentCycleError):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Regenerating an already-generated rent cycle requires administrator approval "
                   "(pass force=true as an administrator)",
        )


class CycleValidationError(RentCycleError):
    def __init__(self, detail: str):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)
