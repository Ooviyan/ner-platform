"""Risk-aware routing: the safest passable path, not the shortest one.

    from ml.routing import build_graph, safest_route

    graph = build_graph(segments, weather={"rain_3day_mm": 310})
    route = safest_route(graph, "RANGPO", "GANGTOK")
    # -> {"id", "origin", "destination", "chosen", "eta_min", "delay_min",
    #     "risk", "segments": [...]}

The return shape is exactly `mock-data/routes.json`, so Person 1 can serve it
from /route without reshaping and the two frontends already render it.

Division of labour, per the study: ML supplies the score, A* does the pathing.
Risk enters as edge cost, never as a black box over the search itself - which
is what lets us answer "why this route" with a straight face.

Standalone demo (no backend, no database):

    python routing.py
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import networkx as nx

from features import segment_features
from risk import score_segment
from score import accessibility

HERE = Path(__file__).parent
CORRIDOR = HERE / "data" / "corridor_nh10.geojson"

# Routing minimises EXPECTED journey time, not distance and not raw travel time:
#
#     cost = travel_min + risk * DISRUPTION_COST_MIN
#
# If a segment has a 30% chance of being blocked and being blocked costs you
# four hours, that segment carries 72 minutes of expected delay on top of the
# time it takes to drive. A safer road that is 20 minutes longer is then simply
# the cheaper choice, and we can say exactly why.
#
# An earlier version multiplied travel time by risk instead. That could not
# express the trade-off at all: as risks saturate in heavy rain the ratio
# between two roads collapses toward the ratio of their risks, so a route more
# than ~18% longer could never win however dangerous the alternative got.
#
# DISRUPTION_COST_MIN is the one number to tune per vehicle class - an ambulance
# should fear a blockage far more than a cargo truck.
DISRUPTION_COST_MIN = 240.0  # 4h: waiting out a clearance, or turning back

# Risk is priced per kilometre of exposure, against this reference length.
#
# The earlier version charged `risk * DISRUPTION_COST_MIN` per EDGE, which made
# the cost depend on how finely the network happens to be chopped up: a road
# split into five rows was penalised five times, the same road as one row once.
# On the Sikkim network that inverted the answer outright -- in heavy rain the
# router sent trucks INTO the Teesta gorge (3 edges, one of them 0.86 risk over
# 7 km) rather than round the Rorathang bypass (5 edges, none above 0.54),
# purely because the bypass had more rows.
#
# Scaling by length fixes it and is what the quantity means anyway: the chance
# this drive is disrupted grows with how much dangerous road you are on, not
# with how many rows the surveyor drew. It is also split-invariant -- one 20 km
# edge at risk r costs exactly what two 10 km edges at risk r cost.
RISK_REFERENCE_KM = 10.0

# Below this accessibility a segment is treated as impassable and dropped from
# the graph entirely, rather than merely made expensive.
IMPASSABLE_BELOW = 15

# Above this risk on its WORST segment, a route has no good answer left. Saying
# "take NH-10, risk 0.99" would dress a coin-flip up as a recommendation, so the
# route carries an explicit advisory and the dashboard can drop into
# emergency-access mode.
#
# Judged on the worst single link, not on the compounded route risk: compounding
# 1-prod(1-r) climbs toward 1 whenever a route has several moderate segments, so
# it would condemn a perfectly sensible detour for being long. What the control
# room is asking is "is there a link on this route that is likely to fail", and
# that is a max, not a product.
NO_SAFE_ROUTE_ABOVE = 0.90

EARTH_RADIUS_KM = 6371.0
MAX_SPEED_KMPH = 60.0  # fastest road in the region; keeps the A* heuristic admissible


def haversine_km(a: Sequence[float], b: Sequence[float]) -> float:
    """Great-circle distance between two [lon, lat] points."""
    lon1, lat1, lon2, lat2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    dlon, dlat = lon2 - lon1, lat2 - lat1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(h))


def line_length_km(coordinates: Sequence[Sequence[float]]) -> float:
    return sum(haversine_km(coordinates[i], coordinates[i + 1])
               for i in range(len(coordinates) - 1))


def _node_id(properties: Mapping[str, Any], point: Sequence[float], end: str) -> str:
    """Prefer an explicit from/to name; fall back to snapping the endpoint.

    Snapping to ~4 decimal places (about 11 m) lets segments that share a
    junction meet in the graph even when nobody named the junction.
    """
    named = properties.get(end)
    if named:
        return str(named)
    return f"@{point[0]:.4f},{point[1]:.4f}"


def load_corridor(path: Path = CORRIDOR) -> list[dict[str, Any]]:
    """Read a GeoJSON FeatureCollection into segment dicts."""
    data = json.loads(Path(path).read_text())
    segments = []
    for feature in data["features"]:
        segment = dict(feature["properties"])
        segment["geometry"] = feature["geometry"]
        segments.append(segment)
    return segments


def load_mock_segments() -> list[dict[str, Any]]:
    """The shared contract data in ../mock-data/segments.json."""
    return json.loads((HERE.parent / "mock-data" / "segments.json").read_text())


def build_graph(segments: Iterable[Mapping[str, Any]],
                weather: Mapping[str, Any] | None = None,
                disruption_cost_min: float = DISRUPTION_COST_MIN,
                risk_overrides: Mapping[str, float] | None = None) -> nx.DiGraph:
    """Build a routable graph, scoring every segment as it goes.

    Roads are bidirectional here - each segment becomes two directed edges.
    `risk_overrides` lets a caller force a segment's risk (used by the demo to
    simulate a rainfall spike, and by the backend when a driver report confirms
    a blockage).
    """
    graph = nx.DiGraph()
    overrides = risk_overrides or {}

    for segment in segments:
        coordinates = segment["geometry"]["coordinates"]
        segment_id = str(segment.get("id"))

        features = segment_features(segment, weather)
        risk = float(overrides[segment_id]) if segment_id in overrides \
            else score_segment(features)
        usability = accessibility(segment, weather, risk=risk)

        if usability < IMPASSABLE_BELOW:
            continue  # closed or effectively impassable - not a routing option

        length_km = line_length_km(coordinates)
        speed = float(segment.get("speed_kmph", 35.0))
        # Poor usability slows a vehicle down even where the road is open.
        effective_speed = max(speed * (0.4 + 0.6 * usability / 100.0), 8.0)
        travel_min = length_km / effective_speed * 60.0
        # Expected delay from disruption, proportional to exposure. See
        # RISK_REFERENCE_KM for why this is per-km and not per-edge.
        exposure = max(length_km, 0.1) / RISK_REFERENCE_KM
        cost = travel_min + risk * disruption_cost_min * exposure

        start = _node_id(segment, coordinates[0], "from")
        end = _node_id(segment, coordinates[-1], "to")
        graph.add_node(start, coordinates=coordinates[0])
        graph.add_node(end, coordinates=coordinates[-1])

        attributes = dict(segment_id=segment_id, name=segment.get("name", segment_id),
                          length_km=round(length_km, 3), risk=round(risk, 4),
                          accessibility=usability, travel_min=round(travel_min, 2),
                          cost=round(cost, 3))
        graph.add_edge(start, end, **attributes)
        graph.add_edge(end, start, **attributes)

    return graph


def _heuristic(graph: nx.DiGraph, goal: str):
    """Straight-line time to the goal - admissible, so A* stays optimal."""
    goal_point = graph.nodes[goal].get("coordinates")

    def estimate(node: str, _target: str) -> float:
        point = graph.nodes[node].get("coordinates")
        if point is None or goal_point is None:
            return 0.0
        return haversine_km(point, goal_point) / MAX_SPEED_KMPH * 60.0

    return estimate


def _walk(graph: nx.DiGraph, path: Sequence[str]) -> list[dict[str, Any]]:
    return [graph.edges[path[i], path[i + 1]] for i in range(len(path) - 1)]


def _summarise(graph: nx.DiGraph, path: Sequence[str], origin: str, destination: str,
               route_id: str, chosen: bool, baseline_min: float | None) -> dict[str, Any]:
    edges = _walk(graph, path)
    eta = sum(edge["travel_min"] for edge in edges)
    # Route risk is "something goes wrong ANYWHERE along it", so the segment
    # risks compound - a chain of moderate risks is not itself moderate.
    survival = math.prod(1.0 - edge["risk"] for edge in edges)
    return {
        "id": route_id,
        "origin": origin,
        "destination": destination,
        "chosen": chosen,
        "eta_min": int(round(eta)),
        "delay_min": int(round(eta - baseline_min)) if baseline_min is not None else 0,
        "risk": round(1.0 - survival, 4),
        "segments": [edge["segment_id"] for edge in edges],
        "distance_km": round(sum(edge["length_km"] for edge in edges), 2),
        "min_accessibility": min(edge["accessibility"] for edge in edges),
        "max_segment_risk": round(max(edge["risk"] for edge in edges), 4),
        "advisory": ("no_safe_route"
                     if max(edge["risk"] for edge in edges) > NO_SAFE_ROUTE_ABOVE
                     else "ok"),
        "path": list(path),
    }


def fastest_route(graph: nx.DiGraph, origin: str, destination: str,
                  route_id: str = "RTE-FAST") -> dict[str, Any]:
    """Ignore risk entirely - what a plain navigation app would return."""
    path = nx.astar_path(graph, origin, destination,
                         heuristic=_heuristic(graph, destination), weight="travel_min")
    return _summarise(graph, path, origin, destination, route_id, False, None)


def safest_route(graph: nx.DiGraph, origin: str, destination: str,
                 route_id: str = "RTE-SAFE", baseline: dict[str, Any] | None = None
                 ) -> dict[str, Any]:
    """The safest passable path, as risk-weighted travel time.

    `delay_min` is measured against the fastest route, so the number the driver
    sees is honestly "this reroute costs you N extra minutes".
    """
    if origin not in graph:
        raise KeyError(f"unknown origin {origin!r}; nodes: {sorted(graph.nodes)}")
    if destination not in graph:
        raise KeyError(f"unknown destination {destination!r}; nodes: {sorted(graph.nodes)}")

    baseline = baseline or fastest_route(graph, origin, destination)
    path = nx.astar_path(graph, origin, destination,
                         heuristic=_heuristic(graph, destination), weight="cost")
    return _summarise(graph, path, origin, destination, route_id, True,
                      baseline["eta_min"])


def alternatives(graph: nx.DiGraph, origin: str, destination: str, k: int = 3
                 ) -> list[dict[str, Any]]:
    """Top-k risk-ranked routes for the dashboard's route-comparison panel."""
    generator = nx.shortest_simple_paths(graph, origin, destination, weight="cost")
    baseline = fastest_route(graph, origin, destination)
    routes = []
    for index, path in enumerate(generator):
        if index >= k:
            break
        routes.append(_summarise(graph, path, origin, destination,
                                 f"RTE-ALT-{index + 1}", index == 0,
                                 baseline["eta_min"]))
    return routes


def _demo() -> None:
    """The Person 2 half of the stage demo - no backend, no database."""
    scenarios = (
        ("clear",   "10mm over 72h",  {"rain_now_mm": 0.0,  "rain_3day_mm": 10.0}),
        ("monsoon", "185mm over 72h", {"rain_now_mm": 12.0, "rain_3day_mm": 185.0}),
        ("extreme", "335mm over 72h", {"rain_now_mm": 22.0, "rain_3day_mm": 335.0}),
    )
    segments = load_corridor()

    print("NH-10 corridor - Rangpo to Gangtok, Sikkim")
    print("  NH-10 via Singtam follows the Teesta: faster, and the stretch that slides.")
    print("  Alternate via Rorathang and Pakyong: 1.2x the distance, far steadier ground.")
    print("=" * 72)

    for name, rain, weather in scenarios:
        graph = build_graph(segments, weather)
        fast = fastest_route(graph, "RANGPO", "GANGTOK")
        safe = safest_route(graph, "RANGPO", "GANGTOK", baseline=fast)
        rerouted = safe["segments"] != fast["segments"]

        print(f"\n{name.upper():<8} {rain}")
        print(f"  fastest  {fast['eta_min']:>3} min  {fast['distance_km']:>5} km  "
              f"risk {fast['risk']:.3f}   {' > '.join(fast['path'])}")
        print(f"  chosen   {safe['eta_min']:>3} min  {safe['distance_km']:>5} km  "
              f"risk {safe['risk']:.3f}   {' > '.join(safe['path'])}")
        if safe["advisory"] == "no_safe_route":
            print(f"  !! NO SAFE ROUTE - every path is likely to fail. "
                  f"Escalate to emergency-access mode.")
        elif rerouted:
            print(f"  >> REROUTED off NH-10, costing {safe['delay_min']:+d} min "
                  f"to drop route risk {fast['risk'] - safe['risk']:.3f}")
        else:
            print(f"  -- NH-10 is fine today; no reason to send anyone the long way")

    print("\n" + "=" * 72)
    print("per-segment detail under 185mm/72h")
    graph = build_graph(segments, {"rain_now_mm": 12.0, "rain_3day_mm": 185.0})
    seen = set()
    print(f"  {'segment':<15} {'risk':>6} {'access':>7} {'min':>6} {'cost':>7}")
    for _, _, edge in graph.edges(data=True):
        if edge["segment_id"] in seen:
            continue
        seen.add(edge["segment_id"])
        print(f"  {edge['segment_id']:<15} {edge['risk']:>6.3f} "
              f"{edge['accessibility']:>7} {edge['travel_min']:>6.1f} {edge['cost']:>7.1f}")

    print("\nsame code against the shared mock-data contract")
    mock_graph = build_graph(load_mock_segments(),
                             {"rain_now_mm": 5.0, "rain_3day_mm": 90.0})
    print(f"  {mock_graph.number_of_nodes()} nodes, "
          f"{mock_graph.number_of_edges() // 2} passable segments "
          f"(closed ones dropped from the graph)")
    try:
        route = safest_route(mock_graph, "@88.5290,27.1760", "@88.6138,27.3314",
                             route_id="RTE-1001")
        print("  " + json.dumps({k: route[k] for k in
                                 ("id", "eta_min", "delay_min", "risk", "segments")}))
    except (KeyError, nx.NetworkXNoPath):
        print("  no passable route through the mock corridor - "
              "which is itself the answer the control room needs")


if __name__ == "__main__":
    _demo()
