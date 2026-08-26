"""Why did this segment score high? SHAP attributions for the risk model.

    from ml.explain import explain, explain_text, global_importance

    explain(features)        # -> ranked per-feature contributions, log-odds
    explain_text(features)   # -> "driven by 310 mm of rain over 72h on a 31 deg slope"
    global_importance()      # -> which features matter across the whole model

This is the module behind the dashboard's "why is this road red" panel, and it
is the part that buys government trust: a number nobody can interrogate does not
get to close a highway.

Reading the numbers
-------------------
Contributions are in **log-odds**, the units the model actually adds up. A
contribution of +2.8 on `rain_3day_mm` means that rainfall reading pushed the
odds of disruption up by e^2.8, roughly 16x, relative to a segment with average
features. They sum, with the base value, to the model's raw output -- so the
explanation is exact, not an approximation of a different model.

Everything degrades rather than raises: with no `risk_model.pkl` you get the
heuristic's own terms instead of SHAP values, clearly labelled as such.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Mapping, Sequence

from features import BOUNDS, FEATURES, to_matrix, to_row

log = logging.getLogger(__name__)

METRICS_PATH = Path(__file__).parent / "metrics.json"

# How to say each feature in a sentence a district officer would use.
PHRASES: dict[str, str] = {
    "rain_now_mm": "{value:.0f} mm of rain in the last hour",
    "rain_3day_mm": "{value:.0f} mm of rain over 72h",
    "slope_deg": "a {value:.0f} degree slope",
    "elevation_m": "{value:.0f} m elevation",
    "incident_density": "{value:.1f} past failures per km",
    "road_class": "road class {value:.0f}",
    "report_signal": "a confirmed driver report",
}


def _model():
    """The loaded bundle, or None. Shares risk.py's cache -- one load, not two."""
    import risk
    return risk._load()


def explain(features: Mapping[str, Any], top_n: int = 3) -> list[dict[str, Any]]:
    """Top contributors to one segment's risk, most influential first.

    Each entry is {"feature", "value", "contribution", "direction"}, with
    `contribution` in log-odds. `direction` is "increases" or "reduces" -- a
    feature can and often does argue *against* risk, and hiding that would make
    the panel look like a prosecution rather than an explanation.
    """
    bundle = _model()
    row = to_row(features)

    if bundle is None:
        import risk
        return [{"feature": "heuristic", "value": None,
                 "contribution": risk._heuristic(features),
                 "direction": "increases",
                 "note": "risk_model.pkl unavailable; heuristic fallback in use"}]

    import xgboost as xgb
    dmatrix = xgb.DMatrix([row], feature_names=FEATURES)
    # pred_contribs gives exact SHAP values for trees, plus a trailing bias term.
    contribs = bundle["model"].get_booster().predict(dmatrix, pred_contribs=True)[0]

    ranked = sorted(zip(FEATURES, row, contribs[:-1]),
                    key=lambda item: -abs(item[2]))[:top_n]
    return [{"feature": name,
             "value": value,
             "contribution": round(float(contribution), 4),
             "direction": "increases" if contribution > 0 else "reduces"}
            for name, value, contribution in ranked]


def explain_batch(rows: Sequence[Mapping[str, Any]],
                  top_n: int = 3) -> list[list[dict[str, Any]]]:
    """One model call for a whole map refresh, instead of one per segment."""
    if not rows:
        return []
    bundle = _model()
    if bundle is None:
        return [explain(row, top_n) for row in rows]

    import xgboost as xgb
    matrix = to_matrix(rows)
    dmatrix = xgb.DMatrix(matrix, feature_names=FEATURES)
    contribs = bundle["model"].get_booster().predict(dmatrix, pred_contribs=True)

    out = []
    for row_values, row_contribs in zip(matrix, contribs):
        ranked = sorted(zip(FEATURES, row_values, row_contribs[:-1]),
                        key=lambda item: -abs(item[2]))[:top_n]
        out.append([{"feature": name, "value": value,
                     "contribution": round(float(c), 4),
                     "direction": "increases" if c > 0 else "reduces"}
                    for name, value, c in ranked])
    return out


def base_value() -> float | None:
    """The model's average output in log-odds -- what SHAP values are relative to."""
    bundle = _model()
    if bundle is None:
        return None
    import xgboost as xgb
    dmatrix = xgb.DMatrix([to_row({})], feature_names=FEATURES)
    return round(float(
        bundle["model"].get_booster().predict(dmatrix, pred_contribs=True)[0][-1]
    ), 4)


def explain_text(features: Mapping[str, Any], top_n: int = 2) -> str:
    """One plain sentence for the driver app and the alert body.

    The dashboard can afford a table of log-odds; a driver on NH-10 in the rain
    cannot. This is the same explanation, said out loud.
    """
    drivers = [item for item in explain(features, top_n=top_n)
               if item["direction"] == "increases"]
    if not drivers:
        return "no single factor stands out; risk is broadly low"
    if drivers[0]["feature"] == "heuristic":
        return "estimated without the trained model (heuristic fallback)"

    parts = [PHRASES.get(item["feature"], item["feature"]).format(value=item["value"])
             for item in drivers]
    if len(parts) == 1:
        return f"driven by {parts[0]}"
    return f"driven by {parts[0]} and {parts[1]}"


def global_importance() -> dict[str, float]:
    """Mean |SHAP| across the training set: what the model relies on overall.

    Written by train_risk.py, so this is the trained model's own answer rather
    than a re-derivation. Empty if the model has not been trained yet.
    """
    try:
        return json.loads(METRICS_PATH.read_text()).get("mean_abs_shap", {})
    except (OSError, ValueError):
        log.warning("%s unreadable - no global importances", METRICS_PATH.name)
        return {}


def counterfactual(features: Mapping[str, Any], feature: str,
                   value: float) -> dict[str, Any]:
    """What would the risk be if one feature changed? "If the rain stopped..."

    Used by the control room to sanity-check a score, and to answer the question
    that always follows a red road: how much of this is the weather?
    """
    if feature not in FEATURES:
        raise ValueError(f"unknown feature {feature!r}; expected one of {FEATURES}")
    import risk

    lo, hi = BOUNDS[feature]
    clamped = max(lo, min(hi, float(value)))
    before = risk.score_segment(features)
    after = risk.score_segment({**features, feature: clamped})
    return {"feature": feature,
            "from": features.get(feature),
            "to": clamped,
            "risk_before": before,
            "risk_after": after,
            "delta": round(after - before, 4)}


if __name__ == "__main__":
    wet = {"rain_now_mm": 18, "rain_3day_mm": 310, "slope_deg": 31,
           "elevation_m": 460, "incident_density": 4.1, "road_class": 3}

    import risk
    print(f"NH-10 Rangpo-Singtam  risk={risk.score_segment(wet)}")
    print(f"  {explain_text(wet)}\n")
    print(f"  base value (log-odds): {base_value()}")
    for item in explain(wet, top_n=len(FEATURES)):
        print(f"  {item['direction']:<9} {item['feature']:<18} "
              f"value={item['value']:<8} shap={item['contribution']:+.4f}")

    print("\n  if the rain stopped:")
    what_if = counterfactual(wet, "rain_3day_mm", 10)
    print(f"    risk {what_if['risk_before']} -> {what_if['risk_after']} "
          f"({what_if['delta']:+.4f})")

    print("\n  global importance (mean |SHAP| over training set):")
    for name, value in global_importance().items():
        print(f"    {name:<18} {value}")
