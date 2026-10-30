from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repositories.financial_repository import (
    FinancialAccountRepository, TransactionRepository, ReceiptRepository, InvoiceRepository, OutstandingBalanceRepository,
)
from app.repositories.tenant_repository import TenantRepository
from app.repositories.owner_repository import OwnerRepository
from app.repositories.rental_repository import RentalInstallmentRepository
from app.repositories.lease_repository import LeasePaymentInstallmentRepository
from app.models.financial import Transaction, TransactionType, TransactionDirection, InvoiceStatus, Invoice
from app.schemas.common import PaginationParams
from app.services.audit_service import AuditService

ENTITY_TYPE_TXN = "transaction"
ENTITY_TYPE_INV = "invoice"
ENTITY_TYPE_ACC = "financial_account"

RECEIPT_ELIGIBLE_TYPES = {TransactionType.TENANT_PAYMENT, TransactionType.OWNER_PAYMENT}


class FinancialAccountService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = FinancialAccountRepository(db)
        self.audit = AuditService(db)

    def _attach_balance(self, account):
        account.current_balance = self.repo.current_balance(account.id)
        return account

    def list_accounts(self, params: PaginationParams):
        items, total = self.repo.list(page=params.page, page_size=params.page_size, search=params.search, search_fields=["name", "account_code"])
        items = [self._attach_balance(a) for a in items]
        return items, total

    def get_account(self, account_id: int):
        account = self.repo.get(account_id)
        if not account:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
        return self._attach_balance(account)

    def create_account(self, data: dict, actor_id: Optional[int]):
        payload = dict(data)
        payload["account_code"] = self.repo.next_account_code()
        account = self.repo.create(payload, actor_id=actor_id)
        self.audit.log_activity(ENTITY_TYPE_ACC, account.id, "created", f"Account {account.account_code} ({account.name}) created", actor_id)
        self.db.commit()
        return self._attach_balance(account)

    def update_account(self, account_id: int, data: dict, actor_id: Optional[int]):
        account = self.repo.get(account_id)
        if not account:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
        self.repo.update(account, data, actor_id=actor_id)
        self.audit.log_activity(ENTITY_TYPE_ACC, account.id, "updated", f"Account {account.account_code} updated", actor_id)
        self.db.commit()
        return self._attach_balance(account)

    def delete_account(self, account_id: int, actor_id: Optional[int]):
        account = self.repo.get(account_id)
        if not account:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
        balance = self.repo.current_balance(account_id)
        if balance != 0:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cannot delete an account with a non-zero balance. Transfer the funds out first.")
        self.repo.soft_delete(account, actor_id=actor_id)
        self.audit.log_activity(ENTITY_TYPE_ACC, account.id, "deleted", f"Account {account.account_code} deleted", actor_id)
        self.db.commit()


class FinancialService:
    def __init__(self, db: Session):
        self.db = db
        self.account_repo = FinancialAccountRepository(db)
        self.txn_repo = TransactionRepository(db)
        self.receipt_repo = ReceiptRepository(db)
        self.invoice_repo = InvoiceRepository(db)
        self.balance_repo = OutstandingBalanceRepository(db)
        self.tenant_repo = TenantRepository(db)
        self.owner_repo = OwnerRepository(db)
        self.rental_installment_repo = RentalInstallmentRepository(db)
        self.lease_installment_repo = LeasePaymentInstallmentRepository(db)
        self.audit = AuditService(db)

    def _attach_transaction_extras(self, txn: Transaction):
        txn.account_name = txn.account.name if txn.account else None
        if txn.receipt:
            txn.receipt_number = txn.receipt.receipt_number
            txn.receipt_id = txn.receipt.id
        elif txn.rental_installment_id:
            # No financial-ledger Receipt exists for this one by design
            # (see create_transaction) — its receipt is the Rental
            # Receipt Module's RR-xxx document instead, which has its
            # own print flow (GET /rentals/installments/{id}/receipt) —
            # receipt_id stays unset here on purpose so the generic
            # "Print Receipt" link doesn't show for these.
            inst = self.rental_installment_repo.get(txn.rental_installment_id)
            txn.receipt_number = inst.receipt_number if inst else None
            txn.receipt_id = None
        else:
            txn.receipt_number = None
            txn.receipt_id = None
        return txn

    # ---------------- Transactions ----------------
    def list_transactions(self, params: PaginationParams, transaction_type, account_id, tenant_id, owner_id, date_from, date_to, property_id=None, building_id=None):
        property_ids = None
        if building_id:
            from app.repositories.property_repository import PropertyRepository
            property_ids = [building_id] + PropertyRepository(self.db).get_unit_ids(building_id)
        items, total = self.txn_repo.list_transactions(
            page=params.page, page_size=params.page_size, search=params.search, transaction_type=transaction_type,
            account_id=account_id, tenant_id=tenant_id, owner_id=owner_id, date_from=date_from, date_to=date_to,
            sort_dir=params.sort_dir or "desc", property_id=property_id, property_ids=property_ids,
        )
        items = [self._attach_transaction_extras(t) for t in items]
        return items, total

    def get_transaction(self, transaction_id: int) -> Transaction:
        txn = self.txn_repo.get_detail(transaction_id)
        if not txn:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
        return self._attach_transaction_extras(txn)

    def create_transaction(self, data: dict, actor_id: Optional[int]) -> Transaction:
        account = self.account_repo.get(data["account_id"])
        if not account:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid account_id")

        if data.get("tenant_id"):
            if not self.tenant_repo.get(data["tenant_id"]):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid tenant_id")
        if data.get("owner_id"):
            if not self.owner_repo.get(data["owner_id"]):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid owner_id")
        if data.get("rental_installment_id"):
            if not self.rental_installment_repo.get(data["rental_installment_id"]):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid rental_installment_id")
        if data.get("lease_installment_id"):
            if not self.lease_installment_repo.get(data["lease_installment_id"]):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid lease_installment_id")

        # Every financial transaction should resolve to a Property (profit
        # center). If property_id wasn't given directly, derive it from
        # whichever contract the transaction is linked to — one extra,
        # cheap lookup rather than leaving the transaction unattributed.
        if not data.get("property_id"):
            if data.get("rental_contract_id"):
                from app.repositories.rental_repository import RentalContractRepository
                contract = RentalContractRepository(self.db).get(data["rental_contract_id"])
                if contract:
                    data["property_id"] = contract.property_id
            elif data.get("lease_agreement_id"):
                from app.repositories.lease_repository import LeaseRepository
                lease = LeaseRepository(self.db).get(data["lease_agreement_id"])
                if lease and lease.property_id:
                    data["property_id"] = lease.property_id

        payload = dict(data)
        payload["transaction_number"] = self.txn_repo.next_transaction_number()
        payload["direction"] = TransactionDirection.OUT if payload["transaction_type"] in TransactionType.OUTFLOW_TYPES else TransactionDirection.IN
        txn = self.txn_repo.create(payload, actor_id=actor_id)

        # Sync with the underlying installment, if linked — one source of truth
        # rather than two disconnected ledgers (Phase 3 / Phase 7 + Phase 8).
        if payload.get("rental_installment_id"):
            inst = self.rental_installment_repo.get(payload["rental_installment_id"])
            if inst:
                inst.payment_status = "paid"
                inst.paid_date = payload["transaction_date"]
                inst.payment_method = payload.get("payment_method")
                inst.reference_number = payload.get("reference_number")
        if payload.get("lease_installment_id"):
            inst = self.lease_installment_repo.get(payload["lease_installment_id"])
            if inst:
                inst.payment_status = "paid"
                inst.paid_date = payload["transaction_date"]
                inst.payment_method = payload.get("payment_method")
                inst.reference_number = payload.get("reference_number")

        # Auto-issue a receipt for payments received/paid out — EXCEPT
        # when this transaction is a rental installment payment
        # (rental_installment_id set). That payment's receipt already
        # exists: the Rental Receipt Module's RR-xxx document
        # (RentalPaymentInstallment.receipt_number), which is the one
        # actually printed/letterheaded/audited. Auto-issuing a second,
        # never-printed RCP-xxx receipt for the same real-world payment
        # would be exactly the duplicate-numbering the Receipt Module
        # Cleanup phase forbids. Owner payouts and Rent Billing Engine
        # invoice payments have no receipt of their own, so they're
        # unaffected and still get one here as before.
        if txn.transaction_type in RECEIPT_ELIGIBLE_TYPES and not payload.get("rental_installment_id"):
            self.receipt_repo.create({
                "receipt_number": self.receipt_repo.next_receipt_number(),
                "transaction_id": txn.id,
                "issued_date": payload["transaction_date"],
            }, actor_id=actor_id)

        # Phase 10: automatic GL posting. Wrapped so a missing/misconfigured
        # posting rule never blocks the underlying financial transaction —
        # it just means no journal entry exists yet for this one.
        try:
            from app.services.accounting_service import JournalEntryService
            JournalEntryService(self.db).auto_post_from_transaction(txn, actor_id=actor_id)
        except Exception:
            pass

        self.audit.log_activity(ENTITY_TYPE_TXN, txn.id, "created", f"Transaction {txn.transaction_number} ({txn.transaction_type}) recorded: {txn.amount}", actor_id)
        self.db.commit()
        return self.get_transaction(txn.id)

    def update_transaction(self, transaction_id: int, data: dict, actor_id: Optional[int]) -> Transaction:
        txn = self.txn_repo.get(transaction_id)
        if not txn:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
        self.txn_repo.update(txn, data, actor_id=actor_id)
        if data.get("transaction_status") == "cancelled":
            self.audit.log_activity(ENTITY_TYPE_TXN, txn.id, "cancelled", f"Transaction {txn.transaction_number} cancelled", actor_id)
        self.db.commit()
        return self.get_transaction(txn.id)

    def delete_transaction(self, transaction_id: int, actor_id: Optional[int]):
        txn = self.txn_repo.get(transaction_id)
        if not txn:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
        try:
            from app.services.accounting_service import JournalEntryService
            if JournalEntryService(self.db).has_posted_entry_for_transaction(transaction_id):
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This transaction has a posted journal entry. Reverse the journal entry first before deleting.")
        except HTTPException:
            raise
        except Exception:
            pass
        self.txn_repo.soft_delete(txn, actor_id=actor_id)
        self.audit.log_activity(ENTITY_TYPE_TXN, txn.id, "deleted", f"Transaction {txn.transaction_number} deleted", actor_id)
        self.db.commit()

    # ---------------- Transfers ----------------
    def create_transfer(self, data: dict, actor_id: Optional[int]):
        from_account = self.account_repo.get(data["from_account_id"])
        to_account = self.account_repo.get(data["to_account_id"])
        if not from_account:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid from_account_id")
        if not to_account:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid to_account_id")

        balance = self.account_repo.current_balance(from_account.id)
        if balance < data["amount"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Insufficient balance in source account (available: {balance})")

        out_txn = self.txn_repo.create({
            "transaction_number": self.txn_repo.next_transaction_number(),
            "transaction_type": TransactionType.TRANSFER_OUT,
            "direction": TransactionDirection.OUT,
            "amount": data["amount"],
            "account_id": from_account.id,
            "transaction_date": data["transaction_date"],
            "reference_number": data.get("reference_number"),
            "description": data.get("description") or f"Transfer to {to_account.name}",
        }, actor_id=actor_id)

        in_txn = self.txn_repo.create({
            "transaction_number": self.txn_repo.next_transaction_number(),
            "transaction_type": TransactionType.TRANSFER_IN,
            "direction": TransactionDirection.IN,
            "amount": data["amount"],
            "account_id": to_account.id,
            "transfer_pair_id": out_txn.id,
            "transaction_date": data["transaction_date"],
            "reference_number": data.get("reference_number"),
            "description": data.get("description") or f"Transfer from {from_account.name}",
        }, actor_id=actor_id)

        out_txn.transfer_pair_id = in_txn.id

        try:
            from app.services.accounting_service import JournalEntryService
            JournalEntryService(self.db).auto_post_transfer(out_txn, in_txn, actor_id=actor_id)
        except Exception:
            pass

        self.audit.log_activity(ENTITY_TYPE_TXN, out_txn.id, "transfer", f"Transferred {data['amount']} from {from_account.name} to {to_account.name}", actor_id)
        self.db.commit()
        return {"out_transaction": self.get_transaction(out_txn.id), "in_transaction": self.get_transaction(in_txn.id)}

    # ---------------- Receipts ----------------
    def list_receipts(self, params: PaginationParams):
        return self.receipt_repo.list_all(page=params.page, page_size=params.page_size)

    def get_receipt(self, receipt_id: int):
        receipt = self.receipt_repo.get_detail(receipt_id)
        if not receipt:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receipt not found")
        self._attach_transaction_extras(receipt.transaction)
        return receipt

    def get_receipt_print_data(self, receipt_id: int) -> dict:
        """A signed, printable receipt for ANY receipt-eligible
        transaction (tenant_payment or owner_payment) — the generic
        counterpart to the Rent Voucher module, for the case raised
        directly: an Owner Payment had no printable document at all,
        just an internal RCP-xxx reference with nothing to hand the
        owner to sign. Reuses the same amount_to_words() helper the
        Rent Voucher print data already uses (app/core/number_to_words.py)
        rather than duplicating that logic.
        """
        from app.core.number_to_words import amount_to_words

        receipt = self.get_receipt(receipt_id)
        txn = receipt.transaction
        is_owner_payment = txn.transaction_type == "owner_payment"
        party_name = txn.owner_display_name if is_owner_payment else txn.tenant_display_name

        currency_code = None
        txn_orm = self.txn_repo.get(receipt.transaction_id)
        if txn_orm and txn_orm.account and txn_orm.account.currency_id:
            from app.repositories.organization_repository import CurrencyRepository
            currency = CurrencyRepository(self.db).get(txn_orm.account.currency_id)
            currency_code = currency.code if currency else None

        return {
            "receipt_id": receipt.id,
            "receipt_number": receipt.receipt_number,
            "transaction_number": txn.transaction_number,
            "transaction_type": txn.transaction_type,
            "issue_date": receipt.issued_date,
            "party_label_en": "Owner" if is_owner_payment else "Tenant",
            "party_label_ar": "المالك" if is_owner_payment else "المستأجر",
            "party_name": party_name,
            "direction_label_en": "Paid To" if is_owner_payment else "Received From",
            "direction_label_ar": "دُفع إلى" if is_owner_payment else "استُلم من",
            "property_title": txn.property_title,
            "unit_number": txn.unit_number,
            "amount": txn.amount,
            "currency_code": currency_code,
            "amount_in_words_en": amount_to_words(txn.amount, language="en"),
            "amount_in_words_ar": amount_to_words(txn.amount, language="ar"),
            "payment_method": txn.payment_method,
            "reference_number": txn.reference_number,
            "account_name": txn.account_name,
            "description": txn.description,
            "print_count": receipt.print_count,
        }

    def record_receipt_print(self, receipt_id: int, actor_id: Optional[int]):
        receipt = self.receipt_repo.get(receipt_id)
        if not receipt:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receipt not found")
        receipt.print_count = (receipt.print_count or 0) + 1
        receipt.printed_at = datetime.utcnow()
        self.db.commit()
        return self.get_receipt(receipt_id)

    # ---------------- Invoices ----------------
    def list_invoices(self, params: PaginationParams, invoice_status, tenant_id):
        items, total = self.invoice_repo.list_invoices(page=params.page, page_size=params.page_size, search=params.search, invoice_status=invoice_status, tenant_id=tenant_id)
        items = [self._attach_invoice_extras(i) for i in items]
        return items, total

    def _attach_invoice_extras(self, invoice):
        return invoice

    def get_invoice(self, invoice_id: int):
        invoice = self.invoice_repo.get_detail(invoice_id)
        if not invoice:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
        return self._attach_invoice_extras(invoice)

    def create_invoice(self, data: dict, actor_id: Optional[int]):
        if not self.tenant_repo.get(data["tenant_id"]):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid tenant_id")
        # Every invoice should resolve to a Property (profit center) —
        # derive it from the linked rental contract when not given directly.
        if not data.get("property_id") and data.get("rental_contract_id"):
            from app.repositories.rental_repository import RentalContractRepository
            contract = RentalContractRepository(self.db).get(data["rental_contract_id"])
            if contract:
                data["property_id"] = contract.property_id
        payload = dict(data)
        payload["invoice_number"] = self.invoice_repo.next_invoice_number()
        payload["invoice_status"] = InvoiceStatus.DRAFT
        invoice = self.invoice_repo.create(payload, actor_id=actor_id)
        self.audit.log_activity(ENTITY_TYPE_INV, invoice.id, "created", f"Invoice {invoice.invoice_number} created", actor_id)
        self.db.commit()
        return self.get_invoice(invoice.id)

    def update_invoice(self, invoice_id: int, data: dict, actor_id: Optional[int]):
        invoice = self.invoice_repo.get(invoice_id)
        if not invoice:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
        if invoice.invoice_status in (InvoiceStatus.PAID, InvoiceStatus.CANCELLED):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Cannot edit a {invoice.invoice_status} invoice")
        self.invoice_repo.update(invoice, data, actor_id=actor_id)
        self.db.commit()
        return self.get_invoice(invoice.id)

    def send_invoice(self, invoice_id: int, actor_id: Optional[int]):
        invoice = self.invoice_repo.get(invoice_id)
        if not invoice:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
        if invoice.invoice_status != InvoiceStatus.DRAFT:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Only draft invoices can be sent (current: {invoice.invoice_status})")
        invoice.invoice_status = InvoiceStatus.SENT
        self.audit.log_activity(ENTITY_TYPE_INV, invoice.id, "sent", f"Invoice {invoice.invoice_number} sent", actor_id)
        self.db.commit()
        return self.get_invoice(invoice.id)

    def cancel_invoice(self, invoice_id: int, actor_id: Optional[int], reason: Optional[str] = None):
        invoice = self.invoice_repo.get(invoice_id)
        if not invoice:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
        if invoice.invoice_status == InvoiceStatus.PAID:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cannot cancel a paid invoice")
        invoice.invoice_status = InvoiceStatus.CANCELLED
        invoice.void_reason = reason
        self.audit.log_activity(ENTITY_TYPE_INV, invoice.id, "cancelled", f"Invoice {invoice.invoice_number} cancelled" + (f" — {reason}" if reason else ""), actor_id)
        self.db.commit()
        return self.get_invoice(invoice.id)

    def void_invoice(self, invoice_id: int, reason: str, actor_id: Optional[int]):
        """Distinct from cancel: per spec, invoices are never deleted,
        only voided or cancelled. Void is for invoices that should never
        have been issued at all (e.g. generated in error) — still fully
        auditable, still permanently on record, just marked as not a
        valid billing document."""
        invoice = self.invoice_repo.get(invoice_id)
        if not invoice:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
        if invoice.invoice_status == InvoiceStatus.PAID:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cannot void a paid invoice")
        if not reason or not reason.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A reason is required to void an invoice")
        invoice.invoice_status = InvoiceStatus.VOID
        invoice.void_reason = reason
        invoice.voided_at = datetime.utcnow()
        self.audit.log_activity(ENTITY_TYPE_INV, invoice.id, "voided", f"Invoice {invoice.invoice_number} voided — {reason}", actor_id)
        self.db.commit()
        return self.get_invoice(invoice.id)

    def record_invoice_print(self, invoice_id: int, actor_id: Optional[int]):
        invoice = self.invoice_repo.get(invoice_id)
        if not invoice:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
        is_reprint = invoice.print_count > 0
        invoice.print_count += 1
        invoice.printed_at = datetime.utcnow()
        self.audit.log_activity(
            ENTITY_TYPE_INV, invoice.id, "reprinted" if is_reprint else "printed",
            f"Invoice {invoice.invoice_number} {'reprinted' if is_reprint else 'printed'} (print #{invoice.print_count})", actor_id,
        )
        self.db.commit()
        return self.get_invoice(invoice.id)

    def mark_invoice_delivered(self, invoice_id: int, actor_id: Optional[int]):
        invoice = self.invoice_repo.get(invoice_id)
        if not invoice:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
        invoice.delivered_at = datetime.utcnow()
        self.audit.log_activity(ENTITY_TYPE_INV, invoice.id, "delivered", f"Invoice {invoice.invoice_number} marked delivered", actor_id)
        self.db.commit()
        return self.get_invoice(invoice.id)

    def record_invoice_payment(
        self, invoice_id: int, account_id: int, payment_method: Optional[str], reference_number: Optional[str],
        transaction_date: date, actor_id: Optional[int], amount: Optional[Decimal] = None,
    ):
        invoice = self.invoice_repo.get(invoice_id)
        if not invoice:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
        if invoice.invoice_status not in (InvoiceStatus.SENT, InvoiceStatus.OVERDUE, InvoiceStatus.PARTIALLY_PAID):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Only sent, overdue, or partially paid invoices can be paid (current: {invoice.invoice_status})")

        # amount defaults to the full outstanding balance — existing
        # callers that don't pass it get byte-identical behavior to
        # before partial-payment support was added (outstanding_amount
        # == invoice.amount for any invoice that hasn't been partially
        # paid yet, which was the only case this method used to allow).
        pay_amount = amount if amount is not None else invoice.outstanding_amount
        if pay_amount <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Payment amount must be greater than zero")
        if pay_amount > invoice.outstanding_amount:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Payment amount ({pay_amount}) exceeds outstanding balance ({invoice.outstanding_amount})")

        # If this invoice was generated by the Rent Cycle Engine, it has
        # a sibling RentalPaymentInstallment for the exact same period
        # (RentCycleRecord links both) — the old schedule that
        # RentalService.run_maintenance_sweep's late-fee assessment
        # still reads. Paying the invoice through this (newer) path
        # must mark that installment paid too, or it goes stale and
        # accrues late fees for rent that was actually collected. See
        # docs/payment-collection-engine.md.
        from app.repositories.rent_cycle_repository import RentCycleRecordRepository
        linked_record = RentCycleRecordRepository(self.db).get_by_invoice_id(invoice_id)
        rental_installment_id = linked_record.installment_id if linked_record and pay_amount >= invoice.outstanding_amount else None

        txn = self.create_transaction({
            "transaction_type": TransactionType.TENANT_PAYMENT,
            "amount": pay_amount,
            "account_id": account_id,
            "tenant_id": invoice.tenant_id,
            "rental_contract_id": invoice.rental_contract_id,
            "rental_installment_id": rental_installment_id,
            "payment_method": payment_method,
            "reference_number": reference_number,
            "transaction_date": transaction_date,
            "description": f"Payment for invoice {invoice.invoice_number}",
        }, actor_id=actor_id)

        # create_transaction() already auto-issued a Receipt for this
        # transaction (RECEIPT_ELIGIBLE_TYPES) — link it back to this
        # invoice rather than duplicating receipt-creation logic here.
        receipt = self.receipt_repo.get_by_transaction(txn.id)
        if receipt:
            receipt.invoice_id = invoice.id

        invoice.amount_paid += pay_amount
        invoice.invoice_status = InvoiceStatus.PAID if invoice.amount_paid >= invoice.amount else InvoiceStatus.PARTIALLY_PAID
        invoice.paid_transaction_id = txn.id
        self.audit.log_activity(
            ENTITY_TYPE_INV, invoice.id, "paid" if invoice.invoice_status == InvoiceStatus.PAID else "partially_paid",
            f"Invoice {invoice.invoice_number} — {pay_amount} paid via {txn.transaction_number} (status: {invoice.invoice_status})", actor_id,
        )
        self.db.commit()
        return self.get_invoice(invoice.id)

    def maintenance_sweep(self, actor_id: Optional[int] = None) -> dict:
        overdue_count = self.invoice_repo.mark_overdue_sweep()
        self.db.commit()
        return {"invoices_marked_overdue": overdue_count}

    # ---------------- Outstanding Balances & Dashboard ----------------
    def outstanding_balances(self) -> dict:
        tenants = self.balance_repo.tenant_outstanding()
        owners = self.balance_repo.owner_outstanding()
        return {
            "tenants": tenants,
            "owners": owners,
            "total_tenant_outstanding": sum((t["outstanding_amount"] for t in tenants), Decimal("0")),
            "total_owner_outstanding": sum((o["outstanding_amount"] for o in owners), Decimal("0")),
        }

    def dashboard(self) -> dict:
        accounts = self.account_repo.list_active()
        cash_total = Decimal("0")
        bank_total = Decimal("0")
        account_outs = []
        for a in accounts:
            balance = self.account_repo.current_balance(a.id)
            a.current_balance = balance
            account_outs.append(a)
            if a.account_type == "cash":
                cash_total += balance
            else:
                bank_total += balance

        today = date.today()
        income, expense = self.txn_repo.monthly_totals(today.year, today.month)

        balances = self.outstanding_balances()

        # Rent Billing Engine widgets — additive to the existing
        # dashboard payload, computed directly from Invoice rather than
        # duplicating outstanding_balances()'s tenant/owner ledger logic.
        from app.models.financial import Invoice
        from sqlalchemy import select, func as sa_func
        invoices_generated = self.db.execute(
            select(sa_func.count()).select_from(Invoice).where(Invoice.deleted_at.is_(None), Invoice.issue_date >= today.replace(day=1))
        ).scalar_one()
        invoices_paid = self.db.execute(
            select(sa_func.count()).select_from(Invoice).where(
                Invoice.deleted_at.is_(None), Invoice.invoice_status == InvoiceStatus.PAID, Invoice.issue_date >= today.replace(day=1),
            )
        ).scalar_one()
        due_today = self.db.execute(
            select(sa_func.count()).select_from(Invoice).where(
                Invoice.deleted_at.is_(None), Invoice.due_date == today,
                Invoice.invoice_status.in_([InvoiceStatus.SENT, InvoiceStatus.PARTIALLY_PAID]),
            )
        ).scalar_one()
        overdue_amount_row = self.db.execute(
            select(sa_func.coalesce(sa_func.sum(Invoice.amount - Invoice.amount_paid), 0)).select_from(Invoice).where(
                Invoice.deleted_at.is_(None), Invoice.invoice_status.in_([InvoiceStatus.SENT, InvoiceStatus.PARTIALLY_PAID, InvoiceStatus.OVERDUE]),
                Invoice.due_date < today,
            )
        ).scalar_one()
        month_billed_row = self.db.execute(
            select(sa_func.coalesce(sa_func.sum(Invoice.amount), 0)).select_from(Invoice).where(
                Invoice.deleted_at.is_(None), Invoice.issue_date >= today.replace(day=1),
            )
        ).scalar_one()
        month_collected_row = self.db.execute(
            select(sa_func.coalesce(sa_func.sum(Invoice.amount_paid), 0)).select_from(Invoice).where(
                Invoice.deleted_at.is_(None), Invoice.issue_date >= today.replace(day=1),
            )
        ).scalar_one()
        collection_rate = float(month_collected_row / month_billed_row * 100) if month_billed_row else 0.0

        top_debtor_rows = self.db.execute(
            select(Invoice.tenant_id, sa_func.sum(Invoice.amount - Invoice.amount_paid).label("outstanding"))
            .where(Invoice.deleted_at.is_(None), Invoice.invoice_status.in_([InvoiceStatus.SENT, InvoiceStatus.PARTIALLY_PAID, InvoiceStatus.OVERDUE]))
            .group_by(Invoice.tenant_id).order_by(sa_func.sum(Invoice.amount - Invoice.amount_paid).desc()).limit(5)
        ).all()
        top_debtors = []
        for tenant_id, outstanding in top_debtor_rows:
            tenant = self.tenant_repo.get(tenant_id)
            if tenant and outstanding > 0:
                top_debtors.append({"tenant_id": tenant_id, "tenant_display_name": tenant.display_name, "outstanding_amount": outstanding})

        return {
            "total_cash_balance": cash_total,
            "total_bank_balance": bank_total,
            "total_income_this_month": income,
            "total_expense_this_month": expense,
            "total_tenant_outstanding": balances["total_tenant_outstanding"],
            "total_owner_outstanding": balances["total_owner_outstanding"],
            "accounts": account_outs,
            "invoices_generated_this_month": invoices_generated,
            "invoices_paid_this_month": invoices_paid,
            "invoices_due_today": due_today,
            "total_overdue_invoice_amount": overdue_amount_row,
            "collection_rate_percentage": round(collection_rate, 2),
            "top_debtors": top_debtors,
        }

    # ==================== Rent Billing Engine ====================
    @staticmethod
    def _compute_period_end(start: date, billing_cycle: str, custom_days: Optional[int] = None) -> date:
        """The billing engine is deliberately not hardcoded to monthly —
        every contract already carries its own payment_frequency
        (RentalPaymentFrequency: monthly/quarterly/semi_annual/annual/
        one_time/custom), and this is the one place that turns "a start
        date + a cycle" into the actual period end, for whichever cycle
        a given contract happens to use."""
        from dateutil.relativedelta import relativedelta
        if billing_cycle == "quarterly":
            return start + relativedelta(months=3, days=-1)
        if billing_cycle == "semi_annual":
            return start + relativedelta(months=6, days=-1)
        if billing_cycle == "annual":
            return start + relativedelta(years=1, days=-1)
        if billing_cycle == "custom":
            return start + relativedelta(days=(custom_days or 30) - 1)
        if billing_cycle == "one_time":
            return start
        return start + relativedelta(months=1, days=-1)  # monthly (default)

    def _build_invoice_snapshot(self, contract, tenant, property_ref) -> dict:
        """Freezes everything the spec requires at generation time —
        tenant, property/building/unit, contract, rent/fees/taxes/
        discount, and company info — into one JSON blob on the invoice
        row itself, so it stays correct forever even if any of the
        source records change or are later deleted. This is the
        "data snapshot" requirement; deliberately a JSON column rather
        than a dozen new denormalized invoice columns."""
        from app.repositories.organization_repository import CompanyProfileRepository
        building = property_ref.parent if (property_ref and property_ref.parent) else None
        company = CompanyProfileRepository(self.db).get_active()

        return {
            "tenant_name": tenant.display_name if tenant else None,
            "tenant_address": getattr(tenant, "address", None),
            "tenant_civil_id": getattr(tenant, "national_id", None),
            "tenant_phone": getattr(tenant, "primary_phone", None),
            "tenant_email": getattr(tenant, "email", None),
            "property_title": property_ref.title if property_ref else None,
            "property_code": property_ref.property_code if property_ref else None,
            "unit_number": (property_ref.unit_number or property_ref.property_code) if property_ref else None,
            "building_name": building.title if building else None,
            "building_number": building.property_code if building else None,
            "contract_number": contract.contract_number if contract else None,
            "rent_amount": str(contract.rent_amount) if contract else None,
            "discount_type": contract.discount_type if contract else None,
            "discount_value": str(contract.discount_value) if contract else None,
            "discount_reason": contract.discount_reason if contract else None,
            "tax_rate": str(contract.tax_rate) if contract else None,
            "company_name": company.legal_name if company else None,
            "company_logo_url": company.logo_url if company else None,
            "company_address": " ".join(filter(None, [company.address_line1, company.address_line2])) if company else None,
            "company_phone": company.phone if company else None,
            "company_email": company.email if company else None,
            "company_website": company.website if company else None,
        }

    def generate_bulk_invoices(
        self, billing_period_start: date, property_ids: Optional[list[int]], actor_id: Optional[int],
    ) -> list[Invoice]:
        """'At the beginning of every billing cycle, automatically
        generate invoices' — manually triggered (no scheduler exists in
        this codebase, same documented decision as the Rental Receipt
        Module's monthly generation). Never generates a duplicate: each
        (contract, billing_period_start) pair is checked before creating
        anything. Each contract's OWN payment_frequency determines its
        invoice's period length, so a mix of monthly and annual leases
        billed in the same run each get the correct period automatically."""
        import uuid
        from app.repositories.rental_repository import RentalContractRepository

        contracts = RentalContractRepository(self.db).list_active_for_billing(property_ids, as_of=billing_period_start)
        generated = []
        for contract in contracts:
            if self.invoice_repo.exists_for_period(contract.id, billing_period_start):
                continue

            period_end = self._compute_period_end(billing_period_start, contract.payment_frequency)
            gross = contract.rent_amount
            if contract.discount_type == "percentage":
                discount = (gross * contract.discount_value / Decimal("100")).quantize(Decimal("0.01"))
            elif contract.discount_type == "fixed":
                discount = contract.discount_value
            else:
                discount = Decimal("0")
            taxable = gross - discount
            tax = (taxable * contract.tax_rate / Decimal("100")).quantize(Decimal("0.01")) if contract.tax_rate else Decimal("0")
            total = taxable + tax

            snapshot = self._build_invoice_snapshot(contract, contract.tenant, contract.property_ref)
            invoice = self.invoice_repo.create({
                "invoice_number": self.invoice_repo.next_invoice_number(),
                "tenant_id": contract.tenant_id,
                "rental_contract_id": contract.id,
                "property_id": contract.property_id,
                "amount": total,
                "issue_date": date.today(),
                "due_date": billing_period_start + timedelta(days=15),
                # Rent Cycle Engine invoices go straight to SENT, not
                # DRAFT — this bulk path exists specifically for "the
                # monthly rent collection cycle... generates invoices
                # and receipts for every active lease, then tracks
                # collection through to close" (Rent Cycle page's own
                # description). A DRAFT invoice can't be paid against
                # (see PaymentsPage.tsx's outstanding-invoice filter),
                # and nothing in the Rent Cycle pipeline ever calls
                # send_invoice() — so every cycle-generated invoice was
                # silently stuck, permanently unpayable, until someone
                # manually visited Financial > Invoices and sent each
                # one by hand, a step this pipeline never told anyone
                # to do. The single manual invoice endpoint
                # (POST /financial/invoices) still creates DRAFT
                # invoices unchanged — that's a genuinely different,
                # deliberate "create and review before sending" use
                # case this fix does not touch.
                "invoice_status": InvoiceStatus.SENT,
                "description": f"Rent for {billing_period_start.strftime('%B %Y')}" if contract.payment_frequency == "monthly" else f"Rent for {billing_period_start.isoformat()} to {period_end.isoformat()}",
                "billing_cycle": contract.payment_frequency,
                "billing_period_start": billing_period_start,
                "billing_period_end": period_end,
                "snapshot": snapshot,
                "qr_token": str(uuid.uuid4()),
            }, actor_id=actor_id)
            self.audit.log_activity(ENTITY_TYPE_INV, invoice.id, "created", f"Invoice {invoice.invoice_number} generated for billing period {billing_period_start} to {period_end}", actor_id)
            generated.append(invoice)

        self.db.commit()
        return [self.get_invoice(i.id) for i in generated]

    def approve_invoices(self, invoice_ids: list[int], actor_id: Optional[int]) -> list[Invoice]:
        """Bulk 'Invoice Approval' step in the workflow: draft -> sent,
        for as many invoices as were selected (e.g. an entire building's
        or owner's worth) in one call."""
        results = []
        for invoice_id in invoice_ids:
            invoice = self.invoice_repo.get(invoice_id)
            if not invoice or invoice.invoice_status != InvoiceStatus.DRAFT:
                continue
            invoice.invoice_status = InvoiceStatus.SENT
            self.audit.log_activity(ENTITY_TYPE_INV, invoice.id, "sent", f"Invoice {invoice.invoice_number} approved and issued", actor_id)
            results.append(invoice)
        self.db.commit()
        return [self.get_invoice(i.id) for i in results]

    def bulk_print_data(self, invoice_ids: list[int], actor_id: Optional[int]) -> list[Invoice]:
        """Fetches every requested invoice in one query (not N), and
        records a print event for each — reused by 'Print Selected',
        'Print Entire Building/Property/Owner/Month', which all reduce
        to 'here is a list of invoice ids' by the time they reach this
        method (the filtering that produces that list happens in
        search_invoices)."""
        invoices = self.invoice_repo.get_many_for_print(invoice_ids)
        for invoice in invoices:
            is_reprint = invoice.print_count > 0
            invoice.print_count += 1
            invoice.printed_at = datetime.utcnow()
            self.audit.log_activity(
                ENTITY_TYPE_INV, invoice.id, "reprinted" if is_reprint else "printed",
                f"Invoice {invoice.invoice_number} {'reprinted' if is_reprint else 'printed'} (bulk, print #{invoice.print_count})", actor_id,
            )
        self.db.commit()
        return invoices

    def search_invoices(
        self, params: PaginationParams, invoice_number: Optional[str] = None, tenant_id: Optional[int] = None,
        property_id: Optional[int] = None, owner_id: Optional[int] = None, rental_contract_id: Optional[int] = None,
        phone: Optional[str] = None, civil_id: Optional[str] = None, invoice_status: Optional[str] = None,
        date_from: Optional[date] = None, date_to: Optional[date] = None,
    ):
        return self.invoice_repo.search(
            params.page, params.page_size, invoice_number, tenant_id, property_id, owner_id,
            rental_contract_id, phone, civil_id, invoice_status, date_from, date_to,
        )

    def _to_print_dto(self, invoice: Invoice) -> dict:
        """Composes the printable DTO from the frozen `snapshot` — never
        from live tenant/property data — so the document matches what
        was actually generated even if the tenant/property/company
        details have since changed. Falls back to live data only for
        invoices generated before this snapshot existed (snapshot is
        nullable for backward compatibility with pre-existing invoices)."""
        from app.core.config import settings
        from app.core.qr_code import generate_invoice_qr_data_uri
        snap = invoice.snapshot or {}
        verification_url = f"{settings.PUBLIC_APP_URL}/verify/{invoice.qr_token}" if invoice.qr_token else None
        return {
            "invoice_id": invoice.id,
            "invoice_number": invoice.invoice_number,
            "issue_date": invoice.issue_date,
            "due_date": invoice.due_date,
            "billing_period_start": invoice.billing_period_start,
            "billing_period_end": invoice.billing_period_end,
            "tenant_name": snap.get("tenant_name") or invoice.tenant_display_name,
            "tenant_address": snap.get("tenant_address"),
            "tenant_civil_id": snap.get("tenant_civil_id"),
            "tenant_phone": snap.get("tenant_phone"),
            "property_title": snap.get("property_title") or invoice.property_title,
            "property_code": snap.get("property_code"),
            "unit_number": snap.get("unit_number"),
            "building_name": snap.get("building_name"),
            "building_number": snap.get("building_number"),
            "contract_number": snap.get("contract_number"),
            "rent_amount": snap.get("rent_amount"),
            "discount_type": snap.get("discount_type"),
            "discount_value": snap.get("discount_value"),
            "tax_rate": snap.get("tax_rate"),
            "amount": invoice.amount,
            "amount_paid": invoice.amount_paid,
            "outstanding_amount": invoice.outstanding_amount,
            "company_name": snap.get("company_name"),
            "company_logo_url": snap.get("company_logo_url"),
            "company_address": snap.get("company_address"),
            "company_phone": snap.get("company_phone"),
            "company_email": snap.get("company_email"),
            "company_website": snap.get("company_website"),
            "qr_verification_url": verification_url,
            "qr_code_data_uri": generate_invoice_qr_data_uri(verification_url) if verification_url else None,
            "print_count": invoice.print_count,
        }

    def get_invoice_print_data(self, invoice_id: int) -> dict:
        invoice = self.invoice_repo.get(invoice_id)
        if not invoice:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
        return self._to_print_dto(invoice)

    def get_bulk_print_data(self, invoice_ids: list[int], actor_id: Optional[int]) -> list[dict]:
        invoices = self.bulk_print_data(invoice_ids, actor_id)
        return [self._to_print_dto(i) for i in invoices]

    def get_invoice_by_qr_token(self, qr_token: str):
        """Backs the QR code's verification URL. Deliberately returns
        only non-sensitive fields — see the router, not this method,
        for what's actually exposed publicly."""
        invoice = self.invoice_repo.get_by_qr_token(qr_token)
        if not invoice:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
        return invoice


