"""
Unit tests for the Payment & Collection Engine
(app/business_workflows/payment/, app/api/v1/routers/payments.py).

Covers: capture (full/partial/multi-invoice allocation), validations
(negative amount, duplicate reference number, cancelled invoice,
exceeding outstanding balance), verify (ledger posting via the existing
FinancialService.record_invoice_payment, status derivation), cancel,
refund, reversal (incl. duplicate-reversal prevention), the collection
dashboard, and permission enforcement.
"""
from datetime import date, timedelta
from decimal import Decimal
import pytest

from app.business_workflows.payment.payment_workflow_service import PaymentWorkflowService
from app.business_workflows.payment.payment_exceptions import (
    NegativePaymentAmountError, DuplicateReferenceNumberError, PaymentExceedsOutstandingError,
    PaymentOnCancelledReceiptError, InvalidPaymentStatusTransitionError, DuplicateReversalError,
)
from app.services.financial_service import FinancialService
from app.core.security import hash_password
from app.models.user import User, Role, Permission


def _auth_headers(client):
    resp = client.post("/api/v1/auth/login", json={"email": "admin@test.com", "password": "Admin@12345"})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _payment_viewer(db_session):
    perms = [Permission(code="payments.view", module="payments", action="view")]
    for p in perms:
        db_session.add(p)
    db_session.flush()
    role = Role(name="Payment Viewer", description="View-only", is_system_role=False)
    role.permissions = perms
    db_session.add(role)
    db_session.flush()
    user = User(
        first_name="Payment", last_name="Viewer", email="payment-viewer@test.com",
        hashed_password=hash_password("Viewer@12345"), is_active=True, is_superuser=False, role_id=role.id,
    )
    db_session.add(user)
    db_session.commit()
    return user


def _create_tenant(client, headers, **overrides):
    payload = {"tenant_type": "individual", "first_name": "Pay", "last_name": "Tenant"}
    payload.update(overrides)
    resp = client.post("/api/v1/tenants", json=payload, headers=headers)
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_unit(client, headers):
    owner = client.post("/api/v1/owners", json={"owner_type": "individual", "first_name": "Pay", "last_name": "Owner"}, headers=headers).json()
    resp = client.post("/api/v1/properties", json={"property_type": "apartment", "title": "Payment Unit", "owner_id": owner["id"]}, headers=headers)
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_active_contract(client, headers, tenant_id, property_id, rent="600.00"):
    contract = client.post("/api/v1/rentals", json={
        "tenant_id": tenant_id, "property_id": property_id,
        # 60 days back guarantees eligibility for a billing period
        # starting the 1st of the current month regardless of what day
        # of the month tests run on (see docs/rent-cycle-engine.md's
        # test notes for the same reasoning).
        "start_date": str(date.today() - timedelta(days=60)), "end_date": str(date.today() + timedelta(days=700)),
        "payment_frequency": "monthly", "rent_amount": rent, "security_deposit_amount": rent,
    }, headers=headers)
    assert contract.status_code == 201, contract.text
    contract = contract.json()
    activated = client.post(f"/api/v1/rentals/{contract['id']}/activate", headers=headers)
    assert activated.status_code == 200
    return contract


def _create_account(client, headers):
    resp = client.post("/api/v1/financial/accounts", json={"account_type": "bank", "name": "Payment Engine Bank", "opening_balance": "0"}, headers=headers)
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_sent_invoice(db_session, tenant_id, actor_id, period_start=None):
    financial = FinancialService(db_session)
    period_start = period_start or date.today().replace(day=1)
    invoices = financial.generate_bulk_invoices(period_start, None, actor_id=actor_id)
    invoice = next(i for i in invoices if i.tenant_id == tenant_id)
    return financial.send_invoice(invoice.id, actor_id=actor_id)


def _setup_tenant_with_invoice(client, headers, db_session, actor_id, rent="600.00"):
    tenant_id = _create_tenant(client, headers)
    unit_id = _create_unit(client, headers)
    _create_active_contract(client, headers, tenant_id, unit_id, rent=rent)
    invoice = _create_sent_invoice(db_session, tenant_id, actor_id)
    return tenant_id, invoice


# ==================== Create (capture) ====================
def test_create_payment_full_amount(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    tenant_id, invoice = _setup_tenant_with_invoice(client, headers, db_session, seeded_admin.id, rent="600.00")
    account_id = _create_account(client, headers)

    service = PaymentWorkflowService(db_session)
    payment = service.create_payment({
        "tenant_id": tenant_id, "account_id": account_id, "payment_method": "cash",
        "payment_date": date.today(), "amount": Decimal("600.00"),
        "allocations": [{"invoice_id": invoice.id, "amount": Decimal("600.00")}],
    }, actor_id=seeded_admin.id)

    assert payment.payment_number.startswith("PAY-")
    assert payment.payment_status == "pending"
    assert len(payment.allocations) == 1
    assert payment.allocations[0].transaction_id is None  # not posted yet
    assert payment.tenant_name is not None


def test_create_payment_rejects_negative_amount(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    tenant_id, invoice = _setup_tenant_with_invoice(client, headers, db_session, seeded_admin.id)
    account_id = _create_account(client, headers)

    service = PaymentWorkflowService(db_session)
    with pytest.raises(NegativePaymentAmountError):
        service.create_payment({
            "tenant_id": tenant_id, "account_id": account_id, "payment_method": "cash",
            "payment_date": date.today(), "amount": Decimal("-10.00"),
            "allocations": [{"invoice_id": invoice.id, "amount": Decimal("-10.00")}],
        }, actor_id=seeded_admin.id)


def test_create_payment_rejects_duplicate_reference_number(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    tenant_id, invoice = _setup_tenant_with_invoice(client, headers, db_session, seeded_admin.id, rent="1000.00")
    account_id = _create_account(client, headers)

    service = PaymentWorkflowService(db_session)
    service.create_payment({
        "tenant_id": tenant_id, "account_id": account_id, "payment_method": "cash",
        "payment_date": date.today(), "amount": Decimal("500.00"), "reference_number": "REF-001",
        "allocations": [{"invoice_id": invoice.id, "amount": Decimal("500.00")}],
    }, actor_id=seeded_admin.id)

    with pytest.raises(DuplicateReferenceNumberError):
        service.create_payment({
            "tenant_id": tenant_id, "account_id": account_id, "payment_method": "cash",
            "payment_date": date.today(), "amount": Decimal("500.00"), "reference_number": "REF-001",
            "allocations": [{"invoice_id": invoice.id, "amount": Decimal("500.00")}],
        }, actor_id=seeded_admin.id)


def test_create_payment_rejects_allocation_exceeding_outstanding(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    tenant_id, invoice = _setup_tenant_with_invoice(client, headers, db_session, seeded_admin.id, rent="600.00")
    account_id = _create_account(client, headers)

    service = PaymentWorkflowService(db_session)
    with pytest.raises(PaymentExceedsOutstandingError):
        service.create_payment({
            "tenant_id": tenant_id, "account_id": account_id, "payment_method": "cash",
            "payment_date": date.today(), "amount": Decimal("900.00"),
            "allocations": [{"invoice_id": invoice.id, "amount": Decimal("900.00")}],
        }, actor_id=seeded_admin.id)


def test_create_payment_rejects_cancelled_invoice(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    tenant_id, invoice = _setup_tenant_with_invoice(client, headers, db_session, seeded_admin.id)
    account_id = _create_account(client, headers)

    financial = FinancialService(db_session)
    financial.cancel_invoice(invoice.id, actor_id=seeded_admin.id, reason="test")

    service = PaymentWorkflowService(db_session)
    with pytest.raises(PaymentOnCancelledReceiptError):
        service.create_payment({
            "tenant_id": tenant_id, "account_id": account_id, "payment_method": "cash",
            "payment_date": date.today(), "amount": Decimal("100.00"),
            "allocations": [{"invoice_id": invoice.id, "amount": Decimal("100.00")}],
        }, actor_id=seeded_admin.id)


def test_create_payment_rejects_amount_allocation_mismatch_at_service_layer(client, db_session, seeded_admin):
    """Domain-level backstop (PaymentValidator.validate_allocations_sum_matches_amount)
    for the same invariant the API schema also enforces — this exercises
    it via a direct service call, which bypasses the Pydantic schema."""
    from app.business_workflows.payment.payment_exceptions import InvalidAllocationError

    headers = _auth_headers(client)
    tenant_id, invoice = _setup_tenant_with_invoice(client, headers, db_session, seeded_admin.id, rent="600.00")
    account_id = _create_account(client, headers)

    service = PaymentWorkflowService(db_session)
    with pytest.raises(InvalidAllocationError):
        service.create_payment({
            "tenant_id": tenant_id, "account_id": account_id, "payment_method": "cash",
            "payment_date": date.today(), "amount": Decimal("600.00"),
            "allocations": [{"invoice_id": invoice.id, "amount": Decimal("500.00")}],
        }, actor_id=seeded_admin.id)


def test_create_payment_covering_multiple_invoices(client, db_session, seeded_admin):
    """'One payment covering multiple receipts' — a single Payment can
    allocate across more than one Invoice."""
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    unit_id = _create_unit(client, headers)
    _create_active_contract(client, headers, tenant_id, unit_id, rent="300.00")
    account_id = _create_account(client, headers)

    financial = FinancialService(db_session)
    invoice1 = _create_sent_invoice(db_session, tenant_id, seeded_admin.id, period_start=date.today().replace(day=1))
    next_month = (date.today().replace(day=1) + timedelta(days=32)).replace(day=1)
    invoices2 = financial.generate_bulk_invoices(next_month, None, actor_id=seeded_admin.id)
    invoice2 = financial.send_invoice(next(i for i in invoices2 if i.tenant_id == tenant_id).id, actor_id=seeded_admin.id)

    service = PaymentWorkflowService(db_session)
    payment = service.create_payment({
        "tenant_id": tenant_id, "account_id": account_id, "payment_method": "bank_transfer",
        "payment_date": date.today(), "amount": Decimal("600.00"),
        "allocations": [
            {"invoice_id": invoice1.id, "amount": Decimal("300.00")},
            {"invoice_id": invoice2.id, "amount": Decimal("300.00")},
        ],
    }, actor_id=seeded_admin.id)

    assert len(payment.allocations) == 2


# ==================== Verify ====================
def test_verify_full_payment_marks_invoice_paid(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    tenant_id, invoice = _setup_tenant_with_invoice(client, headers, db_session, seeded_admin.id, rent="600.00")
    account_id = _create_account(client, headers)

    service = PaymentWorkflowService(db_session)
    payment = service.create_payment({
        "tenant_id": tenant_id, "account_id": account_id, "payment_method": "knet",
        "payment_date": date.today(), "amount": Decimal("600.00"),
        "allocations": [{"invoice_id": invoice.id, "amount": Decimal("600.00")}],
    }, actor_id=seeded_admin.id)

    verified = service.verify_payment(payment.id, actor_id=seeded_admin.id)
    assert verified.payment_status == "paid"
    assert verified.verified_at is not None
    assert verified.allocations[0].transaction_id is not None

    updated_invoice = FinancialService(db_session).get_invoice(invoice.id)
    assert updated_invoice.invoice_status == "paid"


def test_verify_partial_payment_marks_partially_paid(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    tenant_id, invoice = _setup_tenant_with_invoice(client, headers, db_session, seeded_admin.id, rent="600.00")
    account_id = _create_account(client, headers)

    service = PaymentWorkflowService(db_session)
    payment = service.create_payment({
        "tenant_id": tenant_id, "account_id": account_id, "payment_method": "cash",
        "payment_date": date.today(), "amount": Decimal("200.00"),
        "allocations": [{"invoice_id": invoice.id, "amount": Decimal("200.00")}],
    }, actor_id=seeded_admin.id)

    verified = service.verify_payment(payment.id, actor_id=seeded_admin.id)
    assert verified.payment_status == "partially_paid"

    updated_invoice = FinancialService(db_session).get_invoice(invoice.id)
    assert updated_invoice.invoice_status == "partially_paid"
    assert updated_invoice.amount_paid == Decimal("200.00")


def test_verify_twice_rejected(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    tenant_id, invoice = _setup_tenant_with_invoice(client, headers, db_session, seeded_admin.id)
    account_id = _create_account(client, headers)

    service = PaymentWorkflowService(db_session)
    payment = service.create_payment(_dict_payload(tenant_id, account_id, invoice.id, "600.00"), actor_id=seeded_admin.id)
    service.verify_payment(payment.id, actor_id=seeded_admin.id)

    with pytest.raises(InvalidPaymentStatusTransitionError):
        service.verify_payment(payment.id, actor_id=seeded_admin.id)


def _dict_payload(tenant_id, account_id, invoice_id, amount):
    return {
        "tenant_id": tenant_id, "account_id": account_id, "payment_method": "cash",
        "payment_date": date.today(), "amount": Decimal(amount),
        "allocations": [{"invoice_id": invoice_id, "amount": Decimal(amount)}],
    }


# ==================== Cancel ====================
def test_cancel_pending_payment(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    tenant_id, invoice = _setup_tenant_with_invoice(client, headers, db_session, seeded_admin.id)
    account_id = _create_account(client, headers)

    service = PaymentWorkflowService(db_session)
    payment = service.create_payment(_dict_payload(tenant_id, account_id, invoice.id, "600.00"), actor_id=seeded_admin.id)
    cancelled = service.cancel_payment(payment.id, "Entered in error", actor_id=seeded_admin.id)
    assert cancelled.payment_status == "cancelled"


def test_cannot_cancel_a_verified_payment(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    tenant_id, invoice = _setup_tenant_with_invoice(client, headers, db_session, seeded_admin.id)
    account_id = _create_account(client, headers)

    service = PaymentWorkflowService(db_session)
    payment = service.create_payment(_dict_payload(tenant_id, account_id, invoice.id, "600.00"), actor_id=seeded_admin.id)
    service.verify_payment(payment.id, actor_id=seeded_admin.id)

    with pytest.raises(InvalidPaymentStatusTransitionError):
        service.cancel_payment(payment.id, "too late", actor_id=seeded_admin.id)


# ==================== Refund ====================
def test_refund_full_payment(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    tenant_id, invoice = _setup_tenant_with_invoice(client, headers, db_session, seeded_admin.id, rent="600.00")
    account_id = _create_account(client, headers)

    service = PaymentWorkflowService(db_session)
    payment = service.create_payment(_dict_payload(tenant_id, account_id, invoice.id, "600.00"), actor_id=seeded_admin.id)
    service.verify_payment(payment.id, actor_id=seeded_admin.id)

    refunded = service.refund_payment(payment.id, "Tenant overpaid", actor_id=seeded_admin.id)
    assert refunded.payment_status == "refunded"
    assert refunded.refunded_at is not None

    updated_invoice = FinancialService(db_session).get_invoice(invoice.id)
    assert updated_invoice.amount_paid == Decimal("0")
    assert updated_invoice.invoice_status == "sent"


def test_cannot_refund_a_pending_payment(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    tenant_id, invoice = _setup_tenant_with_invoice(client, headers, db_session, seeded_admin.id)
    account_id = _create_account(client, headers)

    service = PaymentWorkflowService(db_session)
    payment = service.create_payment(_dict_payload(tenant_id, account_id, invoice.id, "600.00"), actor_id=seeded_admin.id)

    with pytest.raises(InvalidPaymentStatusTransitionError):
        service.refund_payment(payment.id, "too early", actor_id=seeded_admin.id)


# ==================== Reversal ====================
def test_reverse_payment_undoes_ledger_and_invoice(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    tenant_id, invoice = _setup_tenant_with_invoice(client, headers, db_session, seeded_admin.id, rent="600.00")
    account_id = _create_account(client, headers)

    service = PaymentWorkflowService(db_session)
    payment = service.create_payment(_dict_payload(tenant_id, account_id, invoice.id, "600.00"), actor_id=seeded_admin.id)
    service.verify_payment(payment.id, actor_id=seeded_admin.id)

    reversed_payment = service.reverse_payment(payment.id, "Recorded against wrong tenant", actor_id=seeded_admin.id)
    assert reversed_payment.payment_status == "reversed"
    assert reversed_payment.reversed_at is not None

    updated_invoice = FinancialService(db_session).get_invoice(invoice.id)
    assert updated_invoice.amount_paid == Decimal("0")
    assert updated_invoice.invoice_status == "sent"


def test_duplicate_reversal_rejected(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    tenant_id, invoice = _setup_tenant_with_invoice(client, headers, db_session, seeded_admin.id)
    account_id = _create_account(client, headers)

    service = PaymentWorkflowService(db_session)
    payment = service.create_payment(_dict_payload(tenant_id, account_id, invoice.id, "600.00"), actor_id=seeded_admin.id)
    service.verify_payment(payment.id, actor_id=seeded_admin.id)
    service.reverse_payment(payment.id, "first reversal", actor_id=seeded_admin.id)

    with pytest.raises(DuplicateReversalError):
        service.reverse_payment(payment.id, "second reversal", actor_id=seeded_admin.id)


def test_cannot_reverse_a_pending_payment(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    tenant_id, invoice = _setup_tenant_with_invoice(client, headers, db_session, seeded_admin.id)
    account_id = _create_account(client, headers)

    service = PaymentWorkflowService(db_session)
    payment = service.create_payment(_dict_payload(tenant_id, account_id, invoice.id, "600.00"), actor_id=seeded_admin.id)

    with pytest.raises(InvalidPaymentStatusTransitionError):
        service.reverse_payment(payment.id, "too early", actor_id=seeded_admin.id)


# ==================== Dashboard ====================
def test_dashboard_reflects_verified_payments(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    tenant_id, invoice = _setup_tenant_with_invoice(client, headers, db_session, seeded_admin.id, rent="600.00")
    account_id = _create_account(client, headers)

    service = PaymentWorkflowService(db_session)
    payment = service.create_payment(_dict_payload(tenant_id, account_id, invoice.id, "600.00"), actor_id=seeded_admin.id)
    service.verify_payment(payment.id, actor_id=seeded_admin.id)

    dashboard = service.dashboard()
    assert dashboard["collected_today"] == Decimal("600.00")
    assert dashboard["collected_this_month"] == Decimal("600.00")
    assert dashboard["payments_by_status"].get("paid") == 1


# ==================== API / Permissions ====================
def test_full_api_workflow(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    tenant_id, invoice = _setup_tenant_with_invoice(client, headers, db_session, seeded_admin.id, rent="600.00")
    account_id = _create_account(client, headers)

    created = client.post("/api/v1/payments", json={
        "tenant_id": tenant_id, "account_id": account_id, "payment_method": "cash",
        "payment_date": str(date.today()), "amount": "600.00",
        "allocations": [{"invoice_id": invoice.id, "amount": "600.00"}],
    }, headers=headers)
    assert created.status_code == 201, created.text
    payment_id = created.json()["id"]
    assert created.json()["payment_status"] == "pending"

    verified = client.post(f"/api/v1/payments/{payment_id}/verify", json={}, headers=headers)
    assert verified.status_code == 200
    assert verified.json()["payment_status"] == "paid"

    fetched = client.get(f"/api/v1/payments/{payment_id}", headers=headers)
    assert fetched.status_code == 200

    listed = client.get("/api/v1/payments", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["total"] >= 1

    dash = client.get("/api/v1/payments/dashboard/summary", headers=headers)
    assert dash.status_code == 200

    reversed_resp = client.post(f"/api/v1/payments/{payment_id}/reverse", json={"reason": "test reversal"}, headers=headers)
    assert reversed_resp.status_code == 200
    assert reversed_resp.json()["payment_status"] == "reversed"


def test_create_payment_amount_mismatch_rejected_by_schema(client, seeded_admin):
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    account_id = _create_account(client, headers)

    resp = client.post("/api/v1/payments", json={
        "tenant_id": tenant_id, "account_id": account_id, "payment_method": "cash",
        "payment_date": str(date.today()), "amount": "600.00",
        "allocations": [{"invoice_id": 1, "amount": "500.00"}],
    }, headers=headers)
    assert resp.status_code == 422


def test_payments_reject_without_create_permission(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    tenant_id, invoice = _setup_tenant_with_invoice(client, headers, db_session, seeded_admin.id)
    account_id = _create_account(client, headers)

    _payment_viewer(db_session)
    login = client.post("/api/v1/auth/login", json={"email": "payment-viewer@test.com", "password": "Viewer@12345"})
    viewer_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    resp = client.post("/api/v1/payments", json={
        "tenant_id": tenant_id, "account_id": account_id, "payment_method": "cash",
        "payment_date": str(date.today()), "amount": "600.00",
        "allocations": [{"invoice_id": invoice.id, "amount": "600.00"}],
    }, headers=viewer_headers)
    assert resp.status_code == 403

    listed = client.get("/api/v1/payments", headers=viewer_headers)
    assert listed.status_code == 200  # payments.view is granted


def test_payments_require_authentication(client, seeded_admin):
    resp = client.get("/api/v1/payments")
    assert resp.status_code == 401
