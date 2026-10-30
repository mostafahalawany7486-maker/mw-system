"""
Pending Rent Slip business logic.

The critical guarantee: printing a slip (get_bulk_print_data /
record_print) NEVER creates a Transaction and NEVER touches
RentVoucher. Only confirm_collection() does — and when it does, it
does so by calling the existing, unmodified FinancialService.create_transaction
and RentVoucherService.generate_vouchers exactly as if a human had
gone to Financial -> Record Transaction and then Rent Vouchers ->
Generate themselves. Nothing about either of those flows is
duplicated or reimplemented here.
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repositories.pending_rent_slip_repository import PendingRentSlipRepository
from app.repositories.tenant_repository import TenantRepository
from app.repositories.property_repository import PropertyRepository
from app.models.pending_rent_slip import PendingRentSlip, PendingRentSlipStatus
from app.models.rent_voucher import VoucherCopyType
from app.schemas.common import PaginationParams
from app.services.audit_service import AuditService
from app.services.financial_service import FinancialService
from app.services.rent_voucher_service import RentVoucherService

ENTITY_TYPE = "pending_rent_slip"

_MONTH_NAMES_EN = ["", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
_MONTH_NAMES_AR = ["", "يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"]


class PendingRentSlipService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = PendingRentSlipRepository(db)
        self.tenant_repo = TenantRepository(db)
        self.property_repo = PropertyRepository(db)
        self.audit = AuditService(db)

    # ---------------- Generation (no Transaction, no RentVoucher touched) ----------------
    def generate_slips(self, rental_month: date, entries: list[dict], actor_id: Optional[int]) -> dict:
        created_slips: list[PendingRentSlip] = []
        created = 0
        already_existed = 0

        for entry in entries:
            tenant_id, property_id, expected_amount = entry["tenant_id"], entry["property_id"], entry["expected_amount"]
            if not self.tenant_repo.get(tenant_id):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid tenant_id: {tenant_id}")
            if not self.property_repo.get(property_id):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid property_id: {property_id}")

            for copy_type in (VoucherCopyType.TENANT, VoucherCopyType.COMPANY):
                existing = self.repo.get_by_tenant_property_month_copy(tenant_id, property_id, rental_month, copy_type)
                if existing:
                    created_slips.append(existing)
                    already_existed += 1
                    continue

                slip_number = self.repo.next_slip_number()
                slip = self.repo.create({
                    "slip_number": slip_number,
                    "tenant_id": tenant_id,
                    "property_id": property_id,
                    "copy_type": copy_type,
                    "rental_month": rental_month,
                    "expected_amount": expected_amount,
                    "barcode_value": f"{slip_number}-{tenant_id}-{property_id}",
                    "slip_status": PendingRentSlipStatus.PENDING,
                }, actor_id=actor_id)
                self.audit.log_activity(ENTITY_TYPE, slip.id, "created", f"Pending rent slip {slip.slip_number} ({copy_type} copy) created for {rental_month}", actor_id)
                created_slips.append(slip)
                created += 1

        self.db.commit()
        ordered_ids = [s.id for s in created_slips]
        return {"slips": self.repo.list_by_ids(ordered_ids), "created_count": created, "already_existed_count": already_existed}

    def list_slips(self, params: PaginationParams, rental_month, slip_status, property_id, building_id):
        return self.repo.list_slips(
            page=params.page, page_size=params.page_size, search=params.search,
            rental_month=rental_month, slip_status=slip_status, property_id=property_id, building_id=building_id,
        )

    def dashboard(self) -> dict:
        return self.repo.dashboard_counts()

    def get_slip(self, slip_id: int) -> PendingRentSlip:
        slip = self.repo.get_detail(slip_id)
        if not slip:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pending rent slip not found")
        return slip

    def cancel_slip(self, slip_id: int, actor_id: Optional[int]) -> PendingRentSlip:
        slip = self.get_slip(slip_id)
        if slip.slip_status != PendingRentSlipStatus.PENDING:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Only pending slips can be cancelled (current: {slip.slip_status})")
        slip.slip_status = PendingRentSlipStatus.CANCELLED
        self.audit.log_activity(ENTITY_TYPE, slip.id, "cancelled", f"Pending rent slip {slip.slip_number} cancelled", actor_id)
        self.db.commit()
        return self.repo.get_detail(slip.id)

    # ---------------- Printing (no Transaction, no RentVoucher touched) ----------------
    def get_print_data(self, slip_id: int) -> dict:
        from app.core.number_to_words import amount_to_words

        slip = self.get_slip(slip_id)
        copy_labels = {
            VoucherCopyType.TENANT: ("TENANT COPY", "نسخة المستأجر"),
            VoucherCopyType.COMPANY: ("COMPANY COPY", "نسخة الشركة"),
        }
        copy_label_en, copy_label_ar = copy_labels.get(slip.copy_type, ("", ""))
        month_idx = slip.rental_month.month
        return {
            "voucher_id": slip.id,
            "voucher_number": slip.slip_number,
            "copy_type": slip.copy_type,
            "copy_type_label_en": copy_label_en,
            "copy_type_label_ar": copy_label_ar,
            "issue_date": date.today(),
            "rental_month_display_en": f"{_MONTH_NAMES_EN[month_idx]} {slip.rental_month.year}",
            "rental_month_display_ar": f"{_MONTH_NAMES_AR[month_idx]} {slip.rental_month.year}",
            "tenant_name": slip.tenant_name or "",
            "tenant_code": slip.tenant_code,
            "tenant_national_id": slip.tenant_national_id,
            "tenant_phone": slip.tenant_phone,
            "tenant_email": slip.tenant_email,
            "building_name": slip.building_name,
            "unit_number": slip.unit_number,
            "unit_paci_number": slip.unit_paci_number,
            "property_address": slip.property_address,
            "amount": slip.amount,
            "currency_code": None,
            "amount_in_words_en": amount_to_words(slip.amount, language="en") if slip.amount is not None else "",
            "amount_in_words_ar": amount_to_words(slip.amount, language="ar") if slip.amount is not None else "",
            "payment_method": slip.payment_method,
            "payment_method_label_en": slip.payment_method_label_en,
            "payment_method_label_ar": slip.payment_method_label_ar,
            "barcode_value": slip.barcode_value,
            "print_count": slip.print_count,
            "printed_at": slip.printed_at,
        }

    def get_bulk_print_data(self, slip_ids: list[int]) -> list[dict]:
        slips = self.repo.list_by_ids(slip_ids)
        found_ids = {s.id for s in slips}
        missing = [i for i in slip_ids if i not in found_ids]
        if missing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Pending rent slip(s) not found: {missing}")
        return [self.get_print_data(s.id) for s in slips]

    def record_print(self, slip_id: int, actor_id: Optional[int]) -> PendingRentSlip:
        slip = self.get_slip(slip_id)
        slip.print_count = (slip.print_count or 0) + 1
        slip.printed_at = datetime.utcnow()
        self.db.commit()
        return self.repo.get_detail(slip.id)

    # ---------------- Confirm collection: the ONLY place this module
    # creates a Transaction or a RentVoucher, and it does so by calling
    # the real, unmodified services — never reimplementing their logic. ----------------
    def confirm_collection(self, slip_id: int, account_id: int, payment_method: str, payment_date: date, reference_number: Optional[str], actor_id: Optional[int]) -> dict:
        anchor = self.get_slip(slip_id)
        if anchor.slip_status != PendingRentSlipStatus.PENDING:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"This slip is already {anchor.slip_status}, not pending")

        pair_slips = [
            self.repo.get_by_tenant_property_month_copy(anchor.tenant_id, anchor.property_id, anchor.rental_month, ct)
            for ct in (VoucherCopyType.TENANT, VoucherCopyType.COMPANY)
        ]
        pair_slips = [s for s in pair_slips if s is not None]
        pending_pair = [s for s in pair_slips if s.slip_status == PendingRentSlipStatus.PENDING]
        if not pending_pair:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No pending slip left for this tenant/property/month")

        # Same real path a human would use from Financial -> Record
        # Transaction — see app/services/financial_service.py, untouched.
        txn = FinancialService(self.db).create_transaction({
            "transaction_type": "tenant_payment",
            "amount": anchor.expected_amount,
            "account_id": account_id,
            "tenant_id": anchor.tenant_id,
            "property_id": anchor.property_id,
            "payment_method": payment_method,
            "reference_number": reference_number,
            "transaction_date": payment_date,
            "description": f"Rent collected for {anchor.rental_month.isoformat()} — confirmed from pending slip {anchor.slip_number}",
        }, actor_id=actor_id)

        for s in pending_pair:
            s.slip_status = PendingRentSlipStatus.COLLECTED
            s.collected_transaction_id = txn.id
            s.collected_at = datetime.utcnow()
            self.audit.log_activity(ENTITY_TYPE, s.id, "collected", f"Pending rent slip {s.slip_number} confirmed collected — transaction {txn.transaction_number}", actor_id)

        self.db.commit()

        # Same real path as Rent Vouchers -> Generate — see
        # app/services/rent_voucher_service.py, untouched.
        vouchers, created_count, _ = RentVoucherService(self.db).generate_vouchers([txn.id], anchor.rental_month, actor_id)

        return {
            "transaction_id": txn.id,
            "transaction_number": txn.transaction_number,
            "voucher_ids": [v.id for v in vouchers],
        }
