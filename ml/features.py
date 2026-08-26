"""Feature schema for the disruption-risk model.

This module is the single definition of what the model eats and in what order.
`risk.py`, `train_risk.py` and the notebook all import from here so the training
matrix and the inference call can never drift apart.

Feature set follows the risk-model schema in the project study: the domain edge
is 3-day cumulative rainfall as a soil-saturation proxy, not just current rain.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

# Order matters. XGBoost is fed a positional matrix; this list defines it.
FEATURES: list[str] = [
    "rain_now_mm",       # rainfall in the last hour (mm)
    "rain_3day_mm",      # cumulative 72h rainfall (mm) - soil saturation proxy
    "slope_deg",         # mean gradient of the segment (degrees, from DEM)
    "elevation_m",       # mean elevation (m)
    "incident_density",  # past landslides/floods per km (GSI Bhukosh)
    "road_class",        # 0 unpaved .. 1 rural .. 2 state highway .. 3 national highway
    "report_signal",     # 0..1 live driver-report confirmation of trouble
]

# Neutral fair-weather values, used when a caller omits a feature.
DEFAULTS: dict[str, float] = {
    "rain_now_mm": 0.0,
    "rain_3day_mm": 0.0,
    "slope_deg": 12.0,
    "elevation_m": 800.0,
    "incident_density": 0.3,
    "road_class": 3.0,
    "report_signal": 0.0,
}

# Sanity bounds. Values outside these are clamped rather than rejected, so a bad
# weather feed degrades the score instead of crashing Person 1's API.
BOUNDS: dict[str, tuple[float, float]] = {
    "rain_now_mm": (0.0, 120.0),
    "rain_3day_mm": (0.0, 900.0),
    "slope_deg": (0.0, 60.0),
    "elevation_m": (0.0, 5000.0),
    "incident_density": (0.0, 10.0),
    "road_class": (0.0, 3.0),
    "report_signal": (0.0, 1.0),
}

ROAD_CLASS = {"unpaved": 0, "rural": 1, "state_highway": 2, "national_highway": 3}

# ---------------------------------------------------------------------------
# Placeholder terrain table.
#
# Slope, elevation and incident density really come from SRTM/Bhoonidhi (DEM)
# and GSI Bhukosh, joined in PostGIS. Person 1's database does not exist yet,
# so these are hand-set values for the mock segments, chosen to match the real
# character of each corridor. Delete this table once /segments serves the real
# terrain columns - nothing else in this folder depends on it.
# ---------------------------------------------------------------------------
TERRAIN: dict[str, dict[str, float]] = {
    "SEG-SK-NH10-001": {"slope_deg": 31.0, "elevation_m": 460.0,  "incident_density": 4.1, "road_class": 3},
    "SEG-SK-NH10-002": {"slope_deg": 22.0, "elevation_m": 980.0,  "incident_density": 1.7, "road_class": 3},
    "SEG-AS-NH27-014": {"slope_deg": 2.0,  "elevation_m": 55.0,   "incident_density": 0.2, "road_class": 3},
    "SEG-AS-NH715-007": {"slope_deg": 6.0, "elevation_m": 78.0,   "incident_density": 2.4, "road_class": 2},
}


def coerce(name: str, value: Any) -> float:
    """Turn a contract value into the number the model expects.

    `/segments` carries `road_class` as a string ("national_highway"), and
    `surface` likewise, because that is what the shared contract agreed. The
    model is fed a positional float matrix. Coercing here means Person 1 can pass
    a raw `/segments` row to any function in this folder without translating it
    first -- which is exactly what the README tells them to do.
    """
    if isinstance(value, str):
        text = value.strip().lower()
        if name == "road_class":
            if text not in ROAD_CLASS:
                raise ValueError(
                    f"unknown road_class {value!r}; expected one of "
                    f"{sorted(ROAD_CLASS)} or a number 0-3")
            return float(ROAD_CLASS[text])
        return float(text)
    return float(value)


def clamp(name: str, value: Any) -> float:
    lo, hi = BOUNDS[name]
    return max(lo, min(hi, coerce(name, value)))


def to_row(features: Mapping[str, Any]) -> list[float]:
    """Turn a feature mapping into a positional row in FEATURES order."""
    unknown = set(features) - set(FEATURES)
    if unknown:
        raise ValueError(f"unknown feature(s): {sorted(unknown)}; expected {FEATURES}")
    return [clamp(name, features.get(name, DEFAULTS[name])) for name in FEATURES]


def to_matrix(rows: Sequence[Mapping[str, Any]]) -> list[list[float]]:
    return [to_row(r) for r in rows]


def segment_features(segment: Mapping[str, Any], weather: Mapping[str, Any] | None = None,
                     report_signal: float = 0.0) -> dict[str, float]:
    """Build a feature dict for a segment from `/segments` plus a weather reading.

    Terrain comes from the segment itself when the backend supplies it, and from
    the TERRAIN placeholder table otherwise.
    """
    weather = weather or {}
    terrain = TERRAIN.get(str(segment.get("id")), {})

    def pick(name: str) -> float:
        for source in (segment, terrain):
            if name in source and source[name] is not None:
                return coerce(name, source[name])
        return DEFAULTS[name]

    return {
        "rain_now_mm": float(weather.get("rain_now_mm", DEFAULTS["rain_now_mm"])),
        "rain_3day_mm": float(weather.get("rain_3day_mm", DEFAULTS["rain_3day_mm"])),
        "slope_deg": pick("slope_deg"),
        "elevation_m": pick("elevation_m"),
        "incident_density": pick("incident_density"),
        "road_class": pick("road_class"),
        "report_signal": float(report_signal),
    }
