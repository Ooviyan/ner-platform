"""The /api/* routes the driver PWA calls.

These lock in the translation between the app's dialect and the ../mock-data
contract. If one of these breaks, the driver app breaks at the demo.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import store
from app.main import app


@pytest.fixture()
def client():
    store.MEMORY.reset()
    with TestClient(app) as c:
        yield c


# ------------------------------------------------ GET /api/routes/current ---
def test_current_route_has_the_shape_the_home_screen_reads(client):
    route = client.get("/api/routes/current").json()
    # Home reads origin.name / origin.state, not a flat string.
    for end in ("origin", "destination"):
        assert set(route[end]) >= {"name", "state", "lat", "lng"}
        assert route[end]["name"]
    assert route["vehicle"]["vehicle_id"]
    assert route["segments"]
    for seg in route["segments"]:
        assert set(seg) >= {"id", "name", "distance_km", "eta_min", "risk", "status", "path"}
    assert isinstance(route["alternatives"], list)


def test_segment_paths_are_lat_lng_for_leaflet(client):
    """GeoJSON is [lng, lat]; Leaflet wants [lat, lng]. Getting this backwards
    puts the whole route in the Indian Ocean."""
    route = client.get("/api/routes/current").json()
    for seg in route["segments"]:
        for lat, lng in seg["path"]:
            assert 20.0 < lat < 30.0, f"{lat} is not a NER latitude"
            assert 85.0 < lng < 98.0, f"{lng} is not a NER longitude"


def test_segment_status_uses_the_apps_colour_vocabulary(client):
    route = client.get("/api/routes/current").json()
    for seg in route["segments"]:
        assert seg["status"] in {"clear", "caution", "high_risk", "blocked"}


def test_closed_segment_maps_to_blocked(client):
    """A closed road must reach the app as 'blocked' so the map paints it red."""
    closed = [s for s in client.get("/segments", params={"status": "closed"}).json()]
    assert closed
    seen = set()
    for route in client.get("/routes").json():
        vehicles = client.get("/vehicles", params={"route_id": route["id"]}).json()
        if not vehicles:
            continue
        got = client.get("/api/routes/current",
                         params={"vehicle_id": vehicles[0]["vehicle_id"]}).json()
        for seg in got["segments"]:
            if seg["id"] in {c["id"] for c in closed}:
                seen.add(seg["status"])
    assert seen == {"blocked"} or not seen


def test_known_vehicle_gets_its_own_route(client):
    route = client.get("/api/routes/current",
                       params={"vehicle_id": "SK-01-J-4471"}).json()
    assert route["vehicle"]["vehicle_id"] == "SK-01-J-4471"
    assert route["id"] == "RTE-1001"


def test_unknown_vehicle_still_returns_a_usable_route(client):
    """The app ships a demo registration that need not be in our fleet -- the
    Home screen should still paint, and the response says which vehicle it used."""
    route = client.get("/api/routes/current",
                       params={"vehicle_id": "AS-01-EG-4417"}).json()
    assert route["segments"] and route["vehicle"]["vehicle_id"]


# ------------------------------------------------------ POST /api/reports ---
@pytest.mark.parametrize("sent,stored", [
    ("flood", "flooding"),
    ("blocked_road", "traffic_block"),
    ("landslide", "landslide"),
    ("bridge_damage", "bridge_damage"),
    ("heavy_rain", "heavy_rain"),
])
def test_report_type_aliases(client, sent, stored):
    body = client.post("/api/reports",
                       json={"type": sent, "lat": 27.1935, "lng": 88.5142}).json()
    assert body["type"] == stored


def test_note_becomes_description_and_accuracy_is_kept(client):
    body = client.post("/api/reports", json={
        "type": "flood", "lat": 27.1935, "lng": 88.5142,
        "note": "Water over the carriageway.", "accuracy": 12.5,
    }).json()
    assert "Water over the carriageway." in body["description"]
    assert "12" in body["description"]


def test_report_attaches_to_a_segment_and_state(client):
    body = client.post("/api/reports",
                       json={"type": "landslide", "lat": 27.1935, "lng": 88.5142}).json()
    assert body["segment_id"] and body["state"] == "Sikkim"


def test_replayed_report_is_deduplicated(client):
    payload = {"event_id": "uuid-from-the-pwa", "type": "flood",
               "lat": 27.1935, "lng": 88.5142}
    first = client.post("/api/reports", json=payload)
    second = client.post("/api/reports", json=payload)
    assert first.status_code == 201 and second.status_code == 200
    assert first.json()["event_id"] == second.json()["event_id"]


def test_unknown_report_type_is_rejected(client):
    assert client.post("/api/reports", json={
        "type": "alien_invasion", "lat": 27.0, "lng": 88.0}).status_code == 422


# ------------------------------------------------------- POST /api/alerts ---
def _sos(**over):
    payload = {
        "id": "alt-9f2c1a77", "event": "sos_accident", "severity": "critical",
        "recipients": ["mdoner-control-room", "nearest-patrol-unit"],
        "lang": "en", "status": "raised",
    }
    payload.update(over)
    return payload


def test_sos_without_coordinates_takes_the_vehicle_fix(client):
    """The app's SOS payload carries no lat/lng at all."""
    alert = client.post("/api/alerts", json=_sos(vehicle_id="SK-01-J-4471")).json()
    assert alert["lat"] is not None and alert["lng"] is not None
    assert alert["state"]


def test_sos_gets_a_title_from_its_event(client):
    alert = client.post("/api/alerts", json=_sos()).json()
    assert "accident" in alert["title"].lower()


def test_raised_status_maps_to_pending(client):
    """'raised' is the app's word; the contract only knows pending|sent|..."""
    alert = client.post("/api/alerts", json=_sos()).json()
    assert alert["status"] == "pending"


def test_sos_keeps_recipients_and_language(client):
    alert = client.post("/api/alerts", json=_sos(lang="ne")).json()
    assert "mdoner-control-room" in alert["recipients"]
    assert alert["lang"] == "ne"


def test_sos_shows_up_in_the_canonical_alert_feed(client):
    posted = client.post("/api/alerts", json=_sos()).json()
    assert any(a["id"] == posted["id"] for a in client.get("/alerts").json())


# ---------------------------------------------- POST /api/alerts/location ---
def test_location_pings_are_recorded_and_trail_newest_first(client):
    alert = client.post("/api/alerts", json=_sos()).json()
    for i, (lat, lng) in enumerate([(27.18, 88.52), (27.19, 88.53), (27.20, 88.54)]):
        r = client.post("/api/alerts/location", json={
            "alert_id": alert["id"], "vehicle_id": "SK-01-J-4471", "node": "A",
            "lat": lat, "lng": lng, "accuracy": 8.0,
            "at": f"2026-08-26T11:4{i}:00+05:30",
        })
        assert r.status_code == 201

    trail = client.get("/api/alerts/location", params={"alert_id": alert["id"]}).json()
    assert len(trail) == 3
    assert trail[0]["lat"] == 27.20, "newest fix should come first"


def test_ping_without_a_fix_is_still_accepted(client):
    """A ping can arrive before geolocation resolves; losing it loses the trail."""
    r = client.post("/api/alerts/location",
                    json={"alert_id": "alt-x", "vehicle_id": "SK-01-J-4471"})
    assert r.status_code == 201 and r.json()["lat"] is None


# ------------------------------------------------------------- no drift ----
def test_canonical_routes_are_unchanged_by_the_compat_layer(client):
    """The /api dialect must not leak into the contract surface."""
    segment = client.get("/segments/SEG-SK-NH10-001").json()
    assert segment["status"] == "restricted"      # not "caution"
    assert "risk" in segment and "path" not in segment

    route = client.get("/routes/RTE-1001").json()
    assert route["origin"] == "Siliguri, West Bengal"   # a string, not an object


def test_both_report_routes_share_one_store(client):
    posted = client.post("/api/reports", json={
        "event_id": "EVT-SHARED-1", "type": "flood", "lat": 27.1935, "lng": 88.5142,
    }).json()
    assert client.get(f"/reports/{posted['event_id']}").json()["type"] == "flooding"
