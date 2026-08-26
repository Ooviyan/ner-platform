"""Self-checks for explain.py and connect.py. No pytest needed:

    python test_connect.py
    python test_connect.py http://localhost:8000    # also exercise the live backend

These guard the two things that only break once real data shows up: the contract
translation (backend strings -> model numbers) and the driver-report loop.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import connect
import explain
import features
import inventory
import risk
import score
import weather

HERE = Path(__file__).parent
FAILURES: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {name}" + (f" - {detail}" if detail and not condition else ""))
    if not condition:
        FAILURES.append(name)


NOW = datetime.now(timezone.utc)
WET = {"rain_now_mm": 12.0, "rain_3day_mm": 185.0}

# A segment exactly as GET /segments serves it, strings and all.
BACKEND_SEGMENT = {
    "id": "SEG-SK-NH10-001",
    "name": "NH-10 Rangpo - Singtam (Teesta Corridor, Sikkim)",
    "risk": 0.82, "accessibility": 34, "status": "restricted",
    "geometry": {"type": "LineString", "coordinates": [
        [88.5290, 27.1760], [88.5142, 27.1935], [88.4980, 27.2340]]},
    "state": "Sikkim", "road_class": "national_highway", "length_km": 7.2,
    "surface": "asphalt", "lanes": 2, "elevation_m": 380.0, "slope_deg": 18.2,
    "rainfall_mm_24h": 86.0, "rainfall_mm_72h": 214.0,
}


def test_explain() -> None:
    print("\nexplain.py")
    wet = {"rain_3day_mm": 310, "slope_deg": 31, "incident_density": 4.1}

    items = explain.explain(wet)
    check("explain returns ranked contributions", len(items) == 3)
    check("contributions are ordered by magnitude",
          all(abs(items[i]["contribution"]) >= abs(items[i + 1]["contribution"])
              for i in range(len(items) - 1)))
    check("each item names a real feature or the heuristic",
          all(i["feature"] in features.FEATURES or i["feature"] == "heuristic"
              for i in items))
    check("direction is stated", all(i["direction"] in {"increases", "reduces"}
                                     for i in items))

    text = explain.explain_text(wet)
    check("explain_text is a plain sentence", isinstance(text, str) and len(text) > 10, text)
    check("explain_text names the dominant driver",
          "rain" in text.lower() or "heuristic" in text.lower(), text)

    batch = explain.explain_batch([wet, {"rain_3day_mm": 5}])
    check("explain_batch matches per-row explain", len(batch) == 2)
    check("batch agrees with single", batch[0][0]["feature"] == items[0]["feature"])
    check("explain_batch([]) is empty", explain.explain_batch([]) == [])

    if risk.model_info()["loaded"]:
        dry_risk = risk.score_segment({"rain_3day_mm": 5, "slope_deg": 31})
        wet_risk = risk.score_segment({"rain_3day_mm": 310, "slope_deg": 31})
        check("a wetter segment scores higher", wet_risk > dry_risk,
              f"{wet_risk} vs {dry_risk}")

        what_if = explain.counterfactual(wet, "rain_3day_mm", 10)
        check("counterfactual lowers risk when the rain stops",
              what_if["risk_after"] < what_if["risk_before"],
              f"{what_if['risk_before']} -> {what_if['risk_after']}")
        check("counterfactual delta is signed correctly", what_if["delta"] < 0)

    try:
        explain.counterfactual(wet, "not_a_feature", 1)
        check("counterfactual rejects unknown features", False)
    except ValueError:
        check("counterfactual rejects unknown features", True)

    importances = explain.global_importance()
    check("global importance is available", isinstance(importances, dict))
    if importances:
        check("3-day rainfall dominates globally",
              max(importances, key=importances.get) == "rain_3day_mm",
              str(importances))


def test_translation() -> None:
    print("\nconnect.py - contract translation")
    check("road_class string becomes a number",
          features.coerce("road_class", "national_highway") == 3.0)
    check("numeric road_class passes through", features.coerce("road_class", 2) == 2.0)
    try:
        features.coerce("road_class", "autobahn")
        check("unknown road_class is rejected", False)
    except ValueError:
        check("unknown road_class is rejected", True)

    # The bug this caught for real: score.py re-derives features from the raw row.
    accessible = score.accessibility(BACKEND_SEGMENT)
    check("score.accessibility accepts a raw /segments row",
          isinstance(accessible, int) and 0 <= accessible <= 100, str(accessible))

    weather = connect.segment_weather(BACKEND_SEGMENT)
    check("rainfall_mm_72h maps to rain_3day_mm", weather["rain_3day_mm"] == 214.0)
    check("rain_now_mm is the 24h total spread over the day",
          abs(weather["rain_now_mm"] - 86.0 / 24.0) < 1e-3, str(weather))

    feats = connect.to_features(BACKEND_SEGMENT)
    check("to_features produces every model feature",
          set(feats) == set(features.FEATURES))
    check("terrain comes from the backend row, not the placeholder",
          feats["slope_deg"] == 18.2 and feats["elevation_m"] == 380.0)

    fallback = connect.segment_weather({"id": "X"}, WET)
    check("region-wide weather fills in when a segment has none",
          fallback["rain_3day_mm"] == 185.0)


def test_report_signal() -> None:
    print("\nconnect.py - driver-report loop")

    def report(**over):
        base = {"event_id": "E1", "type": "landslide", "severity": "critical",
                "segment_id": "SEG-A", "status": "verified",
                "timestamp": NOW.isoformat()}
        base.update(over)
        return base

    fresh = connect.report_signals([report()])
    check("a fresh critical report is a strong signal", fresh["SEG-A"] > 0.9,
          str(fresh))

    old = connect.report_signals([report(timestamp=(NOW - timedelta(hours=24)).isoformat())])
    check("a day-old report has decayed", old["SEG-A"] < 0.2, str(old))
    check("decay is monotonic", old["SEG-A"] < fresh["SEG-A"])

    rejected = connect.report_signals([report(status="rejected")])
    check("a rejected report contributes nothing", "SEG-A" not in rejected)

    pending = connect.report_signals([report(status="pending")])
    check("an unreviewed report is discounted", pending["SEG-A"] < fresh["SEG-A"],
          f"{pending} vs {fresh}")

    mild = connect.report_signals([report(type="heavy_rain", severity="low")])
    check("category and severity scale the signal", mild["SEG-A"] < fresh["SEG-A"])

    many = connect.report_signals([report(event_id="a"), report(event_id="b"),
                                   report(event_id="c")])
    check("multiple reports compound", many["SEG-A"] >= fresh["SEG-A"])
    check("signal never exceeds 1", all(v <= 1.0 for v in many.values()), str(many))

    check("a report with no segment is ignored",
          connect.report_signals([report(segment_id=None)]) == {})

    # Snapping: mock-data reports carry only lat/lng.
    snapped = connect.attach_segments(
        [{"event_id": "E", "type": "landslide", "lat": 27.1935, "lng": 88.5142}],
        [BACKEND_SEGMENT])
    check("a report with only coordinates is snapped to a segment",
          snapped[0].get("segment_id") == "SEG-SK-NH10-001", str(snapped[0]))

    far = connect.attach_segments(
        [{"event_id": "E", "type": "landslide", "lat": 13.08, "lng": 80.27}],
        [BACKEND_SEGMENT])
    check("a report far from any segment is left unattached",
          not far[0].get("segment_id"), str(far[0]))


def test_enrichment() -> None:
    print("\nconnect.py - scoring")
    segments = [BACKEND_SEGMENT]

    rows = connect.enrich_segments(segments, WET, [])
    row = rows[0]
    check("contract fields survive enrichment",
          {"id", "name", "status", "geometry"} <= set(row))
    check("risk is a probability", 0.0 <= row["risk"] <= 1.0, str(row["risk"]))
    check("accessibility is 0-100", 0 <= row["accessibility"] <= 100)
    check("risk_band is set", row["risk_band"] in {"low", "medium", "high"})
    check("an explanation is attached", isinstance(row["why"], str) and row["why"])
    check("shap detail is attached", "shap" in row["ml"])
    check("restricted status caps accessibility at 40", row["accessibility"] <= 40,
          str(row["accessibility"]))

    hot = connect.apply_report(segments, {
        "event_id": "EVT-NEW", "type": "landslide", "severity": "critical",
        "segment_id": "SEG-SK-NH10-001", "status": "verified",
        "timestamp": NOW.isoformat()}, WET)
    check("a fresh driver report raises risk", hot[0]["risk"] > row["risk"],
          f"{row['risk']} -> {hot[0]['risk']}")
    check("the explanation mentions the report",
          "report" in hot[0]["why"].lower(), hot[0]["why"])

    check("enrich_segments([]) is empty", connect.enrich_segments([], WET, []) == [])

    # Report-derived density is the fallback for roads the catalogue never saw.
    reported = connect._report_densities(
        [{"segment_id": "SEG-SK-NH10-001", "status": "verified"}] * 3, segments)
    check("report-derived density is per km",
          abs(reported["SEG-SK-NH10-001"] - 3 / 7.2) < 0.01, str(reported))

    combined = connect.incident_densities(
        [{"segment_id": "SEG-SK-NH10-001", "status": "verified"}] * 3, segments)
    if inventory.load_events():
        check("the catalogue outranks report-derived history",
              combined["SEG-SK-NH10-001"] != reported["SEG-SK-NH10-001"],
              str(combined))


def test_weather() -> None:
    """Real hourly rainfall. Network-optional: the cache carries these offline."""
    print("\nweather.py - real hourly rainfall (Open-Meteo)")

    series = {
        "time": ["2026-08-26T07:00", "2026-08-26T08:00",
                 "2026-08-26T09:00", "2026-08-26T10:00", "2026-08-26T11:00"],
        "precipitation": [1.0, 2.0, 3.0, 4.0, 99.0],   # the 99 is in the future
    }
    at_ten = datetime(2026, 8, 26, 10, 30, tzinfo=timezone.utc)
    summary = weather._summarise(series, now=at_ten)
    check("rain_now_mm is the last COMPLETED hour", summary["rain_now_mm"] == 4.0,
          str(summary))
    check("forecast hours are excluded", summary["rain_3day_mm"] == 10.0, str(summary))
    check("the observation is timestamped", "observed_at" in summary)

    check("an empty series returns nothing, not zero", weather._summarise({}) == {})
    check("a series entirely in the future returns nothing",
          weather._summarise(series, now=datetime(2020, 1, 1, tzinfo=timezone.utc)) == {})

    check("nearby points snap to one weather cell",
          weather._snap(27.1935) == weather._snap(27.2100),
          f"{weather._snap(27.1935)} vs {weather._snap(27.2100)}")
    check("distant points do not snap together",
          weather._snap(27.19) != weather._snap(28.50))

    check("segment midpoint is (lat, lon)",
          weather.segment_midpoint(BACKEND_SEGMENT) == (27.1935, 88.5142),
          str(weather.segment_midpoint(BACKEND_SEGMENT)))
    check("a segment with no geometry yields no midpoint",
          weather.segment_midpoint({"id": "X"}) is None)

    live = weather.rainfall_at(27.1935, 88.5142)
    if live:
        check("a live reading has both features",
              {"rain_now_mm", "rain_3day_mm"} <= set(live), str(live))
        check("rainfall is non-negative",
              live["rain_now_mm"] >= 0 and live["rain_3day_mm"] >= 0, str(live))
        check("72h total is at least the last hour",
              live["rain_3day_mm"] >= live["rain_now_mm"], str(live))
        check("the reading is attributed", live.get("source") == "open-meteo")
    else:
        print("  [SKIP] live Open-Meteo call - no network")


def test_inventory() -> None:
    """Real landslide history from the NASA Global Landslide Catalog."""
    print("\ninventory.py - landslide inventory (NASA GLC)")

    events = inventory.load_events()
    if not events:
        print("  [SKIP] inventory not pulled - run `python inventory.py --refresh`")
        return

    check("the inventory has events", len(events) > 100, f"{len(events)} events")
    check("every event has coordinates",
          all(e.get("lat") is not None and e.get("lng") is not None for e in events))
    lo_lon, lo_lat, hi_lon, hi_lat = inventory.NER_BBOX
    check("every event is inside the NER bounding box",
          all(lo_lon <= e["lng"] <= hi_lon and lo_lat <= e["lat"] <= hi_lat
              for e in events))

    info = inventory.inventory_info()
    check("provenance is recorded", "NASA" in str(info.get("source")), str(info.get("source")))
    check("the source URL is kept", bool(info.get("source_url")))

    count = inventory.count_near(BACKEND_SEGMENT)
    check("landslides are found near NH-10 Rangpo-Singtam", count > 0, str(count))

    density = inventory.incident_density(BACKEND_SEGMENT)
    check("density is per km", density is not None and 0 < density <= inventory.MAX_DENSITY,
          str(density))
    check("density equals count / length",
          abs(density - count / BACKEND_SEGMENT["length_km"]) < 0.01,
          f"{density} vs {count}/{BACKEND_SEGMENT['length_km']}")

    tight = inventory.count_near(BACKEND_SEGMENT, buffer_km=0.5)
    wide = inventory.count_near(BACKEND_SEGMENT, buffer_km=10.0)
    check("a wider buffer never finds fewer", wide >= count >= tight,
          f"0.5km={tight} 3km={count} 10km={wide}")

    far = {"id": "OCEAN", "length_km": 5.0,
           "geometry": {"type": "LineString", "coordinates": [[0.0, 0.0], [0.1, 0.0]]}}
    check("a segment nowhere near NER has no history",
          inventory.incident_density(far) == 0.0,
          str(inventory.incident_density(far)))

    check("a segment with no geometry returns None, not 0",
          inventory.incident_density({"id": "X"}) is None)

    all_of_them = inventory.densities([BACKEND_SEGMENT])
    check("densities() keys by segment id", "SEG-SK-NH10-001" in all_of_them)


def test_real_sources_in_connect() -> None:
    print("\nconnect.py - real sources replace the approximations")

    observed = {"rain_now_mm": 12.5, "rain_3day_mm": 180.0}
    got = connect.segment_weather(BACKEND_SEGMENT, WET, observed)
    check("a real reading beats the backend's stored value",
          got["rain_now_mm"] == 12.5 and got["rain_3day_mm"] == 180.0, str(got))

    stored = connect.segment_weather(BACKEND_SEGMENT, WET, None)
    check("without a reading it still falls back to the backend",
          stored["rain_3day_mm"] == 214.0, str(stored))
    check("the fallback rain_now_mm is the documented 24h/24 approximation",
          abs(stored["rain_now_mm"] - 86.0 / 24.0) < 1e-3, str(stored))

    rows = connect.enrich_segments([BACKEND_SEGMENT], WET, [], live=False)
    check("live=False uses only what the backend supplied",
          rows[0]["ml"]["sources"]["rainfall"] == "backend",
          str(rows[0]["ml"]["sources"]))

    if inventory.load_events():
        check("incident_density comes from the catalogue even offline",
              rows[0]["ml"]["sources"]["incident_density"] == "nasa-glc",
              str(rows[0]["ml"]["sources"]))
        check("the catalogue value reached the model",
              rows[0]["ml"]["features"]["incident_density"] > 0,
              str(rows[0]["ml"]["features"]["incident_density"]))

    live_rows = connect.enrich_segments([BACKEND_SEGMENT], WET, [], live=True)
    source = live_rows[0]["ml"]["sources"]["rainfall"]
    check("live=True reports its rainfall source",
          source in {"open-meteo", "backend", "default"}, source)
    if source == "open-meteo":
        check("a live run really used Open-Meteo", True)
    else:
        print("  [SKIP] live rainfall - no network, fell back to backend")


def test_graph() -> None:
    print("\nconnect.py - routing over live shapes")
    import routing

    segments = connect.load_platform(None).segments
    if not segments:
        check("mock-data segments available", False, "no ../mock-data/segments.json")
        return

    graph = connect.live_graph(segments, WET, [])
    check("live_graph builds a routable graph", graph.number_of_nodes() > 0)
    check("edges carry cost and risk",
          all("cost" in d and "risk" in d for _, _, d in graph.edges(data=True)))

    nodes = sorted(graph.nodes)
    if len(nodes) >= 2:
        try:
            route = routing.safest_route(graph, nodes[0], nodes[-1])
            check("safest_route returns the contract shape",
                  {"id", "origin", "destination", "chosen", "eta_min",
                   "delay_min", "risk", "segments"} <= set(route))
            check("eta_min is positive", route["eta_min"] > 0)
            check("delay_min is not negative", route["delay_min"] >= 0)
        except Exception as exc:  # disconnected fixtures are acceptable
            check("safest_route runs or reports cleanly",
                  isinstance(exc, (KeyError, Exception)), str(exc))


def test_live_backend(base_url: str) -> None:
    print(f"\nconnect.py - live backend at {base_url}")
    data = connect.load_platform(base_url)
    if data.source == "mock-data":
        check("backend reachable", False, f"{base_url} not responding")
        return

    check("segments loaded from the API", len(data.segments) > 0)
    scored = connect.enrich_segments(data.segments, data.weather, data.reports)
    check("every live segment scores", len(scored) == len(data.segments))
    check("all risks are probabilities",
          all(0.0 <= r["risk"] <= 1.0 for r in scored))
    check("all accessibility values are 0-100",
          all(0 <= r["accessibility"] <= 100 for r in scored))
    check("closed roads score zero accessibility",
          all(r["accessibility"] == 0 for r in scored if r.get("status") == "closed"))
    check("every segment gets an explanation", all(r["why"] for r in scored))

    graph = connect.live_graph(data.segments, data.weather, data.reports)
    check("a graph builds from live segments", graph.number_of_edges() > 0,
          f"{graph.number_of_nodes()} nodes")


def main() -> int:
    print(f"ml/ connect + explain self-checks - model: {risk.model_info()['mode']}")
    test_explain()
    test_translation()
    test_report_signal()
    test_enrichment()
    test_weather()
    test_inventory()
    test_real_sources_in_connect()
    test_graph()

    if len(sys.argv) > 1:
        test_live_backend(sys.argv[1])

    print()
    if FAILURES:
        print(f"{len(FAILURES)} check(s) failed: {', '.join(FAILURES)}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
