"""GET /alerts -- dispatch records for the dashboard feed and driver push."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app import store
from app.database import get_db
from app.schemas import Alert, AlertCreate

router = APIRouter(tags=["alerts"])


@router.get("/alerts", response_model=List[Alert], summary="List alerts")
def list_alerts(
    active: Optional[bool] = Query(
        None,
        description="Unset returns every alert (what ../mock-data shows). "
                    "active=true is the live dashboard feed; active=false is history.",
    ),
    state: Optional[str] = Query(None),
    severity: Optional[str] = Query(None, pattern="^(low|medium|high|critical)$"),
    status_: Optional[str] = Query(
        None, alias="status", pattern="^(pending|sent|acknowledged|failed)$"
    ),
    near: Optional[str] = Query(
        None, description='"lat,lng" -- only alerts within radius_km of this point.'
    ),
    radius_km: float = Query(50.0, gt=0, le=500),
    limit: int = Query(200, ge=1, le=1000),
    db: Optional[Session] = Depends(get_db),
):
    point = None
    if near:
        try:
            lat, lng = (float(v) for v in near.split(","))
            point = (lng, lat)
        except ValueError:
            raise HTTPException(422, 'near must be "lat,lng"')
    return store.list_alerts(db, active=active, state=state, severity=severity,
                             status=status_, near=point, radius_km=radius_km, limit=limit)


@router.post("/alerts", response_model=Alert, status_code=status.HTTP_201_CREATED,
             summary="Raise an alert")
def create_alert(payload: AlertCreate, db: Optional[Session] = Depends(get_db)):
    """Used by the control centre, and by the platform when a critical report lands."""
    return store.create_alert(db, payload.model_dump())
