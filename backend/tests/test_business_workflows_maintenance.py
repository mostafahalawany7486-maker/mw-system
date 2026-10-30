"""
Unit tests for MaintenanceWorkflowService
(app/business_workflows/maintenance_workflow_service.py).
"""
from datetime import date
from decimal import Decimal

from app.business_workflows.maintenance_workflow_service import MaintenanceWorkflowService


def _auth_headers(client):
    resp = client.post("/api/v1/auth/login", json={"email": "admin@test.com", "password": "Admin@12345"})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _create_property(client, headers):
    owner = client.post("/api/v1/owners", json={"owner_type": "individual", "first_name": "Maint", "last_name": "Owner"}, headers=headers).json()
    resp = client.post("/api/v1/properties", json={"property_type": "apartment", "title": "Workflow Maint Unit", "owner_id": owner["id"]}, headers=headers)
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_account(client, headers):
    resp = client.post("/api/v1/financial/accounts", json={"account_type": "bank", "name": "Maint Test Bank", "opening_balance": "0"}, headers=headers)
    assert resp.status_code == 201
    return resp.json()["id"]


def test_report_and_triage_creates_request_and_notifies(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    property_id = _create_property(client, headers)

    workflow = MaintenanceWorkflowService(db_session)
    result = workflow.report_and_triage({
        "property_id": property_id, "title": "Leaking faucet", "category": "plumbing",
        "priority": "medium", "reported_date": str(date.today()),
    }, actor_id=seeded_admin.id)

    assert result.workflow == "maintenance.report_and_triage"
    assert result.data.maintenance_status == "reported"
    assert result.notifications_sent >= 1
    assert result.metrics  # dashboard() attached


def test_report_and_triage_escalates_urgent_priority(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    property_id = _create_property(client, headers)

    workflow = MaintenanceWorkflowService(db_session)
    result = workflow.report_and_triage({
        "property_id": property_id, "title": "No water", "category": "plumbing",
        "priority": "urgent", "reported_date": str(date.today()),
    }, actor_id=seeded_admin.id)

    assert "Urgent" in result.message or "flagged as high priority" in result.message


def test_complete_and_settle_with_no_cost_posts_nothing(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    property_id = _create_property(client, headers)

    workflow = MaintenanceWorkflowService(db_session)
    request = workflow.report_and_triage({
        "property_id": property_id, "title": "Minor issue", "category": "general",
        "priority": "low", "reported_date": str(date.today()),
    }, actor_id=seeded_admin.id).data

    workflow.maintenance_service.assign_request(request.id, None, None, None, actor_id=seeded_admin.id)
    workflow.maintenance_service.start_request(request.id, actor_id=seeded_admin.id)

    result = workflow.complete_and_settle(request.id, date.today(), actor_id=seeded_admin.id)

    assert result.data.maintenance_status == "completed"
    assert result.accounting_events == []
    assert result.warnings == []


def test_complete_and_settle_posts_expense_when_cost_and_account_given(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    property_id = _create_property(client, headers)
    account_id = _create_account(client, headers)

    workflow = MaintenanceWorkflowService(db_session)
    request = workflow.report_and_triage({
        "property_id": property_id, "title": "Broken AC unit", "category": "hvac",
        "priority": "high", "reported_date": str(date.today()),
    }, actor_id=seeded_admin.id).data

    workflow.maintenance_service.assign_request(request.id, None, None, None, actor_id=seeded_admin.id)
    workflow.maintenance_service.start_request(request.id, actor_id=seeded_admin.id)
    workflow.maintenance_service.add_material(request.id, {"name": "Compressor", "quantity": "1", "unit_cost": "150.00"}, actor_id=seeded_admin.id)

    result = workflow.complete_and_settle(request.id, date.today(), actor_id=seeded_admin.id, account_id=account_id)

    assert result.data.maintenance_status == "completed"
    assert len(result.accounting_events) == 1
    assert "150.00" in result.accounting_events[0] or Decimal("150.00") == request.total_actual_cost
    assert result.warnings == []


def test_complete_and_settle_warns_when_cost_but_no_account(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    property_id = _create_property(client, headers)

    workflow = MaintenanceWorkflowService(db_session)
    request = workflow.report_and_triage({
        "property_id": property_id, "title": "Fix pipe", "category": "plumbing",
        "priority": "medium", "reported_date": str(date.today()),
    }, actor_id=seeded_admin.id).data

    workflow.maintenance_service.assign_request(request.id, None, None, None, actor_id=seeded_admin.id)
    workflow.maintenance_service.start_request(request.id, actor_id=seeded_admin.id)
    workflow.maintenance_service.add_material(request.id, {"name": "Pipe fitting", "quantity": "2", "unit_cost": "25.00"}, actor_id=seeded_admin.id)

    result = workflow.complete_and_settle(request.id, date.today(), actor_id=seeded_admin.id)

    assert result.accounting_events == []
    assert len(result.warnings) == 1
    assert "no account_id" in result.warnings[0]
