"""
Unit tests for the Owner Ledger & Recoverable Expense Engine
(app/business_workflows/owner_ledger/, app/api/v1/routers/owner_ledger.py).

Covers: recoverable expense creation (increases outstanding balance,
never posts as a company EXPENSE), owner reimbursement (reduces
outstanding balance), running-balance correctness (via
OwnerBalanceService.recompute_and_verify), reversal (append-only, no
mutation/deletion, duplicate-reversal rejection), statement generation,
the dashboard, audit logging, and permission enforcement.
"""
from datetime import date, timedelta
from decimal import Decimal
import pytest

from app.business_workflows.owner_ledger.owner_ledger_service import OwnerLedgerService
from app.business_workflows.owner_ledger.recoverable_expense_service import RecoverableExpenseService
from app.business_workflows.owner_ledger.owner_balance_service import OwnerBalanceService
from app.business_workflows.owner_ledger.owner_statement_service import OwnerStatementService
from app.business_workflows.owner_ledger.owner_ledger_validator import (
    OwnerNotFoundError, InvalidPropertyForOwnerError, NegativeAmountError, AlreadyReversedError,
)
from app.models.owner_ledger import OwnerLedgerTransactionType
from app.core.security import hash_password
from app.models.user import User, Role, Permission


def _auth_headers(client):
    resp = client.post("/api/v1/auth/login", json={"email": "admin@test.com", "password": "Admin@12345"})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _ledger_viewer(db_session):
    perms = [Permission(code="owner_ledger.view", module="owner_ledger", action="view")]
    for p in perms:
        db_session.add(p)
    db_session.flush()
    role = Role(name="Owner Ledger Viewer", description="View-only", is_system_role=False)
    role.permissions = perms
    db_session.add(role)
    db_session.flush()
    user = User(
        first_name="Ledger", last_name="Viewer", email="ledger-viewer@test.com",
        hashed_password=hash_password("Viewer@12345"), is_active=True, is_superuser=False, role_id=role.id,
    )
    db_session.add(user)
    db_session.commit()
    return user


def _create_owner(client, headers, **overrides):
    payload = {"owner_type": "individual", "first_name": "Ledger", "last_name": "Owner"}
    payload.update(overrides)
    resp = client.post("/api/v1/owners", json=payload, headers=headers)
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_property(client, headers, owner_id):
    resp = client.post("/api/v1/properties", json={"property_type": "apartment", "title": "Ledger Unit", "owner_id": owner_id}, headers=headers)
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_account(client, headers):
    resp = client.post("/api/v1/financial/accounts", json={"account_type": "bank", "name": "Owner Ledger Bank", "opening_balance": "0"}, headers=headers)
    assert resp.status_code == 201
    return resp.json()["id"]


# ==================== Recoverable expense ====================
def test_create_recoverable_expense_increases_outstanding_balance(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    property_id = _create_property(client, headers, owner_id)
    account_id = _create_account(client, headers)

    service = RecoverableExpenseService(db_session)
    result = service.create_recoverable_expense(
        owner_id=owner_id, account_id=account_id, amount=Decimal("250.00"), expense_category="municipality_fees",
        description="Annual municipality fee paid on owner's behalf", payment_date=date.today(), actor_id=seeded_admin.id,
        property_id=property_id,
    )

    entry = result["ledger_entry"]
    assert entry.transaction_type == "recoverable_expense"
    assert entry.debit == Decimal("250.00")
    assert entry.credit == Decimal("0")
    assert entry.balance == Decimal("-250.00")  # company owes owner less / owner now owes company

    txn = result["transaction"]
    assert txn.transaction_type == "recoverable_expense"
    assert txn.transaction_type != "expense"  # NEVER a normal company operating expense

    balance_service = OwnerBalanceService(db_session)
    assert balance_service.get_current_balance(owner_id) == Decimal("-250.00")
    assert balance_service.get_outstanding_recoverable_expenses(owner_id) == Decimal("250.00")


def test_recoverable_expense_rejects_negative_amount(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    account_id = _create_account(client, headers)

    service = RecoverableExpenseService(db_session)
    with pytest.raises(NegativeAmountError):
        service.create_recoverable_expense(
            owner_id=owner_id, account_id=account_id, amount=Decimal("-10.00"), expense_category="water",
            description="bad", payment_date=date.today(), actor_id=seeded_admin.id,
        )


def test_recoverable_expense_rejects_unknown_owner(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    account_id = _create_account(client, headers)

    service = RecoverableExpenseService(db_session)
    with pytest.raises(OwnerNotFoundError):
        service.create_recoverable_expense(
            owner_id=999999, account_id=account_id, amount=Decimal("10.00"), expense_category="water",
            description="bad", payment_date=date.today(), actor_id=seeded_admin.id,
        )


def test_recoverable_expense_rejects_property_belonging_to_different_owner(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    owner1 = _create_owner(client, headers, first_name="One")
    owner2 = _create_owner(client, headers, first_name="Two")
    property_of_owner2 = _create_property(client, headers, owner2)
    account_id = _create_account(client, headers)

    service = RecoverableExpenseService(db_session)
    with pytest.raises(InvalidPropertyForOwnerError):
        service.create_recoverable_expense(
            owner_id=owner1, account_id=account_id, amount=Decimal("10.00"), expense_category="water",
            description="mismatched", payment_date=date.today(), actor_id=seeded_admin.id,
            property_id=property_of_owner2,
        )


# ==================== Owner reimbursement ====================
def test_recovered_payment_reduces_outstanding_balance(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    account_id = _create_account(client, headers)

    service = RecoverableExpenseService(db_session)
    service.create_recoverable_expense(
        owner_id=owner_id, account_id=account_id, amount=Decimal("500.00"), expense_category="maintenance",
        description="Emergency repair", payment_date=date.today(), actor_id=seeded_admin.id,
    )
    result = service.record_recovered_payment(
        owner_id=owner_id, account_id=account_id, amount=Decimal("300.00"), payment_method="bank_transfer",
        payment_date=date.today(), actor_id=seeded_admin.id,
    )

    entry = result["ledger_entry"]
    assert entry.transaction_type == "recovered_amount"
    assert entry.credit == Decimal("300.00")
    assert entry.balance == Decimal("-200.00")  # 500 owed - 300 recovered

    balance_service = OwnerBalanceService(db_session)
    assert balance_service.get_outstanding_recoverable_expenses(owner_id) == Decimal("200.00")


def test_full_reimbursement_zeroes_outstanding_balance(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    account_id = _create_account(client, headers)

    service = RecoverableExpenseService(db_session)
    service.create_recoverable_expense(
        owner_id=owner_id, account_id=account_id, amount=Decimal("500.00"), expense_category="insurance",
        description="Property insurance", payment_date=date.today(), actor_id=seeded_admin.id,
    )
    service.record_recovered_payment(
        owner_id=owner_id, account_id=account_id, amount=Decimal("500.00"), payment_method="cash",
        payment_date=date.today(), actor_id=seeded_admin.id,
    )

    balance_service = OwnerBalanceService(db_session)
    assert balance_service.get_current_balance(owner_id) == Decimal("0")
    assert balance_service.get_outstanding_recoverable_expenses(owner_id) == Decimal("0")


# ==================== Balance calculation correctness ====================
def test_balance_chain_stays_consistent_across_many_entries(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    account_id = _create_account(client, headers)

    service = RecoverableExpenseService(db_session)
    ledger = OwnerLedgerService(db_session)

    ledger.post_entry(owner_id, date.today(), OwnerLedgerTransactionType.RENTAL_INCOME, "Rent collected", seeded_admin.id, credit=Decimal("1000.00"))
    ledger.post_entry(owner_id, date.today(), OwnerLedgerTransactionType.MANAGEMENT_FEE, "5% management fee", seeded_admin.id, debit=Decimal("50.00"))
    service.create_recoverable_expense(owner_id, account_id, Decimal("120.00"), "electricity", "Electricity bill", date.today(), seeded_admin.id)
    service.record_recovered_payment(owner_id, account_id, Decimal("70.00"), "cash", date.today(), seeded_admin.id)

    balance_service = OwnerBalanceService(db_session)
    # 1000 (income) - 50 (mgmt fee) - 120 (recoverable expense) + 70 (recovered) = 900
    assert balance_service.get_current_balance(owner_id) == Decimal("900.00")
    assert balance_service.recompute_and_verify(owner_id) is True


def test_manual_ledger_entry_rejects_both_debit_and_credit(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)

    from app.business_workflows.owner_ledger.owner_ledger_validator import OwnerLedgerError
    ledger = OwnerLedgerService(db_session)
    with pytest.raises(OwnerLedgerError):
        ledger.post_entry(
            owner_id, date.today(), OwnerLedgerTransactionType.ADJUSTMENT, "bad entry", seeded_admin.id,
            debit=Decimal("10.00"), credit=Decimal("10.00"),
        )


# ==================== Reversal ====================
def test_reverse_entry_appends_opposite_entry_never_mutates_original(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)

    ledger = OwnerLedgerService(db_session)
    original = ledger.post_entry(owner_id, date.today(), OwnerLedgerTransactionType.ADJUSTMENT, "Manual credit", seeded_admin.id, credit=Decimal("100.00"))
    assert original.balance == Decimal("100.00")

    reversal = ledger.reverse_entry(original.id, "Entered in error", actor_id=seeded_admin.id)

    # Original untouched except its status/link — never deleted or its own debit/credit/balance changed.
    refreshed_original = ledger.get_entry(original.id)
    assert refreshed_original.debit == Decimal("0")
    assert refreshed_original.credit == Decimal("100.00")
    assert refreshed_original.entry_status == "reversed"
    assert refreshed_original.reversed_by_id == reversal.id

    assert reversal.debit == Decimal("100.00")
    assert reversal.reversal_of_id == original.id
    assert reversal.entry_status == "reversal"

    balance_service = OwnerBalanceService(db_session)
    assert balance_service.get_current_balance(owner_id) == Decimal("0")


def test_duplicate_reversal_rejected(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)

    ledger = OwnerLedgerService(db_session)
    entry = ledger.post_entry(owner_id, date.today(), OwnerLedgerTransactionType.ADJUSTMENT, "Manual credit", seeded_admin.id, credit=Decimal("50.00"))
    ledger.reverse_entry(entry.id, "first reversal", actor_id=seeded_admin.id)

    with pytest.raises(AlreadyReversedError):
        ledger.reverse_entry(entry.id, "second reversal", actor_id=seeded_admin.id)


# ==================== Audit ====================
def test_recoverable_expense_creates_audit_record(client, db_session, seeded_admin):
    from sqlalchemy import select
    from app.models.system import ActivityLog

    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    account_id = _create_account(client, headers)

    service = RecoverableExpenseService(db_session)
    result = service.create_recoverable_expense(
        owner_id=owner_id, account_id=account_id, amount=Decimal("80.00"), expense_category="water",
        description="Water bill", payment_date=date.today(), actor_id=seeded_admin.id,
    )
    entry_id = result["ledger_entry"].id

    logs = db_session.execute(
        select(ActivityLog).where(ActivityLog.entity_id == entry_id, ActivityLog.entity_type == "owner_ledger_entry")
    ).scalars().all()
    assert len(logs) >= 1
    assert logs[0].actor_id == seeded_admin.id


# ==================== Statement ====================
def test_generate_statement_matches_balance(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    account_id = _create_account(client, headers)

    ledger = OwnerLedgerService(db_session)
    service = RecoverableExpenseService(db_session)
    today = date.today()

    ledger.post_entry(owner_id, today, OwnerLedgerTransactionType.RENTAL_INCOME, "Rent collected", seeded_admin.id, credit=Decimal("2000.00"))
    ledger.post_entry(owner_id, today, OwnerLedgerTransactionType.MANAGEMENT_FEE, "Management fee", seeded_admin.id, debit=Decimal("100.00"))
    service.create_recoverable_expense(owner_id, account_id, Decimal("300.00"), "maintenance", "Repair", today, seeded_admin.id)
    service.record_recovered_payment(owner_id, account_id, Decimal("150.00"), "cash", today, seeded_admin.id)

    statement_service = OwnerStatementService(db_session)
    statement = statement_service.generate_statement(owner_id, today - timedelta(days=1), today)

    assert statement["opening_balance"] == Decimal("0")
    assert statement["rental_income"] == Decimal("2000.00")
    assert statement["management_fees"] == Decimal("100.00")
    assert statement["recoverable_expenses"] == Decimal("300.00")
    assert statement["recovered_amounts"] == Decimal("150.00")
    assert len(statement["line_items"]) == 4

    balance_service = OwnerBalanceService(db_session)
    assert statement["closing_balance"] == balance_service.get_current_balance(owner_id)


# ==================== Dashboard ====================
def test_owner_dashboard_reflects_monthly_activity(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    account_id = _create_account(client, headers)

    ledger = OwnerLedgerService(db_session)
    service = RecoverableExpenseService(db_session)
    today = date.today()

    ledger.post_entry(owner_id, today, OwnerLedgerTransactionType.RENTAL_INCOME, "Rent", seeded_admin.id, credit=Decimal("1000.00"))
    service.create_recoverable_expense(owner_id, account_id, Decimal("200.00"), "electricity", "Electricity", today, seeded_admin.id)

    dashboard = OwnerBalanceService(db_session).get_dashboard(owner_id)
    assert dashboard["monthly_income"] == Decimal("1000.00")
    assert dashboard["monthly_expenses"] == Decimal("200.00")
    assert dashboard["outstanding_recoverable_expenses"] == Decimal("200.00")


# ==================== API / Permissions ====================
def test_create_manual_ledger_entry_via_api(client, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)

    resp = client.post("/api/v1/owner-ledger", json={
        "owner_id": owner_id, "transaction_date": str(date.today()), "transaction_type": "rental_income",
        "description": "Rent collected on owner's behalf", "credit": "750.00", "debit": "0",
    }, headers=headers)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["transaction_type"] == "rental_income"
    assert body["balance"] == "750.00" or float(body["balance"]) == 750.00


def test_full_api_workflow(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    account_id = _create_account(client, headers)

    created = client.post("/api/v1/owner-ledger/recoverable-expense", json={
        "owner_id": owner_id, "account_id": account_id, "amount": "400.00", "expense_category": "maintenance",
        "description": "Roof repair", "payment_date": str(date.today()),
    }, headers=headers)
    assert created.status_code == 201, created.text
    entry_id = created.json()["id"]
    assert created.json()["debit"] == "400.00" or float(created.json()["debit"]) == 400.00

    recovered = client.post("/api/v1/owner-ledger/recovered-payment", json={
        "owner_id": owner_id, "account_id": account_id, "amount": "150.00", "payment_method": "cash",
        "payment_date": str(date.today()),
    }, headers=headers)
    assert recovered.status_code == 201

    balance = client.get(f"/api/v1/owner-ledger/{owner_id}/balance", headers=headers)
    assert balance.status_code == 200
    assert balance.json()["outstanding_recoverable_expenses"] == "250.00" or float(balance.json()["outstanding_recoverable_expenses"]) == 250.00

    dashboard = client.get(f"/api/v1/owner-ledger/{owner_id}/dashboard", headers=headers)
    assert dashboard.status_code == 200

    listed = client.get(f"/api/v1/owner-ledger/{owner_id}", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["total"] >= 2

    listed_all = client.get("/api/v1/owner-ledger", headers=headers)
    assert listed_all.status_code == 200

    statement = client.get(
        f"/api/v1/owner-statement/{owner_id}",
        params={"date_from": str(date.today() - timedelta(days=1)), "date_to": str(date.today())},
        headers=headers,
    )
    assert statement.status_code == 200
    assert "closing_balance" in statement.json()

    reversed_resp = client.post(f"/api/v1/owner-ledger/{entry_id}/reverse", json={"reason": "test reversal"}, headers=headers)
    assert reversed_resp.status_code == 200
    assert reversed_resp.json()["reversal_of_id"] == entry_id


def test_owner_ledger_rejects_without_create_permission(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    account_id = _create_account(client, headers)

    _ledger_viewer(db_session)
    login = client.post("/api/v1/auth/login", json={"email": "ledger-viewer@test.com", "password": "Viewer@12345"})
    viewer_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    resp = client.post("/api/v1/owner-ledger/recoverable-expense", json={
        "owner_id": owner_id, "account_id": account_id, "amount": "100.00", "expense_category": "water",
        "description": "test", "payment_date": str(date.today()),
    }, headers=viewer_headers)
    assert resp.status_code == 403

    listed = client.get(f"/api/v1/owner-ledger/{owner_id}", headers=viewer_headers)
    assert listed.status_code == 200  # owner_ledger.view is granted


def test_owner_ledger_requires_authentication(client, seeded_admin):
    resp = client.get("/api/v1/owner-ledger")
    assert resp.status_code == 401
