"""
rent_cycle_scheduler.py

Small, pure/read-mostly helpers for the calendar mechanics of a rent
cycle: what a cycle's default start/due dates are for a given
(year, month), and its cycle_number. Deliberately has no business rules
about leases/invoices in it — that's rent_cycle_generator.py's job. This
module only knows about dates and numbering.
"""
from datetime import date, timedelta
from calendar import monthrange
from sqlalchemy.orm import Session
from app.repositories.rent_cycle_repository import RentCycleRepository

# Matches the existing Rent Billing Engine convention exactly — see
# FinancialService.generate_bulk_invoices, which sets each generated
# invoice's due_date to billing_period_start + 15 days. Kept identical
# so a rent cycle's own due_date lines up with the invoices it produces.
DEFAULT_DUE_DAYS_AFTER_START = 15


class RentCycleScheduler:
    def __init__(self, db: Session):
        self.db = db
        self.repo = RentCycleRepository(db)

    def default_start_date(self, year: int, month: int) -> date:
        """First calendar day of the given month — matches how
        FinancialService.generate_bulk_invoices is already invoked
        elsewhere in this codebase (`date.today().replace(day=1)`)."""
        return date(year, month, 1)

    def default_due_date(self, start_date: date) -> date:
        return start_date + timedelta(days=DEFAULT_DUE_DAYS_AFTER_START)

    def last_day_of_month(self, year: int, month: int) -> date:
        return date(year, month, monthrange(year, month)[1])

    def next_cycle_number(self) -> str:
        return self.repo.next_cycle_number()
