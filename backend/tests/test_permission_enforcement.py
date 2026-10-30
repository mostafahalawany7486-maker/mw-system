"""
Permission enforcement (403) tests across the modules this production
audit explicitly requires verifying: Accounting, Properties, Tenants,
Owners, Leases/Rentals, Financial, Reports, Roles.

Found during the audit: 19 test files in this suite check 401
(unauthenticated), but before this file only one checked 403 at all.
The root cause was structural, not an oversight repeated 19 times over —
every test that needed a logged-in user used `seeded_admin`, whose
`is_superuser=True` makes `PermissionChecker` bypass its own check
entirely (see app/api/deps.py). The *code* correctly gates every
endpoint; the *test suite* had no way to exercise the "logged in, but
lacking this specific permission" path at all. `seeded_viewer` (added to
conftest.py alongside this file) is a genuinely non-superuser account
with only view-level permissions, which is what actually lets these
tests trigger a real 403.
"""
from datetime import date, timedelta


def _headers(client, email, password):
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _admin_headers(client):
    return _headers(client, "admin@test.com", "Admin@12345")


def _viewer_headers(client):
    return _headers(client, "viewer@test.com", "Viewer@12345")


# ==================== Properties ====================
def test_viewer_can_list_properties_but_not_create(client, seeded_admin, seeded_viewer):
    viewer = _viewer_headers(client)
    listed = client.get("/api/v1/properties", headers=viewer)
    assert listed.status_code == 200  # properties.view is granted

    created = client.post("/api/v1/properties", json={"property_type": "apartment", "title": "Should Not Be Created"}, headers=viewer)
    assert created.status_code == 403


# ==================== Owners ====================
def test_viewer_can_list_owners_but_not_create(client, seeded_admin, seeded_viewer):
    viewer = _viewer_headers(client)
    listed = client.get("/api/v1/owners", headers=viewer)
    assert listed.status_code == 200

    created = client.post("/api/v1/owners", json={"owner_type": "individual", "first_name": "Should", "last_name": "Fail"}, headers=viewer)
    assert created.status_code == 403


# ==================== Tenants ====================
def test_viewer_can_list_tenants_but_not_create(client, seeded_admin, seeded_viewer):
    viewer = _viewer_headers(client)
    listed = client.get("/api/v1/tenants", headers=viewer)
    assert listed.status_code == 200

    created = client.post("/api/v1/tenants", json={"tenant_type": "individual", "first_name": "Should", "last_name": "Fail"}, headers=viewer)
    assert created.status_code == 403


# ==================== Leases (Lease Agreements) ====================
def test_viewer_can_list_leases_but_not_create(client, seeded_admin, seeded_viewer):
    viewer = _viewer_headers(client)
    listed = client.get("/api/v1/leases", headers=viewer)
    assert listed.status_code == 200

    created = client.post("/api/v1/leases", json={}, headers=viewer)
    assert created.status_code == 403  # rejected on permission before even reaching validation


# ==================== Rentals / Rental Receipt confirm-payment ====================
def test_viewer_can_list_rentals_but_not_generate_receipts(client, seeded_admin, seeded_viewer):
    viewer = _viewer_headers(client)
    listed = client.get("/api/v1/rentals", headers=viewer)
    assert listed.status_code == 200

    generated = client.post("/api/v1/rentals/receipts/generate-monthly", json={"year": 2026, "month": 1}, headers=viewer)
    assert generated.status_code == 403


def test_viewer_cannot_confirm_payment_even_with_rentals_view(client, seeded_admin, seeded_viewer):
    """Confirm-payment is deliberately gated by financial.edit, not
    rentals.edit (see docs/rental-receipt-module.md) — a viewer with
    rentals.view but no financial.* must still be rejected."""
    admin = _admin_headers(client)
    owner = client.post("/api/v1/owners", json={"owner_type": "individual", "first_name": "Perm", "last_name": "Owner"}, headers=admin).json()
    prop = client.post("/api/v1/properties", json={"property_type": "apartment", "title": "Perm Test Unit", "owner_id": owner["id"]}, headers=admin).json()
    tenant = client.post("/api/v1/tenants", json={"tenant_type": "individual", "first_name": "Perm", "last_name": "Tenant"}, headers=admin).json()
    contract = client.post("/api/v1/rentals", json={
        "tenant_id": tenant["id"], "property_id": prop["id"],
        "start_date": str(date.today()), "end_date": str(date.today() + timedelta(days=365)),
        "payment_frequency": "monthly", "rent_amount": "500.000", "security_deposit_amount": "500.000",
    }, headers=admin).json()
    client.post(f"/api/v1/rentals/{contract['id']}/activate", headers=admin)
    installments = client.post(f"/api/v1/rentals/{contract['id']}/installments/generate", json={"overwrite_existing": False}, headers=admin).json()

    viewer = _viewer_headers(client)
    resp = client.post(f"/api/v1/rentals/installments/{installments[0]['id']}/confirm-payment", json={
        "account_id": 1, "payment_method": "cash", "transaction_date": str(date.today()),
    }, headers=viewer)
    assert resp.status_code == 403


# ==================== Financial ====================
def test_viewer_can_list_transactions_but_not_create(client, seeded_admin, seeded_viewer):
    viewer = _viewer_headers(client)
    listed = client.get("/api/v1/financial/transactions", headers=viewer)
    assert listed.status_code == 200

    created = client.post("/api/v1/financial/transactions", json={"transaction_type": "income", "amount": "10.00", "account_id": 1, "transaction_date": str(date.today())}, headers=viewer)
    assert created.status_code == 403


def test_viewer_cannot_create_financial_account(client, seeded_admin, seeded_viewer):
    viewer = _viewer_headers(client)
    resp = client.post("/api/v1/financial/accounts", json={"account_type": "cash", "name": "Should Fail", "opening_balance": "0"}, headers=viewer)
    assert resp.status_code == 403


# ==================== Accounting ====================
def test_viewer_can_view_chart_of_accounts_but_not_create(client, seeded_admin, seeded_viewer):
    viewer = _viewer_headers(client)
    listed = client.get("/api/v1/accounting/chart-of-accounts", headers=viewer)
    assert listed.status_code == 200

    created = client.post("/api/v1/accounting/chart-of-accounts", json={"account_code": "9999", "account_name": "Should Fail", "account_type": "asset"}, headers=viewer)
    assert created.status_code == 403


def test_viewer_cannot_post_journal_entry(client, seeded_admin, seeded_viewer):
    viewer = _viewer_headers(client)
    resp = client.post("/api/v1/accounting/journal-entries", json={"entry_date": str(date.today()), "lines": []}, headers=viewer)
    assert resp.status_code == 403


# ==================== Maintenance ====================
def test_viewer_cannot_create_maintenance_request(client, seeded_admin, seeded_viewer):
    viewer = _viewer_headers(client)
    resp = client.post("/api/v1/maintenance/requests", json={"property_id": 1, "title": "Should fail", "priority": "low"}, headers=viewer)
    assert resp.status_code == 403


# ==================== Reports / Export Scheduling ====================
def test_viewer_can_view_reports_but_not_create_schedule(client, seeded_admin, seeded_viewer):
    viewer = _viewer_headers(client)
    financial = client.get("/api/v1/reports/financial", headers=viewer)
    assert financial.status_code == 200  # reports.view is granted

    schedule = client.post("/api/v1/reports/schedules", json={"name": "Should Fail", "report_type": "property", "export_format": "pdf", "frequency": "monthly"}, headers=viewer)
    assert schedule.status_code == 403  # reports.create is not granted


# ==================== Roles & Permissions ====================
def test_viewer_can_view_roles_but_not_create(client, seeded_admin, seeded_viewer):
    viewer = _viewer_headers(client)
    listed = client.get("/api/v1/roles", headers=viewer)
    assert listed.status_code == 200

    created = client.post("/api/v1/roles", json={"name": "Should Fail", "permission_ids": []}, headers=viewer)
    assert created.status_code == 403


def test_viewer_can_view_permission_catalog(client, seeded_admin, seeded_viewer):
    """roles.view is enough to see the permission catalog itself (used to
    populate the role-editor UI's checkbox list) — this must not require
    a higher permission than viewing roles themselves."""
    viewer = _viewer_headers(client)
    resp = client.get("/api/v1/roles/permissions", headers=viewer)
    assert resp.status_code == 200


# ==================== Superuser bypass sanity check ====================
def test_superuser_bypasses_every_permission_check(client, seeded_admin):
    """Confirms the other side of the same mechanism: seeded_admin (is_
    superuser=True) must succeed at actions seeded_viewer is blocked
    from above — otherwise these tests would just be asserting that
    *everyone* gets 403, which would be a meaningless, trivially-passing
    regression test rather than a real permission-boundary check."""
    admin = _admin_headers(client)
    resp = client.post("/api/v1/owners", json={"owner_type": "individual", "first_name": "Admin", "last_name": "CanCreate"}, headers=admin)
    assert resp.status_code == 201
