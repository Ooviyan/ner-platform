"""GET /vehicles -- last known fleet positions (the WebSocket streams the live feed)."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app import store
from app.database import get_db
from app.schemas import Vehicle
from app.simulation import simulator

router = APIRouter(tags=["vehicles"])


@router.get("/vehicles", response_model=List[Vehicle], summary="List vehicles")
def list_vehicles(
    state: Optional[str] = Query(None),
    status: Optional[str] = Query(None, pattern="^(en_route|idle|halted|offline)$"),
    type: Optional[str] = Query(None, description="truck | ambulance | relief | bus"),
    route_id: Optional[str] = Query(None),
    db: Optional[Session] = Depends(get_db),
):
    # The simulator holds the freshest fix; fall back to storage if it is idle.
    live = {v["vehicle_id"]: v for v in simulator.snapshot()}
    rows = store.list_vehicles(db, state=state, status=status,
                               vehicle_type=type, route_id=route_id)
    merged = [live.get(r["vehicle_id"], r) for r in rows]
    return [v for v in merged
            if (not status or v["status"] == status)
            and (not type or v["type"] == type)]
