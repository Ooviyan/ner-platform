"""Self-checks for the ml/ deliverables. No pytest needed:

    python test_ml.py

These guard the promises `risk.py`, `score.py` and `routing.py` make to
Person 1's API - bounded outputs, no exceptions on partial input, and a route
shape that matches mock-data/routes.json.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import features
import risk
import routing
import score

HERE = Path(__file__).parent
FAILURES: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {name}" + (f" - {detail}" if detail and not condition else ""))
    if not condition:
        FAILURES.append(name)


DRY = {"rain_now_mm": 0.0, "rain_3day_mm": 10.0}
WET = {"rain_now_mm": 12.0, "rain_3day_mm": 185.0}      # monsoon: the reroute case
EXTREME = {"rain_now_mm": 22.0, "rain_3day_mm": 335.0}  # everything fails
STEEP = {"slope_deg": 31.0, "elevation_m": 460.0, "incident_density": 4.1, "road_class": 3}


def test_features() -> None:
    print("\nfeatures.py")
    row = features.to_row({"rain_3day_mm": 200})
    check("to_row returns one value per feature", len(row) == len(features.FEATURES))
    check("missing features fall back to defaults",
          row[features.FEATURES.index("slope_deg")] == features.DEFAULTS["slope_deg"])
    check("out-of-range values are clamped",
          features.to_row({"rain_3day_mm": 99999})[1] == features.BOUNDS["rain_3day_mm"][1])
    try:
        features.to_row({"rainfall": 5})
        check("unknown feature names are rejected", False)
    except ValueError:
        check("unknown feature names are rejected", True)


def test_risk() -> None:
    print("\nrisk.py")
    dry_risk = risk.score_segment({**STEEP, **DRY})
    wet_risk = risk.score_segment({**STEEP, **WET})
    check("risk stays within 0..1", 0.0 <= dry_risk <= 1.0 and 0.0 <= wet_risk <= 1.0,
          f"{dry_risk}, {wet_risk}")
    check("saturated slope scores above dry slope", wet_risk > dry_risk,
          f"wet {wet_risk} vs dry {dry_risk}")
    check("empty input does not raise", isinstance(risk.score_segment({}), float))
    check("batch matches single call",
          risk.score_segments([{**STEEP, **WET}])[0] == wet_risk)
    check("batch handles empty list", risk.score_segments([]) == [])

    flat_wet = risk.score_segment({**WET, "slope_deg": 2.0, "incident_density": 0.2})
    check("flat ground is safer than a slope in the same rain", flat_wet < wet_risk,
          f"flat {flat_wet} vs slope {wet_risk}")

    check("bands map correctly",
          risk.risk_band(0.9) == "high" and risk.risk_band(0.5) == "medium"
          and risk.risk_band(0.1) == "low")

    reasons = risk.explain({**STEEP, **WET})
    check("explain returns ranked reasons", len(reasons) > 0 and "feature" in reasons[0])
    check("model_info reports its mode", risk.model_info()["mode"] in {"xgboost", "heuristic"})


def test_score() -> None:
    print("\nscore.py")
    segments = json.loads((HERE.parent / "mock-data" / "segments.json").read_text())
    by_id = {s["id"]: s for s in segments}

    values = [score.accessibility(s, WET) for s in segments]
    check("accessibility stays within 0..100", all(0 <= v <= 100 for v in values), str(values))

    closed = by_id["SEG-AS-NH715-007"]           # status: closed
    check("a closed road scores 0", score.accessibility(closed, DRY) == 0)

    restricted = by_id["SEG-SK-NH10-001"]        # status: restricted
    check("a restricted road is capped at 40", score.accessibility(restricted, DRY) <= 40)

    highway = by_id["SEG-AS-NH27-014"]           # flat Assam highway, open
    check("a good highway scores well in the dry", score.accessibility(highway, DRY) >= 70,
          str(score.accessibility(highway, DRY)))
    check("rain lowers the same road",
          score.accessibility(highway, WET) <= score.accessibility(highway, DRY))

    detail = score.breakdown(highway, WET)
    check("breakdown shows every penalty term",
          set(detail["penalties"]) == set(score.WEIGHTS))
    check("bands map correctly",
          score.band(85) == "green" and score.band(50) == "amber" and score.band(10) == "red")


def test_routing() -> None:
    print("\nrouting.py")
    segments = routing.load_corridor()
    graph = routing.build_graph(segments, WET)
    check("graph builds from the corridor fixture", graph.number_of_nodes() >= 5)

    fast = routing.fastest_route(graph, "RANGPO", "GANGTOK")
    safe = routing.safest_route(graph, "RANGPO", "GANGTOK", baseline=fast)

    contract = {"id", "origin", "destination", "chosen", "eta_min", "delay_min",
                "risk", "segments"}
    check("route matches the routes.json contract", contract <= set(safe))
    check("eta is a positive whole number", isinstance(safe["eta_min"], int) and safe["eta_min"] > 0)
    check("route risk stays within 0..1", 0.0 <= safe["risk"] <= 1.0)
    check("safest route is not riskier than fastest", safe["risk"] <= fast["risk"] + 1e-9,
          f"safe {safe['risk']} vs fast {fast['risk']}")
    check("segments are real ids",
          all(s in {seg["id"] for seg in segments} for s in safe["segments"]))

    dry_graph = routing.build_graph(segments, DRY)
    dry_safe = routing.safest_route(dry_graph, "RANGPO", "GANGTOK")
    check("clear weather keeps the fast highway", "NH10-RNG-SGT" in dry_safe["segments"],
          str(dry_safe["segments"]))
    check("clear weather costs no detour", dry_safe["delay_min"] == 0)
    check("monsoon moves the truck off NH-10",
          "NH10-RNG-SGT" not in safe["segments"], str(safe["segments"]))
    check("the detour is genuinely slower", safe["delay_min"] > 0, str(safe["delay_min"]))
    check("the detour is genuinely safer", safe["max_segment_risk"] < fast["max_segment_risk"],
          f"{safe['max_segment_risk']} vs {fast['max_segment_risk']}")

    extreme_graph = routing.build_graph(segments, EXTREME)
    extreme = routing.safest_route(extreme_graph, "RANGPO", "GANGTOK")
    check("no route is recommended when every road is failing",
          extreme["advisory"] == "no_safe_route", extreme["advisory"])
    check("a usable route is not flagged", dry_safe["advisory"] == "ok")

    check("delay is measured against the fastest route",
          safe["delay_min"] == safe["eta_min"] - fast["eta_min"])

    blocked = routing.build_graph(segments, DRY, risk_overrides={"NH10-RNG-SGT": 0.99})
    detoured = routing.safest_route(blocked, "RANGPO", "GANGTOK")
    check("a confirmed driver report forces a reroute",
          "NH10-RNG-SGT" not in detoured["segments"], str(detoured["segments"]))

    options = routing.alternatives(graph, "RANGPO", "GANGTOK", k=2)
    check("alternatives returns ranked options", len(options) == 2)
    check("exactly one option is marked chosen",
          sum(o["chosen"] for o in options) == 1)

    try:
        routing.safest_route(graph, "NOWHERE", "GANGTOK")
        check("unknown node raises a clear error", False)
    except KeyError:
        check("unknown node raises a clear error", True)


def main() -> int:
    print(f"ml/ self-checks - risk model: {risk.model_info()['mode']}")
    test_features()
    test_risk()
    test_score()
    test_routing()
    print()
    if FAILURES:
        print(f"{len(FAILURES)} check(s) failed: {', '.join(FAILURES)}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
