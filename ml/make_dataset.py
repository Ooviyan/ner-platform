"""Generate a labelled training set for the disruption-risk model.

WHY THIS IS SYNTHETIC
---------------------
The real labels come from the GSI Bhukosh landslide inventory joined to IMD /
Open-Meteo rainfall history for the same segment-days. That join is Person 1's
PostGIS work and does not exist yet. Rather than block, this script samples from
a documented generative process built out of published NER monsoon behaviour:

  * 3-day cumulative rainfall drives soil saturation, and saturation is what
    actually fails a slope - current rain alone is a weak signal.
  * Saturation and slope INTERACT. 300mm over 72h on a 35-degree cut slope is a
    different animal from the same rain on the Brahmaputra floodplain.
  * Segments with a landslide history fail again in the same places.
  * Surface quality sets the floor.

So the model learns a relationship that is real in shape even though the rows
are simulated. Swap this file for a database query the day the inventory lands;
nothing downstream changes because `features.FEATURES` stays fixed.

Do not present the metrics from this data as field-validated accuracy.
"""

from __future__ import annotations

import argparse
import csv
import math
import random
from pathlib import Path

from features import FEATURES

OUT = Path(__file__).parent / "data" / "training_data.csv"


def _logistic(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def _sample_row(rng: random.Random) -> dict[str, float]:
    """One segment-day of NER monsoon conditions."""
    # Terrain: NER spans the Brahmaputra floodplain and the Sikkim/Arunachal
    # ranges, so slope is strongly bimodal.
    if rng.random() < 0.45:                       # hill segment
        slope = rng.gauss(27, 8)
        elevation = rng.gauss(1300, 700)
    else:                                          # valley / floodplain
        slope = rng.gauss(5, 3)
        elevation = rng.gauss(120, 90)
    slope = max(0.0, min(60.0, slope))
    elevation = max(0.0, min(5000.0, elevation))

    # Rainfall: monsoon-weighted, heavy tail. 3-day is roughly current rain
    # scaled up plus a persistent background, then jittered.
    monsoon = rng.random() < 0.6
    rain_now = abs(rng.gauss(6, 9)) if monsoon else abs(rng.gauss(0.6, 1.6))
    rain_3day = max(rain_now, abs(rng.gauss(rain_now * 9 + 40, 70)) if monsoon
                    else abs(rng.gauss(rain_now * 4 + 5, 12)))
    rain_now = min(120.0, rain_now)
    rain_3day = min(900.0, rain_3day)

    # History: hill segments carry far more past incidents.
    incident_density = abs(rng.gauss(1.6 if slope > 18 else 0.25, 1.1))
    incident_density = min(10.0, incident_density)

    road_class = rng.choices([0, 1, 2, 3], weights=[0.12, 0.23, 0.3, 0.35])[0]
    report_signal = rng.random() < 0.08 and rng.random() or 0.0

    return {
        "rain_now_mm": round(rain_now, 2),
        "rain_3day_mm": round(rain_3day, 2),
        "slope_deg": round(slope, 2),
        "elevation_m": round(elevation, 1),
        "incident_density": round(incident_density, 3),
        "road_class": float(road_class),
        "report_signal": round(float(report_signal), 3),
    }


def _label(row: dict[str, float], rng: random.Random) -> int:
    """Probability of a disruption on this segment in the next 48 hours."""
    saturation = row["rain_3day_mm"] / 300.0          # 300mm/72h ~ saturated
    steepness = row["slope_deg"] / 30.0

    logit = (
        -4.6                                          # base rate: most days are fine
        + 2.9 * saturation
        + 1.1 * steepness
        + 3.4 * saturation * steepness                # the interaction that matters
        + 0.55 * row["incident_density"]
        + 0.030 * row["rain_now_mm"]
        - 0.45 * row["road_class"]                    # better surface, fewer failures
        + 0.0004 * row["elevation_m"]
        + 2.2 * row["report_signal"]                  # a driver is looking at it
    )
    return int(rng.random() < _logistic(logit))


def build(n: int, seed: int) -> list[dict[str, float]]:
    rng = random.Random(seed)
    rows = []
    for _ in range(n):
        row = _sample_row(rng)
        row["disrupted_48h"] = _label(row, rng)
        rows.append(row)
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-n", "--rows", type=int, default=6000)
    ap.add_argument("--seed", type=int, default=26002)
    ap.add_argument("-o", "--out", type=Path, default=OUT)
    args = ap.parse_args()

    rows = build(args.rows, args.seed)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FEATURES + ["disrupted_48h"])
        writer.writeheader()
        writer.writerows(rows)

    positives = sum(r["disrupted_48h"] for r in rows)
    print(f"wrote {len(rows)} rows -> {args.out}")
    print(f"disruption rate: {positives / len(rows):.1%} ({positives} positive)")


if __name__ == "__main__":
    main()
