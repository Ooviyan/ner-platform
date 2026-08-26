"""End-to-end tests against the in-memory seed (no PostGIS required).

    pytest -q
"""

from __future__ import annotations

import json
import pathlib

import pytest
from fastapi.testclient import TestClient

from app import store
from app.main import app
from app.ner_states import NER_STATES

MOCK_DIR = pathlib.Path(__file__).resolve().parent.parent.parent / "mock-data"


@pytest.fixture()
def client():
    store.MEMORY.reset()
    with TestClient(app) as c:
        yield c


# ------------------------------------------------- the shared contract ---
CONTRACT = [
    ("segments.json", "/segments", "id"),
    ("routes.json", "/routes", "id"),
    ("vehicles.json", "/vehicles", "vehicle_id"),
    ("reports.json", "/reports", "event_id"),
    ("alerts.json", "/alerts", "id"),
]
# The simulator moves these between the seed and the first request.
LIVE = {"/vehicles": {"progress", "status"}}


@pytest.mark.skipif(not MOCK_DIR.exists(), reason="mock-data not present")
@pytest.mark.parametrize("filename,endpoint,key", CONTRACT)
def test_api_is_a_superset_of_mock_data(client, filename, endpoint, key):
    """Every ../mock-data record must come back with its contract fields intact.

    mock-data is owned by all four of us and Person 2's ml/routing.py reads it
    directly, so a rename here breaks their code and both frontends.
    """
    contract = json.loads((MOCK_DIR / filename).read_text())
    response = client.get(endpoint, params={"limit": 1000})
    assert response.status_code == 200, f"{endpoint} -> {response.status_code}"
    live = {r[key]: r for r in response.json()}
    skip = LIVE.get(endpoint, set())

    for record in contract:
        got = live.get(record[key])
        assert got is not None, f"{filename}: {record[key]} missing from {endpoint}"
        for field, value in record.items():
            if field in skip:
                continue
            assert got.get(field) == value, (
                f"{filename}: {record[key]}.{field} changed -- "
                f"contract={value!r} api={got.get(field)!r}"
            )


def test_contract_vocabularies_are_respected(client):
    for s in client.get("/segments").json():
        assert s["status"] in {"open", "restricted", "closed"}
        assert 0.0 <= s["risk"] <= 1.0 and 0 <= s["accessibility"] <= 100
    for v in client.get("/vehicles").json():
        assert v["status"] in {"en_route", "idle", "halted", "offline"}
    for a in client.get("/alerts").json():
        assert a["severity"] in {"low", "medium", "high", "critical"}
        assert a["status"] in {"pending", "sent", "acknowledged", "failed"}


# ------------------------------------------------------------- segments ---
def test_segments_cover_all_eight_states(client):
    rows = client.get("/segments", params={"limit": 10000}).json()
    assert {r["state"] for r in rows} == {m["name"] for m in NER_STATES.values()}


def test_segments_are_sorted_by_risk_descending(client):
    risks = [r["risk"] for r in client.get("/segments").json()]
    assert risks == sorted(risks, reverse=True)


@pytest.mark.parametrize("state", ["Sikkim", "sikkim", "SK"])
def test_state_filter_accepts_name_slug_and_code(client, state):
    rows = client.get("/segments", params={"state": state}).json()
    assert rows and all(r["state"] == "Sikkim" for r in rows)


def test_unknown_state_is_rejected(client):
    assert client.get("/segments", params={"state": "Bihar"}).status_code == 422


def test_bbox_filter_narrows_the_viewport(client):
    everything = client.get("/segments", params={"limit": 10000}).json()
    box = client.get("/segments", params={"bbox": "88.0,27.0,89.0,28.2"}).json()
    assert 0 < len(box) < len(everything)
    assert all(r["state"] == "Sikkim" for r in box)


def test_segment_detail_and_404(client):
    assert client.get("/segments/SEG-SK-NH10-001").json()["id"] == "SEG-SK-NH10-001"
    assert client.get("/segments/NOPE").status_code == 404


# --------------------------------------------------------------- routes ---
def test_route_between_known_places(client):
    route = client.get("/route", params={"from": "Siliguri", "to": "Gangtok"}).json()
    assert route["segments"]
    assert route["eta_min"] > 0 and route["delay_min"] >= 0
    assert route["origin"] == "Siliguri" and route["destination"] == "Gangtok"
    assert route["geometry"]["type"] == "LineString"


def test_route_accepts_lat_lng(client):
    route = client.get("/route", params={"from": "26.7271,88.4275",
                                         "to": "27.3314,88.6138"}).json()
    assert route["segments"] and route["passable"]


def test_route_flags_a_closed_corridor(client):
    route = client.get("/route", params={"from": "Guwahati", "to": "Badarpur"}).json()
    assert route["passable"] is False
    assert "SEG-ML-NH6-018" in route["closed_segments"]
    assert any("closed" in a.lower() for a in route["advisories"])
    assert route["chosen"] is False


def test_fastest_profile_is_not_slower_than_safest(client):
    params = {"from": "Dimapur", "to": "Imphal"}
    safest = client.get("/route", params={**params, "profile": "safest"}).json()
    fastest = client.get("/route", params={**params, "profile": "fastest"}).json()
    assert fastest["eta_min"] <= safest["eta_min"]
    assert safest["chosen"] and not fastest["chosen"]


def test_delay_min_is_zero_on_a_clear_run(client):
    """delay_min is time lost to risk, so it can never be negative."""
    for name in ("Agartala", "Guwahati", "Dimapur"):
        route = client.get("/route", params={"from": name, "to": "Churaibari"}).json()
        assert route["delay_min"] >= 0


def test_unroutable_place_is_rejected(client):
    assert client.get("/route", params={"from": "Atlantis",
                                        "to": "Gangtok"}).status_code == 422


def test_ad_hoc_pair_still_returns_a_corridor(client):
    route = client.get("/route", params={"from": "Agartala", "to": "Dibrugarh"}).json()
    assert route["distance_km"] > 0
    assert any("Approximate corridor" in a for a in route["advisories"])


# ------------------------------------------------------------- vehicles ---
def test_vehicles_carry_a_position_and_route(client):
    rows = client.get("/vehicles").json()
    assert rows
    for v in rows:
        assert -90 <= v["lat"] <= 90 and -180 <= v["lng"] <= 180
        assert v["route_id"] and v["geometry"]["type"] == "Point"


def test_vehicle_type_filter(client):
    rows = client.get("/vehicles", params={"type": "ambulance"}).json()
    assert rows and all(v["type"] == "ambulance" for v in rows)


# -------------------------------------------------------------- reports ---
def _report(**over):
    payload = {
        "event_id": "EVT-99001",
        "type": "landslide",
        "severity": "high",
        "description": "Debris across the carriageway.",
        "lat": 27.1935,
        "lng": 88.5142,
    }
    payload.update(over)
    return payload


def test_posting_a_report_attaches_it_to_the_nearest_segment(client):
    response = client.post("/reports", json=_report())
    assert response.status_code == 201
    body = response.json()
    assert body["segment_id"] and body["state"] == "Sikkim"
    assert body["status"] == "pending"


def test_replayed_offline_report_is_deduplicated(client):
    first = client.post("/reports", json=_report(event_id="EVT-99002"))
    second = client.post("/reports", json=_report(event_id="EVT-99002"))
    assert first.status_code == 201 and second.status_code == 200
    assert first.json()["event_id"] == second.json()["event_id"]
    matching = [r for r in client.get("/reports").json()
                if r["event_id"] == "EVT-99002"]
    assert len(matching) == 1


def test_report_without_event_id_gets_one_in_contract_format(client):
    body = client.post("/reports", json=_report(event_id=None)).json()
    assert body["event_id"].startswith("EVT-")
    assert client.get(f"/reports/{body['event_id']}").json()["type"] == "landslide"


def test_critical_report_raises_an_alert_linked_by_event(client):
    before = len(client.get("/alerts", params={"severity": "critical"}).json())
    posted = client.post("/reports",
                         json=_report(event_id="EVT-99003", severity="critical")).json()
    after = client.get("/alerts", params={"severity": "critical"}).json()
    assert len(after) == before + 1
    assert any(a["event"] == posted["event_id"] for a in after)


def test_invalid_type_is_rejected(client):
    assert client.post("/reports", json=_report(type="alien_invasion")).status_code == 422


def test_out_of_range_latitude_is_rejected(client):
    assert client.post("/reports", json=_report(lat=120.0)).status_code == 422


# --------------------------------------------------------------- alerts ---
def test_alerts_are_ordered_most_severe_first(client):
    rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    order = [rank[a["severity"]] for a in client.get("/alerts").json()]
    assert order == sorted(order)


def test_alerts_near_a_point(client):
    rows = client.get("/alerts", params={"near": "27.33,88.61",
                                         "radius_km": 60}).json()
    assert rows and all(a["state"] == "Sikkim" for a in rows)


def test_alerts_near_rejects_bad_input(client):
    assert client.get("/alerts", params={"near": "nonsense"}).status_code == 422


def test_alert_recipients_and_language_survive(client):
    alert = next(a for a in client.get("/alerts").json() if a["id"] == "ALT-5001")
    assert "SK-01-J-4471" in alert["recipients"] and alert["lang"] == "en"


# ------------------------------------------------------------ websocket ---
def test_ws_streams_positions_that_advance(client):
    with client.websocket_connect("/ws/vehicles") as ws:
        snapshot = ws.receive_json()
        assert snapshot["type"] == "snapshot" and snapshot["vehicles"]

        ws.send_text("ping")
        assert ws.receive_json()["type"] == "pong"

        frames = []
        while len(frames) < 3:
            frame = ws.receive_json()
            if frame["type"] == "vehicle_positions":
                frames.append(frame)

        moving = {v["vehicle_id"] for v in frames[0]["vehicles"]
                  if v["status"] == "en_route"}
        positions = {
            vid: {(v["lat"], v["lng"]) for f in frames
                  for v in f["vehicles"] if v["vehicle_id"] == vid}
            for vid in moving
        }
        assert any(len(p) > 1 for p in positions.values()), "no vehicle moved"


def test_ws_frames_match_the_vehicle_schema(client):
    rest_keys = sorted(client.get("/vehicles").json()[0])
    with client.websocket_connect("/ws/vehicles") as ws:
        assert sorted(ws.receive_json()["vehicles"][0]) == rest_keys


# --------------------------------------------------------------- system ---
def test_health_reports_the_active_backend(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["database"]["mode"] in {"postgis", "memory-seed"}
    assert body["counts"]["segments"] > 0


def test_summary_totals_line_up_with_segments(client):
    summary = client.get("/summary").json()
    segments = client.get("/segments", params={"limit": 10000}).json()
    assert summary["states"] == 8
    assert summary["segments"] == len(segments)
    assert summary["closed_segments"] == sum(1 for s in segments
                                             if s["status"] == "closed")


def test_states_endpoint_lists_all_eight(client):
    rows = client.get("/states").json()
    assert len(rows) == 8
    assert sum(r["segments"] for r in rows) == len(
        client.get("/segments", params={"limit": 10000}).json())


def test_cors_allows_the_two_frontends(client):
    for origin in ("http://localhost:3000", "http://localhost:3001"):
        response = client.options("/segments", headers={
            "Origin": origin, "Access-Control-Request-Method": "GET"})
        assert response.headers["access-control-allow-origin"] == origin
