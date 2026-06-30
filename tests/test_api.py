"""API, dashboard, filter, and offline-sync tests."""


def data(resp):
    return resp.get_json()["data"]


def test_pages_render(client):
    for path in ["/", "/trips", "/trips/new", "/catches", "/map", "/pins", "/settings", "/offline"]:
        assert client.get(path).status_code == 200, path


def test_pwa_assets(client):
    sw = client.get("/sw.js")
    assert sw.status_code == 200
    assert sw.headers.get("Service-Worker-Allowed") == "/"
    assert client.get("/manifest.webmanifest").status_code == 200


def test_dashboard_totals(client):
    d = data(client.get("/api/dashboard"))
    assert d["total_trips"] == 4
    assert d["total_catches"] == 11
    assert d["top_species"] and d["best_time_of_day"]
    assert any(p["catch_count"] > 0 for p in d["most_productive_pins"])


def test_trip_filters_and_search(client):
    assert len(data(client.get("/api/trips"))) == 4
    assert len(data(client.get("/api/trips?species=smallmouth"))) >= 1
    assert len(data(client.get("/api/trips?q=caddis"))) >= 1
    assert len(data(client.get("/api/trips?water_body=Pistol"))) == 1


def test_trip_and_catch_crud_with_uuid(client):
    tid = "11111111-1111-4111-8111-111111111111"
    r = client.post("/api/trips", json={"id": tid, "date": "2026-06-30",
                                        "water_body": "Test Creek", "fishing_type": "fly"})
    assert r.status_code == 201 and data(r)["id"] == tid

    r = client.post("/api/catches", json={"trip_id": tid, "species": "Bluegill", "length": 7})
    assert r.status_code == 201

    assert len(data(client.get(f"/api/trips/{tid}"))["catches"]) == 1

    # Deleting a trip cascades to its catches.
    assert client.delete(f"/api/trips/{tid}").status_code == 200
    assert len(data(client.get(f"/api/catches?trip_id={tid}"))) == 0


def test_trip_multiple_fishing_types(client):
    """Fishing type is multi-select, stored comma-separated and round-tripped."""
    tid = "22222222-2222-4222-8222-222222222222"
    r = client.post("/api/trips", json={"id": tid, "date": "2026-06-30",
                                        "water_body": "Multi Creek",
                                        "fishing_type": "fly,tenkara,wade"})
    assert r.status_code == 201
    assert data(client.get(f"/api/trips/{tid}"))["fishing_type"] == "fly,tenkara,wade"
    client.delete(f"/api/trips/{tid}")


def test_pin_filters(client):
    pid = "33333333-3333-4333-8333-333333333333"
    r = client.post("/api/pins", json={"id": pid, "name": "Test Pin", "latitude": 35.7,
                                        "longitude": -83.9, "spot_type": "pool", "confidence": 5})
    assert r.status_code == 201
    pins = data(client.get("/api/pins?spot_type=pool&min_confidence=5"))
    assert any(p["id"] == pid for p in pins)


def test_sync_create(client):
    sid = "44444444-4444-4444-8444-444444444444"
    ops = {"operations": [{"op_id": "o1", "entity": "trip", "op": "upsert", "id": sid,
                           "base_updated_at": None,
                           "data": {"id": sid, "date": "2026-07-01", "water_body": "Sync River",
                                    "updated_at": "2026-07-01T10:00:00+00:00"}}]}
    res = data(client.post("/api/sync", json=ops))["results"]
    assert res[0]["status"] == "created"


def test_sync_conflict_resolution(client):
    sid = "55555555-5555-4555-8555-555555555555"
    client.post("/api/trips", json={"id": sid, "date": "2026-07-01", "water_body": "Base"})

    # Stale base + an older client edit => server wins.
    ops = {"operations": [{"op_id": "o2", "entity": "trip", "op": "upsert", "id": sid,
                           "base_updated_at": "2020-01-01T00:00:00+00:00",
                           "data": {"id": sid, "water_body": "Older",
                                    "updated_at": "2019-01-01T00:00:00+00:00"}}]}
    assert data(client.post("/api/sync", json=ops))["results"][0]["status"] == "conflict_server_wins"

    # Stale base + a newer client edit => client wins.
    ops["operations"][0]["op_id"] = "o3"
    ops["operations"][0]["data"]["updated_at"] = "2030-01-01T00:00:00+00:00"
    ops["operations"][0]["data"]["water_body"] = "Newer"
    assert data(client.post("/api/sync", json=ops))["results"][0]["status"] == "conflict_client_wins"


def test_photo_data_url_upload(client):
    tid = data(client.get("/api/trips"))[0]["id"]
    onepx = ("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwC"
             "AAAAC0lEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==")
    r = client.post("/api/photos", json={"trip_id": tid, "data_url": onepx, "caption": "t"})
    assert r.status_code == 201
    assert data(r)["url"].startswith("/static/uploads/")


def test_snapshot_shape(client):
    snap = data(client.get("/api/sync/snapshot"))
    assert {"trips", "catches", "pins"} <= snap.keys()
