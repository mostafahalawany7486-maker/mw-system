"""
Unit tests for LeaseWorkflowService (app/business_workflows/lease_workflow_service.py).

Prerequisite data (owner, lease) is created through the existing public
API — same helper pattern as tests/test_leases.py — but the workflow
itself is exercised directly against the service layer (using the same
`db_session` the `client` fixture is wired to), since the workflow layer
doesn't add its own HTTP routes.
"""
from datetime import date, timedelta
import pytest
from fastapi import HTTPException

from app.business_workflows.lease_workflow_service import LeaseWorkflowService
from app.business_workflows.common import WorkflowResult


def _auth_headers(client):
    resp = client.post("/api/v1/auth/login", json={"email": "admin@test.com", "password": "Admin@12345"})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _create_owner(client, headers):
    resp = client.post("/api/v1/owners", json={"owner_type": "individual", "first_name": "Wf", "last_name": "Owner"}, headers=headers)
    assert resp.status_code == 201
    return resp.json()["id"]


def _lease_payload(owner_id, **overrides):
    payload = {
        "owner_id": owner_id,
        "property_reference": "Workflow Test Unit",
        "start_date": str(date(2026, 1, 1)),
        "end_date": str(date(2026, 12, 1)),
        "payment_frequency": "monthly",
        "rent_amount": "1000.00",
        "security_deposit_amount": "2000.00",
    }
    payload.update(overrides)
    return payload


def _create_draft_lease(client, headers, owner_id, **overrides):
    resp = client.post("/api/v1/leases", json=_lease_payload(owner_id, **overrides), headers=headers)
    assert resp.status_code == 201
    return resp.json()


def test_activate_lease_with_schedule_generates_installments(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    lease = _create_draft_lease(client, headers, owner_id)

    workflow = LeaseWorkflowService(db_session)
    result = workflow.activate_lease_with_schedule(lease["id"], actor_id=seeded_admin.id)

    assert isinstance(result, WorkflowResult)
    assert result.success is True
    assert result.workflow == "lease.activate_with_schedule"
    assert result.data.contract_status == "active"
    assert len(result.data.installments) == 12  # 365-day monthly lease -> 12 installments
    assert result.notifications_sent >= 1  # seeded_admin itself is an active superuser
    assert result.metrics  # dashboard() counts were attached
    assert result.warnings == []


def test_activate_lease_with_schedule_warns_on_preexisting_installments(client, db_session, seeded_admin):
    """If installments already exist (e.g. manually added while still
    draft), the workflow still activates the lease successfully but
    surfaces a warning instead of raising, since
    LeaseService.generate_schedule's 409 (installments already exist)
    is not fatal to activation."""
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    lease = _create_draft_lease(client, headers, owner_id)

    workflow = LeaseWorkflowService(db_session)
    workflow.lease_service.add_installment(
        lease["id"], {"due_date": date.today(), "amount": "1000.00"}, actor_id=seeded_admin.id,
    )

    result = workflow.activate_lease_with_schedule(lease["id"], actor_id=seeded_admin.id)

    assert result.data.contract_status == "active"
    assert len(result.warnings) == 1
    assert "Schedule not generated" in result.warnings[0]


def test_activate_lease_with_schedule_rejects_non_draft_lease(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    lease = _create_draft_lease(client, headers, owner_id)

    workflow = LeaseWorkflowService(db_session)
    workflow.activate_lease_with_schedule(lease["id"], actor_id=seeded_admin.id)

    with pytest.raises(HTTPException) as exc_info:
        workflow.activate_lease_with_schedule(lease["id"], actor_id=seeded_admin.id)
    assert exc_info.value.status_code == 409


def test_activate_lease_with_schedule_skip_flag(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    lease = _create_draft_lease(client, headers, owner_id)

    workflow = LeaseWorkflowService(db_session)
    result = workflow.activate_lease_with_schedule(lease["id"], actor_id=seeded_admin.id, generate_schedule=False)

    assert result.data.contract_status == "active"
    assert result.data.installments == []


def test_renew_lease_and_reschedule(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    lease = _create_draft_lease(client, headers, owner_id)

    workflow = LeaseWorkflowService(db_session)
    workflow.activate_lease_with_schedule(lease["id"], actor_id=seeded_admin.id, generate_schedule=False)

    new_end = date.today() + timedelta(days=730)
    result = workflow.renew_lease_and_reschedule(lease["id"], new_end, actor_id=seeded_admin.id)

    assert result.workflow == "lease.renew_and_reschedule"
    assert result.data.contract_status == "active"
    assert result.data.renewed_from_lease_id == lease["id"]
    assert len(result.data.installments) > 0
    assert result.notifications_sent >= 1

    old_lease = workflow.lease_service.get_lease(lease["id"])
    assert old_lease.contract_status == "renewed"


def test_terminate_lease_requires_reason(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    lease = _create_draft_lease(client, headers, owner_id)

    workflow = LeaseWorkflowService(db_session)
    workflow.activate_lease_with_schedule(lease["id"], actor_id=seeded_admin.id, generate_schedule=False)

    with pytest.raises(HTTPException) as exc_info:
        workflow.terminate_lease_with_notice(lease["id"], date.today(), "   ", actor_id=seeded_admin.id)
    assert exc_info.value.status_code == 400


def test_terminate_lease_with_notice_success(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    lease = _create_draft_lease(client, headers, owner_id)

    workflow = LeaseWorkflowService(db_session)
    workflow.activate_lease_with_schedule(lease["id"], actor_id=seeded_admin.id, generate_schedule=False)

    result = workflow.terminate_lease_with_notice(
        lease["id"], date.today(), "Owner requested early exit", actor_id=seeded_admin.id,
    )
    assert result.data.contract_status == "terminated"
    assert result.data.termination_reason == "Owner requested early exit"
    # security_deposit_status defaults to "held" -> workflow should warn about it
    assert any("security deposit" in w.lower() for w in result.warnings)
