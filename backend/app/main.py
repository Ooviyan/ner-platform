"""NER Road Accessibility API -- FastAPI entrypoint.

    uvicorn app.main:app --reload --port 8000

Then open http://localhost:8000/docs.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app import store
from app.config import settings
from app.database import SessionLocal, db_available, db_status, get_db, init_db
from app.routers import alerts, compat, reports, routes, segments, vehicles, ws
from app.intelligence import ml
from app.schemas import Health
from app.simulation import simulator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
)
log = logging.getLogger("ner")

DESCRIPTION = """
Road accessibility and safe-routing for the eight North East India states
(SIH 2026 - PS26002, MDoNER).

**Data source** - PostGIS holds the OpenStreetMap road network loaded by
`load_ner.py`. A small pre-seeded sample of real NH corridors across all eight
states ships with the repo, so every endpoint returns data before you download
anything. If PostGIS is not running the API serves that sample from memory
instead of failing - check `GET /health` to see which mode you are in.

**Live fleet** - connect a WebSocket to `/ws/vehicles` for simulated GPS positions
moving along the loaded routes.
"""

TAGS = [
    {"name": "segments", "description": "Road network, risk and accessibility scores."},
    {"name": "routes", "description": "Safest-path routing between two points."},
    {"name": "vehicles", "description": "Fleet positions. Live feed on /ws/vehicles."},
    {"name": "reports", "description": "Driver-filed incident reports (offline-safe)."},
    {"name": "alerts", "description": "Advisories for the dashboard and driver push."},
    {"name": "websocket", "description": "Streaming endpoints."},
    {"name": "system", "description": "Health and platform summary."},
    {"name": "driver-app (/api)", "description":
        "Compatibility routes for the driver PWA. Same data as the canonical "
        "endpoints, in the shape that app already speaks."},
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    connected = init_db()
    if connected and settings.auto_seed:
        from app.bootstrap import seed_database

        with SessionLocal() as session:
            seed_database(session)

    # Load the simulator from whichever backend is live, then start ticking.
    session = SessionLocal() if connected else None
    try:
        simulator.load(
            store.list_vehicles(session),
            store.list_routes(session),
            store.list_segments(session, limit=10_000),
        )
    finally:
        if session is not None:
            session.close()

    def persist(positions):
        if not db_available():
            store.upsert_vehicle_positions(None, positions)
            return
        with SessionLocal() as write_session:
            store.upsert_vehicle_positions(write_session, positions)

    simulator.set_tick_callback(persist)
    simulator.start()
    log.info(
        "%s ready - CORS origins: %s", settings.app_name, ", ".join(settings.cors_origins)
    )
    try:
        yield
    finally:
        await simulator.stop()


app = FastAPI(
    title=settings.app_name,
    description=DESCRIPTION,
    version=settings.version,
    openapi_tags=TAGS,
    lifespan=lifespan,
)

# The dashboard (:3000) and driver PWA (:3001) call this API from the browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(segments.router)
app.include_router(routes.router)
app.include_router(vehicles.router)
app.include_router(reports.router)
app.include_router(alerts.router)
app.include_router(ws.router)
# Driver-PWA dialect; delegates to the same store as the canonical routes.
app.include_router(compat.router)


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/docs")


@app.get("/health", response_model=Health, tags=["system"], summary="Health check")
def health(db: Optional[Session] = Depends(get_db)):
    return {
        "status": "ok",
        "version": settings.version,
        "database": db_status(),
        "intelligence": ml.status(),
        "counts": {
            "segments": len(store.list_segments(db, limit=10_000)),
            "routes": len(store.list_routes(db)),
            "vehicles": len(store.list_vehicles(db)),
            "alerts": len(store.list_alerts(db, active=None)),
            "reports": len(store.list_reports(db, limit=10_000)),
            "ws_clients": simulator.client_count,
        },
    }


@app.get("/summary", tags=["system"], summary="Network summary for the dashboard")
def summary(db: Optional[Session] = Depends(get_db)):
    return store.summary(db)
