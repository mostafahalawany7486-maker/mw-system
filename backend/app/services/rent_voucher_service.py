"""
RentVoucherService

Orchestrates the Rent Voucher lifecycle: generate a Tenant Copy +
Company Copy pair for a rent payment Transaction, produce the bilingual
print-ready DTO, and track print/reprint history — exactly mirroring
the print-tracking pattern already used by
RentalService.record_print / FinancialService.record_invoice_print.

Does not implement or duplicate any payment logic: a voucher can only
be generated for an EXISTING TENANT_PAYMENT Transaction (created
through the existing Financial module, completely unchanged). This
service never creates, edits, or reverses a Transaction.
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.rent_voucher import RentVoucher, VoucherCopyType
from app.models.financial import Transaction, TransactionType
from app.repositories.rent_voucher_repository import RentVoucherRepository
from app.repositories.financial_repository import TransactionRepository
from app.repositories.organization_repository import CurrencyRepository
from app.services.audit_service import AuditService
from app.schemas.common import PaginationParams

ENTITY_TYPE = "rent_voucher"

_MONTH_NAMES_EN = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]
_MONTH_NAMES_AR = [
    "", "يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
    "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر",
]


class RentVoucherService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = RentVoucherRepository(db)
        self.txn_repo = TransactionRepository(db)
        self.currency_repo = CurrencyRepository(db)
        self.audit = AuditService(db)

    # ---------------- Lookups ----------------
    def get_voucher(self, voucher_id: int) -> RentVoucher:
        voucher = self.repo.get_detail(voucher_id)
        if not voucher:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rent voucher not found")
        return voucher

    def get_voucher_by_barcode(self, barcode_value: str) -> RentVoucher:
        """Backs 'quick searching and retrieving the voucher' by
        scanning its barcode — same shape as
        FinancialService.get_invoice_by_qr_token."""
        voucher = self.repo.get_by_barcode(barcode_value)
        if not voucher:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No voucher matches that barcode")
        return voucher

    def list_vouchers(
        self, params: PaginationParams, rental_month: Optional[date], copy_type: Optional[str],
        transaction_id: Optional[int],
    ):
        return self.repo.list_vouchers(
            page=params.page, page_size=params.page_size, rental_month=rental_month, copy_type=copy_type,
            transaction_id=transaction_id, sort_by=params.sort_by, sort_dir=params.sort_dir or "desc",
        )

    # ---------------- Generation ----------------
    def generate_vouchers(
        self, transaction_ids: list[int], rental_month: date, actor_id: Optional[int], combine: bool = False,
    ) -> tuple[list[RentVoucher], int, int]:
        """Generates a Tenant Copy + Company Copy pair for every
        transaction in `transaction_ids`. Idempotent per
        (transaction, copy_type) — the DB unique constraint is the
        final backstop, but this checks first so a partially-generated
        batch (e.g. one transaction already vouchered from a prior run)
        doesn't fail the whole call, matching how
        FinancialService.generate_bulk_invoices never duplicates an
        already-generated period instead of erroring on it.

        combine=True (Combined Voucher extension): instead of one pair
        per transaction, produces exactly ONE pair covering the whole
        list — e.g. a tenant paying several months at once. All listed
        transactions must belong to the same tenant. The first
        transaction becomes the voucher's primary `transaction_id`
        (satisfying the existing UniqueConstraint unchanged); the rest
        are recorded in `extra_transaction_ids` for display only. If a
        combined voucher for that exact primary transaction already
        exists, it's reused rather than duplicated, same idempotency
        guarantee as the non-combined path.

        Returns (vouchers, created_count, already_existed_count).
        """
        if combine:
            return self._generate_combined_pair(transaction_ids, rental_month, actor_id)

        all_vouchers: list[RentVoucher] = []
        created = 0
        already_existed = 0

        for transaction_id in transaction_ids:
            txn = self._get_eligible_transaction(transaction_id)
            for copy_type in (VoucherCopyType.TENANT, VoucherCopyType.COMPANY):
                existing = self.repo.get_by_transaction_and_copy(transaction_id, copy_type)
                if existing:
                    all_vouchers.append(existing)
                    already_existed += 1
                    continue

                voucher_number = self.repo.next_voucher_number()
                voucher = self.repo.create({
                    "voucher_number": voucher_number,
                    "transaction_id": txn.id,
                    "copy_type": copy_type,
                    "rental_month": rental_month,
                    "barcode_value": f"{voucher_number}-{txn.transaction_number}",
                }, actor_id=actor_id)
                self.audit.log_activity(
                    ENTITY_TYPE, voucher.id, "created",
                    f"Rent voucher {voucher.voucher_number} ({copy_type} copy) generated for transaction {txn.transaction_number}",
                    actor_id,
                )
                all_vouchers.append(voucher)
                created += 1

        self.db.commit()
        ordered_ids = [v.id for v in all_vouchers]
        return self.repo.list_by_ids(ordered_ids), created, already_existed

    def _generate_combined_pair(self, transaction_ids: list[int], rental_month: date, actor_id: Optional[int]) -> tuple[list[RentVoucher], int, int]:
        if len(transaction_ids) < 2:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="combine=True needs at least 2 transactions — use the normal path for a single transaction")

        txns = [self._get_eligible_transaction(tid) for tid in transaction_ids]
        tenant_ids = {t.tenant_id for t in txns}
        if len(tenant_ids) > 1:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="All transactions in a combined voucher must belong to the same tenant")

        primary, extras = txns[0], txns[1:]
        total_amount = sum((t.amount for t in txns), Decimal("0"))
        extra_ids_str = ",".join(str(t.id) for t in extras)

        all_vouchers: list[RentVoucher] = []
        created = 0
        already_existed = 0

        for copy_type in (VoucherCopyType.TENANT, VoucherCopyType.COMPANY):
            existing = self.repo.get_by_transaction_and_copy(primary.id, copy_type)
            if existing and existing.extra_transaction_ids == extra_ids_str:
                all_vouchers.append(existing)
                already_existed += 1
                continue
            if existing:
                # A non-combined (or differently-combined) voucher already
                # exists for this primary transaction — same "don't
                # silently overwrite, tell the caller" stance as every
                # other idempotency check in this codebase.
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Transaction {primary.transaction_number} already has a {copy_type} voucher that isn't this same combination — reprint the existing one instead.",
                )

            voucher_number = self.repo.next_voucher_number()
            voucher = self.repo.create({
                "voucher_number": voucher_number,
                "transaction_id": primary.id,
                "copy_type": copy_type,
                "rental_month": rental_month,
                "barcode_value": f"{voucher_number}-{primary.transaction_number}",
                "extra_transaction_ids": extra_ids_str,
                "combined_amount": total_amount,
            }, actor_id=actor_id)
            self.audit.log_activity(
                ENTITY_TYPE, voucher.id, "created",
                f"Combined rent voucher {voucher.voucher_number} ({copy_type} copy) generated for {len(txns)} transactions (total {total_amount})",
                actor_id,
            )
            all_vouchers.append(voucher)
            created += 1

        self.db.commit()
        ordered_ids = [v.id for v in all_vouchers]
        return self.repo.list_by_ids(ordered_ids), created, already_existed

    def _get_eligible_transaction(self, transaction_id: int) -> Transaction:
        txn = self.txn_repo.get(transaction_id)
        if not txn:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid transaction_id: {transaction_id}")
        if txn.transaction_type != TransactionType.TENANT_PAYMENT:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Transaction {txn.transaction_number} is not a tenant rent payment "
                       f"(type: {txn.transaction_type}) — a rent voucher can only be generated for one",
            )
        return txn

    # ---------------- Print DTO ----------------
    def get_voucher_print_data(self, voucher_id: int) -> dict:
        """The bilingual print-ready DTO. See RentVoucherPrintDataOut's
        docstring and docs/rent-voucher-module.md: the frontend renders
        the actual A4 / four-per-page / RTL+LTR layout and calls the
        browser print dialog — this only supplies the data, exactly
        like every other printable document in this codebase already
        does (RentalService.get_receipt_document,
        FinancialService._to_print_dto).
        """
        from app.core.number_to_words import amount_to_words

        voucher = self.get_voucher(voucher_id)
        txn = voucher.transaction

        currency_code = None
        if txn and txn.account and txn.account.currency_id:
            currency = self.currency_repo.get(txn.account.currency_id)
            currency_code = currency.code if currency else None

        copy_labels = {
            VoucherCopyType.TENANT: ("TENANT COPY", "نسخة المستأجر"),
            VoucherCopyType.COMPANY: ("COMPANY COPY", "نسخة الشركة"),
        }
        copy_label_en, copy_label_ar = copy_labels.get(voucher.copy_type, ("", ""))

        month_idx = voucher.rental_month.month
        if voucher.is_combined:
            # Combined Voucher extension: the printed period becomes a
            # range starting at rental_month and spanning as many
            # consecutive months as transactions were combined — the
            # simplest coherent reading of "paid several months at
            # once" without needing per-transaction month tracking that
            # doesn't otherwise exist on Transaction.
            count = voucher.combined_transaction_count
            end_month_idx_raw = voucher.rental_month.month + count - 1
            end_year = voucher.rental_month.year + (end_month_idx_raw - 1) // 12
            end_month_idx = ((end_month_idx_raw - 1) % 12) + 1
            rental_month_en = f"{_MONTH_NAMES_EN[month_idx]} {voucher.rental_month.year} – {_MONTH_NAMES_EN[end_month_idx]} {end_year} ({count} months)"
            rental_month_ar = f"{_MONTH_NAMES_AR[month_idx]} {voucher.rental_month.year} – {_MONTH_NAMES_AR[end_month_idx]} {end_year} ({count} أشهر)"
        else:
            rental_month_en = f"{_MONTH_NAMES_EN[month_idx]} {voucher.rental_month.year}"
            rental_month_ar = f"{_MONTH_NAMES_AR[month_idx]} {voucher.rental_month.year}"

        return {
            "voucher_id": voucher.id,
            "voucher_number": voucher.voucher_number,
            "copy_type": voucher.copy_type,
            "copy_type_label_en": copy_label_en,
            "copy_type_label_ar": copy_label_ar,
            "issue_date": date.today(),
            "rental_month_display_en": rental_month_en,
            "rental_month_display_ar": rental_month_ar,
            "tenant_name": voucher.tenant_name or "",
            "tenant_code": voucher.tenant_code,
            "tenant_national_id": voucher.tenant_national_id,
            "tenant_phone": voucher.tenant_phone,
            "tenant_email": voucher.tenant_email,
            "building_name": voucher.building_name,
            "unit_number": voucher.unit_number,
            "floor_unit_numbers": voucher.floor_unit_numbers,
            "unit_paci_number": voucher.unit_paci_number,
            "property_address": voucher.property_address,
            "amount": voucher.amount,
            "currency_code": currency_code,
            "amount_in_words_en": amount_to_words(voucher.amount, language="en") if voucher.amount is not None else "",
            "amount_in_words_ar": amount_to_words(voucher.amount, language="ar") if voucher.amount is not None else "",
            "payment_method": voucher.payment_method,
            "payment_method_label_en": voucher.payment_method_label_en,
            "payment_method_label_ar": voucher.payment_method_label_ar,
            "barcode_value": voucher.barcode_value,
            "print_count": voucher.print_count,
            "printed_at": voucher.printed_at,
        }

    def get_bulk_print_data(self, voucher_ids: list[int]) -> list[dict]:
        """Batch variant for the four-per-page layout — same
        'validate every id up front' shape as
        FinancialService.get_bulk_print_data."""
        vouchers = self.repo.list_by_ids(voucher_ids)
        found_ids = {v.id for v in vouchers}
        missing = [i for i in voucher_ids if i not in found_ids]
        if missing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Voucher(s) not found: {missing}")
        return [self.get_voucher_print_data(v.id) for v in vouchers]

    # ---------------- Print / reprint tracking ----------------
    def record_print(self, voucher_id: int, actor_id: Optional[int]) -> RentVoucher:
        """Called by the frontend right before invoking the browser
        print dialog — same contract as
        RentalService.record_print / FinancialService.record_invoice_print."""
        voucher = self.repo.get(voucher_id)
        if not voucher:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rent voucher not found")
        is_reprint = voucher.print_count > 0
        voucher.print_count += 1
        voucher.printed_at = datetime.utcnow()
        self.audit.log_activity(
            ENTITY_TYPE, voucher.id, "reprinted" if is_reprint else "printed",
            f"Rent voucher {voucher.voucher_number} {'reprinted' if is_reprint else 'printed'} (print #{voucher.print_count})",
            actor_id,
        )
        self.db.commit()
        return self.get_voucher(voucher_id)
