"""Disruption risk for a road segment.

Person 1 imports this:

    from ml.risk import score_segment, explain, risk_band

    p = score_segment({"rain_3day_mm": 310, "slope_deg": 31, "incident_density": 4.1})
    # -> 0.87

Contract: `score_segment` returns a float in [0, 1] for ANY input dict. Missing
features fall back to fair-weather defaults, out-of-range values are clamped,
and if risk_model.pkl is absent or unreadable it drops to a transparent
heuristic instead of raising. The API must never 500 because of this module.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any, Mapping, Sequence

from features import DEFAULTS, FEATURES, to_matrix, to_row

log = logging.getLogger(__name__)

MODEL_PATH = Path(__file__).parent / "risk_model.pkl"

_lock = threading.Lock()
_bundle: dict[str, Any] | None = None
_load_failed = False

# Bands the dashboard colours by. Thresholds are a product decision, not a model
# output - keep them here so there is one definition of "red".
BANDS = ((0.65, "high"), (0.35, "medium"), (0.0, "low"))


def _load() -> dict[str, Any] | None:
    """Load the model once, lazily. Returns None if unavailable."""
    global _bundle, _load_failed
    if _bundle is not None or _load_failed:
        return _bundle
    with _lock:
        if _bundle is None and not _load_failed:
            try:
                import joblib
                bundle = joblib.load(MODEL_PATH)
                trained_on = bundle.get("features")
                if trained_on != FEATURES:
                    raise ValueError(
                        f"feature mismatch: model trained on {trained_on}, "
                        f"features.py defines {FEATURES}. Retrain with train_risk.py.")
                trained_with = bundle.get("xgboost_version")
                if trained_with:
                    import xgboost as _xgb
                    if _xgb.__version__ != trained_with:
                        # Not cosmetic: the same pickle scored 0.9709 on 3.4.1 and
                        # 0.9938 on 2.1.3, which is enough to change which road a
                        # truck is sent down. Pin both sides to the same version.
                        log.warning(
                            "risk_model.pkl was trained with xgboost %s but this "
                            "process has %s - predictions WILL differ. Pin both to "
                            "the same version, or retrain with train_risk.py.",
                            trained_with, _xgb.__version__)
                _bundle = bundle
                log.info("loaded risk model %s trained %s (xgboost %s)",
                         bundle.get("model_version"), bundle.get("trained_at"),
                         trained_with or "unrecorded")
            except FileNotFoundError:
                _load_failed = True
                log.warning("%s not found - falling back to heuristic risk. "
                            "Run `python train_risk.py` in ml/ to build it.", MODEL_PATH.name)
            except Exception:
                _load_failed = True
                log.exception("could not load %s - falling back to heuristic risk",
                              MODEL_PATH.name)
    return _bundle


def _heuristic(features: Mapping[str, float]) -> float:
    """Model-free fallback: saturation x steepness, the dominant real mechanism.

    Deliberately crude and readable. It exists so a missing artifact degrades
    the answer instead of taking the service down.
    """
    f = {name: features.get(name, DEFAULTS[name]) for name in FEATURES}
    saturation = min(f["rain_3day_mm"] / 300.0, 1.5)
    steepness = min(f["slope_deg"] / 30.0, 1.5)
    score = (0.45 * saturation * steepness
             + 0.15 * saturation
             + 0.10 * steepness
             + 0.07 * min(f["incident_density"] / 4.0, 1.0)
             + 0.15 * f["report_signal"]
             - 0.04 * f["road_class"])
    return round(max(0.0, min(1.0, score)), 4)


def score_segment(features: Mapping[str, Any]) -> float:
    """Probability (0..1) that this segment is disrupted in the next 48 hours."""
    bundle = _load()
    if bundle is None:
        return _heuristic(features)
    row = to_row(features)
    proba = bundle["model"].predict_proba([row])[0][1]
    return round(float(proba), 4)


def score_segments(rows: Sequence[Mapping[str, Any]]) -> list[float]:
    """Batch version - one model call for the whole map refresh."""
    if not rows:
        return []
    bundle = _load()
    if bundle is None:
        return [_heuristic(r) for r in rows]
    proba = bundle["model"].predict_proba(to_matrix(rows))[:, 1]
    return [round(float(p), 4) for p in proba]


def risk_band(risk: float) -> str:
    """'low' | 'medium' | 'high' - what the map colours by."""
    for threshold, name in BANDS:
        if risk >= threshold:
            return name
    return "low"


def explain(features: Mapping[str, Any], top_n: int = 3) -> list[dict[str, Any]]:
    """Per-segment SHAP attribution: why is this road red?

    Kept here because Person 1 already imports `risk.explain`. The implementation
    lives in explain.py -- imported lazily, since explain.py imports this module
    for the model cache and heuristic fallback.
    """
    from explain import explain as _explain
    return _explain(features, top_n=top_n)


def model_info() -> dict[str, Any]:
    """What the API can expose at /health so the team can see which model is live."""
    bundle = _load()
    if bundle is None:
        return {"loaded": False, "mode": "heuristic", "features": FEATURES}
    return {"loaded": True, "mode": "xgboost",
            "model_version": bundle.get("model_version"),
            "trained_at": bundle.get("trained_at"),
            "metrics": bundle.get("metrics"),
            "features": FEATURES}


if __name__ == "__main__":
    demo = {"rain_now_mm": 18, "rain_3day_mm": 310, "slope_deg": 31,
            "elevation_m": 460, "incident_density": 4.1, "road_class": 3}
    risk = score_segment(demo)
    print(f"NH-10 Rangpo-Singtam, 310mm/72h on a 31 deg slope")
    print(f"  risk  {risk}  ({risk_band(risk)})")
    for item in explain(demo):
        print(f"  {item['direction']:<9} {item['feature']:<18} "
              f"value={item['value']:<8} shap={item['contribution']}")
    print(f"\n  model: {model_info()['mode']}")
