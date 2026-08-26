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
python train_risk.py      # generates data if missing, trains, writes risk_model.pkl
python test_ml.py         # self-checks over risk, score and routing
python test_connect.py    # self-checks over explain and the platform bridge
python routing.py         # the standalone reroute demo
python explain.py         # SHAP attribution for one segment
python connect.py         # score whatever the platform currently knows
```

`python test_connect.py http://localhost:8000` additionally runs every check
against Person 1's live API.

---

## What Person 1 imports

```python
from ml.risk    import score_segment, risk_band, model_info
from ml.score   import accessibility, breakdown
from ml.routing import build_graph, safest_route, alternatives
from ml.explain import explain, explain_text, counterfactual
from ml.connect import load_platform, enrich_segments, apply_report, live_graph

score_segment({"rain_3day_mm": 185, "slope_deg": 31, "incident_density": 4.1})
# 0.963

accessibility(segment, weather={"rain_3day_mm": 185})
# 28

route = safest_route(build_graph(segments, weather), "RANGPO", "GANGTOK")
# {"id", "origin", "destination", "chosen", "eta_min", "delay_min", "risk",
#  "segments": [...], "advisory": "ok" | "no_safe_route", ...}
```

### The one call that does everything

`connect.py` is the seam between this folder and the platform. Give it what
`/segments` and `/reports` return and it hands back rows in the same contract
shape, with `risk` and `accessibility` replaced by the model's answers:

```python
rows = enrich_segments(segments, weather, reports)
# [{... "risk": 0.954, "risk_band": "high", "accessibility": 0,
#      "why": "driven by 402 mm of rain over 72h and a 26 degree slope",
#      "ml": {"penalties": ..., "report_signal": ..., "shap": [...]}}]
```

`GET /segments` can serve those rows unchanged — every contract field survives,
and `why` / `ml` are additions the dashboard's explainability panel reads.

**Driver reports close the loop.** `POST /reports` should call:

```python
apply_report(segments, new_report, weather, existing=known_reports)
```

A driver confirming a landslide on NH-10 pushes that segment's `report_signal`
to 1.0, which the model was trained on — measured against the live backend,
`SEG-SK-NH10-001` moves from **risk 0.248 to 0.640** the moment the report
lands, and the explanation changes to "…and a confirmed driver report".

Report weight decays with a 6-hour half-life, scales by category and severity,
and is discounted while a report is still `pending`. Several reports on one
segment compound as independent evidence. `rejected` reports count for nothing.

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
| `train_risk.py` | Trains XGBoost → `risk_model.pkl`, `metrics.json`, SHAP importances. |
| `risk.py` | `score_segment()` → 0..1, heuristic fallback, model metadata. |
| `score.py` | `accessibility()` → 0..100 with a full penalty breakdown and tunable weights. |
| `explain.py` | SHAP attribution, plain-English `explain_text()`, counterfactuals. |
| `routing.py` | A\* over networkx, risk priced as expected delay. |
| `connect.py` | The bridge to Person 1's API and the driver app. |
| `weather.py` | Real hourly rainfall from Open-Meteo, cached on disk. |
| `inventory.py` | Real landslide history from the NASA Global Landslide Catalog. |
| `data/landslides_ner.json` | 861 catalogued NER landslides. Refresh with `inventory.py --refresh`. |
| `data/corridor_nh10.geojson` | Test fixture — ML-local, *not* part of the shared contract. |
| `test_ml.py` | Self-checks for risk, score and routing. |
| `test_connect.py` | Self-checks for explain and the platform bridge. |

### Two translations `connect.py` owns

`/segments` speaks the shared contract; `features.py` speaks the model's schema.
Neither should know about the other, so the mapping lives in one place:

| Contract | Model | Note |
| --- | --- | --- |
| `rainfall_mm_72h` | `rain_3day_mm` | exact |
| `rainfall_mm_24h` | `rain_now_mm` | fallback only — a real hourly reading from `weather.py` is preferred |
| `road_class: "national_highway"` | `road_class: 3` | via `features.ROAD_CLASS` |
| `status: open/restricted/closed` | accessibility ceiling | a closed road is 0, not "somewhat accessible" |
| NASA GLC | `incident_density` | events within 3 km, per km; `/reports` history only where the catalogue is silent |
| recent `/reports` | `report_signal` | decayed, weighted, compounded |

`score.py` and `risk.py` accept a raw `/segments` row directly — `features.coerce`
handles the string-valued contract fields — so no caller has to translate first.

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

**2. Terrain is a placeholder.** `/segments` serves `slope_deg` and
`elevation_m`, and `connect.py` prefers them over the `TERRAIN` table in
`features.py`, which now only fills gaps. The DEM values themselves still want
SRTM/Bhoonidhi rather than hand-set numbers.

---

## Where the numbers actually come from

Five of the seven features now come from real sources. Two used to be
approximations and are not any more.

| Feature | Source | Real? |
| --- | --- | --- |
| `rain_now_mm` | Open-Meteo hourly precipitation, last completed hour | **yes** |
| `rain_3day_mm` | Open-Meteo, 72h preceding that hour | **yes** |
| `incident_density` | NASA Global Landslide Catalog, 861 NER events | **yes** |
| `slope_deg` | `/segments`, else `TERRAIN` placeholder | partly |
| `elevation_m` | `/segments`, else `TERRAIN` placeholder | partly |
| `road_class` | `/segments`, the shared contract | yes |
| `report_signal` | live driver reports via `/reports` | yes |

```bash
python weather.py                  # live rainfall at five NER points
python inventory.py --refresh      # re-pull the landslide catalogue
```

**Rainfall — `weather.py`.** Open-Meteo serves hourly precipitation free and
without an API key. `rain_now_mm` is the last completed hour and `rain_3day_mm`
the 72 hours before it, so both come from one real series. The old fudge divided
a 24h total by 24, which is exactly wrong for the case that matters: a cloudburst
dropping 60 mm in three hours looked identical to a day of drizzle, and the burst
is what triggers the slope. Readings are cached on disk for an hour and batched
one call per network refresh. *Weather data by Open-Meteo.com, CC-BY 4.0.*

**Landslide history — `inventory.py`.** 861 catalogued NER landslides with
coordinates and dates, cached in `data/landslides_ner.json`. Density is events
within 3 km of the segment, per km of road. This replaces deriving history from
the platform's own driver reports, which was circular — the system's output
feeding its own input — and empty on day one.

Two caveats that remain, and matter:

- **The GLC is event-reported, not exhaustive.** It records landslides somebody
  wrote down, so it is biased toward roads near towns and toward events that hurt
  people. A remote corridor with no reporting looks safer than it is. Read a high
  density as strong evidence and a low one as weak evidence, not as proof of
  safety.
- **GSI Bhukosh would be better and is not wired in.** The Geological Survey of
  India's inventory is authoritative for India and far denser over NER.
  `bhukosh.gsi.gov.in` did not respond from this network. `inventory.SOURCES`
  records the swap; it is one function and nothing downstream moves.

**Both degrade rather than fail.** With no network, `weather.py` warns and the
caller keeps the backend's stored rainfall; the landslide cache is on disk, so
`incident_density` is unaffected. Every scored segment carries
`ml.sources` naming where each number came from, so a demo can never quietly pass
off a default as a measurement.

**One consequence worth expecting.** Real NER weather is usually not a monsoon
emergency, so `live=True` mostly produces low risks — the model being correct,
not broken. `enrich_segments(..., live=False)` uses the backend's stored
scenario, which is what the seeded demo path depends on.

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
