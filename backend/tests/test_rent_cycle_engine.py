"""
Unit tests for the Rent Cycle Engine
(app/business_workflows/rent_cycle/, app/api/v1/routers/rent_cycles.py).

Covers: cycle creation, duplicate prevention, generation (incl. reuse of
the existing invoicing/receipt engines and duplicate-generation
prevention), regeneration authorization, closing, reopening,
cancellation, and permission enforcement — matching the "UNIT TESTS"
section of the spec.
"""
from datetime import date, timedelta
import pytest

from app.business_workflows.rent_cycle.rent_cycle_service import RentCycleService
from app.business_workflows.rent_cycle.rent_cycle_exceptions import (
    DuplicateCycleError, InvalidCycleStatusTransitionError, RegenerationNotAuthorizedError,
    CycleValidationError,
)
from app.core.security import hash_password
from app.models.user import User, Role, Permission


def _auth_headers(client):
    resp = client.post("/api/v1/auth/login", json={"email": "admin@test.com", "password": "Admin@12345"})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _rent_cycle_viewer(db_session):
    """A non-superuser account with only rent_cycles.view — used to
    exercise the 403 path without touching the shared conftest fixtures."""
    perms = [
        Permission(code="rent_cycles.view", module="rent_cycles", action="view"),
    ]
    for p in perms:
        db_session.add(p)
    db_session.flush()
    role = Role(name="Rent Cycle Viewer", description="View-only", is_system_role=False)
    role.permissions = perms
    db_session.add(role)
    db_session.flush()
    user = User(
        first_name="Cycle", last_name="Viewer", email="cycle-viewer@test.com",
        hashed_password=hash_password("Viewer@12345"), is_active=True, is_superuser=False, role_id=role.id,
    )
    db_session.add(user)
    db_session.commit()
    return user


def _rent_cycle_editor(db_session):
    """A non-superuser account WITH rent_cycles.edit — used to isolate
    the 'force requires administrator' rule from generic permission
    enforcement (which a view-only account would also fail on, but for
    a different reason)."""
    perms = [
        Permission(code="rent_cycles.view", module="rent_cycles", action="view"),
        Permission(code="rent_cycles.edit", module="rent_cycles", action="edit"),
        Permission(code="rent_cycles.create", module="rent_cycles", action="create"),
    ]
    for p in perms:
        db_session.add(p)
    db_session.flush()
    role = Role(name="Rent Cycle Editor", description="Edit, non-admin", is_system_role=False)
    role.permissions = perms
    db_session.add(role)
    db_session.flush()
    user = User(
        first_name="Cycle", last_name="Editor", email="cycle-editor@test.com",
        hashed_password=hash_password("Editor@12345"), is_active=True, is_superuser=False, role_id=role.id,
    )
    db_session.add(user)
    db_session.commit()
    return user


def _create_tenant(client, headers):
    resp = client.post("/api/v1/tenants", json={"tenant_type": "individual", "first_name": "RC", "last_name": "Tenant"}, headers=headers)
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_unit(client, headers):
    owner = client.post("/api/v1/owners", json={"owner_type": "individual", "first_name": "RC", "last_name": "Owner"}, headers=headers).json()
    resp = client.post("/api/v1/properties", json={"property_type": "apartment", "title": "RC Engine Unit", "owner_id": owner["id"]}, headers=headers)
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_active_contract(client, headers, tenant_id, property_id, rent="600.00"):
    contract = client.post("/api/v1/rentals", json={
        "tenant_id": tenant_id, "property_id": property_id,
        # 60 days back guarantees the contract's start_date is always
        # before the first of the *current* month, regardless of what
        # day of the month tests happen to run on — list_active_for_billing
        # requires start_date <= as_of (the cycle's start_date, which is
        # always day 1 of the month here), so a too-recent start_date
        # would make the contract wrongly ineligible depending on today.
        "start_date": str(date.today() - timedelta(days=60)), "end_date": str(date.today() + timedelta(days=700)),
        "payment_frequency": "monthly", "rent_amount": rent, "security_deposit_amount": rent,
    }, headers=headers)
    assert contract.status_code == 201, contract.text
    contract = contract.json()
    activated = client.post(f"/api/v1/rentals/{contract['id']}/activate", headers=headers)
    assert activated.status_code == 200
    # activate_contract does NOT itself generate the installment
    # schedule (a separate step, same as the Lease Agreement side) — the
    # Rent Cycle Engine's receipt step reads RentalPaymentInstallment
    # rows, so tests need this to exist for generate_monthly_receipts to
    # find anything due this month.
    schedule = client.post(f"/api/v1/rentals/{contract['id']}/installments/generate", json={"overwrite_existing": False}, headers=headers)
    assert schedule.status_code == 200, schedule.text
    return contract


def _create_account(client, headers):
    resp = client.post("/api/v1/financial/accounts", json={"account_type": "bank", "name": "RC Engine Bank", "opening_balance": "0"}, headers=headers)
    assert resp.status_code == 201
    return resp.json()["id"]


def _cycle_payload(**overrides):
    today = date.today()
    payload = {
        "month": today.month, "year": today.year,
        "start_date": str(today.replace(day=1)),
        "due_date": str(today.replace(day=1) + timedelta(days=15)),
    }
    payload.update(overrides)
    return payload


# ==================== Creation ====================
def test_create_cycle_via_service(client, db_session, seeded_admin):
    service = RentCycleService(db_session)
    cycle = service.create_cycle(_cycle_payload(), actor_id=seeded_admin.id)

    assert cycle.cycle_number.startswith("RC-")
    assert cycle.cycle_status == "draft"
    assert cycle.records == []


def test_create_cycle_defaults_dates_when_omitted(client, db_session, seeded_admin):
    service = RentCycleService(db_session)
    today = date.today()
    cycle = service.create_cycle({"month": today.month, "year": today.year}, actor_id=seeded_admin.id)

    assert cycle.start_date == today.replace(day=1)
    assert cycle.due_date == cycle.start_date + timedelta(days=15)


def test_create_duplicate_cycle_for_same_period_rejected(client, db_session, seeded_admin):
    service = RentCycleService(db_session)
    service.create_cycle(_cycle_payload(), actor_id=seeded_admin.id)

    with pytest.raises(DuplicateCycleError):
        service.create_cycle(_cycle_payload(), actor_id=seeded_admin.id)


def test_create_cycle_via_api(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    resp = client.post("/api/v1/rent-cycles", json=_cycle_payload(), headers=headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["cycle_status"] == "draft"
    assert body["records"] == []


# ==================== Generation ====================
def test_generate_creates_records_from_active_leases(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    unit_id = _create_unit(client, headers)
    _create_active_contract(client, headers, tenant_id, unit_id, rent="600.00")

    service = RentCycleService(db_session)
    cycle = service.create_cycle(_cycle_payload(), actor_id=seeded_admin.id)
    updated, result = service.generate(cycle.id, actor_id=seeded_admin.id, is_admin=False)

    assert updated.cycle_status == "generated"
    assert result.invoices_generated == 1
    assert result.receipts_generated == 1
    assert len(updated.records) == 1
    record = updated.records[0]
    assert record.rental_contract_id
    assert record.invoice_id is not None
    assert record.installment_id is not None
    assert record.amount == 600.00 or float(record.amount) == 600.00
    assert record.tenant_display_name is not None
    assert record.property_title == "RC Engine Unit"
    assert record.invoice_number is not None
    assert record.receipt_number is not None


def test_generate_skips_leases_outside_active_leases(client, db_session, seeded_admin):
    """No active leases at all -> generation succeeds with zero records,
    never errors."""
    service = RentCycleService(db_session)
    cycle = service.create_cycle(_cycle_payload(), actor_id=seeded_admin.id)
    updated, result = service.generate(cycle.id, actor_id=seeded_admin.id, is_admin=False)

    assert updated.cycle_status == "generated"
    assert result.invoices_generated == 0
    assert updated.records == []


def test_generate_is_idempotent_without_force(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    unit_id = _create_unit(client, headers)
    _create_active_contract(client, headers, tenant_id, unit_id)

    service = RentCycleService(db_session)
    cycle = service.create_cycle(_cycle_payload(), actor_id=seeded_admin.id)
    service.generate(cycle.id, actor_id=seeded_admin.id, is_admin=False)

    updated, result = service.generate(cycle.id, actor_id=seeded_admin.id, is_admin=False)
    assert result.invoices_generated == 0
    assert result.receipts_generated == 0
    assert len(updated.records) == 1  # unchanged, no duplicates


def test_regenerate_requires_admin_approval(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    unit_id = _create_unit(client, headers)
    _create_active_contract(client, headers, tenant_id, unit_id)

    service = RentCycleService(db_session)
    cycle = service.create_cycle(_cycle_payload(), actor_id=seeded_admin.id)
    service.generate(cycle.id, actor_id=seeded_admin.id, is_admin=False)

    with pytest.raises(RegenerationNotAuthorizedError):
        service.generate(cycle.id, actor_id=seeded_admin.id, is_admin=False, force=True)

    # An administrator, however, may force it.
    updated, result = service.generate(cycle.id, actor_id=seeded_admin.id, is_admin=True, force=True)
    assert updated.cycle_status == "generated"


def test_generate_never_creates_duplicate_record_for_same_lease(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    unit_id = _create_unit(client, headers)
    _create_active_contract(client, headers, tenant_id, unit_id)

    service = RentCycleService(db_session)
    cycle = service.create_cycle(_cycle_payload(), actor_id=seeded_admin.id)
    service.generate(cycle.id, actor_id=seeded_admin.id, is_admin=False)
    # Force-regenerate as admin — must still not duplicate the record
    # for the same (cycle, lease) pair.
    updated, _ = service.generate(cycle.id, actor_id=seeded_admin.id, is_admin=True, force=True)
    assert len(updated.records) == 1


def test_cannot_generate_a_cancelled_cycle(client, db_session, seeded_admin):
    service = RentCycleService(db_session)
    cycle = service.create_cycle(_cycle_payload(), actor_id=seeded_admin.id)
    service.cancel_cycle(cycle.id, "No leases this period", actor_id=seeded_admin.id)

    with pytest.raises(InvalidCycleStatusTransitionError):
        service.generate(cycle.id, actor_id=seeded_admin.id, is_admin=True, force=True)


# ==================== Close / Reopen / Cancel ====================
def test_close_cycle_requires_generation_first(client, db_session, seeded_admin):
    service = RentCycleService(db_session)
    cycle = service.create_cycle(_cycle_payload(), actor_id=seeded_admin.id)

    with pytest.raises(InvalidCycleStatusTransitionError):
        service.close_cycle(cycle.id, None, actor_id=seeded_admin.id)


def test_close_and_reopen_cycle(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    unit_id = _create_unit(client, headers)
    _create_active_contract(client, headers, tenant_id, unit_id)

    service = RentCycleService(db_session)
    cycle = service.create_cycle(_cycle_payload(), actor_id=seeded_admin.id)
    service.generate(cycle.id, actor_id=seeded_admin.id, is_admin=False)

    closed = service.close_cycle(cycle.id, "End of month close", actor_id=seeded_admin.id)
    assert closed.cycle_status == "closed"
    assert closed.closing_date is not None

    reopened = service.reopen_cycle(cycle.id, actor_id=seeded_admin.id)
    assert reopened.cycle_status != "closed"
    assert reopened.closing_date is None


def test_cannot_reopen_a_cycle_that_is_not_closed(client, db_session, seeded_admin):
    service = RentCycleService(db_session)
    cycle = service.create_cycle(_cycle_payload(), actor_id=seeded_admin.id)

    with pytest.raises(InvalidCycleStatusTransitionError):
        service.reopen_cycle(cycle.id, actor_id=seeded_admin.id)


def test_cancel_cycle_requires_reason(client, db_session, seeded_admin):
    service = RentCycleService(db_session)
    cycle = service.create_cycle(_cycle_payload(), actor_id=seeded_admin.id)

    with pytest.raises(CycleValidationError):
        service.cancel_cycle(cycle.id, "   ", actor_id=seeded_admin.id)


def test_cancel_cycle_success(client, db_session, seeded_admin):
    service = RentCycleService(db_session)
    cycle = service.create_cycle(_cycle_payload(), actor_id=seeded_admin.id)

    cancelled = service.cancel_cycle(cycle.id, "Portfolio sold mid-period", actor_id=seeded_admin.id)
    assert cancelled.cycle_status == "cancelled"
    assert cancelled.cancellation_reason == "Portfolio sold mid-period"


def test_cannot_cancel_a_closed_cycle(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    unit_id = _create_unit(client, headers)
    _create_active_contract(client, headers, tenant_id, unit_id)

    service = RentCycleService(db_session)
    cycle = service.create_cycle(_cycle_payload(), actor_id=seeded_admin.id)
    service.generate(cycle.id, actor_id=seeded_admin.id, is_admin=False)
    service.close_cycle(cycle.id, None, actor_id=seeded_admin.id)

    with pytest.raises(InvalidCycleStatusTransitionError):
        service.cancel_cycle(cycle.id, "too late", actor_id=seeded_admin.id)


# ==================== Collection progress ====================
def test_collection_progress_updates_after_payment(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    unit_id = _create_unit(client, headers)
    _create_active_contract(client, headers, tenant_id, unit_id, rent="500.00")
    account_id = _create_account(client, headers)

    service = RentCycleService(db_session)
    cycle = service.create_cycle(_cycle_payload(), actor_id=seeded_admin.id)
    updated, _ = service.generate(cycle.id, actor_id=seeded_admin.id, is_admin=False)
    invoice_id = updated.records[0].invoice_id

    from app.services.financial_service import FinancialService
    financial = FinancialService(db_session)
    financial.send_invoice(invoice_id, actor_id=seeded_admin.id)
    financial.record_invoice_payment(invoice_id, account_id, "bank_transfer", None, date.today(), actor_id=seeded_admin.id)

    progress = service.closer.compute_progress(service.get_cycle(cycle.id))
    assert progress.paid_count == 1
    assert progress.percent == 100


# ==================== Dashboard ====================
def test_dashboard_reflects_current_cycle(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    unit_id = _create_unit(client, headers)
    _create_active_contract(client, headers, tenant_id, unit_id, rent="700.00")

    service = RentCycleService(db_session)
    cycle = service.create_cycle(_cycle_payload(), actor_id=seeded_admin.id)
    service.generate(cycle.id, actor_id=seeded_admin.id, is_admin=False)

    dashboard = service.dashboard()
    assert dashboard["current_cycle_number"] == cycle.cycle_number
    assert dashboard["active_lease_count"] == 1
    assert dashboard["generated_receipt_count"] == 1
    assert dashboard["total_expected_income"] == 700.00 or float(dashboard["total_expected_income"]) == 700.00


# ==================== API / Permissions ====================
def test_full_api_workflow(client, seeded_admin):
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    unit_id = _create_unit(client, headers)
    _create_active_contract(client, headers, tenant_id, unit_id)

    created = client.post("/api/v1/rent-cycles", json=_cycle_payload(), headers=headers)
    assert created.status_code == 201
    cycle_id = created.json()["id"]

    generated = client.post(f"/api/v1/rent-cycles/{cycle_id}/generate", json={}, headers=headers)
    assert generated.status_code == 200
    assert generated.json()["invoices_generated"] == 1

    fetched = client.get(f"/api/v1/rent-cycles/{cycle_id}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["cycle_status"] == "generated"

    closed = client.post(f"/api/v1/rent-cycles/{cycle_id}/close", json={}, headers=headers)
    assert closed.status_code == 200
    assert closed.json()["cycle_status"] == "closed"

    reopened = client.post(f"/api/v1/rent-cycles/{cycle_id}/reopen", headers=headers)
    assert reopened.status_code == 200
    assert reopened.json()["cycle_status"] != "closed"

    listed = client.get("/api/v1/rent-cycles", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["total"] >= 1

    dash = client.get("/api/v1/rent-cycles/dashboard/summary", headers=headers)
    assert dash.status_code == 200


def test_force_regenerate_via_api_requires_superuser(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    _rent_cycle_editor(db_session)

    created = client.post("/api/v1/rent-cycles", json=_cycle_payload(), headers=headers)
    cycle_id = created.json()["id"]
    client.post(f"/api/v1/rent-cycles/{cycle_id}/generate", json={}, headers=headers)

    login = client.post("/api/v1/auth/login", json={"email": "cycle-editor@test.com", "password": "Editor@12345"})
    assert login.status_code == 200
    editor_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    # Has rent_cycles.edit (passes the PermissionChecker), but is not a
    # superuser -> the force=true regeneration itself must still be denied.
    resp = client.post(f"/api/v1/rent-cycles/{cycle_id}/generate", json={"force": True}, headers=editor_headers)
    assert resp.status_code == 403

    # A plain (non-force) generate call on an already-generated cycle
    # is fine for the same non-admin user — it's just a no-op.
    resp2 = client.post(f"/api/v1/rent-cycles/{cycle_id}/generate", json={}, headers=editor_headers)
    assert resp2.status_code == 200
    assert resp2.json()["invoices_generated"] == 0

    # An actual administrator succeeds with force=true.
    resp3 = client.post(f"/api/v1/rent-cycles/{cycle_id}/generate", json={"force": True}, headers=headers)
    assert resp3.status_code == 200


def test_create_rejects_without_permission(client, db_session, seeded_admin):
    _rent_cycle_viewer(db_session)
    login = client.post("/api/v1/auth/login", json={"email": "cycle-viewer@test.com", "password": "Viewer@12345"})
    viewer_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    resp = client.post("/api/v1/rent-cycles", json=_cycle_payload(), headers=viewer_headers)
    assert resp.status_code == 403

    listed = client.get("/api/v1/rent-cycles", headers=viewer_headers)
    assert listed.status_code == 200  # rent_cycles.view is granted


def test_rent_cycles_require_authentication(client, seeded_admin):
    resp = client.get("/api/v1/rent-cycles")
    assert resp.status_code == 401
