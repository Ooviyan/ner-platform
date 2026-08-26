"""Small geodesic helpers. Kept dependency-free so the API works without GEOS."""

from __future__ import annotations

import math
from typing import List, Sequence, Tuple

Coord = Tuple[float, float]  # (lon, lat), GeoJSON order
EARTH_RADIUS_KM = 6371.0088


def haversine_km(a: Coord, b: Coord) -> float:
    lon1, lat1 = math.radians(a[0]), math.radians(a[1])
    lon2, lat2 = math.radians(b[0]), math.radians(b[1])
    dlon, dlat = lon2 - lon1, lat2 - lat1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(h))


def line_length_km(coords: Sequence[Coord]) -> float:
    return sum(haversine_km(coords[i], coords[i + 1]) for i in range(len(coords) - 1))


def bearing_deg(a: Coord, b: Coord) -> float:
    """Initial compass bearing from a to b, 0-360 clockwise from north."""
    lon1, lat1 = math.radians(a[0]), math.radians(a[1])
    lon2, lat2 = math.radians(b[0]), math.radians(b[1])
    dlon = lon2 - lon1
    y = math.sin(dlon) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


def interpolate(coords: Sequence[Coord], fraction: float) -> Tuple[Coord, float]:
    """Point at `fraction` (0..1) of the way along a polyline, plus its heading."""
    if len(coords) < 2:
        return tuple(coords[0]), 0.0
    fraction = min(max(fraction, 0.0), 1.0)
    spans = [haversine_km(coords[i], coords[i + 1]) for i in range(len(coords) - 1)]
    total = sum(spans) or 1e-9
    target = fraction * total
    walked = 0.0
    for i, span in enumerate(spans):
        if walked + span >= target or i == len(spans) - 1:
            local = (target - walked) / span if span else 0.0
            local = min(max(local, 0.0), 1.0)
            a, b = coords[i], coords[i + 1]
            point = (a[0] + (b[0] - a[0]) * local, a[1] + (b[1] - a[1]) * local)
            return point, bearing_deg(a, b)
        walked += span
    return tuple(coords[-1]), bearing_deg(coords[-2], coords[-1])


def nearest_point_index(coords: Sequence[Coord], point: Coord) -> int:
    return min(range(len(coords)), key=lambda i: haversine_km(coords[i], point))


def linestring(coords: Sequence[Coord]) -> dict:
    return {"type": "LineString", "coordinates": [[round(x, 6), round(y, 6)] for x, y in coords]}


def point(coord: Coord) -> dict:
    return {"type": "Point", "coordinates": [round(coord[0], 6), round(coord[1], 6)]}


def densify(coords: Sequence[Coord], max_step_km: float = 3.0) -> List[Coord]:
    """Insert intermediate vertices so simulated vehicles move smoothly."""
    if len(coords) < 2:
        return list(coords)
    out: List[Coord] = [tuple(coords[0])]
    for i in range(len(coords) - 1):
        a, b = tuple(coords[i]), tuple(coords[i + 1])
        steps = max(1, int(haversine_km(a, b) // max_step_km))
        for s in range(1, steps + 1):
            t = s / steps
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    return out


def to_wkt_linestring(coords: Sequence[Coord]) -> str:
    inner = ", ".join(f"{x} {y}" for x, y in coords)
    return f"SRID=4326;LINESTRING({inner})"


def to_wkt_point(coord: Coord) -> str:
    return f"SRID=4326;POINT({coord[0]} {coord[1]})"
