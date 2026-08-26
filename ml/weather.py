"""Real hourly rainfall from Open-Meteo.

    from ml.weather import segment_rainfall, rainfall_at

    rainfall_at(27.1935, 88.5142)
    # {"rain_now_mm": 0.4, "rain_3day_mm": 40.5, "source": "open-meteo", ...}

The model was trained on rainfall in the *last hour* and cumulative rainfall over
*72 hours*. Person 1's `/segments` carries 24h and 72h totals, so `rain_now_mm`
used to be faked by dividing the 24h figure by 24 -- which is exactly wrong for
the case that matters, since a cloudburst that drops 60 mm in three hours looks
identical to steady drizzle once you average it over a day. Landslides are
triggered by the burst.

This module removes that fudge. Open-Meteo serves hourly precipitation from the
ECMWF/DWD reanalysis-and-forecast blend, free and without an API key, so both
features come from the same real series:

    rain_now_mm   the most recently completed hour
    rain_3day_mm  the 72 hours before that

Responses are cached on disk, so a map refresh does not re-hit the API once per
segment, and `ml/` still works with the network unplugged.

Attribution: Open-Meteo (https://open-meteo.com), CC-BY 4.0. Weather data by
Open-Meteo.com, derived from national weather-service models.
"""

from __future__ import annotations

import json
import logging
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

log = logging.getLogger(__name__)

API_URL = "https://api.open-meteo.com/v1/forecast"
CACHE_DIR = Path(__file__).parent / ".cache"
CACHE_TTL_SECONDS = 3600.0        # hourly data; refetching sooner buys nothing
REQUEST_TIMEOUT = 20.0
MAX_POINTS_PER_CALL = 100         # Open-Meteo accepts comma-separated coordinates


def _ssl_context() -> ssl.SSLContext | None:
    """A context with a usable CA bundle.

    A framework Python on macOS often ships without one wired up, so urllib
    fails to verify certificates that curl accepts happily. certifi carries the
    bundle; if it is missing we fall back to the system default rather than
    disabling verification, which would be a worse answer than no rainfall.
    """
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        log.debug("certifi not installed - using the default SSL context")
        return None


_SSL = _ssl_context()

# Coordinates are snapped before caching so two segments a few hundred metres
# apart share one API call. ~0.05 deg is about 5 km, well inside a weather cell.
GRID = 0.05


def _snap(value: float) -> float:
    return round(round(float(value) / GRID) * GRID, 4)


def _cache_path(lat: float, lon: float) -> Path:
    return CACHE_DIR / f"rain_{_snap(lat):+.4f}_{_snap(lon):+.4f}.json"


def _read_cache(lat: float, lon: float, ttl: float) -> dict[str, Any] | None:
    path = _cache_path(lat, lon)
    try:
        if time.time() - path.stat().st_mtime > ttl:
            return None
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def _write_cache(lat: float, lon: float, payload: Mapping[str, Any]) -> None:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _cache_path(lat, lon).write_text(json.dumps(payload))
    except OSError:
        log.debug("could not write weather cache", exc_info=True)


def _summarise(hourly: Mapping[str, Any], now: datetime | None = None) -> dict[str, float]:
    """Turn an hourly precipitation series into the two features the model wants.

    The series runs from `past_days` ago into the forecast, so we locate the
    present in it rather than assuming a position -- the API pads to whole days
    and the offset shifts through the day.
    """
    times = hourly.get("time") or []
    values = [0.0 if v is None else float(v) for v in (hourly.get("precipitation") or [])]
    if not times or not values:
        return {}

    now = now or datetime.now(timezone.utc)
    stamps = []
    for stamp in times:
        try:
            parsed = datetime.fromisoformat(stamp)
        except ValueError:
            return {}
        stamps.append(parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc))

    # Index of the last hour that has fully elapsed.
    last = -1
    for index, stamp in enumerate(stamps):
        if stamp <= now:
            last = index
        else:
            break
    if last < 0:
        return {}

    window = values[max(0, last - 71): last + 1]
    return {
        "rain_now_mm": round(values[last], 3),
        "rain_3day_mm": round(sum(window), 2),
        "hours_used": len(window),
        "observed_at": stamps[last].isoformat(),
    }


def _fetch_batch(points: Sequence[tuple[float, float]]) -> list[dict[str, Any]]:
    """One API call for many coordinates. Returns [] on any network failure."""
    query = urllib.parse.urlencode({
        "latitude": ",".join(f"{lat:.4f}" for lat, _ in points),
        "longitude": ",".join(f"{lon:.4f}" for _, lon in points),
        "hourly": "precipitation",
        "past_days": 4,
        "forecast_days": 1,
        "timezone": "UTC",
    })
    request = urllib.request.Request(f"{API_URL}?{query}",
                                     headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT,
                                    context=_SSL) as response:
            payload = json.loads(response.read())
    except (urllib.error.URLError, OSError, ValueError) as exc:
        log.warning("Open-Meteo unavailable (%s) - falling back to supplied rainfall", exc)
        return []
    # A single coordinate comes back as an object, several as a list.
    return payload if isinstance(payload, list) else [payload]


def rainfall(points: Iterable[tuple[float, float]],
             ttl: float = CACHE_TTL_SECONDS,
             use_cache: bool = True) -> dict[tuple[float, float], dict[str, Any]]:
    """Real rainfall for each (lat, lon), keyed by the ORIGINAL coordinates.

    Missing entries mean the API could not be reached and the caller should fall
    back to whatever the backend supplied -- never a silent zero, which would
    read as "no rain" and quietly make every road look safe.
    """
    wanted = list(points)
    out: dict[tuple[float, float], dict[str, Any]] = {}
    pending: dict[tuple[float, float], list[tuple[float, float]]] = {}

    for lat, lon in wanted:
        key = (_snap(lat), _snap(lon))
        cached = _read_cache(lat, lon, ttl) if use_cache else None
        if cached:
            out[(lat, lon)] = cached
        else:
            pending.setdefault(key, []).append((lat, lon))

    keys = list(pending)
    for start in range(0, len(keys), MAX_POINTS_PER_CALL):
        chunk = keys[start:start + MAX_POINTS_PER_CALL]
        for key, result in zip(chunk, _fetch_batch(chunk)):
            summary = _summarise(result.get("hourly") or {})
            if not summary:
                continue
            summary["source"] = "open-meteo"
            summary["grid_lat"] = result.get("latitude")
            summary["grid_lon"] = result.get("longitude")
            _write_cache(*key, summary)
            for original in pending[key]:
                out[original] = summary
    return out


def rainfall_at(lat: float, lon: float, **kwargs) -> dict[str, Any]:
    """Rainfall for one point. `{}` if the API could not be reached."""
    return rainfall([(lat, lon)], **kwargs).get((lat, lon), {})


def segment_midpoint(segment: Mapping[str, Any]) -> tuple[float, float] | None:
    """(lat, lon) at the middle vertex of a segment's LineString."""
    coordinates = (segment.get("geometry") or {}).get("coordinates") or []
    if not coordinates:
        lat, lon = segment.get("lat"), segment.get("lng")
        return (float(lat), float(lon)) if lat is not None and lon is not None else None
    lon, lat = coordinates[len(coordinates) // 2][:2]
    return (float(lat), float(lon))


def segment_rainfall(segments: Sequence[Mapping[str, Any]],
                     **kwargs) -> dict[str, dict[str, Any]]:
    """Real rainfall per segment id, sampled at each segment's midpoint.

    One batched call for the whole network. Segments whose rainfall could not be
    fetched are simply absent, so the caller keeps its existing value.
    """
    midpoints: dict[str, tuple[float, float]] = {}
    for segment in segments:
        point = segment_midpoint(segment)
        if point:
            midpoints[str(segment.get("id"))] = point

    if not midpoints:
        return {}
    readings = rainfall(midpoints.values(), **kwargs)
    return {sid: readings[point] for sid, point in midpoints.items() if point in readings}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    places = [("Rangpo, Sikkim", 27.1935, 88.5142),
              ("Guwahati, Assam", 26.1445, 91.7362),
              ("Ziro, Arunachal", 27.5400, 93.8300),
              ("Aizawl, Mizoram", 23.7271, 92.7176),
              ("Imphal, Manipur", 24.8170, 93.9368)]

    readings = rainfall([(lat, lon) for _, lat, lon in places])
    print(f"{'place':<22} {'last hour':>10} {'72 hours':>10}   observed at")
    for name, lat, lon in places:
        r = readings.get((lat, lon))
        if not r:
            print(f"{name:<22} {'-':>10} {'-':>10}   (unavailable)")
            continue
        print(f"{name:<22} {r['rain_now_mm']:>8.2f}mm {r['rain_3day_mm']:>8.1f}mm   "
              f"{r['observed_at']}")
    print("\nWeather data by Open-Meteo.com (CC-BY 4.0)")
