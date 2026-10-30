"""
Unit Management tests: floor CRUD scoped to buildings, unit-specific
fields (unit number, rent price, meters), and parking/storage space
linkage validation.
"""


def _auth_headers(client):
    resp = client.post("/api/v1/auth/login", json={"email": "admin@test.com", "password": "Admin@12345"})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _create_owner(client, headers):
    resp = client.post("/api/v1/owners", json={"owner_type": "individual", "first_name": "Unit", "last_name": "Owner"}, headers=headers)
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_building(client, headers, owner_id):
    resp = client.post("/api/v1/properties", json={
        "property_type": "building", "title": "Test Tower", "owner_id": owner_id,
    }, headers=headers)
    assert resp.status_code == 201
    return resp.json()


# ---------------- Floors ----------------
def test_create_floor_on_building(client, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    building = _create_building(client, headers, owner_id)
    resp = client.post(f"/api/v1/properties/{building['id']}/floors", json={
        "floor_number": "1", "floor_name": "Ground Floor", "total_units": 6,
    }, headers=headers)
    assert resp.status_code == 201
    assert resp.json()["floor_number"] == "1"
    assert resp.json()["unit_count"] == 0


def test_create_floor_on_non_building_rejected(client, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    villa = client.post("/api/v1/properties", json={"property_type": "villa", "title": "Test Villa", "owner_id": owner_id}, headers=headers).json()
    resp = client.post(f"/api/v1/properties/{villa['id']}/floors", json={"floor_number": "1"}, headers=headers)
    assert resp.status_code == 400


def test_list_floors_for_building(client, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    building = _create_building(client, headers, owner_id)
    client.post(f"/api/v1/properties/{building['id']}/floors", json={"floor_number": "2"}, headers=headers)
    resp = client.get(f"/api/v1/properties/{building['id']}/floors", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_update_floor(client, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    building = _create_building(client, headers, owner_id)
    floor = client.post(f"/api/v1/properties/{building['id']}/floors", json={"floor_number": "1"}, headers=headers).json()
    resp = client.put(f"/api/v1/floors/{floor['id']}", json={"floor_name": "Updated Name"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["floor_name"] == "Updated Name"


def test_delete_floor_with_units_blocked(client, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    building = _create_building(client, headers, owner_id)
    floor = client.post(f"/api/v1/properties/{building['id']}/floors", json={"floor_number": "1"}, headers=headers).json()
    client.post("/api/v1/properties", json={
        "property_type": "apartment", "title": "Unit 101", "owner_id": owner_id,
        "parent_property_id": building["id"], "floor_id": floor["id"],
    }, headers=headers)
    resp = client.delete(f"/api/v1/floors/{floor['id']}", headers=headers)
    assert resp.status_code == 409


def test_delete_empty_floor_succeeds(client, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    building = _create_building(client, headers, owner_id)
    floor = client.post(f"/api/v1/properties/{building['id']}/floors", json={"floor_number": "9"}, headers=headers).json()
    resp = client.delete(f"/api/v1/floors/{floor['id']}", headers=headers)
    assert resp.status_code == 200


def test_invalid_floor_id_on_unit_rejected(client, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    building = _create_building(client, headers, owner_id)
    resp = client.post("/api/v1/properties", json={
        "property_type": "apartment", "title": "Bad Floor Unit", "owner_id": owner_id,
        "parent_property_id": building["id"], "floor_id": 999999,
    }, headers=headers)
    assert resp.status_code == 400


# ---------------- Unit fields ----------------
def test_unit_with_number_and_rent_price(client, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    resp = client.post("/api/v1/properties", json={
        "property_type": "apartment", "title": "Unit 4B", "owner_id": owner_id,
        "unit_number": "4B", "rent_price": "3500.00",
        "electricity_meter_number": "EM-001", "water_meter_number": "WM-001",
    }, headers=headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["unit_number"] == "4B"
    assert body["rent_price"] == "3500.00"
    assert body["electricity_meter_number"] == "EM-001"


def test_negative_rent_price_rejected(client, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    resp = client.post("/api/v1/properties", json={
        "property_type": "apartment", "title": "Bad Rent Unit", "owner_id": owner_id, "rent_price": "-500",
    }, headers=headers)
    assert resp.status_code == 422


# ---------------- Parking / Storage linkage ----------------
def test_assign_parking_space_to_unit(client, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    parking = client.post("/api/v1/properties", json={"property_type": "parking", "title": "Spot 5", "owner_id": owner_id}, headers=headers).json()
    unit = client.post("/api/v1/properties", json={
        "property_type": "apartment", "title": "Unit With Parking", "owner_id": owner_id,
        "parking_space_id": parking["id"],
    }, headers=headers).json()
    assert unit["parking_space_id"] == parking["id"]
    assert unit["parking_space_code"] == parking["property_code"]


def test_assign_non_parking_property_as_parking_rejected(client, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    villa = client.post("/api/v1/properties", json={"property_type": "villa", "title": "Not Parking", "owner_id": owner_id}, headers=headers).json()
    resp = client.post("/api/v1/properties", json={
        "property_type": "apartment", "title": "Unit Bad Parking", "owner_id": owner_id,
        "parking_space_id": villa["id"],
    }, headers=headers)
    assert resp.status_code == 400


def test_assign_storage_space_to_unit(client, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    storage = client.post("/api/v1/properties", json={"property_type": "storage", "title": "Storage 2", "owner_id": owner_id}, headers=headers).json()
    unit = client.post("/api/v1/properties", json={
        "property_type": "apartment", "title": "Unit With Storage", "owner_id": owner_id,
        "storage_space_id": storage["id"],
    }, headers=headers).json()
    assert unit["storage_space_id"] == storage["id"]


def test_unit_cannot_reference_itself_as_parking(client, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    unit = client.post("/api/v1/properties", json={"property_type": "apartment", "title": "Self Ref Unit", "owner_id": owner_id}, headers=headers).json()
    resp = client.put(f"/api/v1/properties/{unit['id']}", json={"parking_space_id": unit["id"]}, headers=headers)
    assert resp.status_code == 400


def test_floors_require_authentication(client, seeded_admin):
    resp = client.get("/api/v1/properties/1/floors")
    assert resp.status_code == 401


# ---------------- Phase 2.0: Search & Filters ----------------
def test_list_properties_filter_by_floor_id(client, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    building = _create_building(client, headers, owner_id)
    floor1 = client.post(f"/api/v1/properties/{building['id']}/floors", json={"floor_number": "1"}, headers=headers).json()
    floor2 = client.post(f"/api/v1/properties/{building['id']}/floors", json={"floor_number": "2"}, headers=headers).json()
    client.post("/api/v1/properties", json={
        "property_type": "apartment", "title": "Floor 1 Unit", "owner_id": owner_id,
        "parent_property_id": building["id"], "floor_id": floor1["id"],
    }, headers=headers)
    client.post("/api/v1/properties", json={
        "property_type": "apartment", "title": "Floor 2 Unit", "owner_id": owner_id,
        "parent_property_id": building["id"], "floor_id": floor2["id"],
    }, headers=headers)

    resp = client.get(f"/api/v1/properties?floor_id={floor1['id']}", headers=headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["title"] == "Floor 1 Unit"


def test_list_properties_search_matches_unit_number(client, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    building = _create_building(client, headers, owner_id)
    client.post("/api/v1/properties", json={
        "property_type": "apartment", "title": "Searchable Unit", "owner_id": owner_id,
        "parent_property_id": building["id"], "unit_number": "UNIQUE-UNIT-42",
    }, headers=headers)

    resp = client.get("/api/v1/properties?search=UNIQUE-UNIT-42", headers=headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["title"] == "Searchable Unit"
