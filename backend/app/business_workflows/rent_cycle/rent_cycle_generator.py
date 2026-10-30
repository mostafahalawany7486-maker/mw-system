"""
rent_cycle_generator.py

The actual "generate this month's rent records" logic. Reuses the two
existing engines rather than reimplementing lease eligibility or
invoice/receipt math:

  - FinancialService.generate_bulk_invoices() — already does exactly
    "load active leases, skip expired/cancelled/future leases, generate
    a billing document per eligible lease, never duplicate" (see
    RentalContractRepository.list_active_for_billing and
    InvoiceRepository.exists_for_period). This produces the Invoice
    (Rent Billing Engine, Phase 8/10).
  - RentalService.generate_monthly_receipts() — already does "assign a
    receipt_number to every installment due this month, for active
    contracts only" (Rental Receipt Module, Phase 7). This produces the
    printable pre-payment receipt the spec calls for; existing receipt
    formatting/printing is completely untouched.

This module's own job is just gluing those two results together per
lease into one RentCycleRecord row, so the cycle has a queryable,
duplicate-proof record of "what this cycle actually generated" —
without owning any lease-eligibility or invoice-numbering logic itself.
"""
from typing import Optional
from sqlalchemy.orm import Session

from app.models.rent_cycle import RentCycle, RentCycleRecord, RentCycleRecordStatus
from app.repositories.rent_cycle_repository import RentCycleRecordRepository
from app.services.financial_service import FinancialService
from app.services.rental_service import RentalService


class RentCycleGenerationResult:
    def __init__(self, invoices_generated: int, receipts_generated: int, leases_skipped: int):
        self.invoices_generated = invoices_generated
        self.receipts_generated = receipts_generated
        self.leases_skipped = leases_skipped


class RentCycleGenerator:
    def __init__(self, db: Session):
        self.db = db
        self.record_repo = RentCycleRecordRepository(db)
        self.financial_service = FinancialService(db)
        self.rental_service = RentalService(db)

    def generate(self, cycle: RentCycle, actor_id: Optional[int]) -> RentCycleGenerationResult:
        """Runs both existing engines for this cycle's period and writes
        one RentCycleRecord per lease touched by either. Safe to call
        more than once for the same cycle: both underlying engines are
        already idempotent per period, and this method only ever
        inserts a RentCycleRecord for a (cycle, contract) pair that
        doesn't already have one (the DB unique constraint is the final
        backstop).
        """
        already_recorded = self.record_repo.existing_contract_ids_for_cycle(cycle.id)

        invoices = self.financial_service.generate_bulk_invoices(
            cycle.start_date, cycle.property_ids, actor_id=actor_id,
        )
        invoices_by_contract = {inv.rental_contract_id: inv for inv in invoices if inv.rental_contract_id}

        receipts = self.rental_service.generate_monthly_receipts(cycle.year, cycle.month, actor_id=actor_id)
        receipts_by_contract = {inst.contract_id: inst for inst in receipts}

        # Every contract touched by either engine this run, scoped to
        # this cycle's property_ids if the cycle is scoped to a subset
        # of the portfolio (an installment being due this month doesn't
        # by itself mean its property is in scope, so we filter here).
        contract_ids = set(invoices_by_contract) | set(receipts_by_contract)
        if cycle.property_ids:
            scoped_ids = set()
            for contract_id in contract_ids:
                invoice = invoices_by_contract.get(contract_id)
                installment = receipts_by_contract.get(contract_id)
                property_id = invoice.property_id if invoice else (
                    installment.contract.property_id if installment and installment.contract else None
                )
                if property_id in cycle.property_ids:
                    scoped_ids.add(contract_id)
            contract_ids = scoped_ids

        created = 0
        for contract_id in contract_ids:
            if contract_id in already_recorded:
                continue
            invoice = invoices_by_contract.get(contract_id)
            installment = receipts_by_contract.get(contract_id)
            amount = invoice.amount if invoice else (installment.amount if installment else None)
            due_date = invoice.due_date if invoice else (installment.due_date if installment else cycle.due_date)
            if amount is None:
                continue

            self.record_repo.create({
                "cycle_id": cycle.id,
                "rental_contract_id": contract_id,
                "invoice_id": invoice.id if invoice else None,
                "installment_id": installment.id if installment else None,
                "amount": amount,
                "due_date": due_date,
                "record_status": RentCycleRecordStatus.GENERATED,
            }, actor_id=actor_id)
            created += 1

        self.db.commit()
        return RentCycleGenerationResult(
            invoices_generated=len(invoices),
            receipts_generated=len(receipts),
            leases_skipped=max(len(contract_ids) - created, 0),
        )
