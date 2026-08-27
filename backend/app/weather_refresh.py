"""Keep the segment rainfall columns fed with real observations.

`/segments` carries `rainfall_mm_24h` and `rainfall_mm_72h`, and those two
numbers drive the risk model harder than anything else - 3-day rainfall is its
largest feature by mean |SHAP|. Seeded values make every score downstream a
work of fiction, however good the model is.

This pulls the real figures from Open-Meteo (via `ml/weather.py`) and writes
them into `road_segments`, so every consumer - the dashboard, the driver app,
the router, the risk model - reads the same real numbers from one place, with
no outbound HTTP call in the request path.

Refresh runs once at startup and then on an interval. It is best-effort: a
failed refresh logs and leaves the previous values in place, because a stale
rainfall reading is worth far more than none.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select

from app.config import settings
from app.database import SessionLocal, db_available
from app.intelligence import ml
from app.models import RoadSegment

log = logging.getLogger("ner.weather")


def _weather_module():
    """ml/weather.py, or None when the intelligence layer is unavailable."""
    if not ml.available():
        return None
    try:
        import weather
        return weather
    except ImportError:
        log.warning("ml/weather.py not importable - rainfall stays as seeded")
        return None


def refresh_once(force: bool = False) -> dict[str, Any]:
    """Fetch real rainfall for every segment and write it to the database.

    Returns a small summary for logging and /health.
    """
    module = _weather_module()
    if module is None:
        return {"updated": 0, "reason": "intelligence layer unavailable"}
    if not db_available():
        return {"updated": 0, "reason": "database unavailable"}

    with SessionLocal() as session:
        rows = list(session.execute(select(RoadSegment)).scalars())
        if not rows:
            return {"updated": 0, "reason": "no segments"}

        # One batched call for the whole network, cached on disk for an hour.
        segments = [
            {"id": r.id, "geometry": {"coordinates": _coords(session, r)}}
            for r in rows
        ]
        segments = [s for s in segments if s["geometry"]["coordinates"]]
        readings = module.segment_rainfall(segments, use_cache=not force)
        if not readings:
            return {"updated": 0, "reason": "no readings (Open-Meteo unreachable)"}

        updated = 0
        for row in rows:
            reading = readings.get(row.id)
            if not reading:
                continue
            row.rainfall_mm_72h = float(reading["rain_3day_mm"])
            # The column is a 24h total; the model wants an hourly rate and
            # derives it back out. Store the last 24h from the same series.
            row.rainfall_mm_24h = round(float(reading["rain_now_mm"]) * 24.0, 2)
            row.updated_at = datetime.now(timezone.utc)
            updated += 1
        session.commit()

    log.info("rainfall refreshed for %d/%d segments from Open-Meteo",
             updated, len(rows))
    return {"updated": updated, "segments": len(rows), "source": "open-meteo"}


def _coords(session, row: RoadSegment) -> list:
    """Segment geometry as [[lon, lat], ...] for the midpoint lookup."""
    import json
    from sqlalchemy import func
    gj = session.execute(select(func.ST_AsGeoJSON(RoadSegment.geom))
                         .where(RoadSegment.id == row.id)).scalar()
    return json.loads(gj)["coordinates"] if gj else []


_task: Optional[asyncio.Task] = None
_last: dict[str, Any] = {"updated": 0, "reason": "not run yet"}


def last_result() -> dict[str, Any]:
    return dict(_last)


async def _loop() -> None:
    global _last
    while True:
        try:
            # Off the event loop: this makes an outbound HTTP call.
            _last = await asyncio.to_thread(refresh_once)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("weather refresh failed - keeping previous values")
        await asyncio.sleep(max(settings.weather_refresh_minutes, 5) * 60)


def start() -> None:
    global _task
    if not settings.weather_refresh_enabled:
        log.info("weather refresh disabled (WEATHER_REFRESH_ENABLED=false)")
        return
    if _task is None or _task.done():
        _task = asyncio.create_task(_loop())
        log.info("weather refresh every %d min", settings.weather_refresh_minutes)


async def stop() -> None:
    global _task
    if _task:
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass
        _task = None
