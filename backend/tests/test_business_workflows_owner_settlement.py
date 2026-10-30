"""
Unit tests for OwnerSettlementWorkflowService
(app/business_workflows/owner_settlement_workflow_service.py).
"""
from datetime import date
from decimal import Decimal
import pytest
from fastapi import HTTPException

from app.business_workflows.owner_settlement_workflow_service import OwnerSettlementWorkflowService


def _auth_headers(client):
    resp = client.post("/api/v1/auth/login", json={"email": "admin@test.com", "password": "Admin@12345"})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _create_owner(client, headers, **overrides):
    payload = {"owner_type": "individual", "first_name": "Settle", "last_name": "Owner"}
    payload.update(overrides)
    resp = client.post("/api/v1/owners", json=payload, headers=headers)
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_active_lease(client, headers, owner_id, rent="1000.00"):
    payload = {
        "owner_id": owner_id,
        "property_reference": "Settlement Test Unit",
        "start_date": str(date(2026, 1, 1)),
        "end_date": str(date(2026, 6, 1)),
        "payment_frequency": "monthly",
        "rent_amount": rent,
        "security_deposit_amount": "0",
    }
    lease = client.post("/api/v1/leases", json=payload, headers=headers).json()
    activated = client.post(f"/api/v1/leases/{lease['id']}/activate", headers=headers)
    assert activated.status_code == 200
    generated = client.post(f"/api/v1/leases/{lease['id']}/installments/generate", json={"overwrite_existing": False}, headers=headers)
    assert generated.status_code == 200
    return client.get(f"/api/v1/leases/{lease['id']}", headers=headers).json()


def _create_account(client, headers):
    resp = client.post("/api/v1/financial/accounts", json={"account_type": "bank", "name": "Settlement Test Bank", "opening_balance": "0"}, headers=headers)
    assert resp.status_code == 201
    return resp.json()["id"]


def test_settle_owner_installment_success(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    lease = _create_active_lease(client, headers, owner_id, rent="1000.00")
    account_id = _create_account(client, headers)
    installment_id = lease["installments"][0]["id"]

    workflow = OwnerSettlementWorkflowService(db_session)
    result = workflow.settle_owner_installment(
        lease["id"], installment_id, account_id, date.today(), actor_id=seeded_admin.id,
    )

    assert result.workflow == "owner_settlement.settle_installment"
    settled = next(i for i in result.data.installments if i.id == installment_id)
    assert settled.payment_status == "paid"
    assert len(result.accounting_events) == 1
    assert result.notifications_sent >= 1


def test_settle_owner_installment_rejects_already_paid(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    lease = _create_active_lease(client, headers, owner_id)
    account_id = _create_account(client, headers)
    installment_id = lease["installments"][0]["id"]

    workflow = OwnerSettlementWorkflowService(db_session)
    workflow.settle_owner_installment(lease["id"], installment_id, account_id, date.today(), actor_id=seeded_admin.id)

    with pytest.raises(HTTPException) as exc_info:
        workflow.settle_owner_installment(lease["id"], installment_id, account_id, date.today(), actor_id=seeded_admin.id)
    assert exc_info.value.status_code == 409


def test_settle_owner_installment_rejects_unknown_installment(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    lease = _create_active_lease(client, headers, owner_id)
    account_id = _create_account(client, headers)

    workflow = OwnerSettlementWorkflowService(db_session)
    with pytest.raises(HTTPException) as exc_info:
        workflow.settle_owner_installment(lease["id"], 999999, account_id, date.today(), actor_id=seeded_admin.id)
    assert exc_info.value.status_code == 404


def test_run_bulk_owner_settlement_pays_all_pending_installments(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    lease = _create_active_lease(client, headers, owner_id, rent="1000.00")
    account_id = _create_account(client, headers)
    installment_count = len(lease["installments"])

    workflow = OwnerSettlementWorkflowService(db_session)
    result = workflow.run_bulk_owner_settlement(account_id, date.today(), actor_id=seeded_admin.id, owner_id=owner_id)

    assert result.workflow == "owner_settlement.run_bulk"
    assert result.metrics["succeeded"] == installment_count
    assert result.metrics["failed"] == 0
    assert Decimal(str(result.metrics["total_paid"])) == Decimal("1000.00") * installment_count

    # Running again finds nothing left to settle.
    second = workflow.run_bulk_owner_settlement(account_id, date.today(), actor_id=seeded_admin.id, owner_id=owner_id)
    assert second.metrics["succeeded"] == 0


def test_run_bulk_owner_settlement_scoped_to_owner(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    owner1 = _create_owner(client, headers, first_name="One")
    owner2 = _create_owner(client, headers, first_name="Two")
    _create_active_lease(client, headers, owner1, rent="500.00")
    lease2 = _create_active_lease(client, headers, owner2, rent="700.00")
    account_id = _create_account(client, headers)

    workflow = OwnerSettlementWorkflowService(db_session)
    result = workflow.run_bulk_owner_settlement(account_id, date.today(), actor_id=seeded_admin.id, owner_id=owner1)

    # owner1's installments were all settled...
    assert result.metrics["succeeded"] == 6  # Jan-Jun inclusive monthly on a Jan1->Jun1 lease
    # ...owner2's installments were left untouched.
    lease2_after = workflow.lease_service.get_lease(lease2["id"])
    assert all(i.payment_status == "pending" for i in lease2_after.installments)
