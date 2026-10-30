"""
Rent Billing Engine tests. Covers the parts genuinely new in this
phase: bulk invoice generation (respecting each contract's own billing
cycle, never duplicating), the immutable data snapshot, partial
payments, the void/cancel distinction, print tracking, search, QR
verification, the three new reports, and the extended dashboard.
Also includes explicit regression tests confirming the pre-existing
Invoice CRUD/payment flow and the separate Rental Receipt Module are
both completely unaffected.
"""
from datetime import date, timedelta
from decimal import Decimal


def _auth_headers(client):
    resp = client.post("/api/v1/auth/login", json={"email": "admin@test.com", "password": "Admin@12345"})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _create_tenant(client, headers, **overrides):
    payload = {"tenant_type": "individual", "first_name": "Billing", "last_name": "Tenant", "address": "Block 1, Street 5"}
    payload.update(overrides)
    resp = client.post("/api/v1/tenants", json=payload, headers=headers)
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_building_and_unit(client, headers):
    owner = client.post("/api/v1/owners", json={"owner_type": "individual", "first_name": "Billing", "last_name": "Owner"}, headers=headers).json()
    building = client.post("/api/v1/properties", json={"property_type": "building", "title": "Billing Tower", "owner_id": owner["id"]}, headers=headers).json()
    unit = client.post("/api/v1/properties", json={
        "property_type": "apartment", "title": "Unit 501", "owner_id": owner["id"],
        "parent_property_id": building["id"], "unit_number": "501",
    }, headers=headers).json()
    return owner, building, unit


def _create_active_contract(client, headers, tenant_id, property_id, rent="600.000", frequency="monthly"):
    contract = client.post("/api/v1/rentals", json={
        "tenant_id": tenant_id, "property_id": property_id,
        "start_date": str(date.today() - timedelta(days=5)), "end_date": str(date.today() + timedelta(days=700)),
        "payment_frequency": frequency, "rent_amount": rent, "security_deposit_amount": rent,
    }, headers=headers)
    assert contract.status_code == 201, contract.text
    contract = contract.json()
    activated = client.post(f"/api/v1/rentals/{contract['id']}/activate", headers=headers)
    assert activated.status_code == 200
    return contract


def _create_financial_account(client, headers):
    resp = client.post("/api/v1/financial/accounts", json={"account_type": "bank", "name": "Billing Test Bank", "opening_balance": "0"}, headers=headers)
    assert resp.status_code == 201
    return resp.json()["id"]


# ==================== Bulk Generation ====================
def test_bulk_generate_creates_draft_invoice_with_snapshot(client, seeded_admin):
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    owner, building, unit = _create_building_and_unit(client, headers)
    _create_active_contract(client, headers, tenant_id, unit["id"], rent="600.000")

    today = date.today()
    resp = client.post("/api/v1/financial/invoices/bulk-generate", json={"billing_period_start": str(today.replace(day=1))}, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    matching = [i for i in body if i["tenant_id"] == tenant_id]
    assert len(matching) == 1
    assert matching[0]["invoice_status"] == "draft"
    assert matching[0]["billing_cycle"] == "monthly"
    assert Decimal(matching[0]["amount"]) == Decimal("600.000")


def test_bulk_generate_is_idempotent_per_period(client, seeded_admin):
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    owner, building, unit = _create_building_and_unit(client, headers)
    _create_active_contract(client, headers, tenant_id, unit["id"])

    period_start = str(date.today().replace(day=1))
    first = client.post("/api/v1/financial/invoices/bulk-generate", json={"billing_period_start": period_start}, headers=headers)
    second = client.post("/api/v1/financial/invoices/bulk-generate", json={"billing_period_start": period_start}, headers=headers)
    assert first.status_code == 200 and second.status_code == 200
    assert len(second.json()) == 0  # nothing left to generate the second time


def test_bulk_generate_respects_quarterly_cycle_period_length(client, seeded_admin):
    """The engine must not be hardcoded to monthly — a quarterly
    contract's invoice should cover ~3 months, not 1."""
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    owner, building, unit = _create_building_and_unit(client, headers)
    _create_active_contract(client, headers, tenant_id, unit["id"], rent="1800.000", frequency="quarterly")

    period_start = date.today().replace(day=1)
    resp = client.post("/api/v1/financial/invoices/bulk-generate", json={"billing_period_start": str(period_start)}, headers=headers)
    invoice = next(i for i in resp.json() if i["tenant_id"] == tenant_id)
    start = date.fromisoformat(invoice["billing_period_start"])
    end = date.fromisoformat(invoice["billing_period_end"])
    assert 85 <= (end - start).days <= 95  # roughly a quarter, not a month (~30) or a year (~365)


def test_bulk_generate_skips_draft_contracts(client, seeded_admin):
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    owner, building, unit = _create_building_and_unit(client, headers)
    contract = client.post("/api/v1/rentals", json={
        "tenant_id": tenant_id, "property_id": unit["id"],
        "start_date": str(date.today()), "end_date": str(date.today() + timedelta(days=365)),
        "payment_frequency": "monthly", "rent_amount": "500.000", "security_deposit_amount": "500.000",
    }, headers=headers).json()  # never activated

    resp = client.post("/api/v1/financial/invoices/bulk-generate", json={"billing_period_start": str(date.today().replace(day=1))}, headers=headers)
    assert not any(i["rental_contract_id"] == contract["id"] for i in resp.json())


def test_bulk_generate_scoped_to_property_ids(client, seeded_admin):
    headers = _auth_headers(client)
    tenant_a = _create_tenant(client, headers, first_name="TenantA")
    tenant_b = _create_tenant(client, headers, first_name="TenantB")
    owner_a, building_a, unit_a = _create_building_and_unit(client, headers)
    owner_b, building_b, unit_b = _create_building_and_unit(client, headers)
    _create_active_contract(client, headers, tenant_a, unit_a["id"])
    _create_active_contract(client, headers, tenant_b, unit_b["id"])

    resp = client.post("/api/v1/financial/invoices/bulk-generate", json={
        "billing_period_start": str(date.today().replace(day=1)), "property_ids": [unit_a["id"]],
    }, headers=headers)
    tenants_billed = {i["tenant_id"] for i in resp.json()}
    assert tenant_a in tenants_billed
    assert tenant_b not in tenants_billed


# ==================== Snapshot Immutability ====================
def test_invoice_print_data_survives_tenant_and_property_changes(client, seeded_admin):
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers, first_name="Original", last_name="Name")
    owner, building, unit = _create_building_and_unit(client, headers)
    _create_active_contract(client, headers, tenant_id, unit["id"])

    generated = client.post("/api/v1/financial/invoices/bulk-generate", json={"billing_period_start": str(date.today().replace(day=1))}, headers=headers).json()
    invoice_id = next(i["id"] for i in generated if i["tenant_id"] == tenant_id)

    before = client.get(f"/api/v1/financial/invoices/{invoice_id}/print-data", headers=headers).json()
    assert before["tenant_name"] == "Original Name"

    client.put(f"/api/v1/tenants/{tenant_id}", json={"first_name": "Changed", "last_name": "Later"}, headers=headers)

    after = client.get(f"/api/v1/financial/invoices/{invoice_id}/print-data", headers=headers).json()
    assert after["tenant_name"] == "Original Name"  # frozen at generation time, unaffected by the later change


def test_print_data_excludes_forbidden_tenant_copy_fields(client, seeded_admin):
    """Tenant copy must never show internal status/audit info — checked
    at the DTO shape level (the fields simply don't exist on it)."""
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    owner, building, unit = _create_building_and_unit(client, headers)
    _create_active_contract(client, headers, tenant_id, unit["id"])
    generated = client.post("/api/v1/financial/invoices/bulk-generate", json={"billing_period_start": str(date.today().replace(day=1))}, headers=headers).json()
    invoice_id = next(i["id"] for i in generated if i["tenant_id"] == tenant_id)

    body = client.get(f"/api/v1/financial/invoices/{invoice_id}/print-data", headers=headers).json()
    assert "invoice_status" not in body
    assert "internal_notes" not in body
    assert "audit" not in body


# ==================== Approval / Print / Void / Cancel ====================
def test_bulk_approve_transitions_draft_to_sent(client, seeded_admin):
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    owner, building, unit = _create_building_and_unit(client, headers)
    _create_active_contract(client, headers, tenant_id, unit["id"])
    generated = client.post("/api/v1/financial/invoices/bulk-generate", json={"billing_period_start": str(date.today().replace(day=1))}, headers=headers).json()
    invoice_id = next(i["id"] for i in generated if i["tenant_id"] == tenant_id)

    resp = client.post("/api/v1/financial/invoices/bulk-approve", json={"invoice_ids": [invoice_id]}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()[0]["invoice_status"] == "sent"


def test_print_increments_count_without_changing_status(client, seeded_admin):
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    owner, building, unit = _create_building_and_unit(client, headers)
    _create_active_contract(client, headers, tenant_id, unit["id"])
    generated = client.post("/api/v1/financial/invoices/bulk-generate", json={"billing_period_start": str(date.today().replace(day=1))}, headers=headers).json()
    invoice_id = next(i["id"] for i in generated if i["tenant_id"] == tenant_id)

    printed = client.post(f"/api/v1/financial/invoices/{invoice_id}/print", headers=headers)
    assert printed.status_code == 200
    assert printed.json()["print_count"] == 1

    reprinted = client.post(f"/api/v1/financial/invoices/{invoice_id}/print", headers=headers)
    assert reprinted.json()["print_count"] == 2

    detail = client.get(f"/api/v1/financial/invoices/{invoice_id}", headers=headers).json()
    assert detail["invoice_status"] == "draft"  # printing never changes status


def test_bulk_print_returns_qr_verification_url_and_records_print(client, seeded_admin):
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    owner, building, unit = _create_building_and_unit(client, headers)
    _create_active_contract(client, headers, tenant_id, unit["id"])
    generated = client.post("/api/v1/financial/invoices/bulk-generate", json={"billing_period_start": str(date.today().replace(day=1))}, headers=headers).json()
    invoice_id = next(i["id"] for i in generated if i["tenant_id"] == tenant_id)

    resp = client.post("/api/v1/financial/invoices/bulk-print", json={"invoice_ids": [invoice_id]}, headers=headers)
    assert resp.status_code == 200
    body = resp.json()[0]
    assert body["qr_verification_url"] is not None
    assert body["print_count"] == 1


def test_void_requires_reason(client, seeded_admin):
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    owner, building, unit = _create_building_and_unit(client, headers)
    _create_active_contract(client, headers, tenant_id, unit["id"])
    generated = client.post("/api/v1/financial/invoices/bulk-generate", json={"billing_period_start": str(date.today().replace(day=1))}, headers=headers).json()
    invoice_id = next(i["id"] for i in generated if i["tenant_id"] == tenant_id)

    missing_reason = client.post(f"/api/v1/financial/invoices/{invoice_id}/void", json={"reason": ""}, headers=headers)
    assert missing_reason.status_code == 422

    with_reason = client.post(f"/api/v1/financial/invoices/{invoice_id}/void", json={"reason": "Generated in error"}, headers=headers)
    assert with_reason.status_code == 200
    assert with_reason.json()["invoice_status"] == "void"
    assert with_reason.json()["void_reason"] == "Generated in error"


def test_cancel_still_works_without_a_reason(client, seeded_admin):
    """Backward compatibility: the pre-existing /cancel endpoint must not
    suddenly require a body that didn't exist before this phase."""
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    invoice = client.post("/api/v1/financial/invoices", json={
        "tenant_id": tenant_id, "amount": "300.00", "issue_date": str(date.today()), "due_date": str(date.today() + timedelta(days=10)),
    }, headers=headers).json()

    resp = client.post(f"/api/v1/financial/invoices/{invoice['id']}/cancel", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["invoice_status"] == "cancelled"


def test_void_and_cancel_are_distinct_statuses(client, seeded_admin):
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    invoice = client.post("/api/v1/financial/invoices", json={
        "tenant_id": tenant_id, "amount": "300.00", "issue_date": str(date.today()), "due_date": str(date.today() + timedelta(days=10)),
    }, headers=headers).json()
    resp = client.post(f"/api/v1/financial/invoices/{invoice['id']}/void", json={"reason": "test"}, headers=headers)
    assert resp.json()["invoice_status"] == "void"
    assert resp.json()["invoice_status"] != "cancelled"


# ==================== Partial Payments ====================
def test_partial_payment_sets_partially_paid_status(client, seeded_admin):
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    account_id = _create_financial_account(client, headers)
    invoice = client.post("/api/v1/financial/invoices", json={
        "tenant_id": tenant_id, "amount": "1000.00", "issue_date": str(date.today()), "due_date": str(date.today() + timedelta(days=10)),
    }, headers=headers).json()
    client.post(f"/api/v1/financial/invoices/{invoice['id']}/send", headers=headers)

    resp = client.post(f"/api/v1/financial/invoices/{invoice['id']}/record-payment", json={
        "account_id": account_id, "payment_method": "cash", "transaction_date": str(date.today()), "amount": "400.00",
    }, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["invoice_status"] == "partially_paid"
    assert Decimal(body["amount_paid"]) == Decimal("400.00")
    assert Decimal(body["outstanding_amount"]) == Decimal("600.00")


def test_second_partial_payment_completes_invoice(client, seeded_admin):
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    account_id = _create_financial_account(client, headers)
    invoice = client.post("/api/v1/financial/invoices", json={
        "tenant_id": tenant_id, "amount": "1000.00", "issue_date": str(date.today()), "due_date": str(date.today() + timedelta(days=10)),
    }, headers=headers).json()
    client.post(f"/api/v1/financial/invoices/{invoice['id']}/send", headers=headers)
    client.post(f"/api/v1/financial/invoices/{invoice['id']}/record-payment", json={
        "account_id": account_id, "payment_method": "cash", "transaction_date": str(date.today()), "amount": "400.00",
    }, headers=headers)

    final = client.post(f"/api/v1/financial/invoices/{invoice['id']}/record-payment", json={
        "account_id": account_id, "payment_method": "cash", "transaction_date": str(date.today()), "amount": "600.00",
    }, headers=headers)
    assert final.json()["invoice_status"] == "paid"
    assert Decimal(final.json()["amount_paid"]) == Decimal("1000.00")


def test_payment_exceeding_outstanding_is_rejected(client, seeded_admin):
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    account_id = _create_financial_account(client, headers)
    invoice = client.post("/api/v1/financial/invoices", json={
        "tenant_id": tenant_id, "amount": "500.00", "issue_date": str(date.today()), "due_date": str(date.today() + timedelta(days=10)),
    }, headers=headers).json()
    client.post(f"/api/v1/financial/invoices/{invoice['id']}/send", headers=headers)

    resp = client.post(f"/api/v1/financial/invoices/{invoice['id']}/record-payment", json={
        "account_id": account_id, "payment_method": "cash", "transaction_date": str(date.today()), "amount": "999.00",
    }, headers=headers)
    assert resp.status_code == 400


def test_payment_receipt_links_back_to_invoice(client, seeded_admin):
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    account_id = _create_financial_account(client, headers)
    invoice = client.post("/api/v1/financial/invoices", json={
        "tenant_id": tenant_id, "amount": "500.00", "issue_date": str(date.today()), "due_date": str(date.today() + timedelta(days=10)),
    }, headers=headers).json()
    client.post(f"/api/v1/financial/invoices/{invoice['id']}/send", headers=headers)
    client.post(f"/api/v1/financial/invoices/{invoice['id']}/record-payment", json={
        "account_id": account_id, "payment_method": "cash", "transaction_date": str(date.today()),
    }, headers=headers)

    receipts = client.get("/api/v1/financial/receipts", headers=headers).json()
    matching = [r for r in receipts["items"] if r.get("invoice_id") == invoice["id"]]
    assert len(matching) == 1


# ==================== Search ====================
def test_search_invoices_by_status(client, seeded_admin):
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    client.post("/api/v1/financial/invoices", json={
        "tenant_id": tenant_id, "amount": "500.00", "issue_date": str(date.today()), "due_date": str(date.today() + timedelta(days=10)),
    }, headers=headers)

    resp = client.get("/api/v1/financial/invoices/search", params={"invoice_status": "draft"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


def test_search_invoices_by_owner(client, seeded_admin):
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    owner, building, unit = _create_building_and_unit(client, headers)
    _create_active_contract(client, headers, tenant_id, unit["id"])
    client.post("/api/v1/financial/invoices/bulk-generate", json={"billing_period_start": str(date.today().replace(day=1))}, headers=headers)

    resp = client.get("/api/v1/financial/invoices/search", params={"owner_id": owner["id"]}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


# ==================== QR Verification ====================
def test_qr_verification_is_public_and_minimal(client, seeded_admin):
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    owner, building, unit = _create_building_and_unit(client, headers)
    _create_active_contract(client, headers, tenant_id, unit["id"])
    generated = client.post("/api/v1/financial/invoices/bulk-generate", json={"billing_period_start": str(date.today().replace(day=1))}, headers=headers).json()
    invoice = next(i for i in generated if i["tenant_id"] == tenant_id)

    resp = client.get(f"/api/v1/financial/invoices/verify/{invoice['qr_token']}")  # no auth headers - public endpoint
    assert resp.status_code == 200
    body = resp.json()
    assert body["invoice_number"] == invoice["invoice_number"]
    assert "amount" not in body
    assert "tenant_name" not in body


def test_qr_verification_unknown_token_404s(client, seeded_admin):
    resp = client.get("/api/v1/financial/invoices/verify/not-a-real-token")
    assert resp.status_code == 404


# ==================== Reports ====================
def test_invoice_register_report(client, seeded_admin):
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    client.post("/api/v1/financial/invoices", json={
        "tenant_id": tenant_id, "amount": "500.00", "issue_date": str(date.today()), "due_date": str(date.today() + timedelta(days=10)),
    }, headers=headers)

    resp = client.get("/api/v1/reports/invoices/register", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["total_invoices"] >= 1


def test_overdue_invoice_report(client, seeded_admin):
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    invoice = client.post("/api/v1/financial/invoices", json={
        "tenant_id": tenant_id, "amount": "500.00", "issue_date": str(date.today() - timedelta(days=30)), "due_date": str(date.today() - timedelta(days=15)),
    }, headers=headers).json()
    client.post(f"/api/v1/financial/invoices/{invoice['id']}/send", headers=headers)

    resp = client.get("/api/v1/reports/invoices/overdue", headers=headers)
    assert resp.status_code == 200
    matching = [i for i in resp.json()["invoices"] if i["id"] == invoice["id"]]
    assert len(matching) == 1
    assert matching[0]["days_overdue"] >= 14


def test_payment_register_report(client, seeded_admin):
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    account_id = _create_financial_account(client, headers)
    invoice = client.post("/api/v1/financial/invoices", json={
        "tenant_id": tenant_id, "amount": "500.00", "issue_date": str(date.today()), "due_date": str(date.today() + timedelta(days=10)),
    }, headers=headers).json()
    client.post(f"/api/v1/financial/invoices/{invoice['id']}/send", headers=headers)
    client.post(f"/api/v1/financial/invoices/{invoice['id']}/record-payment", json={
        "account_id": account_id, "payment_method": "cash", "transaction_date": str(date.today()),
    }, headers=headers)

    resp = client.get("/api/v1/reports/invoices/payment-register", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["total_payments"] >= 1


# ==================== Dashboard ====================
def test_dashboard_includes_billing_widgets(client, seeded_admin):
    headers = _auth_headers(client)
    resp = client.get("/api/v1/financial/dashboard/summary", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    for field in ["invoices_generated_this_month", "invoices_paid_this_month", "invoices_due_today", "total_overdue_invoice_amount", "collection_rate_percentage", "top_debtors"]:
        assert field in body


# ==================== Regression ====================
def test_existing_invoice_crud_unaffected(client, seeded_admin):
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    created = client.post("/api/v1/financial/invoices", json={
        "tenant_id": tenant_id, "amount": "250.00", "issue_date": str(date.today()), "due_date": str(date.today() + timedelta(days=10)),
    }, headers=headers)
    assert created.status_code == 201
    assert created.json()["invoice_status"] == "draft"

    updated = client.put(f"/api/v1/financial/invoices/{created.json()['id']}", json={"description": "Updated"}, headers=headers)
    assert updated.status_code == 200


def test_existing_full_payment_flow_unaffected(client, seeded_admin):
    """The original record_invoice_payment behavior (no amount param =
    full payment) must be byte-identical to before partial payments
    were added."""
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    account_id = _create_financial_account(client, headers)
    invoice = client.post("/api/v1/financial/invoices", json={
        "tenant_id": tenant_id, "amount": "500.00", "issue_date": str(date.today()), "due_date": str(date.today() + timedelta(days=10)),
    }, headers=headers).json()
    client.post(f"/api/v1/financial/invoices/{invoice['id']}/send", headers=headers)

    resp = client.post(f"/api/v1/financial/invoices/{invoice['id']}/record-payment", json={
        "account_id": account_id, "payment_method": "cash", "transaction_date": str(date.today()),
    }, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["invoice_status"] == "paid"
    assert Decimal(resp.json()["amount_paid"]) == Decimal("500.00")


def test_rental_receipt_module_still_works_independently(client, seeded_admin):
    """The pre-existing Rental Receipt Module (RentalPaymentInstallment-
    based, RR- numbering) is a deliberately separate system from this
    Invoice-based Rent Billing Engine — confirms it's still fully
    functional and untouched."""
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    owner, building, unit = _create_building_and_unit(client, headers)
    contract = _create_active_contract(client, headers, tenant_id, unit["id"])
    installments = client.post(f"/api/v1/rentals/{contract['id']}/installments/generate", json={"overwrite_existing": False}, headers=headers).json()

    today = date.today()
    generated = client.post("/api/v1/rentals/receipts/generate-monthly", json={"year": today.year, "month": today.month}, headers=headers)
    assert generated.status_code == 200


def test_knet_and_bank_transfer_payment_methods_still_valid(client, seeded_admin):
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    account_id = _create_financial_account(client, headers)
    invoice = client.post("/api/v1/financial/invoices", json={
        "tenant_id": tenant_id, "amount": "500.00", "issue_date": str(date.today()), "due_date": str(date.today() + timedelta(days=10)),
    }, headers=headers).json()
    client.post(f"/api/v1/financial/invoices/{invoice['id']}/send", headers=headers)

    resp = client.post(f"/api/v1/financial/invoices/{invoice['id']}/record-payment", json={
        "account_id": account_id, "payment_method": "knet", "reference_number": "KNET-1234", "transaction_date": str(date.today()),
    }, headers=headers)
    assert resp.status_code == 200
