"""GET /route -- safest-path lookup between two points."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import store
from app.database import get_db
from app.places import PLACES, resolve
from app.schemas import Route

router = APIRouter(tags=["routes"])

_HELP = 'Place name or "lat,lng" -- e.g. "Siliguri" or "26.7271,88.4275".'


@router.get("/route", response_model=Route, summary="Best route between two points")
def get_route(
    from_: str = Query(..., alias="from", description=_HELP),
    to: str = Query(..., description=_HELP),
    profile: str = Query("safest", pattern="^(safest|fastest|shortest)$"),
    avoid_closed: bool = Query(True, description="Flag closed segments on the path."),
    db: Optional[Session] = Depends(get_db),
):
    origin, destination = resolve(from_), resolve(to)
    if origin is None:
        raise HTTPException(
            422,
            f"cannot resolve from={from_!r}. Use lat,lng or one of: "
            f"{', '.join(sorted(PLACES)[:12])}...",
        )
    if destination is None:
        raise HTTPException(422, f"cannot resolve to={to!r}. Use lat,lng or a known place.")

    (origin_pt, origin_name), (dest_pt, dest_name) = origin, destination
    return store.find_route(db, origin_pt, origin_name, dest_pt, dest_name,
                            profile=profile, avoid_closed=avoid_closed)


@router.get("/routes", response_model=List[Route], summary="Pre-computed corridors")
def list_routes(state: Optional[str] = Query(None), db: Optional[Session] = Depends(get_db)):
    return store.list_routes(db, state=state)


@router.get("/routes/{route_id}", response_model=Route, summary="One corridor")
def get_route_by_id(route_id: str, db: Optional[Session] = Depends(get_db)):
    route = store.get_route(db, route_id)
    if route is None:
        raise HTTPException(404, f"route {route_id!r} not found")
    return route
