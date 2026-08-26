"""Push the pre-seeded sample into PostGIS when the tables are empty.

Keeps a fresh `docker run postgis/postgis` useful straight away; `load_ner.py`
layers real OpenStreetMap geometry on top afterwards.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime

from geoalchemy2 import WKTElement
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import geo, seed
from app.models import Alert, Incident, RoadSegment, Route, Vehicle

log = logging.getLogger("ner.bootstrap")


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _coords(geometry: dict):
    return [tuple(c) for c in geometry["coordinates"]]


def segment_row(d: dict) -> RoadSegment:
    return RoadSegment(
        id=d["id"], name=d["name"], risk=d["risk"], accessibility=d["accessibility"],
        status=d["status"], state=d["state"], state_code=d.get("state_code"),
        highway=d.get("highway"), road_class=d.get("road_class"),
        length_km=d.get("length_km", 0.0), surface=d.get("surface"),
        lanes=d.get("lanes"), elevation_m=d.get("elevation_m"),
        slope_deg=d.get("slope_deg"), rainfall_mm_24h=d.get("rainfall_mm_24h", 0.0),
        rainfall_mm_72h=d.get("rainfall_mm_72h", 0.0), risk_band=d.get("risk_band"),
        source=d.get("source", "seed"), osm_id=d.get("osm_id"),
        updated_at=_dt(d["updated_at"]) if d.get("updated_at") else None,
        geom=WKTElement(geo.to_wkt_linestring(_coords(d["geometry"]))),
    )


def _route_row(d: dict) -> Route:
    return Route(
        id=d["id"], origin=d["origin"], destination=d["destination"],
        chosen=d["chosen"], eta_min=d["eta_min"], delay_min=d["delay_min"],
        risk=d["risk"], segment_ids=json.dumps(d["segments"]),
        origin_lat=d["origin_point"]["lat"], origin_lng=d["origin_point"]["lng"],
        destination_lat=d["destination_point"]["lat"],
        destination_lng=d["destination_point"]["lng"],
        distance_km=d.get("distance_km", 0.0), risk_band=d.get("risk_band"),
        accessibility=d.get("accessibility", 100), passable=d.get("passable", True),
        closed_segments=json.dumps(d.get("closed_segments", [])),
        advisories=json.dumps(d.get("advisories", [])),
        profile=d.get("profile", "safest"), generated_at=_dt(d["generated_at"]),
        geom=WKTElement(geo.to_wkt_linestring(_coords(d["geometry"]))),
    )


def _vehicle_row(d: dict) -> Vehicle:
    return Vehicle(
        vehicle_id=d["vehicle_id"], cargo=d.get("cargo"), route_id=d.get("route_id"),
        progress=d["progress"], status=d["status"], type=d.get("type"),
        operator=d.get("operator"), state=d.get("state"), lat=d["lat"], lng=d["lng"],
        heading=d.get("heading", 0.0), speed_kmph=d.get("speed_kmph", 0.0),
        segment_id=d.get("segment_id"),
        distance_remaining_km=d.get("distance_remaining_km"),
        eta_min=d.get("eta_min"), last_ping=_dt(d["last_ping"]),
        geom=WKTElement(geo.to_wkt_point((d["lng"], d["lat"]))),
    )


def _alert_row(d: dict) -> Alert:
    return Alert(
        id=d["id"], event=d.get("event"), severity=d["severity"],
        recipients=json.dumps(d.get("recipients", [])), lang=d.get("lang", "en"),
        status=d.get("status", "pending"), type=d.get("type"), title=d.get("title"),
        message=d.get("message"), state=d.get("state"), segment_id=d.get("segment_id"),
        lat=d["lat"], lng=d["lng"], radius_km=d.get("radius_km", 20.0),
        source=d.get("source", "manual"), active=d.get("active", True),
        issued_at=_dt(d["issued_at"]), expires_at=_dt(d["expires_at"]),
        geom=WKTElement(geo.to_wkt_point((d["lng"], d["lat"]))),
    )


def _incident_row(d: dict) -> Incident:
    return Incident(
        event_id=d["event_id"], type=d["type"], lat=d["lat"], lng=d["lng"],
        timestamp=_dt(d["timestamp"]), photo=d.get("photo"),
        vehicle_id=d.get("vehicle_id"), state=d.get("state"), id=d.get("id"),
        severity=d.get("severity", "medium"), description=d.get("description"),
        segment_id=d.get("segment_id"), reporter=d.get("reporter"),
        status=d.get("status", "pending"), created_at=_dt(d["created_at"]),
        geom=WKTElement(geo.to_wkt_point((d["lng"], d["lat"]))),
    )


# Foreign-key order: parents before the rows that reference them.
_TABLES = (
    (RoadSegment, seed.SEGMENTS, segment_row),
    (Route, seed.ROUTES, _route_row),
    (Vehicle, seed.VEHICLES, _vehicle_row),
    (Incident, seed.REPORTS, _incident_row),
    (Alert, seed.ALERTS, _alert_row),
)


def seed_database(session: Session, force: bool = False) -> dict:
    """Insert the sample rows into any table that is still empty.

    `_TABLES` is in foreign-key order and each table is committed before the next
    one starts, so children always find their parent. Deletes run in reverse.
    """
    inserted = {}

    if force:
        for model, _, _ in reversed(_TABLES):
            session.query(model).delete()
        session.commit()

    for model, rows, to_row in _TABLES:
        count = session.execute(select(func.count()).select_from(model)).scalar_one()
        if count:
            inserted[model.__tablename__] = 0
            continue
        session.add_all([to_row(r) for r in rows])
        session.commit()
        inserted[model.__tablename__] = len(rows)

    if sum(inserted.values()):
        log.info("seeded PostGIS: %s", inserted)
    return inserted
