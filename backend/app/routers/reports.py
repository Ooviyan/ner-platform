"""POST /reports -- driver-filed incident reports, plus the read side."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app import store
from app.database import get_db
from app.schemas import Report, ReportCreate

router = APIRouter(tags=["reports"])


@router.post(
    "/reports",
    response_model=Report,
    status_code=status.HTTP_201_CREATED,
    summary="File an incident report",
    responses={200: {"description": "Already filed -- returns the stored report."}},
)
def create_report(
    payload: ReportCreate,
    response: Response,
    db: Optional[Session] = Depends(get_db),
):
    """Accepts a report from the driver PWA.

    The app queues reports offline and replays them on reconnect, so a repeated
    `event_id` returns the existing report with **200** rather than creating a
    duplicate. A fresh report gets **201**. Either way the body is the same shape.
    """
    report, created = store.create_report(db, payload.model_dump(by_alias=False))
    if not created:
        response.status_code = status.HTTP_200_OK
    elif report["severity"] == "critical":
        # A critical report is worth an immediate broadcast to nearby drivers.
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


@router.get("/reports", response_model=List[Report], summary="List reports")
def list_reports(
    state: Optional[str] = Query(None),
    type: Optional[str] = Query(None, description="landslide | flooding | road_damage | ..."),
    status_: Optional[str] = Query(
        None, alias="status", pattern="^(pending|verified|resolved|rejected)$"
    ),
    limit: int = Query(200, ge=1, le=1000),
    db: Optional[Session] = Depends(get_db),
):
    return store.list_reports(db, state=state, type_=type, status=status_, limit=limit)


@router.get("/reports/{event_id}", response_model=Report, summary="Look up by event id")
def get_report(event_id: str, db: Optional[Session] = Depends(get_db)):
    """Lets the driver app confirm a queued report landed before clearing it."""
    report = store.get_report(db, event_id)
    if report is None:
        raise HTTPException(404, f"no report with event_id {event_id!r}")
    return report
