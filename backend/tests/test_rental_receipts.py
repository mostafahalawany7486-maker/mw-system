"""
Rental Receipt Module tests. Exercises the full approved workflow:
generate (pre-payment) -> print (audit trail only, no status change) ->
confirm payment (the only action that makes it official, reusing
FinancialService.create_transaction() unchanged) -> search. Also
confirms zero regressions on the existing installment/transaction/
accounting machinery this module was built on top of.
"""
from datetime import date, timedelta
from decimal import Decimal


def _auth_headers(client):
    resp = client.post("/api/v1/auth/login", json={"email": "admin@test.com", "password": "Admin@12345"})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _create_tenant(client, headers, **overrides):
    payload = {"tenant_type": "individual", "first_name": "Receipt", "last_name": "Tenant", "address": "Block 3, Street 12, Salmiya"}
    payload.update(overrides)
    resp = client.post("/api/v1/tenants", json=payload, headers=headers)
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_building_and_unit(client, headers):
    owner = client.post("/api/v1/owners", json={"owner_type": "individual", "first_name": "Receipt", "last_name": "Owner"}, headers=headers).json()
    building = client.post("/api/v1/properties", json={"property_type": "building", "title": "Al Fahad Tower", "owner_id": owner["id"]}, headers=headers).json()
    unit = client.post("/api/v1/properties", json={
        "property_type": "apartment", "title": "Unit 402", "owner_id": owner["id"],
        "parent_property_id": building["id"], "unit_number": "402",
    }, headers=headers).json()
    return building, unit


def _create_active_contract(client, headers, tenant_id, property_id, rent="500.000"):
    contract = client.post("/api/v1/rentals", json={
        "tenant_id": tenant_id, "property_id": property_id,
        "start_date": str(date.today()), "end_date": str(date.today() + timedelta(days=365)),
        "payment_frequency": "monthly", "rent_amount": rent, "security_deposit_amount": rent,
    }, headers=headers)
    assert contract.status_code == 201, contract.text
    contract = contract.json()
    activated = client.post(f"/api/v1/rentals/{contract['id']}/activate", headers=headers)
    assert activated.status_code == 200
    generated = client.post(f"/api/v1/rentals/{contract['id']}/installments/generate", json={"overwrite_existing": False}, headers=headers)
    assert generated.status_code == 200, generated.text
    return contract, generated.json()


def _create_financial_account(client, headers):
    resp = client.post("/api/v1/financial/accounts", json={"account_type": "bank", "name": "Receipt Test Bank", "bank_name": "NBK", "opening_balance": "0"}, headers=headers)
    assert resp.status_code == 201
    return resp.json()["id"]


# ==================== Generate Monthly Receipts ====================
def test_generate_monthly_receipts_assigns_numbers_to_active_leases(client, seeded_admin):
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    building, unit = _create_building_and_unit(client, headers)
    contract, installments = _create_active_contract(client, headers, tenant_id, unit["id"])
    this_month_inst = next(i for i in installments if i["due_date"][:7] == str(date.today())[:7])
    assert this_month_inst["receipt_number"] is None

    today = date.today()
    resp = client.post("/api/v1/rentals/receipts/generate-monthly", json={"year": today.year, "month": today.month}, headers=headers)
    assert resp.status_code == 200
    generated = resp.json()
    matching = [i for i in generated if i["id"] == this_month_inst["id"]]
    assert len(matching) == 1
    assert matching[0]["receipt_number"] is not None
    assert matching[0]["receipt_number"].startswith("RR-")


def test_generate_monthly_receipts_is_idempotent(client, seeded_admin):
    """Running it twice for the same month must not create duplicate
    receipt numbers or error — already-numbered installments are skipped."""
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    building, unit = _create_building_and_unit(client, headers)
    _create_active_contract(client, headers, tenant_id, unit["id"])

    today = date.today()
    first = client.post("/api/v1/rentals/receipts/generate-monthly", json={"year": today.year, "month": today.month}, headers=headers)
    second = client.post("/api/v1/rentals/receipts/generate-monthly", json={"year": today.year, "month": today.month}, headers=headers)
    assert first.status_code == 200 and second.status_code == 200
    assert len(second.json()) == 0  # nothing left ungenerated the second time


def test_generate_monthly_receipts_skips_draft_contracts(client, seeded_admin):
    """A contract that was never activated must not get receipts."""
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    building, unit = _create_building_and_unit(client, headers)
    contract = client.post("/api/v1/rentals", json={
        "tenant_id": tenant_id, "property_id": unit["id"],
        "start_date": str(date.today()), "end_date": str(date.today() + timedelta(days=365)),
        "payment_frequency": "monthly", "rent_amount": "500.000", "security_deposit_amount": "500.000",
    }, headers=headers).json()
    client.post(f"/api/v1/rentals/{contract['id']}/installments/generate", json={"overwrite_existing": False}, headers=headers)

    today = date.today()
    resp = client.post("/api/v1/rentals/receipts/generate-monthly", json={"year": today.year, "month": today.month}, headers=headers)
    body = resp.json()
    assert not any(i["contract_id"] == contract["id"] for i in body)


def test_generate_monthly_receipts_rejects_invalid_month(client, seeded_admin):
    headers = _auth_headers(client)
    resp = client.post("/api/v1/rentals/receipts/generate-monthly", json={"year": 2026, "month": 13}, headers=headers)
    assert resp.status_code == 422


# ==================== Printable Receipt Document ====================
def test_receipt_document_excludes_forbidden_fields_and_includes_required_ones(client, seeded_admin):
    """Per Phase 1 §10: no phone/civil-ID/contract-number should appear
    anywhere in the response; tenant name/address, building/unit,
    amount, and amount-in-words (both languages) must be present."""
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers, national_id="123456789")
    building, unit = _create_building_and_unit(client, headers)
    contract, installments = _create_active_contract(client, headers, tenant_id, unit["id"], rent="350.500")
    inst_id = installments[0]["id"]

    today = date.today()
    client.post("/api/v1/rentals/receipts/generate-monthly", json={"year": today.year, "month": today.month}, headers=headers)

    resp = client.get(f"/api/v1/rentals/installments/{inst_id}/receipt", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "national_id" not in body and "phone" not in body and "contract_number" not in body
    assert body["tenant_address"] == "Block 3, Street 12, Salmiya"
    assert body["building_name"] == "Al Fahad Tower"
    assert body["unit_number"] == "402"
    assert "Kuwaiti Dinars" in body["amount_in_words_en"]
    assert "دينار" in body["amount_in_words_ar"]
    assert Decimal(body["amount"]) == Decimal("350.500")
    # Payment section is blank until payment is confirmed — this system
    # generates receipts before payment, per the approved workflow.
    assert body["payment_method"] is None
    assert body["bank_name"] is None
    assert body["reference_number"] is None


def test_receipt_document_shows_payment_method_after_cash_confirmation(client, seeded_admin):
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    building, unit = _create_building_and_unit(client, headers)
    contract, installments = _create_active_contract(client, headers, tenant_id, unit["id"])
    inst_id = installments[0]["id"]
    account_id = _create_financial_account(client, headers)
    today = date.today()
    client.post("/api/v1/rentals/receipts/generate-monthly", json={"year": today.year, "month": today.month}, headers=headers)
    client.post(f"/api/v1/rentals/installments/{inst_id}/confirm-payment", json={
        "account_id": account_id, "payment_method": "cash", "transaction_date": str(today),
    }, headers=headers)

    resp = client.get(f"/api/v1/rentals/installments/{inst_id}/receipt", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["payment_method"] == "cash"
    # Bank Name / Reference Number only apply to bank_transfer/cheque, not cash.
    assert body["bank_name"] is None
    assert body["reference_number"] is None


def test_receipt_document_shows_bank_name_after_bank_transfer_confirmation(client, seeded_admin):
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    building, unit = _create_building_and_unit(client, headers)
    contract, installments = _create_active_contract(client, headers, tenant_id, unit["id"])
    inst_id = installments[0]["id"]
    account_id = _create_financial_account(client, headers)  # bank account with bank_name "NBK"
    today = date.today()
    client.post("/api/v1/rentals/receipts/generate-monthly", json={"year": today.year, "month": today.month}, headers=headers)
    client.post(f"/api/v1/rentals/installments/{inst_id}/confirm-payment", json={
        "account_id": account_id, "payment_method": "bank_transfer", "reference_number": "TRF-99201", "transaction_date": str(today),
    }, headers=headers)

    resp = client.get(f"/api/v1/rentals/installments/{inst_id}/receipt", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["payment_method"] == "bank_transfer"
    assert body["bank_name"] == "NBK"
    assert body["reference_number"] == "TRF-99201"


def test_receipt_document_shows_cheque_number_after_cheque_confirmation(client, seeded_admin):
    """reference_number doubles as the cheque number when payment_method
    is 'cheque' — no separate cheque_number column exists, by design."""
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    building, unit = _create_building_and_unit(client, headers)
    contract, installments = _create_active_contract(client, headers, tenant_id, unit["id"])
    inst_id = installments[0]["id"]
    account_id = _create_financial_account(client, headers)
    today = date.today()
    client.post("/api/v1/rentals/receipts/generate-monthly", json={"year": today.year, "month": today.month}, headers=headers)
    client.post(f"/api/v1/rentals/installments/{inst_id}/confirm-payment", json={
        "account_id": account_id, "payment_method": "cheque", "reference_number": "CHQ-004421", "transaction_date": str(today),
    }, headers=headers)

    resp = client.get(f"/api/v1/rentals/installments/{inst_id}/receipt", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["payment_method"] == "cheque"
    assert body["reference_number"] == "CHQ-004421"
    assert body["bank_name"] is None  # bank_name only applies to bank_transfer


def test_receipt_document_404_before_generation(client, seeded_admin):
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    building, unit = _create_building_and_unit(client, headers)
    contract, installments = _create_active_contract(client, headers, tenant_id, unit["id"])
    inst_id = installments[0]["id"]

    resp = client.get(f"/api/v1/rentals/installments/{inst_id}/receipt", headers=headers)
    assert resp.status_code == 409  # exists as an installment, but not yet "generated" as a receipt


# ==================== Print Tracking (audit only, no status change) ====================
def test_printing_receipt_does_not_change_payment_status(client, seeded_admin):
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    building, unit = _create_building_and_unit(client, headers)
    contract, installments = _create_active_contract(client, headers, tenant_id, unit["id"])
    inst_id = installments[0]["id"]
    today = date.today()
    client.post("/api/v1/rentals/receipts/generate-monthly", json={"year": today.year, "month": today.month}, headers=headers)

    printed = client.post(f"/api/v1/rentals/installments/{inst_id}/receipt/print", headers=headers)
    assert printed.status_code == 200
    assert printed.json()["print_count"] == 1
    assert printed.json()["printed_at"] is not None

    # confirm the underlying installment's payment_status is untouched by printing
    contract_detail = client.get(f"/api/v1/rentals/{contract['id']}", headers=headers).json()
    inst = next(i for i in contract_detail["installments"] if i["id"] == inst_id)
    assert inst["payment_status"] == "pending"


def test_reprinting_increments_count(client, seeded_admin):
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    building, unit = _create_building_and_unit(client, headers)
    contract, installments = _create_active_contract(client, headers, tenant_id, unit["id"])
    inst_id = installments[0]["id"]
    today = date.today()
    client.post("/api/v1/rentals/receipts/generate-monthly", json={"year": today.year, "month": today.month}, headers=headers)

    client.post(f"/api/v1/rentals/installments/{inst_id}/receipt/print", headers=headers)
    second = client.post(f"/api/v1/rentals/installments/{inst_id}/receipt/print", headers=headers)
    assert second.json()["print_count"] == 2


# ==================== Confirm Payment (the only official action) ====================
def test_confirm_payment_creates_transaction_and_updates_installment(client, seeded_admin):
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    building, unit = _create_building_and_unit(client, headers)
    contract, installments = _create_active_contract(client, headers, tenant_id, unit["id"], rent="500.000")
    inst_id = installments[0]["id"]
    account_id = _create_financial_account(client, headers)
    today = date.today()
    client.post("/api/v1/rentals/receipts/generate-monthly", json={"year": today.year, "month": today.month}, headers=headers)

    resp = client.post(f"/api/v1/rentals/installments/{inst_id}/confirm-payment", json={
        "account_id": account_id, "payment_method": "knet", "reference_number": "KNET-88213",
        "transaction_date": str(today),
    }, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["payment_status"] == "paid"
    assert body["payment_method"] == "knet"
    assert body["reference_number"] == "KNET-88213"

    # a Transaction should now exist, attributed to the unit's property
    txns = client.get("/api/v1/financial/transactions", params={"tenant_id": tenant_id}, headers=headers).json()
    matching = [t for t in txns["items"] if t["rental_contract_id"] == contract["id"]]
    assert len(matching) == 1
    assert matching[0]["property_id"] == unit["id"]


def test_confirm_payment_twice_is_rejected(client, seeded_admin):
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    building, unit = _create_building_and_unit(client, headers)
    contract, installments = _create_active_contract(client, headers, tenant_id, unit["id"])
    inst_id = installments[0]["id"]
    account_id = _create_financial_account(client, headers)
    today = date.today()
    client.post("/api/v1/rentals/receipts/generate-monthly", json={"year": today.year, "month": today.month}, headers=headers)

    payload = {"account_id": account_id, "payment_method": "cash", "transaction_date": str(today)}
    first = client.post(f"/api/v1/rentals/installments/{inst_id}/confirm-payment", json=payload, headers=headers)
    assert first.status_code == 200
    second = client.post(f"/api/v1/rentals/installments/{inst_id}/confirm-payment", json=payload, headers=headers)
    assert second.status_code == 409


def test_confirm_payment_rejects_invalid_payment_method(client, seeded_admin):
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    building, unit = _create_building_and_unit(client, headers)
    contract, installments = _create_active_contract(client, headers, tenant_id, unit["id"])
    inst_id = installments[0]["id"]
    account_id = _create_financial_account(client, headers)
    today = date.today()
    client.post("/api/v1/rentals/receipts/generate-monthly", json={"year": today.year, "month": today.month}, headers=headers)

    resp = client.post(f"/api/v1/rentals/installments/{inst_id}/confirm-payment", json={
        "account_id": account_id, "payment_method": "paypal", "transaction_date": str(today),
    }, headers=headers)
    assert resp.status_code == 422


def test_confirm_payment_requires_authentication(client, seeded_admin):
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    building, unit = _create_building_and_unit(client, headers)
    contract, installments = _create_active_contract(client, headers, tenant_id, unit["id"])
    inst_id = installments[0]["id"]

    resp = client.post(f"/api/v1/rentals/installments/{inst_id}/confirm-payment", json={
        "account_id": 999999, "payment_method": "cash", "transaction_date": str(date.today()),
    })  # no auth headers at all
    assert resp.status_code == 401


# ==================== Search ====================
def test_search_receipts_by_receipt_number(client, seeded_admin):
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    building, unit = _create_building_and_unit(client, headers)
    contract, installments = _create_active_contract(client, headers, tenant_id, unit["id"])
    today = date.today()
    generated = client.post("/api/v1/rentals/receipts/generate-monthly", json={"year": today.year, "month": today.month}, headers=headers).json()
    assert len(generated) >= 1
    receipt_number = generated[0]["receipt_number"]

    resp = client.get("/api/v1/rentals/receipts/search", params={"receipt_number": receipt_number}, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert any(r["receipt_number"] == receipt_number for r in body["items"])


def test_search_receipts_excludes_ungenerated_installments(client, seeded_admin):
    """Installments that exist but haven't been assigned a receipt number
    yet must not show up in receipt search results."""
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    building, unit = _create_building_and_unit(client, headers)
    contract, installments = _create_active_contract(client, headers, tenant_id, unit["id"])

    resp = client.get("/api/v1/rentals/receipts/search", headers=headers)
    body = resp.json()
    assert not any(r.get("installment_id") in [i["id"] for i in installments] for r in body["items"])


# ==================== Regression: existing rental/financial functionality unaffected ====================
def test_existing_installment_crud_still_works(client, seeded_admin):
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    building, unit = _create_building_and_unit(client, headers)
    contract, installments = _create_active_contract(client, headers, tenant_id, unit["id"])
    inst_id = installments[0]["id"]

    updated = client.put(f"/api/v1/rentals/{contract['id']}/installments/{inst_id}", json={"notes": "Regression check"}, headers=headers)
    assert updated.status_code == 200
    assert updated.json()["notes"] == "Regression check"


def test_existing_direct_transaction_creation_still_works(client, seeded_admin):
    """A transaction created without going through the receipt module at
    all (the pre-existing direct path) must be completely unaffected."""
    headers = _auth_headers(client)
    account_id = _create_financial_account(client, headers)
    resp = client.post("/api/v1/financial/transactions", json={
        "transaction_type": "income", "amount": "100.00", "account_id": account_id, "transaction_date": str(date.today()),
    }, headers=headers)
    assert resp.status_code == 201


def test_existing_invoice_payment_flow_still_works(client, seeded_admin):
    """The pre-existing Invoice->record_invoice_payment path (a different
    concept from rental receipts — see Phase 1 §16) must be unaffected."""
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    account_id = _create_financial_account(client, headers)
    invoice = client.post("/api/v1/financial/invoices", json={
        "tenant_id": tenant_id, "amount": "200.00", "issue_date": str(date.today()), "due_date": str(date.today() + timedelta(days=15)),
    }, headers=headers)
    assert invoice.status_code == 201
    inv_id = invoice.json()["id"]
    client.post(f"/api/v1/financial/invoices/{inv_id}/send", headers=headers)
    paid = client.post(f"/api/v1/financial/invoices/{inv_id}/record-payment", json={
        "account_id": account_id, "payment_method": "cash", "transaction_date": str(date.today()),
    }, headers=headers)
    assert paid.status_code == 200
    assert paid.json()["invoice_status"] == "paid"


def test_knet_now_valid_for_direct_transactions_too(client, seeded_admin):
    """The knet payment method addition is on the shared VALID_PAYMENT_METHODS
    set, so it should also work for ordinary transactions, not just
    receipt confirmations."""
    headers = _auth_headers(client)
    account_id = _create_financial_account(client, headers)
    resp = client.post("/api/v1/financial/transactions", json={
        "transaction_type": "income", "amount": "50.00", "account_id": account_id,
        "payment_method": "knet", "transaction_date": str(date.today()),
    }, headers=headers)
    assert resp.status_code == 201
    assert resp.json()["payment_method"] == "knet"


# ---------------- Receipt Module Cleanup ----------------
def test_confirming_rental_payment_does_not_duplicate_receipt_numbering(client, seeded_admin):
    """Confirming a Rental Receipt installment's payment must NOT also
    auto-issue a second, separate financial-ledger Receipt (RCP-xxx) for
    the same real-world payment — that would be duplicate receipt
    numbering for one event. The Rental Receipt (RR-xxx) already IS this
    payment's receipt. Owner payments and invoice payments (a different,
    unrelated flow) are untouched by this — see
    test_recording_invoice_payment_still_works below."""
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    building, unit = _create_building_and_unit(client, headers)
    contract, installments = _create_active_contract(client, headers, tenant_id, unit["id"])
    inst_id = installments[0]["id"]
    account_id = _create_financial_account(client, headers)
    today = date.today()
    client.post("/api/v1/rentals/receipts/generate-monthly", json={"year": today.year, "month": today.month}, headers=headers)
    receipt_before = client.get(f"/api/v1/rentals/installments/{inst_id}/receipt", headers=headers).json()
    rr_number = receipt_before["receipt_number"]
    assert rr_number.startswith("RR-")

    before_count = client.get("/api/v1/financial/receipts", params={"page_size": 1}, headers=headers).json()["total"]

    client.post(f"/api/v1/rentals/installments/{inst_id}/confirm-payment", json={
        "account_id": account_id, "payment_method": "cash", "transaction_date": str(today),
    }, headers=headers)

    after_count = client.get("/api/v1/financial/receipts", params={"page_size": 1}, headers=headers).json()["total"]
    assert after_count == before_count  # no new financial-ledger Receipt was created

    # The transaction still shows a receipt number — it just correctly
    # falls back to the SAME single RR-xxx receipt, not a second one.
    txns = client.get("/api/v1/financial/transactions", params={"tenant_id": tenant_id}, headers=headers).json()
    matching = [t for t in txns["items"] if t["rental_installment_id"] == inst_id]
    assert len(matching) == 1
    assert matching[0]["receipt_number"] == rr_number


def test_owner_payment_still_gets_its_own_receipt(client, seeded_admin):
    """Owner payouts have no Rental Receipt equivalent — they must keep
    getting an auto-issued financial-ledger Receipt exactly as before."""
    headers = _auth_headers(client)
    account_id = _create_financial_account(client, headers)
    owner = client.post("/api/v1/owners", json={"owner_type": "individual", "first_name": "Payout", "last_name": "Owner"}, headers=headers).json()
    resp = client.post("/api/v1/financial/transactions", json={
        "transaction_type": "owner_payment", "amount": "800.00", "account_id": account_id,
        "owner_id": owner["id"], "payment_method": "bank_transfer", "transaction_date": str(date.today()),
    }, headers=headers)
    assert resp.status_code == 201
    assert resp.json()["receipt_number"] is not None
    assert resp.json()["receipt_number"].startswith("RCP-")
