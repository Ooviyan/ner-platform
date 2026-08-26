"""Accessibility score (0-100) for a road segment.

    from ml.score import accessibility, breakdown

    accessibility(segment)              # -> 34
    breakdown(segment)                  # -> every term, so the UI can show its work

This is the single number the whole product hangs off: the map colours by it,
the router costs by it, and the emergency-access view filters by it.

It is a DECISION-SUPPORT metric we define, not an official government standard.
Say that out loud in the pitch - judges ask. The weights below are the entire
definition, deliberately in one editable place.
"""

from __future__ import annotations

from typing import Any, Mapping

from features import segment_features
from risk import score_segment

# How much each factor can pull the score down, out of 100.
#
# These are the entire definition of the score. They are module-level so they can
# be read and audited in one place, and `accessibility(..., weights=...)` takes an
# override so a caller can re-weight per vehicle class -- an ambulance cares more
# about surface than a loaded truck does -- without mutating global state.
WEIGHTS: dict[str, float] = {
    "disruption_risk": 45.0,   # predicted 48h failure probability
    "terrain":         15.0,   # steepness the vehicle has to negotiate
    "history":         15.0,   # how often this segment has failed before
    "surface":         25.0,   # road class / condition
}


def resolve_weights(weights: Mapping[str, float] | None = None) -> dict[str, float]:
    """Merge an override over the defaults, rejecting unknown keys.

    A typo in a weight name would otherwise silently score every road in the
    region wrong, which is exactly the kind of bug nobody notices in a demo.
    """
    if not weights:
        return dict(WEIGHTS)
    unknown = set(weights) - set(WEIGHTS)
    if unknown:
        raise ValueError(
            f"unknown weight(s): {sorted(unknown)}; expected {sorted(WEIGHTS)}")
    merged = dict(WEIGHTS)
    merged.update({k: float(v) for k, v in weights.items()})
    return merged

# Status is not a penalty, it is a ceiling. A closed road is not "somewhat
# accessible" no matter how good its slope and surface are.
STATUS_CEILING: dict[str, float] = {
    "open": 100.0,
    "restricted": 40.0,   # one lane, convoy, daylight-only
    "closed": 0.0,
    "unknown": 70.0,
}

BANDS = ((70.0, "green"), (40.0, "amber"), (0.0, "red"))


def _terrain_penalty(slope_deg: float) -> float:
    """0 at flat, full penalty by 35 degrees."""
    return min(max(slope_deg, 0.0) / 35.0, 1.0)


def _history_penalty(incident_density: float) -> float:
    """0 with a clean record, full penalty at 4+ past incidents per km."""
    return min(max(incident_density, 0.0) / 4.0, 1.0)


def _surface_penalty(road_class: float) -> float:
    """National highway 0, unpaved track 1."""
    return 1.0 - min(max(road_class, 0.0), 3.0) / 3.0


def breakdown(segment: Mapping[str, Any], weather: Mapping[str, Any] | None = None,
              risk: float | None = None, report_signal: float = 0.0,
              weights: Mapping[str, float] | None = None) -> dict[str, Any]:
    """Full working for one segment: every deduction and the ceiling applied."""
    features = segment_features(segment, weather, report_signal)
    if risk is None:
        risk = score_segment(features)

    w = resolve_weights(weights)
    penalties = {
        "disruption_risk": w["disruption_risk"] * risk,
        "terrain": w["terrain"] * _terrain_penalty(features["slope_deg"]),
        "history": w["history"] * _history_penalty(features["incident_density"]),
        "surface": w["surface"] * _surface_penalty(features["road_class"]),
    }
    raw = 100.0 - sum(penalties.values())

    status = str(segment.get("status", "unknown")).lower()
    ceiling = STATUS_CEILING.get(status, STATUS_CEILING["unknown"])
    final = max(0.0, min(raw, ceiling))

    return {
        "segment_id": segment.get("id"),
        "accessibility": int(round(final)),
        "band": band(final),
        "risk": round(float(risk), 4),
        "status": status,
        "ceiling_applied": raw > ceiling,
        "raw_score": round(raw, 2),
        "penalties": {k: round(v, 2) for k, v in penalties.items()},
        "weights": w,
        "features": features,
    }


def accessibility(segment: Mapping[str, Any], weather: Mapping[str, Any] | None = None,
                  risk: float | None = None, report_signal: float = 0.0,
                  weights: Mapping[str, float] | None = None) -> int:
    """Road usability, 0 (impassable) to 100 (fully usable).

    `weights` re-weights the penalties for this call only; see resolve_weights.
    """
    return breakdown(segment, weather, risk, report_signal, weights)["accessibility"]


def band(score: float) -> str:
    """'green' | 'amber' | 'red' - the district connectivity colours."""
    for threshold, name in BANDS:
        if score >= threshold:
            return name
    return "red"


if __name__ == "__main__":
    import json
    from pathlib import Path

    mock = Path(__file__).resolve().parents[1] / "mock-data" / "segments.json"
    segments = json.loads(mock.read_text())
    monsoon = {"rain_now_mm": 18.0, "rain_3day_mm": 310.0}

    print(f"{'segment':<20} {'status':<11} {'risk':>6} {'score':>6}  band")
    for segment in segments:
        result = breakdown(segment, monsoon)
        print(f"{result['segment_id']:<20} {result['status']:<11} "
              f"{result['risk']:>6} {result['accessibility']:>6}  {result['band']}")
    print("\nworked example -", segments[0]["id"])
    print(json.dumps(breakdown(segments[0], monsoon)["penalties"], indent=2))
