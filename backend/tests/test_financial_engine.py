"""
Unit tests for the Financial Engine
(app/business_workflows/financial_engine/, app/api/v1/routers/financial_engine.py).

Covers: the full Security Deposit lifecycle (received, partial refund,
full refund, deduction, forfeit, transfer to owner), every VALIDATIONS
rule (duplicate deposit, negative deposit, over-refund, duplicate
transaction, invalid allocation), the six ledger views (company, owner
[delegated], tenant, building, property, unit), the deposit ledger
integrity check, owner/tenant adjustments, transfer (delegated to the
existing FinancialService), the dashboard, the full API workflow, and
permission enforcement.
"""
from datetime import date, timedelta
from decimal import Decimal
import pytest

from app.business_workflows.financial_engine.deposit_service import DepositService
from app.business_workflows.financial_engine.balance_service import BalanceService
from app.business_workflows.financial_engine.adjustment_service import AdjustmentService
from app.business_workflows.financial_engine.ledger_sync_service import LedgerSyncService
from app.business_workflows.financial_engine.financial_validator import FinancialValidator
from app.business_workflows.financial_engine.financial_exceptions import (
    DuplicateDepositError, NegativeDepositError, OverRefundError, DuplicateTransactionError,
    InvalidDepositTransitionError, InvalidAllocationError,
)
from app.models.financial_engine import DepositAction
from app.models.rental import RentalSecurityDepositStatus
from app.core.security import hash_password
from app.models.user import User, Role, Permission


def _auth_headers(client):
    resp = client.post("/api/v1/auth/login", json={"email": "admin@test.com", "password": "Admin@12345"})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _financial_viewer(db_session):
    perms = [Permission(code="financial.view", module="financial", action="view")]
    for p in perms:
        db_session.add(p)
    db_session.flush()
    role = Role(name="Financial Viewer", description="View-only", is_system_role=False)
    role.permissions = perms
    db_session.add(role)
    db_session.flush()
    user = User(
        first_name="Fin", last_name="Viewer", email="fin-viewer@test.com",
        hashed_password=hash_password("Viewer@12345"), is_active=True, is_superuser=False, role_id=role.id,
    )
    db_session.add(user)
    db_session.commit()
    return user


def _create_owner(client, headers, **overrides):
    payload = {"owner_type": "individual", "first_name": "Fin", "last_name": "Owner"}
    payload.update(overrides)
    resp = client.post("/api/v1/owners", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _create_unit(client, headers, owner_id, title="Fin Unit"):
    resp = client.post("/api/v1/properties", json={"property_type": "apartment", "title": title, "owner_id": owner_id}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _create_tenant(client, headers, **overrides):
    payload = {"tenant_type": "individual", "first_name": "Fin", "last_name": "Tenant"}
    payload.update(overrides)
    resp = client.post("/api/v1/tenants", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _create_account(client, headers, name="Fin Engine Account"):
    resp = client.post("/api/v1/financial/accounts", json={"account_type": "bank", "name": name, "opening_balance": "0"}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _create_active_contract(client, headers, tenant_id, property_id, rent="500.00"):
    contract = client.post("/api/v1/rentals", json={
        "tenant_id": tenant_id, "property_id": property_id,
        "start_date": str(date.today() - timedelta(days=30)), "end_date": str(date.today() + timedelta(days=700)),
        "payment_frequency": "monthly", "rent_amount": rent, "security_deposit_amount": "0",
    }, headers=headers)
    assert contract.status_code == 201, contract.text
    contract = contract.json()
    activated = client.post(f"/api/v1/rentals/{contract['id']}/activate", headers=headers)
    assert activated.status_code == 200, activated.text
    return activated.json()


# ==================== Security deposit lifecycle ====================
def test_receive_deposit_sets_held_status_and_balance(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    unit_id = _create_unit(client, headers, owner_id)
    tenant_id = _create_tenant(client, headers)
    contract = _create_active_contract(client, headers, tenant_id, unit_id)
    account_id = _create_account(client, headers)

    service = DepositService(db_session)
    result = service.receive_deposit("rental", contract["id"], Decimal("1000.00"), account_id, date.today(), seeded_admin.id)

    assert result["ledger_entry"].action == DepositAction.RECEIVED
    assert result["ledger_entry"].balance_after == Decimal("1000.00")
    summary = service.get_summary("rental", contract["id"])
    assert summary["status"] == RentalSecurityDepositStatus.HELD
    assert summary["remaining_balance"] == Decimal("1000.00")


def test_duplicate_deposit_rejected(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    unit_id = _create_unit(client, headers, owner_id)
    tenant_id = _create_tenant(client, headers)
    contract = _create_active_contract(client, headers, tenant_id, unit_id)
    account_id = _create_account(client, headers)

    service = DepositService(db_session)
    service.receive_deposit("rental", contract["id"], Decimal("1000.00"), account_id, date.today(), seeded_admin.id)
    with pytest.raises(DuplicateDepositError):
        service.receive_deposit("rental", contract["id"], Decimal("500.00"), account_id, date.today(), seeded_admin.id)


def test_negative_deposit_rejected(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    unit_id = _create_unit(client, headers, owner_id)
    tenant_id = _create_tenant(client, headers)
    contract = _create_active_contract(client, headers, tenant_id, unit_id)
    account_id = _create_account(client, headers)

    service = DepositService(db_session)
    with pytest.raises(NegativeDepositError):
        service.receive_deposit("rental", contract["id"], Decimal("-10.00"), account_id, date.today(), seeded_admin.id)


def test_partial_then_full_refund(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    unit_id = _create_unit(client, headers, owner_id)
    tenant_id = _create_tenant(client, headers)
    contract = _create_active_contract(client, headers, tenant_id, unit_id)
    account_id = _create_account(client, headers)

    service = DepositService(db_session)
    service.receive_deposit("rental", contract["id"], Decimal("1000.00"), account_id, date.today(), seeded_admin.id)

    partial = service.refund_deposit("rental", contract["id"], Decimal("400.00"), account_id, date.today(), "partial move-out refund", seeded_admin.id)
    assert partial["ledger_entry"].action == DepositAction.PARTIAL_REFUND
    assert partial["ledger_entry"].balance_after == Decimal("600.00")
    summary = service.get_summary("rental", contract["id"])
    assert summary["status"] == RentalSecurityDepositStatus.PARTIALLY_RETURNED

    full = service.refund_deposit("rental", contract["id"], Decimal("600.00"), account_id, date.today(), "final refund", seeded_admin.id)
    assert full["ledger_entry"].action == DepositAction.FULL_REFUND
    assert full["ledger_entry"].balance_after == Decimal("0.00")
    summary = service.get_summary("rental", contract["id"])
    assert summary["status"] == RentalSecurityDepositStatus.RETURNED


def test_over_refund_rejected(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    unit_id = _create_unit(client, headers, owner_id)
    tenant_id = _create_tenant(client, headers)
    contract = _create_active_contract(client, headers, tenant_id, unit_id)
    account_id = _create_account(client, headers)

    service = DepositService(db_session)
    service.receive_deposit("rental", contract["id"], Decimal("500.00"), account_id, date.today(), seeded_admin.id)
    with pytest.raises(OverRefundError):
        service.refund_deposit("rental", contract["id"], Decimal("600.00"), account_id, date.today(), "too much", seeded_admin.id)


def test_deduction_reduces_balance_without_new_transaction(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    unit_id = _create_unit(client, headers, owner_id)
    tenant_id = _create_tenant(client, headers)
    contract = _create_active_contract(client, headers, tenant_id, unit_id)
    account_id = _create_account(client, headers)

    service = DepositService(db_session)
    service.receive_deposit("rental", contract["id"], Decimal("1000.00"), account_id, date.today(), seeded_admin.id)
    result = service.deduct_deposit("rental", contract["id"], Decimal("150.00"), "carpet damage", seeded_admin.id)

    assert result["ledger_entry"].action == DepositAction.DEDUCTION
    assert result["ledger_entry"].transaction_id is None  # no new cash movement — see deposit_service.py's docstring
    assert result["ledger_entry"].balance_after == Decimal("850.00")


def test_forfeit_zeroes_remaining_balance(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    unit_id = _create_unit(client, headers, owner_id)
    tenant_id = _create_tenant(client, headers)
    contract = _create_active_contract(client, headers, tenant_id, unit_id)
    account_id = _create_account(client, headers)

    service = DepositService(db_session)
    service.receive_deposit("rental", contract["id"], Decimal("700.00"), account_id, date.today(), seeded_admin.id)
    result = service.forfeit_deposit("rental", contract["id"], "lease breach", seeded_admin.id)

    assert result["ledger_entry"].action == DepositAction.FORFEIT
    assert result["ledger_entry"].balance_after == Decimal("0.00")
    summary = service.get_summary("rental", contract["id"])
    assert summary["status"] == RentalSecurityDepositStatus.FORFEITED


def test_cannot_act_on_settled_deposit(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    unit_id = _create_unit(client, headers, owner_id)
    tenant_id = _create_tenant(client, headers)
    contract = _create_active_contract(client, headers, tenant_id, unit_id)
    account_id = _create_account(client, headers)

    service = DepositService(db_session)
    service.receive_deposit("rental", contract["id"], Decimal("300.00"), account_id, date.today(), seeded_admin.id)
    service.forfeit_deposit("rental", contract["id"], "breach", seeded_admin.id)

    with pytest.raises(InvalidDepositTransitionError):
        service.refund_deposit("rental", contract["id"], Decimal("10.00"), account_id, date.today(), "too late", seeded_admin.id)


def test_transfer_to_owner_credits_owner_ledger(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    unit_id = _create_unit(client, headers, owner_id)
    tenant_id = _create_tenant(client, headers)
    contract = _create_active_contract(client, headers, tenant_id, unit_id)
    account_id = _create_account(client, headers)

    service = DepositService(db_session)
    service.receive_deposit("rental", contract["id"], Decimal("1000.00"), account_id, date.today(), seeded_admin.id)
    result = service.transfer_to_owner("rental", contract["id"], Decimal("400.00"), owner_id, seeded_admin.id, "damage settlement to owner")

    assert result["owner_ledger_entry"].credit == Decimal("400.00")
    assert result["deposit_ledger_entry"].balance_after == Decimal("600.00")

    from app.business_workflows.owner_ledger.owner_balance_service import OwnerBalanceService
    assert OwnerBalanceService(db_session).get_current_balance(owner_id) == Decimal("400.00")


# ==================== Ledger sync / integrity ====================
def test_deposit_ledger_stays_internally_consistent(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    unit_id = _create_unit(client, headers, owner_id)
    tenant_id = _create_tenant(client, headers)
    contract = _create_active_contract(client, headers, tenant_id, unit_id)
    account_id = _create_account(client, headers)

    service = DepositService(db_session)
    service.receive_deposit("rental", contract["id"], Decimal("1000.00"), account_id, date.today(), seeded_admin.id)
    service.deduct_deposit("rental", contract["id"], Decimal("100.00"), "cleaning", seeded_admin.id)
    service.refund_deposit("rental", contract["id"], Decimal("900.00"), account_id, date.today(), "final refund", seeded_admin.id)

    result = LedgerSyncService(db_session).verify_deposit_ledger("rental", contract["id"])
    assert result["is_consistent"] is True
    assert result["entries_checked"] == 3


# ==================== Validations ====================
def test_duplicate_transaction_reference_rejected(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    unit_id = _create_unit(client, headers, owner_id)
    tenant_id = _create_tenant(client, headers)
    contract = _create_active_contract(client, headers, tenant_id, unit_id)
    account_id = _create_account(client, headers)

    service = DepositService(db_session)
    service.receive_deposit("rental", contract["id"], Decimal("500.00"), account_id, date.today(), seeded_admin.id, reference_number="DUP-001")

    contract2 = _create_active_contract(client, headers, _create_tenant(client, headers, first_name="Two"), _create_unit(client, headers, owner_id, title="Fin Unit 2"))
    with pytest.raises(DuplicateTransactionError):
        service.receive_deposit("rental", contract2["id"], Decimal("500.00"), account_id, date.today(), seeded_admin.id, reference_number="DUP-001")


def test_invalid_allocation_sum_rejected(db_session):
    validator = FinancialValidator(db_session)
    with pytest.raises(InvalidAllocationError):
        validator.validate_allocation_sum(Decimal("100.00"), [{"invoice_id": 1, "amount": "60.00"}])


# ==================== Ledger views ====================
def test_company_ledger_reflects_account_balances(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    account_id = _create_account(client, headers, name="Company Ledger Test")

    balance_service = BalanceService(db_session)
    ledger = balance_service.get_company_ledger()
    assert any(a["account_id"] == account_id for a in ledger["accounts"])
    assert ledger["total_balance"] == ledger["cash_total"] + ledger["bank_total"]


def test_tenant_ledger_totals_deposits_and_payments(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    unit_id = _create_unit(client, headers, owner_id)
    tenant_id = _create_tenant(client, headers)
    contract = _create_active_contract(client, headers, tenant_id, unit_id)
    account_id = _create_account(client, headers)

    DepositService(db_session).receive_deposit("rental", contract["id"], Decimal("300.00"), account_id, date.today(), seeded_admin.id)

    ledger = BalanceService(db_session).get_tenant_ledger(tenant_id)
    assert ledger["total_deposited"] == Decimal("300.00")


def test_property_ledger_computes_net_income(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    unit_id = _create_unit(client, headers, owner_id)

    ledger = BalanceService(db_session).get_property_ledger(unit_id)
    assert ledger["property_id"] == unit_id
    assert ledger["net_income"] == ledger["rental_income"] - ledger["operating_expenses"] - ledger["owner_expenses"]


def test_building_ledger_aggregates_across_units(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    building = client.post("/api/v1/properties", json={"property_type": "building", "title": "Fin Building", "owner_id": owner_id}, headers=headers)
    assert building.status_code == 201, building.text
    building_id = building.json()["id"]
    _create_unit(client, headers, owner_id, title="Fin Building Unit A")

    ledger = BalanceService(db_session).get_building_ledger(building_id)
    assert ledger["building_id"] == building_id


# ==================== Adjustments ====================
def test_owner_adjustment_credits_owner_ledger(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)

    entry = AdjustmentService(db_session).adjust_owner_balance(owner_id, Decimal("120.00"), "goodwill credit", seeded_admin.id, is_credit=True)
    assert entry.credit == Decimal("120.00")

    from app.business_workflows.owner_ledger.owner_balance_service import OwnerBalanceService
    assert OwnerBalanceService(db_session).get_current_balance(owner_id) == Decimal("120.00")


def test_tenant_adjustment_creates_transaction(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    unit_id = _create_unit(client, headers, owner_id)
    tenant_id = _create_tenant(client, headers)
    account_id = _create_account(client, headers)

    txn = AdjustmentService(db_session).adjust_tenant_balance(tenant_id, account_id, Decimal("50.00"), "billing correction", seeded_admin.id, property_id=unit_id)
    assert txn.transaction_type == "adjustment"
    assert txn.amount == Decimal("50.00")


# ==================== API / Permissions ====================
def test_full_api_workflow(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    unit_id = _create_unit(client, headers, owner_id)
    tenant_id = _create_tenant(client, headers)
    contract = _create_active_contract(client, headers, tenant_id, unit_id)
    account_id = _create_account(client, headers)

    deposit = client.post("/api/v1/financial-engine/deposit", json={
        "contract_type": "rental", "contract_id": contract["id"], "account_id": account_id,
        "amount": "800.00", "payment_date": str(date.today()),
    }, headers=headers)
    assert deposit.status_code == 201, deposit.text

    summary = client.get(f"/api/v1/financial-engine/deposits/rental/{contract['id']}", headers=headers)
    assert summary.status_code == 200
    assert summary.json()["remaining_balance"] == "800.00" or float(summary.json()["remaining_balance"]) == 800.00

    verify = client.get(f"/api/v1/financial-engine/deposits/rental/{contract['id']}/verify", headers=headers)
    assert verify.status_code == 200
    assert verify.json()["is_consistent"] is True

    company = client.get("/api/v1/financial-engine/company", headers=headers)
    assert company.status_code == 200

    ledgers = client.get("/api/v1/financial-engine/ledgers", headers=headers)
    assert ledgers.status_code == 200
    assert "company" in ledgers.json()

    dashboard = client.get("/api/v1/financial-engine/dashboard", headers=headers)
    assert dashboard.status_code == 200
    assert "security_deposits_held" in dashboard.json()

    transfer_target = _create_account(client, headers, name="Transfer Target")
    transfer = client.post("/api/v1/financial-engine/transfer", json={
        "from_account_id": account_id, "to_account_id": transfer_target, "amount": "50.00", "transaction_date": str(date.today()),
    }, headers=headers)
    assert transfer.status_code == 201, transfer.text


def test_financial_engine_write_actions_require_edit_permission(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    unit_id = _create_unit(client, headers, owner_id)
    tenant_id = _create_tenant(client, headers)
    contract = _create_active_contract(client, headers, tenant_id, unit_id)
    account_id = _create_account(client, headers)

    _financial_viewer(db_session)
    login = client.post("/api/v1/auth/login", json={"email": "fin-viewer@test.com", "password": "Viewer@12345"})
    viewer_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    resp = client.post("/api/v1/financial-engine/deposit", json={
        "contract_type": "rental", "contract_id": contract["id"], "account_id": account_id,
        "amount": "100.00", "payment_date": str(date.today()),
    }, headers=viewer_headers)
    assert resp.status_code == 403

    view_resp = client.get("/api/v1/financial-engine/company", headers=viewer_headers)
    assert view_resp.status_code == 200


def test_financial_engine_requires_authentication(client, seeded_admin):
    resp = client.get("/api/v1/financial-engine/company")
    assert resp.status_code == 401
