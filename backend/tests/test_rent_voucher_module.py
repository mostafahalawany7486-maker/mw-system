"""
Unit tests for the Rent Voucher Printing module
(app/services/rent_voucher_service.py, app/api/v1/routers/rent_vouchers.py).

Covers: generation (tenant + company copy pair, idempotent, rejects
non-tenant-payment transactions), the bilingual print DTO, barcode
uniqueness/lookup, print/reprint tracking, and permission enforcement.
"""
from datetime import date
from decimal import Decimal
import pytest
from fastapi import HTTPException

from app.services.rent_voucher_service import RentVoucherService
from app.core.security import hash_password
from app.models.user import User, Role, Permission


def _auth_headers(client):
    resp = client.post("/api/v1/auth/login", json={"email": "admin@test.com", "password": "Admin@12345"})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _voucher_viewer(db_session):
    perms = [Permission(code="rent_vouchers.view", module="rent_vouchers", action="view")]
    for p in perms:
        db_session.add(p)
    db_session.flush()
    role = Role(name="Voucher Viewer", description="View-only", is_system_role=False)
    role.permissions = perms
    db_session.add(role)
    db_session.flush()
    user = User(
        first_name="Voucher", last_name="Viewer", email="voucher-viewer@test.com",
        hashed_password=hash_password("Viewer@12345"), is_active=True, is_superuser=False, role_id=role.id,
    )
    db_session.add(user)
    db_session.commit()
    return user


def _create_tenant(client, headers, **overrides):
    payload = {"tenant_type": "individual", "first_name": "Voucher", "last_name": "Tenant"}
    payload.update(overrides)
    resp = client.post("/api/v1/tenants", json=payload, headers=headers)
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_unit(client, headers):
    owner = client.post("/api/v1/owners", json={"owner_type": "individual", "first_name": "Voucher", "last_name": "Owner"}, headers=headers).json()
    building = client.post("/api/v1/properties", json={"property_type": "building", "title": "Voucher Tower", "owner_id": owner["id"]}, headers=headers).json()
    unit = client.post("/api/v1/properties", json={
        "property_type": "apartment", "title": "Unit 12", "owner_id": owner["id"],
        "parent_property_id": building["id"], "unit_number": "12",
    }, headers=headers)
    assert unit.status_code == 201
    return unit.json()["id"]


def _create_account(client, headers):
    resp = client.post("/api/v1/financial/accounts", json={"account_type": "bank", "name": "Voucher Test Bank", "opening_balance": "0"}, headers=headers)
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_tenant_payment_transaction(client, headers, tenant_id, property_id, account_id, amount="1250.00", payment_method="knet"):
    resp = client.post("/api/v1/financial/transactions", json={
        "transaction_type": "tenant_payment", "amount": amount, "account_id": account_id,
        "tenant_id": tenant_id, "property_id": property_id, "payment_method": payment_method,
        "transaction_date": str(date.today()),
    }, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _create_expense_transaction(client, headers, account_id, amount="100.00"):
    resp = client.post("/api/v1/financial/transactions", json={
        "transaction_type": "expense", "amount": amount, "account_id": account_id,
        "transaction_date": str(date.today()),
    }, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


# ==================== Generation ====================
def test_generate_creates_tenant_and_company_copy(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    unit_id = _create_unit(client, headers)
    account_id = _create_account(client, headers)
    txn_id = _create_tenant_payment_transaction(client, headers, tenant_id, unit_id, account_id)

    service = RentVoucherService(db_session)
    vouchers, created, already_existed = service.generate_vouchers(
        [txn_id], date.today().replace(day=1), actor_id=seeded_admin.id,
    )

    assert created == 2
    assert already_existed == 0
    copy_types = sorted(v.copy_type for v in vouchers)
    assert copy_types == ["company", "tenant"]
    assert len({v.voucher_number for v in vouchers}) == 2
    assert len({v.barcode_value for v in vouchers}) == 2
    for v in vouchers:
        assert v.transaction_id == txn_id
        assert v.tenant_name is not None
        assert v.building_name == "Voucher Tower"
        assert v.unit_number == "12"
        assert v.amount == Decimal("1250.00")


def test_generate_is_idempotent_per_transaction(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    unit_id = _create_unit(client, headers)
    account_id = _create_account(client, headers)
    txn_id = _create_tenant_payment_transaction(client, headers, tenant_id, unit_id, account_id)

    service = RentVoucherService(db_session)
    service.generate_vouchers([txn_id], date.today().replace(day=1), actor_id=seeded_admin.id)
    vouchers, created, already_existed = service.generate_vouchers(
        [txn_id], date.today().replace(day=1), actor_id=seeded_admin.id,
    )

    assert created == 0
    assert already_existed == 2
    assert len(vouchers) == 2  # still just the tenant+company pair, no duplicates


def test_generate_rejects_non_tenant_payment_transaction(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    account_id = _create_account(client, headers)
    expense_txn_id = _create_expense_transaction(client, headers, account_id)

    service = RentVoucherService(db_session)
    with pytest.raises(HTTPException) as exc_info:
        service.generate_vouchers([expense_txn_id], date.today().replace(day=1), actor_id=seeded_admin.id)
    assert exc_info.value.status_code == 400


def test_generate_rejects_invalid_transaction_id(client, db_session, seeded_admin):
    service = RentVoucherService(db_session)
    with pytest.raises(HTTPException) as exc_info:
        service.generate_vouchers([999999], date.today().replace(day=1), actor_id=seeded_admin.id)
    assert exc_info.value.status_code == 400


def test_generate_for_multiple_transactions(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    unit_id = _create_unit(client, headers)
    account_id = _create_account(client, headers)

    tenant1 = _create_tenant(client, headers, first_name="One")
    tenant2 = _create_tenant(client, headers, first_name="Two")
    txn1 = _create_tenant_payment_transaction(client, headers, tenant1, unit_id, account_id, amount="500.00")
    txn2 = _create_tenant_payment_transaction(client, headers, tenant2, unit_id, account_id, amount="600.00")

    service = RentVoucherService(db_session)
    vouchers, created, already_existed = service.generate_vouchers(
        [txn1, txn2], date.today().replace(day=1), actor_id=seeded_admin.id,
    )
    assert created == 4  # 2 transactions x (tenant copy + company copy)
    assert len(vouchers) == 4


# ==================== Print DTO ====================
def test_print_data_is_bilingual(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    unit_id = _create_unit(client, headers)
    account_id = _create_account(client, headers)
    txn_id = _create_tenant_payment_transaction(client, headers, tenant_id, unit_id, account_id, amount="1250.00", payment_method="knet")

    service = RentVoucherService(db_session)
    vouchers, _, _ = service.generate_vouchers([txn_id], date(2026, 7, 1), actor_id=seeded_admin.id)
    tenant_copy = next(v for v in vouchers if v.copy_type == "tenant")

    dto = service.get_voucher_print_data(tenant_copy.id)

    assert dto["copy_type_label_en"] == "TENANT COPY"
    assert dto["copy_type_label_ar"] == "نسخة المستأجر"
    assert dto["rental_month_display_en"] == "July 2026"
    assert "يوليو" in dto["rental_month_display_ar"]
    assert dto["payment_method_label_en"] == "K-Net"
    assert dto["payment_method_label_ar"] == "كي نت"
    assert dto["amount"] == Decimal("1250.00")
    assert "One Thousand Two Hundred Fifty" in dto["amount_in_words_en"]
    assert dto["amount_in_words_ar"]  # non-empty Arabic string produced
    assert dto["barcode_value"] == tenant_copy.barcode_value
    assert tenant_copy.voucher_number in dto["barcode_value"]


def test_print_data_maps_cash_and_other_payment_methods(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    unit_id = _create_unit(client, headers)
    account_id = _create_account(client, headers)
    txn_id = _create_tenant_payment_transaction(client, headers, tenant_id, unit_id, account_id, payment_method="cash")

    service = RentVoucherService(db_session)
    vouchers, _, _ = service.generate_vouchers([txn_id], date.today().replace(day=1), actor_id=seeded_admin.id)
    dto = service.get_voucher_print_data(vouchers[0].id)
    assert dto["payment_method_label_en"] == "Cash"
    assert dto["payment_method_label_ar"] == "نقدي"


def test_bulk_print_data(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    unit_id = _create_unit(client, headers)
    account_id = _create_account(client, headers)
    txn_id = _create_tenant_payment_transaction(client, headers, tenant_id, unit_id, account_id)

    service = RentVoucherService(db_session)
    vouchers, _, _ = service.generate_vouchers([txn_id], date.today().replace(day=1), actor_id=seeded_admin.id)

    dtos = service.get_bulk_print_data([v.id for v in vouchers])
    assert len(dtos) == 2


def test_bulk_print_data_rejects_missing_ids(client, db_session, seeded_admin):
    service = RentVoucherService(db_session)
    with pytest.raises(HTTPException) as exc_info:
        service.get_bulk_print_data([999999])
    assert exc_info.value.status_code == 404


# ==================== Barcode lookup ====================
def test_lookup_voucher_by_barcode(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    unit_id = _create_unit(client, headers)
    account_id = _create_account(client, headers)
    txn_id = _create_tenant_payment_transaction(client, headers, tenant_id, unit_id, account_id)

    service = RentVoucherService(db_session)
    vouchers, _, _ = service.generate_vouchers([txn_id], date.today().replace(day=1), actor_id=seeded_admin.id)
    target = vouchers[0]

    found = service.get_voucher_by_barcode(target.barcode_value)
    assert found.id == target.id


def test_lookup_unknown_barcode_404s(client, db_session, seeded_admin):
    service = RentVoucherService(db_session)
    with pytest.raises(HTTPException) as exc_info:
        service.get_voucher_by_barcode("does-not-exist")
    assert exc_info.value.status_code == 404


# ==================== Print / reprint tracking ====================
def test_record_print_increments_and_flags_reprint(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    unit_id = _create_unit(client, headers)
    account_id = _create_account(client, headers)
    txn_id = _create_tenant_payment_transaction(client, headers, tenant_id, unit_id, account_id)

    service = RentVoucherService(db_session)
    vouchers, _, _ = service.generate_vouchers([txn_id], date.today().replace(day=1), actor_id=seeded_admin.id)
    voucher_id = vouchers[0].id

    first = service.record_print(voucher_id, actor_id=seeded_admin.id)
    assert first.print_count == 1
    assert first.printed_at is not None

    second = service.record_print(voucher_id, actor_id=seeded_admin.id)
    assert second.print_count == 2


# ==================== API / Permissions ====================
def test_full_api_workflow(client, seeded_admin):
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    unit_id = _create_unit(client, headers)
    account_id = _create_account(client, headers)
    txn_id = _create_tenant_payment_transaction(client, headers, tenant_id, unit_id, account_id)

    generated = client.post("/api/v1/rent-vouchers/generate", json={
        "transaction_ids": [txn_id], "rental_month": str(date.today().replace(day=1)),
    }, headers=headers)
    assert generated.status_code == 201
    body = generated.json()
    assert body["created_count"] == 2
    voucher_ids = [v["id"] for v in body["vouchers"]]

    listed = client.get("/api/v1/rent-vouchers", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["total"] >= 2

    print_data = client.get(f"/api/v1/rent-vouchers/{voucher_ids[0]}/print-data", headers=headers)
    assert print_data.status_code == 200
    assert "copy_type_label_ar" in print_data.json()

    bulk = client.post("/api/v1/rent-vouchers/print-data/bulk", json={"voucher_ids": voucher_ids}, headers=headers)
    assert bulk.status_code == 200
    assert len(bulk.json()) == 2

    recorded = client.post(f"/api/v1/rent-vouchers/{voucher_ids[0]}/record-print", headers=headers)
    assert recorded.status_code == 200
    assert recorded.json()["print_count"] == 1

    barcode_value = client.get(f"/api/v1/rent-vouchers/{voucher_ids[0]}", headers=headers).json()["barcode_value"]
    by_barcode = client.get(f"/api/v1/rent-vouchers/barcode/{barcode_value}", headers=headers)
    assert by_barcode.status_code == 200
    assert by_barcode.json()["id"] == voucher_ids[0]


def test_generate_rejects_without_create_permission(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    unit_id = _create_unit(client, headers)
    account_id = _create_account(client, headers)
    txn_id = _create_tenant_payment_transaction(client, headers, tenant_id, unit_id, account_id)

    _voucher_viewer(db_session)
    login = client.post("/api/v1/auth/login", json={"email": "voucher-viewer@test.com", "password": "Viewer@12345"})
    viewer_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    resp = client.post("/api/v1/rent-vouchers/generate", json={
        "transaction_ids": [txn_id], "rental_month": str(date.today().replace(day=1)),
    }, headers=viewer_headers)
    assert resp.status_code == 403

    listed = client.get("/api/v1/rent-vouchers", headers=viewer_headers)
    assert listed.status_code == 200  # rent_vouchers.view is granted


def test_rent_vouchers_require_authentication(client, seeded_admin):
    resp = client.get("/api/v1/rent-vouchers")
    assert resp.status_code == 401
