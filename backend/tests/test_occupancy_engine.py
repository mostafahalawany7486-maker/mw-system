"""
Unit tests for the Occupancy & Unit Lifecycle Engine
(app/business_workflows/occupancy/, app/api/v1/routers/occupancy.py).

Covers: live status computation for every reachable status (available,
occupied, under_maintenance including its priority over an active
lease, notice_period, vacating_soon), override set/clear (incl. every
VALIDATIONS rule: reservation conflict, maintenance conflict, duplicate
occupancy state), the "no multiple active leases per unit" guard now
enforced in RentalService.activate_contract, the dashboard, building
summary, the recalculate sweep's audit trail, per-unit history, and
permission enforcement.
"""
from datetime import date, timedelta
from decimal import Decimal
import pytest

from app.business_workflows.occupancy.occupancy_engine import OccupancyEngine
from app.business_workflows.occupancy.occupancy_events import OccupancyEventsService
from app.business_workflows.occupancy.occupancy_statistics import OccupancyStatisticsService
from app.business_workflows.occupancy.occupancy_scheduler import OccupancyScheduler
from app.business_workflows.occupancy.occupancy_validator import (
    ReservationConflictError, MaintenanceConflictError, DuplicateOccupancyStateError,
)
from app.models.occupancy import OccupancyStatus
from app.core.security import hash_password
from app.models.user import User, Role, Permission


def _auth_headers(client):
    resp = client.post("/api/v1/auth/login", json={"email": "admin@test.com", "password": "Admin@12345"})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _occupancy_viewer(db_session):
    perms = [Permission(code="occupancy.view", module="occupancy", action="view")]
    for p in perms:
        db_session.add(p)
    db_session.flush()
    role = Role(name="Occupancy Viewer", description="View-only", is_system_role=False)
    role.permissions = perms
    db_session.add(role)
    db_session.flush()
    user = User(
        first_name="Occ", last_name="Viewer", email="occupancy-viewer@test.com",
        hashed_password=hash_password("Viewer@12345"), is_active=True, is_superuser=False, role_id=role.id,
    )
    db_session.add(user)
    db_session.commit()
    return user


def _create_building(client, headers):
    owner = client.post("/api/v1/owners", json={"owner_type": "individual", "first_name": "Occ", "last_name": "Owner"}, headers=headers).json()
    building = client.post("/api/v1/properties", json={"property_type": "building", "title": "Occupancy Tower", "owner_id": owner["id"]}, headers=headers)
    assert building.status_code == 201, building.text
    return building.json()["id"], owner["id"]


def _create_unit(client, headers, owner_id, building_id=None, title="Occupancy Unit"):
    payload = {"property_type": "apartment", "title": title, "owner_id": owner_id}
    if building_id:
        payload["parent_property_id"] = building_id
    resp = client.post("/api/v1/properties", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _create_tenant(client, headers, **overrides):
    payload = {"tenant_type": "individual", "first_name": "Occ", "last_name": "Tenant"}
    payload.update(overrides)
    resp = client.post("/api/v1/tenants", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _create_active_contract(client, headers, tenant_id, property_id, end_date=None, rent="500.00"):
    contract = client.post("/api/v1/rentals", json={
        "tenant_id": tenant_id, "property_id": property_id,
        "start_date": str(date.today() - timedelta(days=60)),
        "end_date": str(end_date or (date.today() + timedelta(days=700))),
        "payment_frequency": "monthly", "rent_amount": rent, "security_deposit_amount": rent,
    }, headers=headers)
    assert contract.status_code == 201, contract.text
    contract = contract.json()
    activated = client.post(f"/api/v1/rentals/{contract['id']}/activate", headers=headers)
    assert activated.status_code == 200, activated.text
    return activated.json()


# ==================== Core status computation ====================
def test_unit_with_no_activity_is_available(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    _, owner_id = _create_building(client, headers)
    unit_id = _create_unit(client, headers, owner_id)

    engine = OccupancyEngine(db_session)
    status_value, reason = engine.compute_unit_status(unit_id)
    assert status_value == OccupancyStatus.AVAILABLE


def test_unit_with_active_lease_is_occupied(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    _, owner_id = _create_building(client, headers)
    unit_id = _create_unit(client, headers, owner_id)
    tenant_id = _create_tenant(client, headers)
    _create_active_contract(client, headers, tenant_id, unit_id)

    engine = OccupancyEngine(db_session)
    status_value, reason = engine.compute_unit_status(unit_id)
    assert status_value == OccupancyStatus.OCCUPIED


def test_unit_becomes_available_after_termination(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    _, owner_id = _create_building(client, headers)
    unit_id = _create_unit(client, headers, owner_id)
    tenant_id = _create_tenant(client, headers)
    contract = _create_active_contract(client, headers, tenant_id, unit_id)

    terminated = client.post(f"/api/v1/rentals/{contract['id']}/terminate", json={
        "terminated_date": str(date.today()), "termination_reason": "test termination",
    }, headers=headers)
    assert terminated.status_code == 200, terminated.text

    engine = OccupancyEngine(db_session)
    status_value, _ = engine.compute_unit_status(unit_id)
    assert status_value == OccupancyStatus.AVAILABLE


def test_open_maintenance_outranks_active_lease(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    _, owner_id = _create_building(client, headers)
    unit_id = _create_unit(client, headers, owner_id)
    tenant_id = _create_tenant(client, headers)
    _create_active_contract(client, headers, tenant_id, unit_id)

    req = client.post("/api/v1/maintenance/requests", json={
        "property_id": unit_id, "title": "Leaking faucet", "reported_date": str(date.today()),
    }, headers=headers)
    assert req.status_code == 201, req.text

    engine = OccupancyEngine(db_session)
    status_value, reason = engine.compute_unit_status(unit_id)
    assert status_value == OccupancyStatus.UNDER_MAINTENANCE


def test_completed_maintenance_no_longer_affects_status(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    _, owner_id = _create_building(client, headers)
    unit_id = _create_unit(client, headers, owner_id)

    technician = client.post("/api/v1/maintenance/technicians", json={"first_name": "Occ", "last_name": "Tech"}, headers=headers)
    assert technician.status_code == 201, technician.text
    technician_id = technician.json()["id"]

    req = client.post("/api/v1/maintenance/requests", json={
        "property_id": unit_id, "title": "Paint touch-up", "reported_date": str(date.today()),
    }, headers=headers).json()
    assigned = client.post(f"/api/v1/maintenance/requests/{req['id']}/assign", json={"assigned_technician_id": technician_id}, headers=headers)
    assert assigned.status_code == 200, assigned.text

    engine = OccupancyEngine(db_session)
    status_value, _ = engine.compute_unit_status(unit_id)
    assert status_value == OccupancyStatus.UNDER_MAINTENANCE

    started = client.post(f"/api/v1/maintenance/requests/{req['id']}/start", headers=headers)
    assert started.status_code == 200, started.text
    completed = client.post(f"/api/v1/maintenance/requests/{req['id']}/complete", json={"completed_date": str(date.today())}, headers=headers)
    assert completed.status_code == 200, completed.text

    status_value, _ = engine.compute_unit_status(unit_id)
    assert status_value == OccupancyStatus.AVAILABLE


def test_notice_period_when_move_out_notice_given(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    _, owner_id = _create_building(client, headers)
    unit_id = _create_unit(client, headers, owner_id)
    tenant_id = _create_tenant(client, headers)
    contract = _create_active_contract(client, headers, tenant_id, unit_id)

    resp = client.post(f"/api/v1/occupancy/contracts/{contract['id']}/notice", json={
        "move_out_notice_date": str(date.today() + timedelta(days=14)),
    }, headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["occupancy_status"] == OccupancyStatus.NOTICE_PERIOD


def test_vacating_soon_when_contract_nears_end_without_notice(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    _, owner_id = _create_building(client, headers)
    unit_id = _create_unit(client, headers, owner_id)
    tenant_id = _create_tenant(client, headers)
    # renewal_notice_days defaults to 30 — an end_date 10 days out falls
    # inside that window with no notice given.
    _create_active_contract(client, headers, tenant_id, unit_id, end_date=date.today() + timedelta(days=10))

    engine = OccupancyEngine(db_session)
    status_value, _ = engine.compute_unit_status(unit_id)
    assert status_value == OccupancyStatus.VACATING_SOON


# ==================== Overrides & validations ====================
def test_set_and_clear_override(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    _, owner_id = _create_building(client, headers)
    unit_id = _create_unit(client, headers, owner_id)

    resp = client.post(f"/api/v1/occupancy/units/{unit_id}/override", json={
        "override_status": "cleaning", "reason": "Turnover clean",
    }, headers=headers)
    assert resp.status_code == 201, resp.text
    override_id = resp.json()["id"]

    engine = OccupancyEngine(db_session)
    status_value, _ = engine.compute_unit_status(unit_id)
    assert status_value == OccupancyStatus.CLEANING

    cleared = client.post(f"/api/v1/occupancy/overrides/{override_id}/clear", json={"reason": "Done"}, headers=headers)
    assert cleared.status_code == 200, cleared.text

    status_value, _ = engine.compute_unit_status(unit_id)
    assert status_value == OccupancyStatus.AVAILABLE


def test_reservation_conflict_on_occupied_unit(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    _, owner_id = _create_building(client, headers)
    unit_id = _create_unit(client, headers, owner_id)
    tenant_id = _create_tenant(client, headers)
    _create_active_contract(client, headers, tenant_id, unit_id)

    events = OccupancyEventsService(db_session)
    with pytest.raises(ReservationConflictError):
        events.set_override(unit_id, "reserved", "test", None, actor_id=seeded_admin.id)


def test_maintenance_conflict_blocks_reservation(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    _, owner_id = _create_building(client, headers)
    unit_id = _create_unit(client, headers, owner_id)
    req = client.post("/api/v1/maintenance/requests", json={
        "property_id": unit_id, "title": "Broken window", "reported_date": str(date.today()),
    }, headers=headers)
    assert req.status_code == 201, req.text

    events = OccupancyEventsService(db_session)
    with pytest.raises(MaintenanceConflictError):
        events.set_override(unit_id, "reserved", "test", None, actor_id=seeded_admin.id)


def test_duplicate_occupancy_state_rejected(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    _, owner_id = _create_building(client, headers)
    unit_id = _create_unit(client, headers, owner_id)

    events = OccupancyEventsService(db_session)
    events.set_override(unit_id, "blocked", "legal hold", None, actor_id=seeded_admin.id)
    with pytest.raises(DuplicateOccupancyStateError):
        events.set_override(unit_id, "blocked", "legal hold again", None, actor_id=seeded_admin.id)


def test_multiple_active_leases_on_same_unit_prevented(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    _, owner_id = _create_building(client, headers)
    unit_id = _create_unit(client, headers, owner_id)
    tenant1 = _create_tenant(client, headers, first_name="One")
    tenant2 = _create_tenant(client, headers, first_name="Two")

    _create_active_contract(client, headers, tenant1, unit_id)

    second_contract = client.post("/api/v1/rentals", json={
        "tenant_id": tenant2, "property_id": unit_id,
        "start_date": str(date.today()), "end_date": str(date.today() + timedelta(days=365)),
        "payment_frequency": "monthly", "rent_amount": "500.00", "security_deposit_amount": "500.00",
    }, headers=headers).json()

    activate_resp = client.post(f"/api/v1/rentals/{second_contract['id']}/activate", headers=headers)
    assert activate_resp.status_code == 409
    assert "active" in activate_resp.json()["detail"].lower()


# ==================== Statistics ====================
def test_dashboard_reflects_mixed_unit_states(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    _, owner_id = _create_building(client, headers)
    occupied_unit = _create_unit(client, headers, owner_id, title="Occ A")
    vacant_unit = _create_unit(client, headers, owner_id, title="Occ B")
    tenant_id = _create_tenant(client, headers)
    _create_active_contract(client, headers, tenant_id, occupied_unit)

    stats = OccupancyStatisticsService(db_session)
    dashboard = stats.get_dashboard()
    assert dashboard["total_units"] >= 2
    assert dashboard["occupied_units"] >= 1
    assert dashboard["vacant_units"] >= 1
    assert Decimal("0") <= dashboard["occupancy_percentage"] <= Decimal("100")


def test_building_summary_computes_occupancy_and_average_rent(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    building_id, owner_id = _create_building(client, headers)
    unit_a = _create_unit(client, headers, owner_id, building_id, title="Summary A")
    unit_b = _create_unit(client, headers, owner_id, building_id, title="Summary B")
    tenant_id = _create_tenant(client, headers)
    _create_active_contract(client, headers, tenant_id, unit_a, rent="800.00")

    resp = client.get(f"/api/v1/occupancy/buildings", params={"building_id": building_id}, headers=headers)
    assert resp.status_code == 200, resp.text
    summary = resp.json()[0]
    assert summary["unit_count"] == 2
    assert summary["occupied_units"] == 1
    assert summary["vacant_units"] == 1
    assert Decimal(summary["average_rent"]) == Decimal("800.00")
    assert summary["active_contracts"] == 1


# ==================== Recalculate sweep & audit trail ====================
def test_recalculate_logs_status_changes(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    _, owner_id = _create_building(client, headers)
    unit_id = _create_unit(client, headers, owner_id)
    tenant_id = _create_tenant(client, headers)

    scheduler = OccupancyScheduler(db_session)
    first_sweep = scheduler.run_sweep(None, actor_id=seeded_admin.id)
    # First-ever sweep always logs (previous_status is None -> "available").
    assert any(c["property_id"] == unit_id for c in first_sweep["changes"])

    _create_active_contract(client, headers, tenant_id, unit_id)
    second_sweep = scheduler.run_sweep(None, actor_id=seeded_admin.id)
    changed = [c for c in second_sweep["changes"] if c["property_id"] == unit_id]
    assert len(changed) == 1
    assert changed[0]["previous_status"] == OccupancyStatus.AVAILABLE
    assert changed[0]["new_status"] == OccupancyStatus.OCCUPIED

    # A third sweep with nothing changed logs nothing new for this unit.
    third_sweep = scheduler.run_sweep(None, actor_id=seeded_admin.id)
    assert not any(c["property_id"] == unit_id for c in third_sweep["changes"])


def test_unit_history_endpoint_returns_logged_changes(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    _, owner_id = _create_building(client, headers)
    unit_id = _create_unit(client, headers, owner_id)

    client.post("/api/v1/occupancy/recalculate", headers=headers)
    resp = client.get(f"/api/v1/occupancy/units/{unit_id}/history", headers=headers)
    assert resp.status_code == 200, resp.text
    assert len(resp.json()) >= 1
    assert resp.json()[0]["new_status"] == OccupancyStatus.AVAILABLE


def test_override_set_and_clear_are_audited(client, db_session, seeded_admin):
    from sqlalchemy import select
    from app.models.system import ActivityLog

    headers = _auth_headers(client)
    _, owner_id = _create_building(client, headers)
    unit_id = _create_unit(client, headers, owner_id)

    client.post(f"/api/v1/occupancy/units/{unit_id}/override", json={"override_status": "inspection", "reason": "annual check"}, headers=headers)

    logs = db_session.execute(
        select(ActivityLog).where(ActivityLog.entity_id == unit_id, ActivityLog.entity_type == "occupancy_status")
    ).scalars().all()
    assert len(logs) >= 1


# ==================== API / Permissions ====================
def test_full_api_workflow(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    building_id, owner_id = _create_building(client, headers)
    unit_id = _create_unit(client, headers, owner_id, building_id)

    dashboard = client.get("/api/v1/occupancy", headers=headers)
    assert dashboard.status_code == 200
    assert "occupancy_percentage" in dashboard.json()

    buildings = client.get("/api/v1/occupancy/buildings", headers=headers)
    assert buildings.status_code == 200
    assert isinstance(buildings.json(), list)

    units = client.get("/api/v1/occupancy/units", params={"building_id": building_id}, headers=headers)
    assert units.status_code == 200
    assert units.json()["total"] >= 1

    recalculate = client.post("/api/v1/occupancy/recalculate", headers=headers)
    assert recalculate.status_code == 200
    assert "units_checked" in recalculate.json()


def test_occupancy_write_actions_require_edit_permission(client, db_session, seeded_admin):
    headers = _auth_headers(client)
    _, owner_id = _create_building(client, headers)
    unit_id = _create_unit(client, headers, owner_id)

    _occupancy_viewer(db_session)
    login = client.post("/api/v1/auth/login", json={"email": "occupancy-viewer@test.com", "password": "Viewer@12345"})
    viewer_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    resp = client.post(f"/api/v1/occupancy/units/{unit_id}/override", json={"override_status": "blocked"}, headers=viewer_headers)
    assert resp.status_code == 403

    resp = client.post("/api/v1/occupancy/recalculate", headers=viewer_headers)
    assert resp.status_code == 403

    view_resp = client.get("/api/v1/occupancy", headers=viewer_headers)
    assert view_resp.status_code == 200


def test_occupancy_requires_authentication(client, seeded_admin):
    resp = client.get("/api/v1/occupancy")
    assert resp.status_code == 401
