"""Bridge between this folder and the rest of the platform.

Everything else in `ml/` is pure: dicts in, numbers out, no network. This module
is the one place that knows where the data actually comes from -- Person 1's
FastAPI backend, the driver app's reports, or the shared `../mock-data` fixtures
when neither is running.

    from ml.connect import load_platform, enrich_segments, live_graph

    data = load_platform("http://localhost:8000")   # or None for mock-data
    scored = enrich_segments(data.segments, data.weather, data.reports)
    graph = live_graph(data.segments, data.weather, data.reports)

Two translations happen here, and both matter.

**Backend -> model features.** `/segments` speaks the shared contract
(`rainfall_mm_24h`, `road_class: "national_highway"`, `status: "restricted"`);
`features.py` speaks the model's schema (`rain_now_mm`, `road_class: 3`). Neither
side should have to know about the other, so the mapping lives here.

Two of those features now come from real sources rather than the backend's
stored values: `weather.py` fetches genuine hourly rainfall from Open-Meteo, and
`inventory.py` derives `incident_density` from NASA's Global Landslide Catalog.
Pass `live=False` to use only what the backend supplied.

**Driver reports -> `report_signal`.** This is the loop that makes the product
work: a driver files "landslide" on NH-10, that segment's `report_signal` goes
up, its risk goes up, the router sends the next truck the long way round. The
model already has the feature -- this module is what feeds it.
"""

from __future__ import annotations

import json
import logging
import math
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import inventory
import weather as weather_module
from features import ROAD_CLASS, segment_features
from risk import risk_band, score_segments
from score import breakdown

log = logging.getLogger(__name__)

HERE = Path(__file__).parent
MOCK_DIR = HERE.parent / "mock-data"
DEFAULT_BACKEND = "http://localhost:8000"

# A driver report is strong evidence right after it lands and fades as the road
# is cleared. 6h half-life: still meaningful next shift, gone by tomorrow.
REPORT_HALF_LIFE_HOURS = 6.0

# How much each report category argues that the road is actually disrupted.
# A blocked road seen by a driver is near-certain; heavy rain is a warning.
REPORT_WEIGHT: dict[str, float] = {
    "landslide": 1.0,
    "traffic_block": 0.9,
    "blocked_road": 0.9,
    "bridge_damage": 1.0,
    "flooding": 0.8,
    "flood": 0.8,
    "road_damage": 0.6,
    "accident": 0.5,
    "heavy_rain": 0.35,
    "snow": 0.6,
    "sos": 0.7,
    "other": 0.3,
}

SEVERITY_MULTIPLIER: dict[str, float] = {
    "critical": 1.0, "high": 0.85, "medium": 0.6, "low": 0.35,
}

# Reports the control room rejected carry no signal at all.
IGNORED_REPORT_STATUS = {"rejected"}


@dataclass
class Platform:
    """One consistent snapshot of what the platform currently knows."""

    segments: list[dict[str, Any]] = field(default_factory=list)
    reports: list[dict[str, Any]] = field(default_factory=list)
    routes: list[dict[str, Any]] = field(default_factory=list)
    weather: dict[str, float] = field(default_factory=dict)
    source: str = "mock-data"

    def __repr__(self) -> str:  # keeps the demo output readable
        return (f"Platform(source={self.source!r}, segments={len(self.segments)}, "
                f"reports={len(self.reports)}, routes={len(self.routes)})")


# --------------------------------------------------------------- loading ----
def _get(url: str, timeout: float = 5.0) -> Any:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read())


def _read_mock(name: str) -> list[dict[str, Any]]:
    path = MOCK_DIR / name
    if not path.exists():
        log.warning("%s not found", path)
        return []
    data = json.loads(path.read_text())
    return data if isinstance(data, list) else [data]


def load_platform(base_url: str | None = DEFAULT_BACKEND,
                  weather: Mapping[str, float] | None = None) -> Platform:
    """Fetch segments, reports and routes -- from the API, or mock-data if it is down.

    Passing `base_url=None` forces mock-data. Otherwise a backend that is not
    running is not an error: this folder is supposed to work standalone, so we
    log it and fall back.
    """
    if base_url:
        try:
            segments = _get(f"{base_url}/segments?limit=10000")
            reports = _get(f"{base_url}/reports?limit=1000")
            routes = _get(f"{base_url}/routes")
            log.info("loaded %d segments from %s", len(segments), base_url)
            return Platform(segments=segments, reports=reports, routes=routes,
                            weather=dict(weather or {}), source=base_url)
        except (urllib.error.URLError, OSError, ValueError) as exc:
            log.warning("backend at %s unavailable (%s) - using ../mock-data",
                        base_url, exc)

    return Platform(segments=_read_mock("segments.json"),
                    reports=_read_mock("reports.json"),
                    routes=_read_mock("routes.json"),
                    weather=dict(weather or {}), source="mock-data")


# ------------------------------------------------- contract -> model ----
def _road_class_value(segment: Mapping[str, Any]) -> float | None:
    """`"national_highway"` -> 3. Already-numeric values pass through."""
    raw = segment.get("road_class")
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    return float(ROAD_CLASS.get(str(raw).strip().lower(), 3))


def segment_weather(segment: Mapping[str, Any],
                    fallback: Mapping[str, float] | None = None,
                    observed: Mapping[str, Any] | None = None) -> dict[str, float]:
    """Rainfall for one segment, best source first.

    1. `observed` -- a real hourly reading from `weather.py` (Open-Meteo).
       `rain_now_mm` is the last completed hour and `rain_3day_mm` the 72 hours
       before it, both from the same series the model was trained to expect.
    2. The backend's stored `rainfall_mm_24h` / `rainfall_mm_72h`. The 72h figure
       maps across exactly; there is no hourly figure, so `rain_now_mm` is the
       24h total spread over the day. That underestimates a cloudburst, which is
       precisely the trigger case -- hence preferring a real reading above.
    3. A region-wide `fallback` reading.
    """
    fallback = fallback or {}
    out: dict[str, float] = {}

    if observed:
        if observed.get("rain_3day_mm") is not None:
            out["rain_3day_mm"] = float(observed["rain_3day_mm"])
        if observed.get("rain_now_mm") is not None:
            out["rain_now_mm"] = float(observed["rain_now_mm"])

    if "rain_3day_mm" not in out:
        if segment.get("rainfall_mm_72h") is not None:
            out["rain_3day_mm"] = float(segment["rainfall_mm_72h"])
        elif "rain_3day_mm" in fallback:
            out["rain_3day_mm"] = float(fallback["rain_3day_mm"])

    if "rain_now_mm" not in out:
        if segment.get("rainfall_mm_24h") is not None:
            out["rain_now_mm"] = round(float(segment["rainfall_mm_24h"]) / 24.0, 3)
        elif "rain_now_mm" in fallback:
            out["rain_now_mm"] = float(fallback["rain_now_mm"])

    return out


def to_features(segment: Mapping[str, Any],
                fallback_weather: Mapping[str, float] | None = None,
                report_signal: float = 0.0,
                observed: Mapping[str, Any] | None = None) -> dict[str, float]:
    """A backend `/segments` row as a model feature dict."""
    normalised = dict(segment)
    road_class = _road_class_value(segment)
    if road_class is not None:
        normalised["road_class"] = road_class
    return segment_features(normalised,
                            segment_weather(segment, fallback_weather, observed),
                            report_signal)


# ------------------------------------------- driver reports -> signal ----
def _parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def attach_segments(reports: Iterable[Mapping[str, Any]],
                    segments: Sequence[Mapping[str, Any]],
                    max_km: float = 5.0) -> list[dict[str, Any]]:
    """Give every report a `segment_id`, snapping by coordinates where it lacks one.

    The backend fills `segment_id` in when a report is filed, but the shared
    `mock-data/reports.json` carries only lat/lng -- and a report that is not tied
    to a segment cannot influence any risk score, which would quietly break the
    whole driver-report loop when running standalone. Reports further than
    `max_km` from any segment are left unattached rather than forced onto the
    least-wrong road.
    """
    from routing import haversine_km

    segments = list(segments)
    out = []
    for report in reports:
        row = dict(report)
        if not row.get("segment_id"):
            lat, lng = row.get("lat"), row.get("lng")
            if lat is not None and lng is not None:
                best, best_km = None, float("inf")
                for segment in segments:
                    coords = (segment.get("geometry") or {}).get("coordinates") or []
                    for lon_c, lat_c in coords:
                        # haversine_km takes (lon, lat), GeoJSON order.
                        km = haversine_km((float(lng), float(lat)), (lon_c, lat_c))
                        if km < best_km:
                            best, best_km = segment.get("id"), km
                if best is not None and best_km <= max_km:
                    row["segment_id"] = best
                    row["_snap_km"] = round(best_km, 3)
        out.append(row)
    return out


def report_signals(reports: Iterable[Mapping[str, Any]],
                   now: datetime | None = None,
                   half_life_hours: float = REPORT_HALF_LIFE_HOURS,
                   ) -> dict[str, float]:
    """Per-segment 0..1 confirmation strength from driver reports.

    Weight is `category x severity x exp(-age / half-life)`, and several reports
    on one segment combine as independent evidence -- 1 - prod(1 - w) -- so three
    drivers reporting the same landslide is stronger than one, without any single
    report being able to exceed 1.0.

    A `verified` report keeps its full weight; a `pending` one is discounted,
    because an unreviewed report is exactly the case where a mistake reaches the
    router. `rejected` reports contribute nothing.
    """
    now = now or datetime.now(timezone.utc)
    survival: dict[str, float] = {}

    for report in reports:
        segment_id = report.get("segment_id")
        if not segment_id:
            continue
        status = str(report.get("status", "pending")).lower()
        if status in IGNORED_REPORT_STATUS:
            continue

        weight = REPORT_WEIGHT.get(str(report.get("type", "other")).lower(), 0.3)
        weight *= SEVERITY_MULTIPLIER.get(str(report.get("severity", "medium")).lower(), 0.6)
        if status == "pending":
            weight *= 0.7      # unreviewed: believed, but not fully
        elif status == "resolved":
            weight *= 0.15     # the road was cleared; keep a trace, not a veto

        filed = _parse_time(report.get("timestamp") or report.get("created_at"))
        if filed is not None:
            age_hours = max((now - filed).total_seconds() / 3600.0, 0.0)
            weight *= math.pow(0.5, age_hours / half_life_hours)

        if weight <= 0.0:
            continue
        survival[segment_id] = survival.get(segment_id, 1.0) * (1.0 - min(weight, 1.0))

    return {sid: round(1.0 - s, 4) for sid, s in survival.items()}


def incident_densities(reports: Iterable[Mapping[str, Any]],
                       segments: Sequence[Mapping[str, Any]],
                       use_inventory: bool = True) -> dict[str, float]:
    """Historical failures per km for the `incident_density` feature.

    Prefers `inventory.py` -- NASA's Global Landslide Catalog, a real curated
    record of past landslides with coordinates. Falls back to counting the
    platform's own driver reports where the inventory has nothing, which is
    somewhat circular (the system's own output feeding its own input) but is
    better than a confident zero on a road the catalogue simply never covered.
    """
    if use_inventory:
        from_catalog = inventory.densities(list(segments))
        if from_catalog:
            reported = _report_densities(reports, segments)
            # Catalogue wins; reports only fill segments it never saw.
            return {**reported, **from_catalog}
    return _report_densities(reports, segments)


def _report_densities(reports: Iterable[Mapping[str, Any]],
                      segments: Sequence[Mapping[str, Any]]) -> dict[str, float]:
    """Failures per km counted from the platform's own reports."""
    lengths = {str(s.get("id")): float(s.get("length_km") or 0.0) for s in segments}
    counts: dict[str, int] = {}
    for report in reports:
        segment_id = report.get("segment_id")
        if segment_id and str(report.get("status", "")).lower() not in IGNORED_REPORT_STATUS:
            counts[segment_id] = counts.get(segment_id, 0) + 1

    out: dict[str, float] = {}
    for segment_id, count in counts.items():
        km = lengths.get(segment_id) or 0.0
        if km > 0:
            out[segment_id] = round(min(count / km, 10.0), 3)
    return out


# ------------------------------------------------------------- scoring ----
def enrich_segments(segments: Sequence[Mapping[str, Any]],
                    weather: Mapping[str, float] | None = None,
                    reports: Iterable[Mapping[str, Any]] | None = None,
                    weights: Mapping[str, float] | None = None,
                    explain_top_n: int = 2,
                    live: bool = True) -> list[dict[str, Any]]:
    # `live` controls whether we go to the network for rainfall. The landslide
    # inventory is cached historical fact, not a live feed, so it always applies
    # -- switching it off with live=False would throw away real data for no gain.
    """Score every segment and return them in the shared contract shape.

    The output is a `/segments` row with `risk` and `accessibility` replaced by
    this model's answers, plus `risk_band`, `why` and `ml` for the dashboard's
    explainability panel. Person 1 can serve these rows unchanged -- the contract
    field names are preserved exactly.
    """
    from explain import explain_batch, explain_text

    segments = list(segments)
    if not segments:
        return []

    reports = attach_segments(reports or [], segments)
    signals = report_signals(reports)
    densities = incident_densities(reports, segments)

    # One batched call for the whole network, cached on disk for an hour.
    observed = weather_module.segment_rainfall(segments) if live else {}

    rows = []
    for segment in segments:
        segment_id = str(segment.get("id"))
        enriched = dict(segment)
        # Catalogue-derived history only fills a gap; a real terrain column wins.
        if segment.get("incident_density") is None and segment_id in densities:
            enriched["incident_density"] = densities[segment_id]
        rows.append(to_features(enriched, weather, signals.get(segment_id, 0.0),
                                observed.get(segment_id)))

    risks = score_segments(rows)
    explanations = explain_batch(rows, top_n=explain_top_n)

    out = []
    for segment, features, risk, why in zip(segments, rows, risks, explanations):
        segment_id = str(segment.get("id"))
        detail = breakdown(segment, weather=None, risk=risk,
                           report_signal=features["report_signal"], weights=weights)
        scored = dict(segment)
        scored.update({
            "risk": risk,
            "risk_band": risk_band(risk),
            "accessibility": detail["accessibility"],
            "why": explain_text(features, top_n=explain_top_n),
            "ml": {
                "band": detail["band"],
                "penalties": detail["penalties"],
                "report_signal": features["report_signal"],
                "features": features,
                "shap": why,
                "sources": {
                    "rainfall": ("open-meteo" if segment_id in observed
                                 else "backend" if segment.get("rainfall_mm_72h") is not None
                                 else "default"),
                    "incident_density": ("nasa-glc" if segment_id in densities
                                         else "segment" if segment.get("incident_density")
                                         is not None else "default"),
                },
            },
        })
        out.append(scored)
    return out


def live_graph(segments: Sequence[Mapping[str, Any]],
               weather: Mapping[str, float] | None = None,
               reports: Iterable[Mapping[str, Any]] | None = None,
               live: bool = True,
               **kwargs) -> Any:
    """A routable graph over the platform's current segments and driver reports.

    Thin wrapper over `routing.build_graph` that pre-scores with this module's
    backend translation and report signals, so the router sees the same risks the
    map does.
    """
    from routing import build_graph

    scored = enrich_segments(segments, weather, reports, live=live)
    overrides = {str(s["id"]): float(s["risk"]) for s in scored}
    return build_graph(scored, weather, risk_overrides=overrides, **kwargs)


def apply_report(segments: Sequence[Mapping[str, Any]],
                 report: Mapping[str, Any],
                 weather: Mapping[str, float] | None = None,
                 existing: Iterable[Mapping[str, Any]] | None = None
                 ) -> list[dict[str, Any]]:
    """Re-score after one new driver report lands -- the live loop, in one call.

    This is what Person 1 calls from `POST /reports`: a driver confirms a
    blockage, and the affected segment's risk and accessibility move immediately.
    """
    return enrich_segments(segments, weather, list(existing or []) + [dict(report)])


# ---------------------------------------------------------------- demo ----
def _demo() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    import sys

    base = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_BACKEND
    if base.lower() in {"none", "mock", "mock-data"}:
        base = None

    data = load_platform(base)
    print(f"\n{data}\n")

    scored = enrich_segments(data.segments, data.weather, data.reports)
    print(f"{'segment':<20} {'rain72':>7} {'slides/km':>10} {'risk':>6} "
          f"{'band':>7} {'score':>6}  why")
    for row in sorted(scored, key=lambda r: -r["risk"])[:10]:
        f = row["ml"]["features"]
        print(f"{str(row['id']):<20} {f['rain_3day_mm']:>6.1f}mm "
              f"{f['incident_density']:>10.2f} {row['risk']:>6.3f} "
              f"{row['risk_band']:>7} {row['accessibility']:>6}  {row['why']}")

    used = {}
    for row in scored:
        for field, source in row["ml"]["sources"].items():
            used.setdefault(field, {}).setdefault(source, 0)
            used[field][source] += 1
    print("\ndata provenance across the network:")
    for field, counts in used.items():
        print(f"  {field:<18} " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))

    signals = report_signals(attach_segments(data.reports, data.segments))
    if signals:
        print("\ndriver-report signal by segment (recency-weighted):")
        for segment_id, value in sorted(signals.items(), key=lambda kv: -kv[1]):
            print(f"  {segment_id:<20} {value}")

    graph = live_graph(data.segments, data.weather, data.reports)
    print(f"\nrouting graph: {graph.number_of_nodes()} nodes, "
          f"{graph.number_of_edges()} edges")


if __name__ == "__main__":
    _demo()
