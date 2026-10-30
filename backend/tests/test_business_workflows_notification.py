"""
Unit tests for NotificationWorkflowService
(app/business_workflows/notification_workflow_service.py).
"""
from datetime import date

from app.business_workflows.notification_workflow_service import NotificationWorkflowService
from app.services.notification_service import NotificationService


def _auth_headers(client):
    resp = client.post("/api/v1/auth/login", json={"email": "admin@test.com", "password": "Admin@12345"})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_notify_admins_delivers_to_every_active_superuser(client, db_session, seeded_admin):
    _auth_headers(client)  # ensure the admin exists/is queryable
    workflow = NotificationWorkflowService(db_session)

    count = workflow.notify_admins("Test title", "Test message", entity_type="business_workflow")

    assert count == 1
    unread = NotificationService(db_session).list_for_user(seeded_admin.id)
    assert any(n.title == "Test title" for n in unread)


def test_run_daily_notification_sweep_aggregates_all_modules(client, db_session, seeded_admin):
    _auth_headers(client)
    workflow = NotificationWorkflowService(db_session)

    result = workflow.run_daily_notification_sweep(actor_id=seeded_admin.id)

    assert result.workflow == "notification.daily_sweep"
    expected_keys = {
        "leases_auto_expired", "lease_installments_marked_overdue", "lease_renewal_reminders_sent",
        "rentals_auto_expired", "rental_installments_marked_overdue", "rental_late_fees_assessed",
        "rental_renewal_reminders_sent", "invoices_marked_overdue",
    }
    assert expected_keys.issubset(result.metrics.keys())
    assert result.notifications_sent >= 1


def test_notify_outstanding_balances_with_no_data(client, db_session, seeded_admin):
    _auth_headers(client)
    workflow = NotificationWorkflowService(db_session)

    result = workflow.notify_outstanding_balances(actor_id=seeded_admin.id)

    assert result.workflow == "notification.outstanding_balances"
    assert result.metrics["tenants_with_outstanding_balance"] == 0
    assert result.metrics["owners_with_outstanding_balance"] == 0
    assert result.notifications_sent >= 1


def test_notify_outstanding_balances_reflects_owner_debt(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    owner = client.post("/api/v1/owners", json={"owner_type": "individual", "first_name": "Debt", "last_name": "Owner"}, headers=headers).json()
    lease = client.post("/api/v1/leases", json={
        "owner_id": owner["id"], "property_reference": "Notif Test Unit",
        "start_date": str(date(2026, 1, 1)), "end_date": str(date(2026, 3, 1)),
        "payment_frequency": "monthly", "rent_amount": "800.00", "security_deposit_amount": "0",
    }, headers=headers).json()
    client.post(f"/api/v1/leases/{lease['id']}/activate", headers=headers)
    client.post(f"/api/v1/leases/{lease['id']}/installments/generate", json={"overwrite_existing": False}, headers=headers)

    workflow = NotificationWorkflowService(db_session)
    result = workflow.notify_outstanding_balances(actor_id=seeded_admin.id)

    assert result.metrics["owners_with_outstanding_balance"] == 1
    assert result.metrics["total_owner_outstanding"] > 0
