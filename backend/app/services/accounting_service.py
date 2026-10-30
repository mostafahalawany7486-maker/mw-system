"""
Accounting business logic (Phase 10).

Journal Entry lifecycle: draft -> posted -> (optionally) reversed.
- Creating an entry leaves it in `draft` (the Pydantic schema already
  enforces total debits == total credits at creation time).
- Posting an entry re-validates the balance and that every line's account
  allows posting (not a header/summary account), then stamps posted_at.
- A posted entry can never be edited or deleted — only reversed, which
  creates a brand-new entry with debit/credit swapped on every line and
  marks the original as `reversed`. This mirrors how real accounting
  systems protect the integrity of a posted ledger.

Automatic Posting: `auto_post_from_transaction` is called by Phase 8's
FinancialService right after a Transaction is created. It looks up a
PostingRule for the transaction's (type, category), resolves the cash/
bank leg from the transaction's own FinancialAccount.gl_account_id, and
posts an already-`posted` system-generated entry. If no rule is
configured or no GL account is linked, it silently skips (returns None)
rather than blocking the underlying Phase 8 transaction — an unmapped
transaction type just means no automatic entry exists yet, not an error.
"""
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.repositories.accounting_repository import (
    ChartOfAccountRepository, CostCenterRepository, VatRateRepository,
    PostingRuleRepository, JournalEntryRepository, AccountingReportRepository,
)
from app.models.accounting import EntryStatus, SourceType, AccountType, JournalEntry, JournalEntryLine
from app.schemas.common import PaginationParams
from app.services.audit_service import AuditService

ENTITY_TYPE_JE = "journal_entry"
ENTITY_TYPE_COA = "chart_of_account"


class ChartOfAccountService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = ChartOfAccountRepository(db)
        self.audit = AuditService(db)

    def _attach_extras(self, account, with_balance: bool = False):
        account.parent_account_name = account.parent.account_name if account.parent else None
        account.normal_balance = account.normal_balance
        if with_balance:
            account.balance = self.repo.account_balance(account.id)
        return account

    def list_accounts(self, account_type: Optional[str] = None, with_balances: bool = False):
        items = self.repo.list_all(account_type)
        return [self._attach_extras(a, with_balances) for a in items]

    def get_account(self, account_id: int):
        account = self.repo.get(account_id)
        if not account:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
        return self._attach_extras(account, with_balance=True)

    def create_account(self, data: dict, actor_id: Optional[int]):
        if self.repo.get_by_code(data["account_code"]):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Account code {data['account_code']} already exists")
        if data.get("parent_account_id"):
            parent = self.repo.get(data["parent_account_id"])
            if not parent:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid parent_account_id")
            if parent.account_type != data["account_type"]:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A child account must have the same account_type as its parent")
        account = self.repo.create(data, actor_id=actor_id)
        self.audit.log_activity(ENTITY_TYPE_COA, account.id, "created", f"Account {account.account_code} ({account.account_name}) created", actor_id)
        self.db.commit()
        return self._attach_extras(account, with_balance=True)

    def update_account(self, account_id: int, data: dict, actor_id: Optional[int]):
        account = self.repo.get(account_id)
        if not account:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
        if data.get("parent_account_id") == account_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="An account cannot be its own parent")
        self.repo.update(account, data, actor_id=actor_id)
        self.db.commit()
        return self._attach_extras(account, with_balance=True)

    def delete_account(self, account_id: int, actor_id: Optional[int]):
        account = self.repo.get(account_id)
        if not account:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
        if self.repo.has_children(account_id):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cannot delete an account that has child accounts")
        if self.repo.has_journal_lines(account_id):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cannot delete an account that has journal entry lines posted to it")
        self.repo.soft_delete(account, actor_id=actor_id)
        self.audit.log_activity(ENTITY_TYPE_COA, account.id, "deleted", f"Account {account.account_code} deleted", actor_id)
        self.db.commit()


class CostCenterService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = CostCenterRepository(db)

    def _attach_extras(self, cc):
        cc.property_title = cc.property_ref.title if cc.property_ref else None
        return cc

    def list_cost_centers(self):
        return [self._attach_extras(c) for c in self.repo.list_active()]

    def get_cost_center(self, cost_center_id: int):
        cc = self.repo.get_detail(cost_center_id)
        if not cc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cost center not found")
        return self._attach_extras(cc)

    def create_cost_center(self, data: dict, actor_id: Optional[int]):
        _, existing_count = self.repo.list(page=1, page_size=1, search=data["cost_center_code"], search_fields=["cost_center_code"])
        if existing_count > 0:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Cost center code {data['cost_center_code']} already exists")
        cc = self.repo.create(data, actor_id=actor_id)
        self.db.commit()
        return self._attach_extras(self.repo.get_detail(cc.id))

    def update_cost_center(self, cost_center_id: int, data: dict, actor_id: Optional[int]):
        cc = self.repo.get(cost_center_id)
        if not cc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cost center not found")
        self.repo.update(cc, data, actor_id=actor_id)
        self.db.commit()
        return self._attach_extras(self.repo.get_detail(cc.id))

    def delete_cost_center(self, cost_center_id: int, actor_id: Optional[int]):
        cc = self.repo.get(cost_center_id)
        if not cc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cost center not found")
        self.repo.soft_delete(cc, actor_id=actor_id)
        self.db.commit()


class VatRateService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = VatRateRepository(db)

    def _attach_extras(self, v):
        v.gl_account_name = v.gl_account.account_name if v.gl_account else None
        return v

    def list_rates(self):
        return [self._attach_extras(v) for v in self.repo.list_active()]

    def create_rate(self, data: dict, actor_id: Optional[int]):
        rate = self.repo.create(data, actor_id=actor_id)
        self.db.commit()
        return self._attach_extras(rate)

    def update_rate(self, rate_id: int, data: dict, actor_id: Optional[int]):
        rate = self.repo.get(rate_id)
        if not rate:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="VAT rate not found")
        self.repo.update(rate, data, actor_id=actor_id)
        self.db.commit()
        return self._attach_extras(rate)

    def delete_rate(self, rate_id: int, actor_id: Optional[int]):
        rate = self.repo.get(rate_id)
        if not rate:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="VAT rate not found")
        self.repo.soft_delete(rate, actor_id=actor_id)
        self.db.commit()


class PostingRuleService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = PostingRuleRepository(db)
        self.account_repo = ChartOfAccountRepository(db)

    def _attach_extras(self, rule):
        rule.offset_account_name = rule.offset_account.account_name if rule.offset_account else None
        return rule

    def list_rules(self):
        return [self._attach_extras(r) for r in self.repo.list_all()]

    def create_rule(self, data: dict, actor_id: Optional[int]):
        account = self.account_repo.get(data["offset_account_id"])
        if not account:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid offset_account_id")
        if not account.allow_posting:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="offset_account_id must be a posting-allowed (leaf) account")
        if self.repo.exists_for(data["transaction_type"], data.get("category")):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A posting rule already exists for this transaction_type/category combination")
        rule = self.repo.create(data, actor_id=actor_id)
        self.db.commit()
        return self._attach_extras(rule)

    def update_rule(self, rule_id: int, data: dict, actor_id: Optional[int]):
        rule = self.repo.get(rule_id)
        if not rule:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Posting rule not found")
        if data.get("offset_account_id"):
            account = self.account_repo.get(data["offset_account_id"])
            if not account:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid offset_account_id")
        self.repo.update(rule, data, actor_id=actor_id)
        self.db.commit()
        return self._attach_extras(rule)

    def delete_rule(self, rule_id: int, actor_id: Optional[int]):
        rule = self.repo.get(rule_id)
        if not rule:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Posting rule not found")
        self.repo.soft_delete(rule, actor_id=actor_id)
        self.db.commit()


class JournalEntryService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = JournalEntryRepository(db)
        self.account_repo = ChartOfAccountRepository(db)
        self.posting_rule_repo = PostingRuleRepository(db)
        self.audit = AuditService(db)

    def _attach_totals(self, entry):
        entry.total_debit = entry.total_debit
        entry.total_credit = entry.total_credit
        return entry

    def list_entries(self, params: PaginationParams, entry_status: Optional[str], source_type: Optional[str], date_from: Optional[date], date_to: Optional[date]):
        items, total = self.repo.list_entries(
            page=params.page, page_size=params.page_size, search=params.search, entry_status=entry_status,
            source_type=source_type, date_from=date_from, date_to=date_to, sort_dir=params.sort_dir or "desc",
        )
        return [self._attach_totals(e) for e in items], total

    def get_entry(self, entry_id: int):
        entry = self.repo.get_detail(entry_id)
        if not entry:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Journal entry not found")
        return self._attach_totals(entry)

    def create_entry(self, data: dict, actor_id: Optional[int]):
        lines_data = data.pop("lines")
        for line in lines_data:
            account = self.account_repo.get(line["account_id"])
            if not account:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid account_id {line['account_id']}")
            if not account.allow_posting:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Account {account.account_code} does not allow direct posting (it's a header/summary account)")
            if line.get("property_id") is not None:
                from app.repositories.property_repository import PropertyRepository
                if not PropertyRepository(self.db).get(line["property_id"]):
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid property_id {line['property_id']}")

        payload = dict(data)
        payload["entry_number"] = self.repo.next_entry_number()
        payload["source_type"] = SourceType.MANUAL
        payload["entry_status"] = EntryStatus.DRAFT
        entry = self.repo.create(payload, actor_id=actor_id)
        for line in lines_data:
            self.db.add(JournalEntryLine(journal_entry_id=entry.id, **line))

        self.audit.log_activity(ENTITY_TYPE_JE, entry.id, "created", f"Journal entry {entry.entry_number} drafted", actor_id)
        self.db.commit()
        return self.get_entry(entry.id)

    def update_entry(self, entry_id: int, data: dict, actor_id: Optional[int]):
        entry = self.repo.get(entry_id)
        if not entry:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Journal entry not found")
        if entry.entry_status != EntryStatus.DRAFT:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only draft entries can be edited")
        self.repo.update(entry, data, actor_id=actor_id)
        self.db.commit()
        return self.get_entry(entry.id)

    def delete_entry(self, entry_id: int, actor_id: Optional[int]):
        entry = self.repo.get(entry_id)
        if not entry:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Journal entry not found")
        if entry.entry_status != EntryStatus.DRAFT:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only draft entries can be deleted — post and reverse instead")
        self.repo.soft_delete(entry, actor_id=actor_id)
        self.db.commit()

    def post_entry(self, entry_id: int, actor_id: Optional[int]):
        entry = self.repo.get_detail(entry_id)
        if not entry:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Journal entry not found")
        if entry.entry_status != EntryStatus.DRAFT:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Only draft entries can be posted (current: {entry.entry_status})")
        if not entry.is_balanced:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Entry is not balanced (debits={entry.total_debit}, credits={entry.total_credit})")
        for line in entry.lines:
            if not line.account.allow_posting:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Account {line.account.account_code} does not allow direct posting")

        entry.entry_status = EntryStatus.POSTED
        entry.posted_at = datetime.utcnow()
        self.audit.log_activity(ENTITY_TYPE_JE, entry.id, "posted", f"Journal entry {entry.entry_number} posted", actor_id)
        self.db.commit()
        return self.get_entry(entry.id)

    def reverse_entry(self, entry_id: int, reversal_date: date, actor_id: Optional[int]):
        entry = self.repo.get_detail(entry_id)
        if not entry:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Journal entry not found")
        if entry.entry_status != EntryStatus.POSTED:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Only posted entries can be reversed (current: {entry.entry_status})")

        reversal = JournalEntry(
            entry_number=self.repo.next_entry_number(), entry_date=reversal_date,
            description=f"Reversal of {entry.entry_number}", reference_number=entry.entry_number,
            source_type=entry.source_type, source_transaction_id=entry.source_transaction_id,
            entry_status=EntryStatus.POSTED, posted_at=datetime.utcnow(),
        )
        self.db.add(reversal)
        self.db.flush()
        for line in entry.lines:
            self.db.add(JournalEntryLine(
                journal_entry_id=reversal.id, account_id=line.account_id, cost_center_id=line.cost_center_id,
                property_id=line.property_id,
                debit_amount=line.credit_amount, credit_amount=line.debit_amount,
                description=f"Reversal: {line.description or ''}".strip(),
                vat_rate_id=line.vat_rate_id, vat_amount=line.vat_amount,
            ))

        entry.entry_status = EntryStatus.REVERSED
        entry.reversed_entry_id = reversal.id
        self.audit.log_activity(ENTITY_TYPE_JE, entry.id, "reversed", f"Journal entry {entry.entry_number} reversed by {reversal.entry_number}", actor_id)
        self.db.commit()
        return self.get_entry(reversal.id)

    # ---------------- Automatic Posting ----------------
    def auto_post_from_transaction(self, txn, actor_id: Optional[int] = None):
        """Called by Phase 8's FinancialService right after a Transaction
        is created. Returns the posted JournalEntry, or None if no
        PostingRule / GL account mapping exists yet (an unmapped
        transaction type is not an error — it just has no automatic
        entry until someone configures the mapping)."""
        rule = self.posting_rule_repo.find_rule(txn.transaction_type, txn.category)
        if not rule:
            return None
        from app.repositories.financial_repository import FinancialAccountRepository
        financial_account = FinancialAccountRepository(self.db).get(txn.account_id)
        cash_gl_account_id = financial_account.gl_account_id if financial_account else None
        if not cash_gl_account_id:
            return None

        net_amount = txn.amount
        vat_amount = Decimal("0")
        if rule.vat_rate_id and rule.vat_rate and rule.vat_rate.rate_percentage > 0:
            rate = rule.vat_rate.rate_percentage
            net_amount = (txn.amount / (1 + rate / Decimal("100"))).quantize(Decimal("0.01"))
            vat_amount = txn.amount - net_amount

        entry = JournalEntry(
            entry_number=self.repo.next_entry_number(), entry_date=txn.transaction_date,
            description=f"Auto-posted: {txn.transaction_number} ({txn.transaction_type})",
            reference_number=txn.transaction_number, source_type=SourceType.SYSTEM, source_transaction_id=txn.id,
            entry_status=EntryStatus.POSTED, posted_at=datetime.utcnow(),
        )
        self.db.add(entry)
        self.db.flush()

        cost_center_id = rule.cost_center_id
        line_property_id = txn.property_id
        if txn.direction == "in":
            self.db.add(JournalEntryLine(journal_entry_id=entry.id, account_id=cash_gl_account_id, property_id=line_property_id, debit_amount=txn.amount, credit_amount=0, description=entry.description))
            self.db.add(JournalEntryLine(journal_entry_id=entry.id, account_id=rule.offset_account_id, cost_center_id=cost_center_id, property_id=line_property_id, debit_amount=0, credit_amount=net_amount, description=entry.description, vat_rate_id=rule.vat_rate_id, vat_amount=vat_amount))
            if vat_amount > 0 and rule.vat_rate and rule.vat_rate.gl_account_id:
                self.db.add(JournalEntryLine(journal_entry_id=entry.id, account_id=rule.vat_rate.gl_account_id, property_id=line_property_id, debit_amount=0, credit_amount=vat_amount, description=f"Output VAT on {txn.transaction_number}", vat_rate_id=rule.vat_rate_id))
        else:
            self.db.add(JournalEntryLine(journal_entry_id=entry.id, account_id=rule.offset_account_id, cost_center_id=cost_center_id, property_id=line_property_id, debit_amount=net_amount, credit_amount=0, description=entry.description, vat_rate_id=rule.vat_rate_id, vat_amount=vat_amount))
            if vat_amount > 0 and rule.vat_rate and rule.vat_rate.gl_account_id:
                self.db.add(JournalEntryLine(journal_entry_id=entry.id, account_id=rule.vat_rate.gl_account_id, property_id=line_property_id, debit_amount=vat_amount, credit_amount=0, description=f"Input VAT on {txn.transaction_number}", vat_rate_id=rule.vat_rate_id))
            self.db.add(JournalEntryLine(journal_entry_id=entry.id, account_id=cash_gl_account_id, property_id=line_property_id, debit_amount=0, credit_amount=txn.amount, description=entry.description))

        self.audit.log_activity(ENTITY_TYPE_JE, entry.id, "auto_posted", f"Journal entry {entry.entry_number} auto-posted from {txn.transaction_number}", actor_id)
        self.db.flush()
        return entry

    def auto_post_transfer(self, out_txn, in_txn, actor_id: Optional[int] = None):
        """One journal entry per transfer pair (not two) — debits the
        destination GL cash account and credits the source GL cash
        account. Skips silently if either FinancialAccount lacks a
        gl_account_id."""
        from app.repositories.financial_repository import FinancialAccountRepository
        account_repo = FinancialAccountRepository(self.db)
        from_financial_account = account_repo.get(out_txn.account_id)
        to_financial_account = account_repo.get(in_txn.account_id)
        from_gl = from_financial_account.gl_account_id if from_financial_account else None
        to_gl = to_financial_account.gl_account_id if to_financial_account else None
        if not from_gl or not to_gl:
            return None

        entry = JournalEntry(
            entry_number=self.repo.next_entry_number(), entry_date=out_txn.transaction_date,
            description=f"Auto-posted transfer: {out_txn.transaction_number} \u2192 {in_txn.transaction_number}",
            reference_number=out_txn.transaction_number, source_type=SourceType.SYSTEM, source_transaction_id=out_txn.id,
            entry_status=EntryStatus.POSTED, posted_at=datetime.utcnow(),
        )
        self.db.add(entry)
        self.db.flush()
        transfer_property_id = out_txn.property_id or in_txn.property_id
        self.db.add(JournalEntryLine(journal_entry_id=entry.id, account_id=to_gl, property_id=transfer_property_id, debit_amount=out_txn.amount, credit_amount=0, description=entry.description))
        self.db.add(JournalEntryLine(journal_entry_id=entry.id, account_id=from_gl, property_id=transfer_property_id, debit_amount=0, credit_amount=out_txn.amount, description=entry.description))
        self.audit.log_activity(ENTITY_TYPE_JE, entry.id, "auto_posted", f"Journal entry {entry.entry_number} auto-posted from transfer", actor_id)
        self.db.flush()
        return entry

    def has_posted_entry_for_transaction(self, transaction_id: int) -> bool:
        stmt = select(func.count()).select_from(JournalEntry).where(
            JournalEntry.source_transaction_id == transaction_id,
            JournalEntry.entry_status == EntryStatus.POSTED,
            JournalEntry.deleted_at.is_(None),
        )
        return self.db.execute(stmt).scalar_one() > 0


class AccountingReportService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = AccountingReportRepository(db)
        self.account_repo = ChartOfAccountRepository(db)

    def trial_balance(self, as_of_date: date) -> dict:
        lines = self.repo.trial_balance(as_of_date)
        total_debit = sum((l["debit_balance"] for l in lines), Decimal("0"))
        total_credit = sum((l["credit_balance"] for l in lines), Decimal("0"))
        return {"as_of_date": as_of_date, "lines": lines, "total_debit": total_debit, "total_credit": total_credit, "is_balanced": total_debit == total_credit}

    def general_ledger(self, account_id: int, date_from: Optional[date], date_to: Optional[date]) -> dict:
        account = self.account_repo.get(account_id)
        if not account:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
        normal_debit = account.account_type in AccountType.DEBIT_NORMAL
        opening = self.repo.opening_balance(account_id, date_from, normal_debit) if date_from else Decimal("0")
        lines = self.repo.general_ledger_lines(account_id, date_from, date_to)
        running = opening
        out_lines = []
        for line in lines:
            delta = (line.debit_amount - line.credit_amount) if normal_debit else (line.credit_amount - line.debit_amount)
            running += delta
            out_lines.append({
                "journal_entry_id": line.journal_entry_id, "entry_number": line.journal_entry.entry_number,
                "entry_date": line.journal_entry.entry_date, "description": line.description or line.journal_entry.description,
                "debit_amount": line.debit_amount, "credit_amount": line.credit_amount, "running_balance": running,
            })
        return {
            "account_id": account.id, "account_code": account.account_code, "account_name": account.account_name,
            "opening_balance": opening, "lines": out_lines, "closing_balance": running,
        }

    def balance_sheet(self, as_of_date: date) -> dict:
        assets = self.repo.section_balances(AccountType.ASSET, None, as_of_date)
        liabilities = self.repo.section_balances(AccountType.LIABILITY, None, as_of_date)
        equity = self.repo.section_balances(AccountType.EQUITY, None, as_of_date)
        total_assets = sum((a["balance"] for a in assets), Decimal("0"))
        total_liabilities = sum((l["balance"] for l in liabilities), Decimal("0"))
        total_equity = sum((e["balance"] for e in equity), Decimal("0"))
        return {
            "as_of_date": as_of_date, "assets": assets, "liabilities": liabilities, "equity": equity,
            "total_assets": total_assets, "total_liabilities": total_liabilities, "total_equity": total_equity,
            "is_balanced": total_assets == (total_liabilities + total_equity),
        }

    def income_statement(self, date_from: date, date_to: date, property_id: Optional[int] = None) -> dict:
        revenue = self.repo.section_balances(AccountType.REVENUE, date_from, date_to, property_id)
        expenses = self.repo.section_balances(AccountType.EXPENSE, date_from, date_to, property_id)
        total_revenue = sum((r["balance"] for r in revenue), Decimal("0"))
        total_expenses = sum((e["balance"] for e in expenses), Decimal("0"))
        return {
            "date_from": date_from, "date_to": date_to, "revenue": revenue, "expenses": expenses,
            "total_revenue": total_revenue, "total_expenses": total_expenses, "net_income": total_revenue - total_expenses,
        }

    def cash_flow(self, date_from: date, date_to: date) -> dict:
        lines = self.repo.cash_flow_by_transaction_type(date_from, date_to)
        net_operating = sum((l["total_amount"] for l in lines), Decimal("0"))
        opening = self.repo.cash_balance_as_of(date_from - timedelta(days=1))
        closing = self.repo.cash_balance_as_of(date_to)
        return {
            "date_from": date_from, "date_to": date_to, "operating_activities": lines,
            "net_operating_cash_flow": net_operating, "net_change_in_cash": closing - opening,
            "opening_cash_balance": opening, "closing_cash_balance": closing,
        }

    def property_cash_flow(self, property_id: int, date_from: date, date_to: date) -> dict:
        """Cash isn't physically segregated per property in this system
        (all properties share the same company Cash/Bank accounts), so
        unlike the portfolio cash_flow report above, this has no
        opening/closing *bank balance* — it reports the property's own
        net cash contribution instead (inflows minus outflows
        attributable to it), which is the meaningful profit-center metric."""
        self._get_property_or_404(property_id)
        lines = self.repo.cash_flow_by_transaction_type(date_from, date_to, property_id)
        net_cash_flow = sum((l["total_amount"] for l in lines), Decimal("0"))
        return {
            "property_id": property_id, "date_from": date_from, "date_to": date_to,
            "activities": lines, "net_cash_flow": net_cash_flow,
        }

    def property_ledger(self, property_id: int, date_from: Optional[date], date_to: Optional[date]) -> dict:
        self._get_property_or_404(property_id)
        lines = self.repo.property_ledger_lines(property_id, date_from, date_to)
        total_debit = sum((l.debit_amount for l in lines), Decimal("0"))
        total_credit = sum((l.credit_amount for l in lines), Decimal("0"))
        out_lines = [{
            "journal_entry_id": l.journal_entry_id, "entry_number": l.journal_entry.entry_number,
            "entry_date": l.journal_entry.entry_date, "account_code": l.account_code, "account_name": l.account_name,
            "description": l.description or l.journal_entry.description,
            "debit_amount": l.debit_amount, "credit_amount": l.credit_amount,
        } for l in lines]
        return {"property_id": property_id, "date_from": date_from, "date_to": date_to, "lines": out_lines, "total_debit": total_debit, "total_credit": total_credit}

    def property_balance_summary(self, property_id: int, as_of_date: date) -> dict:
        self._get_property_or_404(property_id)
        lines = self.repo.property_balance_summary(property_id, as_of_date)
        total_debit = sum((l["debit_balance"] for l in lines), Decimal("0"))
        total_credit = sum((l["credit_balance"] for l in lines), Decimal("0"))
        return {"property_id": property_id, "as_of_date": as_of_date, "lines": lines, "total_debit": total_debit, "total_credit": total_credit}

    def _get_property_or_404(self, property_id: int):
        from app.repositories.property_repository import PropertyRepository
        prop = PropertyRepository(self.db).get(property_id)
        if not prop:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
        return prop

    def vat_report(self, date_from: date, date_to: date) -> dict:
        lines = self.repo.vat_report(date_from, date_to)
        total_output = sum((l["output_vat"] for l in lines), Decimal("0"))
        total_input = sum((l["input_vat"] for l in lines), Decimal("0"))
        return {
            "date_from": date_from, "date_to": date_to, "lines": lines,
            "total_output_vat": total_output, "total_input_vat": total_input, "total_net_vat": total_output - total_input,
        }
