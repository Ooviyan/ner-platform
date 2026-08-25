# ml — Person 2

**Owner:** Person 2. Nobody else edits this folder.

AI risk scoring, the 0–100 accessibility score, and risk-aware routing. Everything
here runs standalone — no backend, no database, no network.

---

## Setup

```bash
brew install libomp                 # REQUIRED on macOS - see note below
python3.12 -m venv venv
source venv/bin/activate            # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

> **macOS / Apple Silicon:** xgboost's wheel links against the OpenMP runtime and
> will fail at *import* with `Library not loaded: @rpath/libomp.dylib` without it.
> `brew install libomp` fixes it; nothing needs configuring afterwards.

Python 3.11+. Built and tested on 3.12.

## Build the model

```bash
python train.py          # generates data if missing, trains, writes risk_model.pkl
python test_ml.py        # 33 self-checks over all three deliverables
python routing.py        # the standalone reroute demo
```

---

## What Person 1 imports

```python
from ml.risk    import score_segment, explain, risk_band, model_info
from ml.score   import accessibility, breakdown
from ml.routing import build_graph, safest_route, alternatives

score_segment({"rain_3day_mm": 185, "slope_deg": 31, "incident_density": 4.1})
# 0.963

accessibility(segment, weather={"rain_3day_mm": 185})
# 28

route = safest_route(build_graph(segments, weather), "RANGPO", "GANGTOK")
# {"id", "origin", "destination", "chosen", "eta_min", "delay_min", "risk",
#  "segments": [...], "advisory": "ok" | "no_safe_route", ...}
```

`safest_route` returns the exact shape of `mock-data/routes.json`, plus a few
extra keys, so `/route` can serve it without reshaping.

**Guarantees these functions make:** `score_segment` returns a float in [0,1] for
any input dict — missing features fall back to fair-weather defaults, out-of-range
values are clamped, and if `risk_model.pkl` is missing it drops to a documented
heuristic rather than raising. The API should never 500 because of this module.
`explain()` returns SHAP attributions for the dashboard's "why is this road red"
panel.

---

## Files

| File | What it is |
| --- | --- |
| `features.py` | The feature schema. One definition of what the model eats, in what order. |
| `make_dataset.py` | Generates the labelled training set. |
| `train.py` | Trains XGBoost → `risk_model.pkl`, `metrics.json`, SHAP importances. |
| `risk.py` | `score_segment()` → 0..1, `explain()`, heuristic fallback. |
| `score.py` | `accessibility()` → 0..100 with a full penalty breakdown. |
| `routing.py` | A\* over networkx, risk priced as expected delay. |
| `data/corridor_nh10.geojson` | Test fixture — ML-local, *not* part of the shared contract. |
| `test_ml.py` | Self-checks. `python test_ml.py`, no pytest needed. |

---

## Two things to be honest about

**1. The training data is synthetic.** Real labels need the GSI Bhukosh landslide
inventory joined to IMD/Open-Meteo rainfall history per segment-day — that join is
Person 1's PostGIS work and does not exist yet. `make_dataset.py` samples from a
documented generative process built on published NER monsoon behaviour, so the
*shape* of the relationship is real even though the rows are simulated.

Current metrics (ROC-AUC 0.894, PR-AUC 0.721, Brier 0.083) measure how well the
model recovers that process. **They are not field-validated accuracy and must not
be presented as such.** Swapping in real data changes only `make_dataset.py` —
`features.FEATURES` stays fixed, so nothing downstream moves.

**2. Terrain is a placeholder.** Slope, elevation and incident density belong in
PostGIS from SRTM/Bhoonidhi and Bhukosh. Until `/segments` serves them, the
`TERRAIN` table in `features.py` hand-sets them for the mock segments. Delete it
when the real columns land.

---

## Two design decisions worth defending

**Routing minimises expected journey time, not distance.**

```
cost = travel_min + risk × DISRUPTION_COST_MIN
```

A 30% chance of a blockage that costs four hours is 72 minutes of expected delay
on top of drive time, so a safer road 20 minutes longer is simply cheaper — and
we can say exactly why. Multiplying travel time by risk instead cannot express
the trade-off at all: as risks saturate in heavy rain, the ratio between two
roads collapses toward the ratio of their risks, so a route more than ~18% longer
could never win however dangerous the alternative got. `DISRUPTION_COST_MIN` is
the one knob to tune per vehicle class — an ambulance should fear a blockage far
more than a cargo truck.

**The model is deliberately not class-weighted.** Nothing downstream consumes a
class label — `score.py` turns the probability into a score and `routing.py`
turns it into a cost — so what we need is a *calibrated* probability. Weighting
positives up gave mean prediction 0.264 against a true rate of 0.173, and
collapsed the wet-weather gap between a landslide-prone highway and a safe
alternate from 0.148 to 0.036, leaving the router unable to tell them apart.
The asymmetric cost of being wrong lives in `DISRUPTION_COST_MIN` instead.

---

## What the demo shows

`python routing.py`, Rangpo → Gangtok:

| Rainfall (72h) | Route | ETA | Route risk |
| --- | --- | --- | --- |
| 10 mm | NH-10 via Singtam | 42 min | 0.140 |
| 185 mm | **reroutes** via Rorathang–Pakyong | 76 min (+24) | 0.902 |
| 335 mm | none — `advisory: no_safe_route` | — | 1.000 |

The middle row is the money shot: rain rises, the Teesta-gorge stretch of NH-10
goes to 0.96, and the truck is sent the long way round for 24 extra minutes. The
third row matters too — at 335 mm every road is failing, and the honest answer is
to escalate to emergency-access mode rather than dress a coin-flip up as a
recommendation.
