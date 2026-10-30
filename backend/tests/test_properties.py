"""
Property module tests: creation validation across property types, GPS
bounds, building/unit hierarchy, amenities, images, documents, and
permission enforcement.
"""
import io


def _auth_headers(client):
    resp = client.post("/api/v1/auth/login", json={"email": "admin@test.com", "password": "Admin@12345"})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _create_owner(client, headers):
    resp = client.post("/api/v1/owners", json={"owner_type": "individual", "first_name": "Prop", "last_name": "Owner"}, headers=headers)
    assert resp.status_code == 201
    return resp.json()["id"]


def _property_payload(owner_id, **overrides):
    payload = {
        "property_type": "apartment",
        "title": "Test Apartment 4B",
        "owner_id": owner_id,
        "area_sqm": "85.5",
        "bedrooms": 2,
        "bathrooms": 1,
    }
    payload.update(overrides)
    return payload


def test_create_property_success(client, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    resp = client.post("/api/v1/properties", json=_property_payload(owner_id), headers=headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["property_code"].startswith("PRP-")
    assert body["availability_status"] == "available"


def test_create_property_invalid_type_rejected(client, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    resp = client.post("/api/v1/properties", json=_property_payload(owner_id, property_type="mansion"), headers=headers)
    assert resp.status_code == 422


def test_create_property_invalid_owner_rejected(client, seeded_admin):
    headers = _auth_headers(client)
    resp = client.post("/api/v1/properties", json=_property_payload(999999), headers=headers)
    assert resp.status_code == 400


def test_create_property_invalid_latitude_rejected(client, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    resp = client.post("/api/v1/properties", json=_property_payload(owner_id, latitude="200"), headers=headers)
    assert resp.status_code == 422


def test_create_property_invalid_availability_status_rejected(client, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    resp = client.post("/api/v1/properties", json=_property_payload(owner_id, availability_status="sold"), headers=headers)
    assert resp.status_code == 422


def test_all_ten_property_types_accepted(client, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    types = ["building", "villa", "apartment", "commercial_unit", "warehouse", "shop", "office", "land", "parking", "storage"]
    for t in types:
        resp = client.post("/api/v1/properties", json=_property_payload(owner_id, property_type=t, title=f"Test {t}"), headers=headers)
        assert resp.status_code == 201, f"Failed for type {t}: {resp.text}"
        assert resp.json()["property_type"] == t


def test_building_unit_hierarchy(client, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    building = client.post("/api/v1/properties", json=_property_payload(owner_id, property_type="building", title="Test Building"), headers=headers).json()
    unit = client.post("/api/v1/properties", json=_property_payload(
        owner_id, property_type="apartment", title="Unit 101", parent_property_id=building["id"],
    ), headers=headers).json()
    assert unit["parent_property_id"] == building["id"]

    units_resp = client.get(f"/api/v1/properties/{building['id']}/units", headers=headers)
    assert units_resp.status_code == 200
    assert any(u["id"] == unit["id"] for u in units_resp.json())


def test_invalid_parent_property_rejected(client, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    resp = client.post("/api/v1/properties", json=_property_payload(owner_id, parent_property_id=999999), headers=headers)
    assert resp.status_code == 400


def test_list_and_search_properties(client, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    client.post("/api/v1/properties", json=_property_payload(owner_id, title="Searchable Loft"), headers=headers)
    resp = client.get("/api/v1/properties?search=Searchable", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


def test_filter_properties_by_type_and_availability(client, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    client.post("/api/v1/properties", json=_property_payload(owner_id, property_type="shop", title="Test Shop"), headers=headers)
    resp = client.get("/api/v1/properties?property_type=shop&availability_status=available", headers=headers)
    assert resp.status_code == 200
    assert all(p["property_type"] == "shop" for p in resp.json()["items"])


def test_update_property(client, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    prop = client.post("/api/v1/properties", json=_property_payload(owner_id), headers=headers).json()
    resp = client.put(f"/api/v1/properties/{prop['id']}", json={"availability_status": "under_maintenance"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["availability_status"] == "under_maintenance"


def test_delete_property_soft_deletes(client, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    prop = client.post("/api/v1/properties", json=_property_payload(owner_id), headers=headers).json()
    resp = client.delete(f"/api/v1/properties/{prop['id']}", headers=headers)
    assert resp.status_code == 200
    get_resp = client.get(f"/api/v1/properties/{prop['id']}", headers=headers)
    assert get_resp.status_code == 404


# ---------------- Amenities ----------------
def test_create_property_with_amenities(client, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    amenity = client.post("/api/v1/amenities", json={"name": "Test Rooftop Access", "category": "comfort"}, headers=headers).json()
    prop = client.post("/api/v1/properties", json=_property_payload(owner_id, amenity_ids=[amenity["id"]]), headers=headers).json()
    assert len(prop["amenities"]) == 1
    assert prop["amenities"][0]["name"] == "Test Rooftop Access"


def test_duplicate_amenity_name_rejected(client, seeded_admin):
    headers = _auth_headers(client)
    client.post("/api/v1/amenities", json={"name": "Test Duplicate Amenity"}, headers=headers)
    resp = client.post("/api/v1/amenities", json={"name": "Test Duplicate Amenity"}, headers=headers)
    assert resp.status_code == 409


# ---------------- Images ----------------
def test_upload_property_image(client, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    prop = client.post("/api/v1/properties", json=_property_payload(owner_id), headers=headers).json()
    file_content = io.BytesIO(b"\x89PNG\r\n\x1a\n fake png content")
    resp = client.post(
        f"/api/v1/properties/{prop['id']}/images",
        data={"caption": "Front view", "is_cover": "true"},
        files={"file": ("front.png", file_content, "image/png")},
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["is_cover"] is True


def test_upload_non_image_rejected_on_images_endpoint(client, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    prop = client.post("/api/v1/properties", json=_property_payload(owner_id), headers=headers).json()
    file_content = io.BytesIO(b"%PDF-1.4 fake pdf content")
    resp = client.post(
        f"/api/v1/properties/{prop['id']}/images",
        data={"is_cover": "false"},
        files={"file": ("doc.pdf", file_content, "application/pdf")},
        headers=headers,
    )
    assert resp.status_code == 400


def test_only_one_cover_image(client, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    prop = client.post("/api/v1/properties", json=_property_payload(owner_id), headers=headers).json()
    for name in ["a.png", "b.png"]:
        client.post(
            f"/api/v1/properties/{prop['id']}/images",
            data={"is_cover": "true"},
            files={"file": (name, io.BytesIO(b"\x89PNG fake"), "image/png")},
            headers=headers,
        )
    detail = client.get(f"/api/v1/properties/{prop['id']}", headers=headers).json()
    covers = [img for img in detail["images"] if img["is_cover"]]
    assert len(covers) == 1
    assert covers[0]["file_name"] == "b.png"


# ---------------- Documents ----------------
def test_upload_property_document(client, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    prop = client.post("/api/v1/properties", json=_property_payload(owner_id), headers=headers).json()
    file_content = io.BytesIO(b"%PDF-1.4 fake title deed")
    resp = client.post(
        f"/api/v1/properties/{prop['id']}/documents",
        data={"document_type": "title_deed", "document_number": "TD-001"},
        files={"file": ("deed.pdf", file_content, "application/pdf")},
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["document_type"] == "title_deed"


# ---------------- Dashboard & permissions ----------------
def test_property_dashboard_summary(client, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    client.post("/api/v1/properties", json=_property_payload(owner_id), headers=headers)
    resp = client.get("/api/v1/properties/dashboard/summary", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_properties"] >= 1
    assert "apartment" in body["by_type"]


def test_properties_require_authentication(client, seeded_admin):
    resp = client.get("/api/v1/properties")
    assert resp.status_code == 401


def test_current_lease_linkage(client, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    prop = client.post("/api/v1/properties", json=_property_payload(owner_id), headers=headers).json()
    assert prop["current_lease_id"] is None

    lease = client.post("/api/v1/leases", json={
        "owner_id": owner_id, "property_id": prop["id"], "property_reference": "Test Apartment 4B",
        "start_date": "2026-01-01", "end_date": "2026-12-31", "rent_amount": "1000.00",
    }, headers=headers).json()
    client.post(f"/api/v1/leases/{lease['id']}/activate", headers=headers)

    updated_prop = client.get(f"/api/v1/properties/{prop['id']}", headers=headers).json()
    assert updated_prop["current_lease_id"] == lease["id"]
    assert updated_prop["current_lease_contract_number"] == lease["contract_number"]


# ==================== Building Management ====================
# A Property with property_type="building" already IS the Building
# entity (Phase 4/5) — these tests exercise the aggregation endpoints
# that surface its Units/Floors/Leases/Tenants/Maintenance together.
from datetime import date, timedelta


def _create_building(client, headers, owner_id):
    resp = client.post("/api/v1/properties", json={"property_type": "building", "title": "Test Tower", "owner_id": owner_id}, headers=headers)
    assert resp.status_code == 201
    return resp.json()


def _create_unit(client, headers, owner_id, building_id, availability_status=None):
    payload = {"property_type": "apartment", "title": "Test Unit", "owner_id": owner_id, "parent_property_id": building_id}
    resp = client.post("/api/v1/properties", json=payload, headers=headers)
    assert resp.status_code == 201
    unit = resp.json()
    if availability_status:
        upd = client.put(f"/api/v1/properties/{unit['id']}", json={"availability_status": availability_status}, headers=headers)
        assert upd.status_code == 200
        unit = upd.json()
    return unit


def test_building_summary_empty_building(client, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    building = _create_building(client, headers, owner_id)

    resp = client.get(f"/api/v1/properties/{building['id']}/building-summary", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["unit_count"] == 0
    assert body["floor_count"] == 0
    assert body["active_leases_count"] == 0
    assert body["tenant_count"] == 0


def test_building_summary_counts_units_and_leases(client, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    building = _create_building(client, headers, owner_id)
    unit1 = _create_unit(client, headers, owner_id, building["id"])
    _create_unit(client, headers, owner_id, building["id"])

    tenant = client.post("/api/v1/tenants", json={"tenant_type": "individual", "first_name": "Building", "last_name": "Tenant"}, headers=headers).json()
    contract = client.post("/api/v1/rentals", json={
        "tenant_id": tenant["id"], "property_id": unit1["id"],
        "start_date": str(date.today()), "end_date": str(date.today() + timedelta(days=365)),
        "payment_frequency": "monthly", "rent_amount": "1200.00", "security_deposit_amount": "1200.00",
    }, headers=headers)
    assert contract.status_code == 201
    contract_id = contract.json()["id"]
    activated = client.post(f"/api/v1/rentals/{contract_id}/activate", headers=headers)
    assert activated.status_code == 200

    summary = client.get(f"/api/v1/properties/{building['id']}/building-summary", headers=headers).json()
    assert summary["unit_count"] == 2
    assert summary["active_leases_count"] == 1
    assert summary["tenant_count"] == 1
    assert summary["occupied_units"] == 1
    assert summary["vacant_units"] == 1


def test_building_leases_endpoint_reuses_rental_schema(client, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    building = _create_building(client, headers, owner_id)
    unit = _create_unit(client, headers, owner_id, building["id"])
    tenant = client.post("/api/v1/tenants", json={"tenant_type": "individual", "first_name": "Lease", "last_name": "Tester"}, headers=headers).json()
    client.post("/api/v1/rentals", json={
        "tenant_id": tenant["id"], "property_id": unit["id"],
        "start_date": str(date.today()), "end_date": str(date.today() + timedelta(days=365)),
        "payment_frequency": "monthly", "rent_amount": "900.00", "security_deposit_amount": "900.00",
    }, headers=headers)

    resp = client.get(f"/api/v1/properties/{building['id']}/leases", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["property_id"] == unit["id"]
    assert body["items"][0]["tenant_display_name"] is not None


def test_building_leases_filters_by_status(client, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    building = _create_building(client, headers, owner_id)
    unit = _create_unit(client, headers, owner_id, building["id"])
    tenant = client.post("/api/v1/tenants", json={"tenant_type": "individual", "first_name": "Status", "last_name": "Tester"}, headers=headers).json()
    client.post("/api/v1/rentals", json={
        "tenant_id": tenant["id"], "property_id": unit["id"],
        "start_date": str(date.today()), "end_date": str(date.today() + timedelta(days=365)),
        "payment_frequency": "monthly", "rent_amount": "900.00", "security_deposit_amount": "900.00",
    }, headers=headers)

    active_resp = client.get(f"/api/v1/properties/{building['id']}/leases", params={"contract_status": "active"}, headers=headers)
    assert active_resp.json()["total"] == 0  # still draft, never activated
    draft_resp = client.get(f"/api/v1/properties/{building['id']}/leases", params={"contract_status": "draft"}, headers=headers)
    assert draft_resp.json()["total"] == 1


def test_building_tenants_endpoint_reuses_tenant_schema(client, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    building = _create_building(client, headers, owner_id)
    unit = _create_unit(client, headers, owner_id, building["id"])
    tenant = client.post("/api/v1/tenants", json={"tenant_type": "individual", "first_name": "Unique", "last_name": "Tenant"}, headers=headers).json()
    client.post("/api/v1/rentals", json={
        "tenant_id": tenant["id"], "property_id": unit["id"],
        "start_date": str(date.today()), "end_date": str(date.today() + timedelta(days=365)),
        "payment_frequency": "monthly", "rent_amount": "700.00", "security_deposit_amount": "700.00",
    }, headers=headers)

    resp = client.get(f"/api/v1/properties/{building['id']}/tenants", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["id"] == tenant["id"]
    assert body[0]["display_name"]


def test_building_maintenance_requests_endpoint(client, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    building = _create_building(client, headers, owner_id)
    unit = _create_unit(client, headers, owner_id, building["id"])
    req = client.post("/api/v1/maintenance/requests", json={
        "property_id": unit["id"], "title": "Building unit leak", "category": "plumbing",
        "priority": "high", "reported_date": str(date.today()),
    }, headers=headers)
    assert req.status_code == 201

    resp = client.get(f"/api/v1/properties/{building['id']}/maintenance-requests", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["property_id"] == unit["id"]

    summary = client.get(f"/api/v1/properties/{building['id']}/building-summary", headers=headers).json()
    assert summary["open_maintenance_requests_count"] == 1


def test_building_summary_requires_valid_building_id(client, seeded_admin):
    headers = _auth_headers(client)
    resp = client.get("/api/v1/properties/999999/building-summary", headers=headers)
    assert resp.status_code == 404


def test_building_endpoints_require_authentication(client, seeded_admin):
    resp = client.get("/api/v1/properties/1/building-summary")
    assert resp.status_code == 401


# ---------------- Phase 2.0: Property Structure & Unit Management ----------------

def test_create_commercial_building_and_complex_and_mixed_use(client, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    for ptype in ["commercial_building", "commercial_complex", "mixed_use"]:
        resp = client.post("/api/v1/properties", json=_property_payload(owner_id, property_type=ptype, title=f"Test {ptype}"), headers=headers)
        assert resp.status_code == 201, resp.text
        assert resp.json()["property_type"] == ptype


def test_villa_and_building_characteristics_round_trip(client, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    resp = client.post("/api/v1/properties", json=_property_payload(
        owner_id, property_type="villa", title="Test Villa",
        garden=True, swimming_pool=True, maid_room=False, parking_spaces_count=2,
    ), headers=headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["garden"] is True
    assert body["swimming_pool"] is True
    assert body["maid_room"] is False
    assert body["parking_spaces_count"] == 2

    building = client.post("/api/v1/properties", json=_property_payload(
        owner_id, property_type="building", title="Test Building", elevators=3, parking_spaces_count=20,
    ), headers=headers)
    assert building.status_code == 201
    assert building.json()["elevators"] == 3
    assert building.json()["parking_spaces_count"] == 20


def test_dashboard_includes_rolled_up_widgets(client, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    _create_building(client, headers, owner_id)
    client.post("/api/v1/properties", json=_property_payload(owner_id, property_type="villa", title="Dash Villa"), headers=headers)

    resp = client.get("/api/v1/properties/dashboard/summary", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    for key in ["total_buildings", "total_villas", "total_commercial_properties", "total_warehouses", "total_lands", "total_units", "occupied_units", "vacant_units", "occupancy_rate"]:
        assert key in body
    assert body["total_buildings"] >= 1
    assert body["total_villas"] >= 1


def test_property_detail_includes_summary_for_building_only(client, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    building = _create_building(client, headers, owner_id)
    _create_unit(client, headers, owner_id, building["id"])

    building_detail = client.get(f"/api/v1/properties/{building['id']}", headers=headers).json()
    assert building_detail["summary"] is not None
    assert building_detail["summary"]["total_units"] == 1
    assert "occupancy_rate" in building_detail["summary"]
    assert "monthly_revenue" in building_detail["summary"]

    plain_unit = client.post("/api/v1/properties", json=_property_payload(owner_id), headers=headers).json()
    unit_detail = client.get(f"/api/v1/properties/{plain_unit['id']}", headers=headers).json()
    assert unit_detail["summary"] is None
