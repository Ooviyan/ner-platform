"""GET /segments -- the road network with its risk and accessibility scores."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import store
from app.database import get_db
from app.ner_states import NER_STATES, normalize_state
from app.schemas import Segment, StateInfo

router = APIRouter(tags=["segments"])


@router.get("/segments", response_model=List[Segment], summary="List road segments")
def list_segments(
    state: Optional[str] = Query(
        None, description='NER state name, slug or code -- "Sikkim", "sikkim", "SK".'
    ),
    status: Optional[str] = Query(None, pattern="^(open|restricted|closed)$"),
    risk_band: Optional[str] = Query(None, pattern="^(low|medium|high|critical)$"),
    min_risk: Optional[float] = Query(None, ge=0.0, le=1.0),
    highway: Optional[str] = Query(None, description='e.g. "NH-10"'),
    bbox: Optional[str] = Query(
        None, description="min_lng,min_lat,max_lng,max_lat -- map viewport filter."
    ),
    limit: int = Query(500, ge=1, le=10_000),
    offset: int = Query(0, ge=0),
    db: Optional[Session] = Depends(get_db),
):
    if state and normalize_state(state) is None:
        raise HTTPException(422, f"unknown state {state!r}")
    box = None
    if bbox:
        try:
            box = [float(v) for v in bbox.split(",")]
            if len(box) != 4:
                raise ValueError
        except ValueError:
            raise HTTPException(422, "bbox must be min_lng,min_lat,max_lng,max_lat")
    return store.list_segments(
        db, state=state, status=status, risk_band=risk_band, min_risk=min_risk,
        highway=highway, bbox=box, limit=limit, offset=offset,
    )


@router.get("/segments/{segment_id}", response_model=Segment, summary="One segment")
def get_segment(segment_id: str, db: Optional[Session] = Depends(get_db)):
    segment = store.get_segment(db, segment_id)
    if segment is None:
        raise HTTPException(404, f"segment {segment_id!r} not found")
    return segment


@router.get("/states", response_model=List[StateInfo], summary="The eight NER states")
def list_states(db: Optional[Session] = Depends(get_db)):
    counts: dict = {}
    for segment in store.list_segments(db, limit=10_000):
        counts[segment["state"]] = counts.get(segment["state"], 0) + 1
    return [
        {"slug": slug, "name": m["name"], "code": m["code"], "capital": m["capital"],
         "center": m["center"], "bbox": m["bbox"], "segments": counts.get(m["name"], 0)}
        for slug, m in NER_STATES.items()
    ]
