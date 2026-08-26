"""`/api/*` routes for the driver PWA.

The driver app was built against its own fixtures before this API existed, so it
speaks a slightly different dialect: an `/api` prefix, `note` instead of
`description`, `flood` instead of `flooding`, an SOS alert with no coordinates,
and a nested route shape with Leaflet-ordered paths.

Rather than make Person 4 rewrite a working, tested app -- or bend the shared
../mock-data contract to one client -- this module translates between the two.
The canonical `/segments`, `/route`, `/reports`, `/alerts` routes are unchanged
and remain the contract surface; everything here delegates to the same store.
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app import store
from app.database import get_db
from app.schemas import (
    REPORT_TYPE_ALIASES,
    DriverAlertCreate,
    DriverReportCreate,
    DriverRoute,
    LocationPingAck,
    LocationPingCreate,
    Alert,
    Report,
)

router = APIRouter(prefix="/api", tags=["driver-app (/api)"])

# Severity to attach to a report when the app does not send one.
_SEVERITY_BY_TYPE = {
    "landslide": "critical",
    "bridge_damage": "critical",
    "flooding": "high",
    "traffic_block": "medium",
    "road_damage": "medium",
    "heavy_rain": "medium",
}

_SOS_TITLES = {
    "sos_accident": "SOS - accident reported",
    "sos_medical": "SOS - medical emergency",
    "sos_danger": "SOS - driver reports danger",
    "sos_breakdown": "SOS - vehicle breakdown",
}


@router.get(
    "/routes/current",
    response_model=DriverRoute,
    summary="Current route assignment for a vehicle",
)
def current_route(
    vehicle_id: Optional[str] = Query(
        None,
        description="Registration, e.g. SK-01-J-4471. Unknown or omitted resolves "
                    "to a vehicle on a chosen route -- the response names which.",
    ),
    db: Optional[Session] = Depends(get_db),
):
    """The route this vehicle is running, shaped for the driver app's Home screen.

    Segment `path` is `[lat, lng]` (Leaflet order), and segment `status` is
    `clear|caution|high_risk|blocked` rather than the contract's
    `open|restricted|closed`, because that is what the app's map renders.
    """
    route = store.driver_route(db, vehicle_id)
    if route is None:
        raise HTTPException(404, "no route assignment available")
    return route


@router.get("/reports", response_model=List[Report], summary="List reports")
def list_reports(
    state: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    db: Optional[Session] = Depends(get_db),
):
    return store.list_reports(db, state=state, limit=limit)


@router.post(
    "/reports",
    response_model=Report,
    status_code=status.HTTP_201_CREATED,
    summary="File a report (driver-app dialect)",
    responses={200: {"description": "Already filed -- returns the stored report."}},
)
def create_report(
    payload: DriverReportCreate,
    response: Response,
    db: Optional[Session] = Depends(get_db),
):
    """Accepts the driver app's report payload.

    `type` is aliased onto the contract vocabulary (`flood` -> `flooding`,
    `blocked_road` -> `traffic_block`), `note` becomes `description`, and
    `accuracy` is folded into the description so the GPS quality is not lost.
    De-duplication by `event_id` works exactly as on `POST /reports`.
    """
    kind = REPORT_TYPE_ALIASES.get(payload.type, payload.type)
    if kind not in _SEVERITY_BY_TYPE and kind not in {
        "accident", "snow", "sos", "other"
    }:
        raise HTTPException(422, f"unknown report type {payload.type!r}")

    description = payload.note
    if payload.accuracy is not None:
        suffix = f"(GPS accuracy ±{payload.accuracy:.0f} m)"
        description = f"{description} {suffix}" if description else suffix

    report, created = store.create_report(db, {
        "event_id": payload.event_id,
        "type": kind,
        "lat": payload.lat,
        "lng": payload.lng,
        "timestamp": payload.timestamp,
        "photo": payload.photo,
        "vehicle_id": payload.vehicle_id,
        "severity": payload.severity or _SEVERITY_BY_TYPE.get(kind, "medium"),
        "description": description,
        "reporter": payload.vehicle_id,
    })

    if not created:
        response.status_code = status.HTTP_200_OK
    elif report["severity"] == "critical":
        store.create_alert(db, {
            "event": report["event_id"],
            "severity": "critical",
            "type": report["type"],
            "title": f"Driver report: {report['type'].replace('_', ' ')}",
            "message": report["description"] or "Reported by a driver in the field.",
            "lat": report["lat"], "lng": report["lng"],
            "segment_id": report["segment_id"],
            "recipients": [r for r in [report["vehicle_id"],
                                       "fleet-ops@ner-logistics.in"] if r],
            "source": "report", "status": "pending",
        })
    return report


@router.post(
    "/alerts",
    response_model=Alert,
    status_code=status.HTTP_201_CREATED,
    summary="Raise an SOS (driver-app dialect)",
)
def create_alert(payload: DriverAlertCreate, db: Optional[Session] = Depends(get_db)):
    """Raises an alert from the driver app's one-tap SOS.

    That payload carries no coordinates and no title -- only who to notify and
    how bad it is -- so the position comes from the vehicle's last known fix and
    the title from the `event` (`sos_accident` -> "SOS - accident reported").
    """
    lat, lng = payload.lat, payload.lng
    vehicle = None
    if lat is None or lng is None:
        vehicle = store.resolve_vehicle(db, payload.vehicle_id)
        if vehicle is None:
            raise HTTPException(
                422, "no coordinates supplied and no vehicle to take a fix from"
            )
        lat, lng = vehicle["lat"], vehicle["lng"]

    event = payload.event or "sos"
    title = payload.title or _SOS_TITLES.get(event, f"SOS - {event.replace('_', ' ')}")
    vehicle_id = payload.vehicle_id or (vehicle or {}).get("vehicle_id")

    return store.create_alert(db, {
        "id": payload.id,
        "event": event,
        "severity": payload.severity,
        # "raised" is the app's word for a freshly-sent alert.
        "status": "pending" if payload.status in (None, "raised") else payload.status,
        "recipients": payload.recipients,
        "lang": payload.lang if payload.lang in
                {"en", "as", "bn", "hi", "ne", "lus", "mni"} else "en",
        "type": "sos",
        "title": title,
        "message": payload.message or (
            f"One-tap SOS from {vehicle_id}." if vehicle_id else "One-tap SOS."
        ),
        "lat": lat, "lng": lng,
        "radius_km": 25.0,
        "source": "driver-app",
    })


@router.post(
    "/alerts/location",
    response_model=LocationPingAck,
    status_code=status.HTTP_201_CREATED,
    summary="Location ping for an active SOS",
)
def location_ping(payload: LocationPingCreate, db: Optional[Session] = Depends(get_db)):
    """One position fix while an SOS is running.

    The app sends these every 15s and buffers them while offline, then flushes
    on reconnect -- so out-of-order and late arrivals are normal and accepted.
    """
    return store.create_location_ping(db, payload.model_dump())


@router.get(
    "/alerts/location",
    response_model=List[LocationPingAck],
    summary="Track an SOS",
)
def list_pings(
    alert_id: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    db: Optional[Session] = Depends(get_db),
):
    """The trail of fixes for an alert, newest first -- what the control room follows."""
    return store.list_location_pings(db, alert_id=alert_id, limit=limit)
