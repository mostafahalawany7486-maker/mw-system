"""
rent_cycle_closer.py

Handles the back half of a rent cycle's lifecycle: recomputing its
collection-progress status (Collecting / Partially Collected /
Completed) from the live status of the invoices its records point to,
and the explicit user-driven transitions (close / reopen / cancel).

No invoice/payment logic lives here — collection progress is read
straight from Invoice.invoice_status via FinancialService.get_invoice,
exactly like FinancialService.outstanding_balances() already reads
installment payment_status rather than keeping its own duplicate
ledger. This module only interprets those existing statuses at the
cycle level.
"""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from sqlalchemy.orm import Session

from app.models.financial import InvoiceStatus
from app.models.rent_cycle import RentCycle, RentCycleStatus
from app.services.financial_service import FinancialService


class CollectionProgress:
    def __init__(self, total_expected: Decimal, total_collected: Decimal, invoice_count: int, paid_count: int):
        self.total_expected = total_expected
        self.total_collected = total_collected
        self.invoice_count = invoice_count
        self.paid_count = paid_count

    @property
    def percent(self) -> Decimal:
        if self.total_expected <= 0:
            return Decimal("0")
        return (self.total_collected / self.total_expected * Decimal("100")).quantize(Decimal("0.01"))


class RentCycleCloser:
    def __init__(self, db: Session):
        self.db = db
        self.financial_service = FinancialService(db)

    def compute_progress(self, cycle: RentCycle) -> CollectionProgress:
        total_expected = Decimal("0")
        total_collected = Decimal("0")
        invoice_count = 0
        paid_count = 0

        for record in cycle.records:
            if not record.invoice_id:
                continue
            invoice = self.financial_service.get_invoice(record.invoice_id)
            invoice_count += 1
            total_expected += invoice.amount
            total_collected += invoice.amount_paid
            if invoice.invoice_status == InvoiceStatus.PAID:
                paid_count += 1

        return CollectionProgress(total_expected, total_collected, invoice_count, paid_count)

    def refresh_status(self, cycle: RentCycle) -> RentCycle:
        """Advances cycle_status based on collection progress. Only
        moves the cycle through the *collection* states
        (Collecting/Partially Collected/Completed) — it never touches
        Draft/Generated/Printed/Distributed (those are set explicitly by
        rent_cycle_service as generation/distribution steps happen) or
        Closed/Cancelled (explicit, user-driven, handled below).
        """
        if cycle.cycle_status not in (
            RentCycleStatus.GENERATED, RentCycleStatus.PRINTED, RentCycleStatus.DISTRIBUTED,
            RentCycleStatus.COLLECTING, RentCycleStatus.PARTIALLY_COLLECTED, RentCycleStatus.COMPLETED,
        ):
            return cycle

        progress = self.compute_progress(cycle)
        if progress.invoice_count == 0:
            return cycle
        if progress.paid_count == progress.invoice_count:
            cycle.cycle_status = RentCycleStatus.COMPLETED
        elif progress.paid_count > 0:
            cycle.cycle_status = RentCycleStatus.PARTIALLY_COLLECTED
        else:
            cycle.cycle_status = RentCycleStatus.COLLECTING
        return cycle

    def close(self, cycle: RentCycle, notes: Optional[str]) -> RentCycle:
        cycle.cycle_status = RentCycleStatus.CLOSED
        cycle.closing_date = datetime.now(timezone.utc).date()
        cycle.closed_at = datetime.now(timezone.utc)
        if notes:
            cycle.notes = f"{cycle.notes}\n{notes}" if cycle.notes else notes
        return cycle

    def reopen(self, cycle: RentCycle) -> RentCycle:
        cycle.closing_date = None
        cycle.closed_at = None
        # Re-derive the correct in-progress state from live collection
        # data rather than assuming — a reopened cycle may since have
        # had payments recorded against it while closed.
        progress = self.compute_progress(cycle)
        if progress.invoice_count == 0:
            cycle.cycle_status = RentCycleStatus.GENERATED
        elif progress.paid_count == progress.invoice_count:
            cycle.cycle_status = RentCycleStatus.COMPLETED
        elif progress.paid_count > 0:
            cycle.cycle_status = RentCycleStatus.PARTIALLY_COLLECTED
        else:
            cycle.cycle_status = RentCycleStatus.COLLECTING
        return cycle

    def cancel(self, cycle: RentCycle, reason: str) -> RentCycle:
        cycle.cycle_status = RentCycleStatus.CANCELLED
        cycle.cancellation_reason = reason
        return cycle
