"""
Rental Contract business logic. Mirrors LeaseService (Phase 3) closely —
same status machine, same renewal pattern, same on-demand maintenance
sweep — with additions for discounts, taxes, and late fees, and a
tenant-blacklist warning surfaced (not enforced) at creation time.
"""
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional
from dateutil.relativedelta import relativedelta
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.repositories.rental_repository import RentalContractRepository, RentalInstallmentRepository
from app.repositories.tenant_repository import TenantRepository
from app.repositories.property_repository import PropertyRepository
from app.models.rental import RentalContract, RentalContractStatus, RentalPaymentFrequency
from app.models.user import User
from app.schemas.common import PaginationParams
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService
ENTITY_TYPE = "rental_contract"

FREQUENCY_MONTHS = {
    RentalPaymentFrequency.MONTHLY: 1,
    RentalPaymentFrequency.QUARTERLY: 3,
    RentalPaymentFrequency.SEMI_ANNUAL: 6,
    RentalPaymentFrequency.ANNUAL: 12,
}


class RentalService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = RentalContractRepository(db)
        self.installment_repo = RentalInstallmentRepository(db)
        self.tenant_repo = TenantRepository(db)
        self.property_repo = PropertyRepository(db)
        self.audit = AuditService(db)
        self.notifications = NotificationService(db)

    # ---------------- CRUD ----------------
    def _attach_blacklist_flag(self, contract: RentalContract) -> RentalContract:
        contract.tenant_is_blacklisted = bool(contract.tenant.is_blacklisted) if contract.tenant else False
        return contract

    def list_contracts(self, params: PaginationParams, contract_status, tenant_id, property_id, branch_id, expiring_soon, include_archived: bool = False, building_id: Optional[int] = None):
        items, total = self.repo.list_contracts(
            page=params.page, page_size=params.page_size, search=params.search,
            contract_status=contract_status, tenant_id=tenant_id, property_id=property_id, branch_id=branch_id,
            expiring_soon=expiring_soon, sort_by=params.sort_by, sort_dir=params.sort_dir or "desc",
            include_archived=include_archived, building_id=building_id,
        )
        items = [self._attach_blacklist_flag(c) for c in items]
        return items, total

    def get_contract(self, contract_id: int) -> RentalContract:
        contract = self.repo.get_detail(contract_id)
        if not contract:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rental contract not found")
        return self._attach_blacklist_flag(contract)

    def create_contract(self, data: dict, actor_id: Optional[int]) -> RentalContract:
        tenant = self.tenant_repo.get(data["tenant_id"])
        if not tenant:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid tenant_id")
        property_ = self.property_repo.get(data["property_id"])
        if not property_:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid property_id")

        payload = dict(data)
        payload["contract_number"] = self.repo.next_contract_number()
        payload["contract_status"] = RentalContractStatus.DRAFT
        contract = self.repo.create(payload, actor_id=actor_id)

        description = f"Rental contract {contract.contract_number} created (draft)"
        if tenant.is_blacklisted:
            description += " — WARNING: tenant is blacklisted"
        self.audit.log_activity(ENTITY_TYPE, contract.id, "created", description, actor_id)
        self.audit.log_audit(ENTITY_TYPE, contract.id, "created", None, actor_id)
        self.db.commit()
        return self._attach_blacklist_flag(self.repo.get_detail(contract.id))

    def update_contract(self, contract_id: int, data: dict, actor_id: Optional[int]) -> RentalContract:
        contract = self.get_contract(contract_id)
        if contract.contract_status in (RentalContractStatus.TERMINATED, RentalContractStatus.RENEWED):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Cannot edit a {contract.contract_status} contract")
        before = {k: getattr(contract, k) for k in data.keys()}
        self.repo.update(contract, data, actor_id=actor_id)
        after = {k: getattr(contract, k) for k in data.keys()}
        changes = self.audit.diff(before, after)
        if changes:
            self.audit.log_activity(ENTITY_TYPE, contract.id, "updated", f"Rental contract {contract.contract_number} updated", actor_id)
            self.audit.log_audit(ENTITY_TYPE, contract.id, "updated", changes, actor_id)
        self.db.commit()
        return self._attach_blacklist_flag(self.repo.get_detail(contract.id))

    def delete_contract(self, contract_id: int, actor_id: Optional[int]) -> None:
        contract = self.get_contract(contract_id)
        # A contract still marked ACTIVE means a tenant is, as far as
        # this system is concerned, currently living in that unit —
        # deleting it directly would make the unit look vacant while
        # nothing about the actual occupancy changed. Terminate() is
        # the correct path first; deletion is for draft/already-ended
        # contracts.
        if contract.contract_status == RentalContractStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot delete an active rental contract — terminate it first, then delete.",
            )
        self.repo.soft_delete(contract, actor_id=actor_id)
        self.audit.log_activity(ENTITY_TYPE, contract.id, "deleted", f"Rental contract {contract.contract_number} deleted", actor_id)
        self.db.commit()

    def archive_contract(self, contract_id: int, actor_id: Optional[int]) -> RentalContract:
        """Distinct from delete — see BaseRepository.archive(). Typically
        used on an expired/terminated contract you want out of the main
        list but still fully intact for lookups, reports, and audit."""
        contract = self.get_contract(contract_id)
        self.repo.archive(contract, actor_id=actor_id)
        self.audit.log_activity(ENTITY_TYPE, contract.id, "archived", f"Rental contract {contract.contract_number} archived", actor_id)
        self.db.commit()
        return contract

    def unarchive_contract(self, contract_id: int, actor_id: Optional[int]) -> RentalContract:
        contract = self.get_contract(contract_id)
        self.repo.unarchive(contract, actor_id=actor_id)
        self.audit.log_activity(ENTITY_TYPE, contract.id, "unarchived", f"Rental contract {contract.contract_number} restored from archive", actor_id)
        self.db.commit()
        return contract

    # ---------------- Status transitions ----------------
    def activate_contract(self, contract_id: int, actor_id: Optional[int]) -> RentalContract:
        contract = self.get_contract(contract_id)
        if contract.contract_status != RentalContractStatus.DRAFT:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Only draft contracts can be activated (current: {contract.contract_status})")

        # Phase 18 (Occupancy Engine) — a unit can only have one active
        # lease at a time; nothing enforced this before. Uses the same
        # repository-level count the Occupancy Engine's own validator
        # (business_workflows/occupancy/occupancy_validator.py) calls,
        # so there's exactly one implementation of "how many other
        # active contracts does this unit have" — not two that could
        # drift apart. Imported from app/repositories/ (a shared lower
        # layer both services and business_workflows may depend on),
        # never from business_workflows/ itself — services must never
        # depend on that package, only the reverse.
        from app.repositories.occupancy_repository import OccupancyDataRepository
        if OccupancyDataRepository(self.db).count_other_active_contracts(contract.property_id, exclude_contract_id=contract.id) > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Unit {contract.property_id} already has another active rental contract — a unit can only have one active lease at a time",
            )

        contract.contract_status = RentalContractStatus.ACTIVE

        property_ = self.property_repo.get(contract.property_id)
        if property_ and property_.availability_status != "leased":
            property_.availability_status = "leased"

        self._sync_floor_wide_overrides(property_, contract, active=True, actor_id=actor_id)

        self.audit.log_activity(ENTITY_TYPE, contract.id, "activated", f"Rental contract {contract.contract_number} activated", actor_id)
        self.db.commit()
        return self._attach_blacklist_flag(self.repo.get_detail(contract.id))

    def _sync_floor_wide_overrides(self, property_: Optional["Property"], contract: RentalContract, active: bool, actor_id: Optional[int]) -> None:
        """When property_ is the special "whole floor" Property
        (property_type=FLOOR — see PropertyService.get_or_create_floor_unit),
        block/unblock every individual unit on that floor via
        UnitOccupancyOverride so they stop showing as independently
        vacant while this contract covers the whole floor. Does nothing
        for a normal single-unit contract — property_.property_type
        will never be FLOOR for those."""
        from app.models.property import PropertyType, Property as PropertyModel
        if not property_ or property_.property_type != PropertyType.FLOOR or not property_.floor_id:
            return
        from app.business_workflows.occupancy.occupancy_service import OccupancyService
        from app.models.occupancy import OccupancyStatus, UnitOccupancyOverride

        occ_service = OccupancyService(self.db)
        sibling_units = self.db.query(PropertyModel).filter(
            PropertyModel.floor_id == property_.floor_id, PropertyModel.deleted_at.is_(None),
            PropertyModel.property_type != PropertyType.FLOOR,
        ).all()
        for unit in sibling_units:
            if active:
                occ_service.set_override(
                    unit.id, OccupancyStatus.BLOCKED,
                    f"Part of whole-floor contract {contract.contract_number} — not independently rentable", None, actor_id,
                )
            else:
                open_override = self.db.query(UnitOccupancyOverride).filter(
                    UnitOccupancyOverride.property_id == unit.id, UnitOccupancyOverride.cleared_at.is_(None),
                    UnitOccupancyOverride.reason.ilike(f"%{contract.contract_number}%"),
                ).first()
                if open_override:
                    occ_service.clear_override(open_override.id, f"Contract {contract.contract_number} ended", actor_id)

    def terminate_contract(self, contract_id: int, terminated_date: date, reason: str, actor_id: Optional[int]) -> RentalContract:
        contract = self.get_contract(contract_id)
        if contract.contract_status != RentalContractStatus.ACTIVE:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Only active contracts can be terminated (current: {contract.contract_status})")
        contract.contract_status = RentalContractStatus.TERMINATED
        contract.terminated_date = terminated_date
        contract.termination_reason = reason

        property_ = self.property_repo.get(contract.property_id)
        if property_ and property_.availability_status == "leased":
            property_.availability_status = "available"

        self._sync_floor_wide_overrides(property_, contract, active=False, actor_id=actor_id)

        self.audit.log_activity(ENTITY_TYPE, contract.id, "terminated", f"Rental contract {contract.contract_number} terminated: {reason}", actor_id)
        self.audit.log_audit(ENTITY_TYPE, contract.id, "terminated", {"contract_status": {"old": "active", "new": "terminated"}}, actor_id)
        self.db.commit()
        return self._attach_blacklist_flag(self.repo.get_detail(contract.id))

    def renew_contract(self, contract_id: int, new_end_date: date, new_start_date: Optional[date],
                        rent_amount: Optional[Decimal], notes_summary: Optional[str], actor_id: Optional[int]) -> RentalContract:
        old_contract = self.get_contract(contract_id)
        if old_contract.contract_status != RentalContractStatus.ACTIVE:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Only active contracts can be renewed (current: {old_contract.contract_status})")
        if not old_contract.is_renewable:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This contract is marked as non-renewable")

        start = new_start_date or (old_contract.end_date + timedelta(days=1))
        if new_end_date <= start:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="new_end_date must be after the new start date")

        new_contract = self._create_renewed_contract(old_contract, start, new_end_date, rent_amount, notes_summary, actor_id)
        self.db.commit()
        return self._attach_blacklist_flag(self.repo.get_detail(new_contract.id))

    def _create_renewed_contract(
        self, old_contract: RentalContract, start: date, new_end_date: date,
        rent_amount: Optional[Decimal], notes_summary: Optional[str], actor_id: Optional[int],
    ) -> RentalContract:
        """Shared by both renew_contract() (manual, human-picked end
        date) and _process_auto_renewals() (automatic, computed end
        date) — one place builds a renewal, so the two paths can never
        drift apart on what a "renewal" actually copies forward."""
        new_payload = {
            "tenant_id": old_contract.tenant_id,
            "property_id": old_contract.property_id,
            "branch_id": old_contract.branch_id,
            "start_date": start,
            "end_date": new_end_date,
            "is_renewable": old_contract.is_renewable,
            "renewal_notice_days": old_contract.renewal_notice_days,
            "auto_renew": old_contract.auto_renew,
            "payment_frequency": old_contract.payment_frequency,
            "rent_amount": rent_amount if rent_amount is not None else old_contract.rent_amount,
            "currency_id": old_contract.currency_id,
            "security_deposit_amount": old_contract.security_deposit_amount,
            "discount_type": old_contract.discount_type,
            "discount_value": old_contract.discount_value,
            "discount_reason": old_contract.discount_reason,
            "tax_rate": old_contract.tax_rate,
            "late_fee_type": old_contract.late_fee_type,
            "late_fee_value": old_contract.late_fee_value,
            "late_fee_grace_period_days": old_contract.late_fee_grace_period_days,
            "notes_summary": notes_summary or f"Renewed from {old_contract.contract_number}",
            "contract_number": self.repo.next_contract_number(),
            "contract_status": RentalContractStatus.ACTIVE,
            "renewed_from_contract_id": old_contract.id,
        }
        new_contract = self.repo.create(new_payload, actor_id=actor_id)
        old_contract.contract_status = RentalContractStatus.RENEWED

        self.audit.log_activity(ENTITY_TYPE, old_contract.id, "renewed", f"Rental contract {old_contract.contract_number} renewed as {new_contract.contract_number}", actor_id)
        self.audit.log_activity(ENTITY_TYPE, new_contract.id, "created", f"Rental contract {new_contract.contract_number} created via renewal of {old_contract.contract_number}", actor_id)
        return new_contract

    def _process_auto_renewals(self, actor_id: Optional[int] = None) -> int:
        """Contracts with auto_renew=True get renewed automatically once
        they enter their renewal window — same term length as before
        (new_start = old.end_date + 1, new_end = new_start + the
        original contract's own duration), same rent/terms, and —
        unlike a manually-renewed contract — the new contract's payment
        schedule is generated immediately too (generate_schedule()),
        since there's no human step coming afterward to notice it's
        missing. Contracts without auto_renew are completely unaffected
        — they keep going through _send_renewal_reminders() exactly as
        before. Master Leases (owner side) are untouched entirely; this
        only ever touches RentalContract."""
        expiring = self.repo.get_expiring_soon()
        renewed_count = 0
        for old_contract in expiring:
            if not old_contract.auto_renew or not old_contract.is_renewable:
                continue
            term_length = old_contract.end_date - old_contract.start_date
            start = old_contract.end_date + timedelta(days=1)
            new_end_date = start + term_length
            new_contract = self._create_renewed_contract(old_contract, start, new_end_date, None, "Auto-renewed — no manual action taken", actor_id)
            self.db.flush()
            try:
                self.generate_schedule(new_contract.id, overwrite_existing=False, actor_id=actor_id)
            except HTTPException:
                pass  # e.g. custom payment frequency — schedule needs a manual add either way, same as any other contract of that type
            renewed_count += 1
        if renewed_count:
            self.db.commit()
        return renewed_count

    # ---------------- Payment Schedule ----------------
    def generate_schedule(self, contract_id: int, overwrite_existing: bool, actor_id: Optional[int]) -> list:
        contract = self.get_contract(contract_id)
        if contract.payment_frequency == RentalPaymentFrequency.CUSTOM:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Custom payment frequency requires manually adding installments")

        existing = self.installment_repo.list_for_contract(contract_id)
        if existing and not overwrite_existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This contract already has installments. Pass overwrite_existing=true to regenerate.")
        for inst in existing:
            self.installment_repo.soft_delete(inst, actor_id=actor_id)

        discount = contract.discount_amount_computed
        tax = contract.tax_amount_computed
        installments = []

        if contract.payment_frequency == RentalPaymentFrequency.ONE_TIME:
            installments.append(self.installment_repo.create({
                "contract_id": contract.id, "installment_number": 1, "due_date": contract.start_date,
                "amount": contract.rent_amount, "discount_amount": discount, "tax_amount": tax,
            }, actor_id=actor_id))
        else:
            step_months = FREQUENCY_MONTHS[contract.payment_frequency]
            current_due = contract.start_date
            number = 1
            while current_due <= contract.end_date:
                installments.append(self.installment_repo.create({
                    "contract_id": contract.id, "installment_number": number, "due_date": current_due,
                    "amount": contract.rent_amount, "discount_amount": discount, "tax_amount": tax,
                }, actor_id=actor_id))
                current_due = current_due + relativedelta(months=step_months)
                number += 1

        self.audit.log_activity(ENTITY_TYPE, contract.id, "schedule_generated", f"Payment schedule generated ({len(installments)} installment(s))", actor_id)
        self.db.commit()
        return self.installment_repo.list_for_contract(contract_id)

    def add_installment(self, contract_id: int, data: dict, actor_id: Optional[int]):
        self.get_contract(contract_id)
        data["contract_id"] = contract_id
        data["installment_number"] = self.installment_repo.next_installment_number(contract_id)
        inst = self.installment_repo.create(data, actor_id=actor_id)
        self.audit.log_activity(ENTITY_TYPE, contract_id, "installment_added", f"Installment #{inst.installment_number} added", actor_id)
        self.db.commit()
        return inst

    def update_installment(self, contract_id: int, installment_id: int, data: dict, actor_id: Optional[int]):
        inst = self.installment_repo.get(installment_id)
        if not inst or inst.contract_id != contract_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Installment not found")
        was_pending = inst.payment_status == "pending"
        self.installment_repo.update(inst, data, actor_id=actor_id)
        if data.get("payment_status") == "paid" and was_pending:
            self.audit.log_activity(ENTITY_TYPE, contract_id, "installment_paid", f"Installment #{inst.installment_number} marked paid", actor_id)
        self.db.commit()
        return inst

    def delete_installment(self, contract_id: int, installment_id: int, actor_id: Optional[int]):
        inst = self.installment_repo.get(installment_id)
        if not inst or inst.contract_id != contract_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Installment not found")
        self.installment_repo.soft_delete(inst, actor_id=actor_id)
        self.db.commit()

    # ---------------- Dashboard & Maintenance ----------------
    def dashboard(self) -> dict:
        return self.repo.dashboard_counts()

    def run_maintenance_sweep(self, actor_id: Optional[int] = None) -> dict:
        """On-demand sweep: expires past-due contracts, marks overdue
        installments + assesses late fees past grace period, auto-renews
        any contract with auto_renew=True (generating its schedule too),
        and sends renewal reminder notifications for everything else.
        See docs/phase3-renewal-reminders.md for the same honest
        limitation (no scheduler yet) — this endpoint applies identically
        to rental contracts."""
        expired_count = self.repo.auto_expire_overdue_contracts()
        overdue_count, late_fee_count = self.installment_repo.assess_late_fees_and_mark_overdue()
        auto_renewed_count = self._process_auto_renewals(actor_id)
        reminders_sent = self._send_renewal_reminders()
        self.db.commit()
        return {
            "contracts_auto_expired": expired_count,
            "installments_marked_overdue": overdue_count,
            "late_fees_assessed": late_fee_count,
            "contracts_auto_renewed": auto_renewed_count,
            "renewal_reminders_sent": reminders_sent,
        }

    def _send_renewal_reminders(self) -> int:
        expiring = self.repo.get_expiring_soon()
        admin_ids = list(self.db.execute(
            select(User.id).where(User.is_superuser.is_(True), User.is_active.is_(True))
        ).scalars().all())

        sent = 0
        for contract in expiring:
            if contract.renewal_reminder_sent:
                continue
            if contract.auto_renew:
                # Handled by _process_auto_renewals() instead — no human
                # needs reminding about a contract that renews itself.
                continue
            for admin_id in admin_ids:
                self.notifications.notify(
                    recipient_id=admin_id,
                    title="Rental contract renewal due soon",
                    message=f"Rental contract {contract.contract_number} ({contract.tenant_display_name or 'tenant'}) expires in {contract.days_until_expiry} day(s).",
                    notification_type="warning",
                    entity_type=ENTITY_TYPE,
                    entity_id=contract.id,
                )
            contract.renewal_reminder_sent = True
            sent += 1
        return sent

    # ==================== Rental Receipt Module ====================
    # Built entirely on top of the existing installment schedule and the
    # existing FinancialService.create_transaction() — see Phase 1
    # analysis. No parallel payment pipeline, no new "receipt" table.

    def generate_monthly_receipts(self, year: int, month: int, actor_id: Optional[int]) -> list:
        """'Beginning of the month, prepare receipts for active leases':
        assigns a receipt_number to every installment due in (year, month)
        for an active contract that doesn't already have one. Manually
        triggered (no scheduler exists in this codebase — see Phase 1),
        the same pattern as the existing maintenance_sweep()/
        run_maintenance_sweep() batch operations."""
        due = self.installment_repo.due_this_month_for_active_contracts(year, month)
        generated = []
        for inst in due:
            if inst.receipt_number:
                continue
            inst.receipt_number = self.installment_repo.next_receipt_number()
            self.audit.log_activity("rental_payment_installment", inst.id, "receipt_generated", f"Receipt {inst.receipt_number} generated for {year}-{month:02d}", actor_id)
            generated.append(inst)
        self.db.commit()
        return generated

    def get_receipt(self, installment_id: int):
        inst = self.installment_repo.get_with_context(installment_id)
        if not inst:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rental receipt not found")
        if not inst.receipt_number:
            # Was a hard 409 block here — receipt_number used to only
            # ever get assigned by the old Rental Receipt Module's
            # monthly batch step (generate_monthly_receipts, reached
            # from RentalReceiptsPage.tsx), which has been unreachable
            # from the sidebar for a long time now. Every installment
            # created the normal way (Auto-Generate on the Payment
            # Schedule tab) was silently missing this field forever, so
            # confirm_payment() — which calls get_receipt() first —
            # was unusable for any installment, on every single
            # contract, no matter what. Self-heals instead: assign one
            # here, lazily, the moment it's actually needed, using the
            # exact same next_receipt_number() the old batch step used.
            inst.receipt_number = self.installment_repo.next_receipt_number()
            self.db.commit()
        return inst

    def get_receipt_document(self, installment_id: int) -> dict:
        """Composes the full printable DTO — the one place that maps the
        Property hierarchy (a "Building" is a Property row; a "Unit" is
        its child via parent_property_id, see Phase 1 analysis) onto the
        Building/Unit fields the approved receipt content requires, and
        computes the amount-in-words in both languages."""
        from app.core.number_to_words import amount_to_words
        from app.repositories.financial_repository import TransactionRepository

        inst = self.get_receipt(installment_id)
        contract = inst.contract
        tenant = contract.tenant if contract else None
        unit = contract.property_ref if contract else None
        building = unit.parent if (unit and unit.parent) else None

        # Payment Method / Reference Number are already synced onto the
        # installment itself by FinancialService.create_transaction()
        # when payment was confirmed (see confirm_payment above) — read
        # them directly rather than duplicating a lookup. Bank Name has
        # nowhere on the installment or Transaction to live (it's a
        # FinancialAccount field), so that one lookup finds the
        # Transaction this payment created, to reach its account's
        # bank_name. All three are None until payment is confirmed — a
        # receipt printed beforehand (this system's normal "generate
        # before payment" workflow) correctly shows this section blank.
        txn = TransactionRepository(self.db).get_by_rental_installment(inst.id)

        return {
            "installment_id": inst.id,
            "receipt_number": inst.receipt_number,
            "receipt_date": date.today(),
            "rental_month": inst.due_date.strftime("%Y-%m"),
            "tenant_name": tenant.display_name if tenant else "",
            "tenant_address": tenant.address if tenant else None,
            "building_name": building.title if building else None,
            "building_number": building.property_code if building else None,
            "unit_name": unit.title if unit else None,
            "unit_number": (unit.unit_number or unit.property_code) if unit else None,
            "amount": inst.total_payable,
            "amount_in_words_en": amount_to_words(inst.total_payable, language="en"),
            "amount_in_words_ar": amount_to_words(inst.total_payable, language="ar"),
            "payment_method": inst.payment_method,
            "bank_name": (txn.account.bank_name if (txn and txn.account and inst.payment_method == "bank_transfer") else None),
            # reference_number doubles as the cheque number when
            # payment_method == "cheque" — same generic field already
            # used for a bank transfer's reference, no separate
            # cheque_number column needed.
            "reference_number": inst.reference_number if inst.payment_method in ("bank_transfer", "cheque") else None,
            "print_count": inst.print_count,
            "printed_at": inst.printed_at,
        }

    def record_print(self, installment_id: int, actor_id: Optional[int]):
        """Called by the frontend right before invoking the browser print
        dialog — tracks the audit trail (created vs reprinted) without
        altering the receipt content or its payment_status in any way."""
        inst = self.get_receipt(installment_id)
        from datetime import datetime
        is_reprint = inst.print_count > 0
        inst.print_count += 1
        inst.printed_at = datetime.utcnow()
        self.audit.log_activity(
            "rental_payment_installment", inst.id,
            "receipt_reprinted" if is_reprint else "receipt_printed",
            f"Receipt {inst.receipt_number} {'reprinted' if is_reprint else 'printed'} (print #{inst.print_count})", actor_id,
        )
        self.db.commit()
        return inst

    def confirm_payment(
        self, installment_id: int, account_id: int, payment_method: str,
        reference_number: Optional[str], transaction_date: date, notes: Optional[str], actor_id: Optional[int],
    ):
        """The ONLY place a rental receipt's payment becomes official —
        reuses FinancialService.create_transaction() completely unchanged
        (property attribution, GL posting, installment-status sync, and
        auto-issuing the existing proof-of-payment Receipt all already
        happen inside it). This method's only job is translating "confirm
        this receipt" into the transaction payload create_transaction
        already understands."""
        inst = self.get_receipt(installment_id)
        if inst.payment_status == "paid":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This receipt has already been confirmed as paid")

        from app.services.financial_service import FinancialService
        from app.models.financial import TransactionType
        financial = FinancialService(self.db)
        txn = financial.create_transaction({
            "transaction_type": TransactionType.TENANT_PAYMENT,
            "amount": inst.total_payable,
            "account_id": account_id,
            "tenant_id": inst.contract.tenant_id,
            "rental_contract_id": inst.contract_id,
            "rental_installment_id": inst.id,
            "payment_method": payment_method,
            "reference_number": reference_number,
            "transaction_date": transaction_date,
            "description": f"Rental receipt {inst.receipt_number} confirmed — {inst.due_date.strftime('%B %Y')}",
        }, actor_id=actor_id)

        if notes:
            inst.notes = notes
        self.audit.log_activity(
            "rental_payment_installment", inst.id, "payment_confirmed",
            f"Receipt {inst.receipt_number} payment confirmed via {payment_method} (txn {txn.transaction_number})", actor_id,
        )
        self.db.commit()
        return self.get_receipt(installment_id), txn.id

    def search_receipts(
        self, params: PaginationParams, receipt_number: Optional[str] = None, tenant_id: Optional[int] = None,
        property_id: Optional[int] = None, rental_month: Optional[str] = None, date_from: Optional[date] = None,
        date_to: Optional[date] = None, payment_method: Optional[str] = None, reference_number: Optional[str] = None,
    ):
        return self.installment_repo.search_receipts(
            params.page, params.page_size, receipt_number, tenant_id, property_id,
            rental_month, date_from, date_to, payment_method, reference_number,
        )
