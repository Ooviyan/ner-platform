"""Repository layer.

Every function takes an optional SQLAlchemy Session. When it is None (PostGIS not
running) the same query is answered from the in-memory seed, so the JSON shape the
dashboard and driver app see is identical either way.

Field names throughout are the shared ../mock-data contract.
"""

from __future__ import annotations

import json
import threading
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Sequence

from geoalchemy2 import Geography, WKTElement
from sqlalchemy import cast, func, select
from sqlalchemy.orm import Session

from app import geo, seed
from app.models import Alert, Incident, RoadSegment, Route, Vehicle
from app.ner_states import NER_STATES, normalize_state

_lock = threading.Lock()
IST = seed.IST


def _now() -> datetime:
    return datetime.now(IST)


def _iso(value) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(IST).isoformat()


def _dt(value: Optional[str]) -> datetime:
    if not value:
        return _now()
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _json(value, default):
    try:
        return json.loads(value) if value else default
    except (TypeError, ValueError):
        return default


# --------------------------------------------------------- in-memory state ---
class MemoryStore:
    """Mutable copy of the seed, used whenever PostGIS is not connected."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.segments = deepcopy(seed.SEGMENTS)
        self.routes = deepcopy(seed.ROUTES)
        self.vehicles = deepcopy(seed.VEHICLES)
        self.alerts = deepcopy(seed.ALERTS)
        self.reports = deepcopy(seed.REPORTS)


MEMORY = MemoryStore()


# ------------------------------------------------------------ row -> dict ---
def _segment_row(row, geometry: dict) -> dict:
    return {
        "id": row.id, "name": row.name, "risk": row.risk,
        "accessibility": row.accessibility, "status": row.status,
        "geometry": geometry,
        "state": row.state, "state_code": row.state_code, "highway": row.highway,
        "road_class": row.road_class, "length_km": round(row.length_km or 0.0, 2),
        "surface": row.surface, "lanes": row.lanes, "elevation_m": row.elevation_m,
        "slope_deg": row.slope_deg, "rainfall_mm_24h": row.rainfall_mm_24h,
        "rainfall_mm_72h": row.rainfall_mm_72h, "risk_band": row.risk_band,
        "source": row.source, "updated_at": _iso(row.updated_at),
    }


def _route_row(row, geometry: dict) -> dict:
    return {
        "id": row.id, "origin": row.origin, "destination": row.destination,
        "chosen": row.chosen, "eta_min": row.eta_min, "delay_min": row.delay_min,
        "risk": row.risk, "segments": _json(row.segment_ids, []),
        "geometry": geometry,
        "origin_point": {"lng": row.origin_lng, "lat": row.origin_lat},
        "destination_point": {"lng": row.destination_lng, "lat": row.destination_lat},
        "distance_km": round(row.distance_km or 0.0, 2), "risk_band": row.risk_band,
        "accessibility": row.accessibility, "passable": row.passable,
        "closed_segments": _json(row.closed_segments, []),
        "advisories": _json(row.advisories, []), "profile": row.profile,
        "generated_at": _iso(row.generated_at),
    }


def _vehicle_row(row, geometry: dict) -> dict:
    return {
        "vehicle_id": row.vehicle_id, "cargo": row.cargo, "route_id": row.route_id,
        "progress": row.progress, "status": row.status,
        "type": row.type, "operator": row.operator, "state": row.state,
        "lat": row.lat, "lng": row.lng, "heading": row.heading,
        "speed_kmph": row.speed_kmph, "segment_id": row.segment_id,
        "distance_remaining_km": row.distance_remaining_km, "eta_min": row.eta_min,
        "last_ping": _iso(row.last_ping), "geometry": geometry,
    }


def _report_row(row, geometry: dict) -> dict:
    return {
        "event_id": row.event_id, "type": row.type, "lat": row.lat, "lng": row.lng,
        "timestamp": _iso(row.timestamp), "photo": row.photo,
        "vehicle_id": row.vehicle_id, "state": row.state,
        "id": row.id, "severity": row.severity, "description": row.description,
        "segment_id": row.segment_id, "reporter": row.reporter, "status": row.status,
        "created_at": _iso(row.created_at), "geometry": geometry,
    }


def _alert_row(row, geometry: dict) -> dict:
    return {
        "id": row.id, "event": row.event, "severity": row.severity,
        "recipients": _json(row.recipients, []), "lang": row.lang, "status": row.status,
        "type": row.type, "title": row.title, "message": row.message,
        "state": row.state, "segment_id": row.segment_id, "lat": row.lat,
        "lng": row.lng, "radius_km": row.radius_km, "source": row.source,
        "active": row.active, "issued_at": _iso(row.issued_at),
        "expires_at": _iso(row.expires_at), "geometry": geometry,
    }


def _fetch(db: Session, model, to_dict, where=None, order_by=None, limit=None, offset=None):
    """Select entities plus their geometry as GeoJSON, in one round trip."""
    stmt = select(model, func.ST_AsGeoJSON(model.geom))
    if where:
        stmt = stmt.where(*where)
    if order_by is not None:
        stmt = stmt.order_by(*order_by)
    if offset:
        stmt = stmt.offset(offset)
    if limit:
        stmt = stmt.limit(limit)
    return [to_dict(row, json.loads(gj)) for row, gj in db.execute(stmt).all()]


# ---------------------------------------------------------------- filters ---
def _state_name(value: str) -> str:
    slug = normalize_state(value)
    return NER_STATES[slug]["name"] if slug else value


def _state_matches(value: Optional[str], target: Optional[str]) -> bool:
    if not target:
        return True
    return (value or "").lower() == _state_name(target).lower()


def _in_bbox(geometry: dict, bbox: Optional[Sequence[float]]) -> bool:
    if not bbox:
        return True
    min_lng, min_lat, max_lng, max_lat = bbox
    coords = geometry["coordinates"]
    pts = [coords] if geometry["type"] == "Point" else coords
    return any(min_lng <= x <= max_lng and min_lat <= y <= max_lat for x, y in pts)


# --------------------------------------------------------------- segments ---
def list_segments(
    db: Optional[Session],
    state: Optional[str] = None,
    status: Optional[str] = None,
    risk_band: Optional[str] = None,
    min_risk: Optional[float] = None,
    highway: Optional[str] = None,
    bbox: Optional[Sequence[float]] = None,
    limit: int = 500,
    offset: int = 0,
) -> List[dict]:
    if db is not None:
        where = []
        if state:
            where.append(RoadSegment.state == _state_name(state))
        if status:
            where.append(RoadSegment.status == status)
        if risk_band:
            where.append(RoadSegment.risk_band == risk_band)
        if min_risk is not None:
            where.append(RoadSegment.risk >= min_risk)
        if highway:
            where.append(RoadSegment.highway == highway)
        if bbox:
            where.append(func.ST_Intersects(
                RoadSegment.geom,
                func.ST_MakeEnvelope(bbox[0], bbox[1], bbox[2], bbox[3], 4326),
            ))
        return _fetch(db, RoadSegment, _segment_row, where,
                      order_by=[RoadSegment.risk.desc(), RoadSegment.id],
                      limit=limit, offset=offset)

    rows = [
        s for s in MEMORY.segments
        if _state_matches(s["state"], state)
        and (not status or s["status"] == status)
        and (not risk_band or s["risk_band"] == risk_band)
        and (min_risk is None or s["risk"] >= min_risk)
        and (not highway or s["highway"] == highway)
        and _in_bbox(s["geometry"], bbox)
    ]
    rows.sort(key=lambda s: (-s["risk"], s["id"]))
    return deepcopy(rows[offset: offset + limit])


def get_segment(db: Optional[Session], segment_id: str) -> Optional[dict]:
    if db is not None:
        found = _fetch(db, RoadSegment, _segment_row, [RoadSegment.id == segment_id], limit=1)
        return found[0] if found else None
    return next((deepcopy(s) for s in MEMORY.segments if s["id"] == segment_id), None)


def nearest_segment(db: Optional[Session], point: geo.Coord) -> Optional[dict]:
    """Closest segment to a point -- used to attach reports to the network."""
    if db is not None:
        here = func.ST_SetSRID(func.ST_MakePoint(point[0], point[1]), 4326)
        stmt = (select(RoadSegment, func.ST_AsGeoJSON(RoadSegment.geom))
                .order_by(func.ST_Distance(cast(RoadSegment.geom, Geography),
                                           cast(here, Geography)))
                .limit(1))
        row = db.execute(stmt).first()
        return _segment_row(row[0], json.loads(row[1])) if row else None

    best, best_km = None, float("inf")
    for segment in MEMORY.segments:
        for coord in segment["geometry"]["coordinates"]:
            d = geo.haversine_km(point, tuple(coord))
            if d < best_km:
                best, best_km = segment, d
    return deepcopy(best) if best else None


# ----------------------------------------------------------------- routes ---
def list_routes(db: Optional[Session], state: Optional[str] = None) -> List[dict]:
    rows = (_fetch(db, Route, _route_row, order_by=[Route.id])
            if db is not None else deepcopy(MEMORY.routes))
    if not state:
        return rows
    keep = {s["id"] for s in list_segments(db, state=state, limit=10_000)}
    return [r for r in rows if keep.intersection(r["segments"])]


def get_route(db: Optional[Session], route_id: str) -> Optional[dict]:
    if db is not None:
        found = _fetch(db, Route, _route_row, [Route.id == route_id], limit=1)
        return found[0] if found else None
    return next((deepcopy(r) for r in MEMORY.routes if r["id"] == route_id), None)


# Speed a vehicle sustains on a segment of each risk band (km/h), and the
# clear-run speed the delay is measured against.
_SPEED_BY_BAND = {"low": 55.0, "medium": 42.0, "high": 28.0, "critical": 18.0}
_FAST_BY_BAND = {"low": 65.0, "medium": 55.0, "high": 40.0, "critical": 26.0}
_CLEAR_SPEED = 60.0
_PROFILE_NOTE = {
    "safest": "Optimised to avoid high-risk and closed stretches.",
    "fastest": "Optimised for travel time; may include higher-risk stretches.",
    "shortest": "Optimised for distance only.",
}


def _endpoints(route: dict) -> tuple:
    coords = [tuple(c) for c in route["geometry"]["coordinates"]]
    return coords[0], coords[-1]


def _score(route: dict, origin: geo.Coord, destination: geo.Coord) -> float:
    start, end = _endpoints(route)
    return geo.haversine_km(origin, start) + geo.haversine_km(destination, end)


def _summarise(route: dict) -> dict:
    return {
        "id": route["id"], "eta_min": route["eta_min"],
        "delay_min": route["delay_min"], "risk": route["risk"],
        "risk_band": route.get("risk_band"), "passable": route.get("passable"),
        "distance_km": route.get("distance_km"),
    }


def find_route(
    db: Optional[Session],
    origin: geo.Coord,
    origin_name: str,
    destination: geo.Coord,
    destination_name: str,
    profile: str = "safest",
    avoid_closed: bool = True,
) -> dict:
    """Best route between two points.

    Prefers a pre-computed corridor when the endpoints line up with one; otherwise
    synthesises a direct corridor. Person 2's `ml/routing.py safest_route()`
    replaces the scoring here at merge time -- this function is that seam.
    """
    candidates = list_routes(db)
    scored = sorted(candidates, key=lambda r: _score(r, origin, destination))
    best = scored[0] if scored else None

    if best is not None and _score(best, origin, destination) <= 80.0:
        route = deepcopy(best)
        alternatives = [r for r in scored[1:4]
                        if _score(r, origin, destination) <= 200.0]
    else:
        route = _synthesise(db, origin, origin_name, destination, destination_name)
        alternatives = []

    route["origin"] = origin_name
    route["destination"] = destination_name
    route["origin_point"] = {"lng": origin[0], "lat": origin[1]}
    route["destination_point"] = {"lng": destination[0], "lat": destination[1]}
    route["profile"] = profile
    route["generated_at"] = _iso(_now())

    segments = [s for s in (get_segment(db, sid) for sid in route["segments"]) if s]
    if segments:
        speeds = _FAST_BY_BAND if profile == "fastest" else _SPEED_BY_BAND
        eta = sum(s["length_km"] / speeds[s["risk_band"]] * 60 for s in segments)
        clear = sum(s["length_km"] / _CLEAR_SPEED * 60 for s in segments)
        route["eta_min"] = round(eta)
        route["delay_min"] = max(0, round(eta - clear))
        route["closed_segments"] = [s["id"] for s in segments if s["status"] == "closed"]
        route["passable"] = not route["closed_segments"]
        route["risk"] = round(max(s["risk"] for s in segments), 2)
        route["risk_band"] = seed.risk_band(route["risk"])
        route["accessibility"] = round(
            sum(s["accessibility"] for s in segments) / len(segments))
        route["distance_km"] = round(sum(s["length_km"] for s in segments), 2)

    route["chosen"] = profile == "safest" and route.get("passable", True)

    advisories = list(route.get("advisories", []))
    note = _PROFILE_NOTE.get(profile)
    if note and note not in advisories:
        advisories.append(note)
    if avoid_closed and route.get("closed_segments"):
        advisories.insert(0, "No fully passable corridor found - "
                             f"{len(route['closed_segments'])} segment(s) currently closed.")
    route["advisories"] = advisories
    route["alternatives"] = [_summarise(a) for a in alternatives]
    return route


def _synthesise(db, origin, origin_name, destination, destination_name) -> dict:
    """Direct corridor for an OD pair no seeded route covers."""
    ids = []
    for segment in (nearest_segment(db, origin), nearest_segment(db, destination)):
        if segment and segment["id"] not in ids:
            ids.append(segment["id"])
    coords = geo.densify([origin, destination], max_step_km=20.0)
    distance = geo.line_length_km(coords)
    eta = round(distance / 40.0 * 60)
    return {
        "id": "RTE-ADHOC",
        "origin": origin_name, "destination": destination_name,
        "chosen": False, "eta_min": eta,
        "delay_min": max(0, eta - round(distance / _CLEAR_SPEED * 60)),
        "risk": 0.0, "segments": ids,
        "geometry": geo.linestring(coords),
        "origin_point": {"lng": origin[0], "lat": origin[1]},
        "destination_point": {"lng": destination[0], "lat": destination[1]},
        "distance_km": round(distance, 2), "risk_band": "low",
        "accessibility": 100, "passable": True, "closed_segments": [],
        "advisories": ["Approximate corridor: no loaded road network links these "
                       "points. Run load_ner.py for the full OSM graph."],
        "profile": "safest", "generated_at": _iso(_now()),
    }


# --------------------------------------------------------------- vehicles ---
def list_vehicles(
    db: Optional[Session],
    state: Optional[str] = None,
    status: Optional[str] = None,
    vehicle_type: Optional[str] = None,
    route_id: Optional[str] = None,
) -> List[dict]:
    if db is not None:
        where = []
        if state:
            where.append(Vehicle.state == _state_name(state))
        if status:
            where.append(Vehicle.status == status)
        if vehicle_type:
            where.append(Vehicle.type == vehicle_type)
        if route_id:
            where.append(Vehicle.route_id == route_id)
        return _fetch(db, Vehicle, _vehicle_row, where, order_by=[Vehicle.vehicle_id])

    return deepcopy([
        v for v in MEMORY.vehicles
        if _state_matches(v["state"], state)
        and (not status or v["status"] == status)
        and (not vehicle_type or v["type"] == vehicle_type)
        and (not route_id or v["route_id"] == route_id)
    ])


def upsert_vehicle_positions(db: Optional[Session], positions: List[dict]) -> None:
    """Persist a simulation tick so GET /vehicles agrees with the WebSocket."""
    by_id = {p["vehicle_id"]: p for p in positions}
    if db is not None:
        for row in db.execute(select(Vehicle)).scalars():
            update = by_id.get(row.vehicle_id)
            if not update:
                continue
            row.lat, row.lng = update["lat"], update["lng"]
            row.heading = update["heading"]
            row.speed_kmph = update["speed_kmph"]
            row.status = update["status"]
            row.progress = update["progress"]
            row.segment_id = update["segment_id"]
            row.distance_remaining_km = update["distance_remaining_km"]
            row.eta_min = update["eta_min"]
            row.last_ping = _now()
            row.geom = WKTElement(geo.to_wkt_point((update["lng"], update["lat"])))
        db.commit()
        return

    with _lock:
        for vehicle in MEMORY.vehicles:
            update = by_id.get(vehicle["vehicle_id"])
            if update:
                vehicle.update(update)


# ---------------------------------------------------------------- reports ---
def list_reports(
    db: Optional[Session],
    state: Optional[str] = None,
    type_: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 200,
) -> List[dict]:
    if db is not None:
        where = []
        if state:
            where.append(Incident.state == _state_name(state))
        if type_:
            where.append(Incident.type == type_)
        if status:
            where.append(Incident.status == status)
        return _fetch(db, Incident, _report_row, where,
                      order_by=[Incident.timestamp.desc()], limit=limit)

    rows = [
        r for r in MEMORY.reports
        if _state_matches(r["state"], state)
        and (not type_ or r["type"] == type_)
        and (not status or r["status"] == status)
    ]
    rows.sort(key=lambda r: r["timestamp"], reverse=True)
    return deepcopy(rows[:limit])


def get_report(db: Optional[Session], event_id: str) -> Optional[dict]:
    if not event_id:
        return None
    if db is not None:
        found = _fetch(db, Incident, _report_row, [Incident.event_id == event_id], limit=1)
        return found[0] if found else None
    return next((deepcopy(r) for r in MEMORY.reports if r["event_id"] == event_id), None)


def _next_event_id(db: Optional[Session]) -> str:
    """Mint an EVT-NNNNN id in the contract's format."""
    existing = [r["event_id"] for r in list_reports(db, limit=10_000)]
    numbers = [int(e.split("-")[1]) for e in existing
               if e.startswith("EVT-") and e.split("-")[1].isdigit()]
    return f"EVT-{max(numbers, default=90000) + 1}"


def create_report(db: Optional[Session], payload: dict) -> tuple[dict, bool]:
    """Insert a driver report. Returns (report, created).

    The driver PWA queues reports offline and replays them, so an existing
    `event_id` returns the stored row instead of creating a duplicate.
    """
    event_id = payload.get("event_id") or _next_event_id(db)
    existing = get_report(db, event_id)
    if existing:
        return existing, False

    point = (payload["lng"], payload["lat"])
    segment = nearest_segment(db, point)
    timestamp = payload.get("timestamp") or _iso(_now())
    report = {
        "event_id": event_id,
        "type": payload["type"],
        "lat": payload["lat"],
        "lng": payload["lng"],
        "timestamp": timestamp,
        "photo": payload.get("photo"),
        "vehicle_id": payload.get("vehicle_id"),
        "state": segment["state"] if segment else None,
        "id": f"RPT-{event_id.split('-')[-1]}",
        "severity": payload.get("severity") or "medium",
        "description": payload.get("description"),
        "segment_id": segment["id"] if segment else None,
        "reporter": payload.get("reporter") or payload.get("vehicle_id"),
        "status": "pending",
        "created_at": _iso(_now()),
        "geometry": geo.point(point),
    }

    if db is not None:
        db.add(Incident(
            event_id=event_id, type=report["type"], lat=report["lat"],
            lng=report["lng"], timestamp=_dt(timestamp), photo=report["photo"],
            vehicle_id=report["vehicle_id"], state=report["state"], id=report["id"],
            severity=report["severity"], description=report["description"],
            segment_id=report["segment_id"], reporter=report["reporter"],
            status="pending", created_at=_now(),
            geom=WKTElement(geo.to_wkt_point(point)),
        ))
        db.commit()
    else:
        with _lock:
            MEMORY.reports.insert(0, report)
    return report, True


# ----------------------------------------------------------------- alerts ---
def list_alerts(
    db: Optional[Session],
    active: Optional[bool] = True,
    state: Optional[str] = None,
    severity: Optional[str] = None,
    status: Optional[str] = None,
    near: Optional[geo.Coord] = None,
    radius_km: float = 50.0,
    limit: int = 200,
) -> List[dict]:
    if db is not None:
        where = []
        if active is not None:
            where.append(Alert.active.is_(active))
        if state:
            where.append(Alert.state == _state_name(state))
        if severity:
            where.append(Alert.severity == severity)
        if status:
            where.append(Alert.status == status)
        if near:
            # Cast to geography so the radius is true metres, not degrees.
            here = func.ST_SetSRID(func.ST_MakePoint(near[0], near[1]), 4326)
            where.append(func.ST_DWithin(cast(Alert.geom, Geography),
                                         cast(here, Geography), radius_km * 1000.0))
        rows = _fetch(db, Alert, _alert_row, where,
                      order_by=[Alert.issued_at.desc()], limit=limit)
    else:
        rows = [
            a for a in MEMORY.alerts
            if (active is None or a["active"] is active)
            and _state_matches(a["state"], state)
            and (not severity or a["severity"] == severity)
            and (not status or a["status"] == status)
        ]
        if near:
            rows = [a for a in rows
                    if geo.haversine_km(near, (a["lng"], a["lat"])) <= radius_km]
        rows.sort(key=lambda a: a["issued_at"], reverse=True)
        rows = deepcopy(rows[:limit])

    rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    rows.sort(key=lambda a: rank.get(a["severity"], 9))
    return rows


def _next_alert_id(db: Optional[Session]) -> str:
    existing = [a["id"] for a in list_alerts(db, active=None, limit=10_000)]
    numbers = [int(a.split("-")[1]) for a in existing
               if a.startswith("ALT-") and a.split("-")[1].isdigit()]
    return f"ALT-{max(numbers, default=5000) + 1}"


def create_alert(db: Optional[Session], payload: dict) -> dict:
    point = (payload["lng"], payload["lat"])
    segment = (get_segment(db, payload["segment_id"])
               if payload.get("segment_id") else None) or nearest_segment(db, point)
    issued = _now()
    expires = payload.get("expires_at") or _iso(issued + timedelta(hours=24))
    alert = {
        "id": payload.get("id") or _next_alert_id(db),
        "event": payload.get("event"),
        "severity": payload.get("severity", "medium"),
        "recipients": payload.get("recipients") or [],
        "lang": payload.get("lang", "en"),
        "status": payload.get("status", "pending"),
        "type": payload.get("type", "advisory"),
        "title": payload["title"],
        "message": payload.get("message"),
        "state": segment["state"] if segment else payload.get("state"),
        "segment_id": segment["id"] if segment else None,
        "lat": payload["lat"],
        "lng": payload["lng"],
        "radius_km": payload.get("radius_km", 20.0),
        "source": payload.get("source", "manual"),
        "active": True,
        "issued_at": _iso(issued),
        "expires_at": expires,
        "geometry": geo.point(point),
    }
    if db is not None:
        db.add(Alert(
            id=alert["id"], event=alert["event"], severity=alert["severity"],
            recipients=json.dumps(alert["recipients"]), lang=alert["lang"],
            status=alert["status"], type=alert["type"], title=alert["title"],
            message=alert["message"], state=alert["state"],
            segment_id=alert["segment_id"], lat=alert["lat"], lng=alert["lng"],
            radius_km=alert["radius_km"], source=alert["source"], active=True,
            issued_at=issued, expires_at=_dt(expires),
            geom=WKTElement(geo.to_wkt_point(point)),
        ))
        db.commit()
    else:
        with _lock:
            MEMORY.alerts.insert(0, alert)
    return alert


# ------------------------------------------------------------------ stats ---
def summary(db: Optional[Session]) -> dict:
    segments = list_segments(db, limit=10_000)
    by_state: dict = {}
    for s in segments:
        b = by_state.setdefault(s["state"], {"segments": 0, "length_km": 0.0, "closed": 0})
        b["segments"] += 1
        b["length_km"] = round(b["length_km"] + (s["length_km"] or 0), 2)
        b["closed"] += s["status"] == "closed"

    vehicles = list_vehicles(db)
    return {
        "states": len(NER_STATES),
        "segments": len(segments),
        "network_km": round(sum(s["length_km"] or 0 for s in segments), 2),
        "closed_segments": sum(1 for s in segments if s["status"] == "closed"),
        "restricted_segments": sum(1 for s in segments if s["status"] == "restricted"),
        "high_risk_segments": sum(1 for s in segments if s["risk"] >= 0.5),
        "mean_accessibility": (round(sum(s["accessibility"] for s in segments)
                                     / len(segments), 1) if segments else None),
        "vehicles": len(vehicles),
        "vehicles_en_route": sum(1 for v in vehicles if v["status"] == "en_route"),
        "active_alerts": len(list_alerts(db, active=True)),
        "open_reports": len(list_reports(db, status="pending")),
        "by_state": by_state,
    }
