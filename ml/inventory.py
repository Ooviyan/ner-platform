"""Historical landslide inventory for the eight NER states.

    from ml.inventory import incident_density, load_events, refresh

    incident_density(segment)      # past landslides per km along this road
    load_events()                  # the cached inventory
    python inventory.py --refresh  # re-pull from the source

`incident_density` is one of the seven features the risk model was trained on,
and it was the weakest link in this folder: it used to be derived from the
platform's own driver reports, which is circular (the system's own output
feeding its own input) and empty on day one.

This module replaces that with a real, citable inventory: **NASA's Global
Landslide Catalog (GLC)**, a curated record of rainfall-triggered landslides
compiled from news, government and academic reports, with coordinates and dates.
861 events fall inside the NER bounding box.

Density is `events within BUFFER_KM of the segment / segment length in km`,
capped at the model's feature bound.

Two honest caveats
------------------
**The GLC is event-reported, not exhaustive.** It records landslides somebody
wrote down, so it is biased toward roads near towns and toward events that hurt
people. A remote corridor with no reporting looks safer than it is. Treat a high
density as strong evidence and a low one as weak evidence.

**GSI Bhukosh would be better and is not reachable here.** The Geological Survey
of India's Bhukosh portal is the authoritative Indian inventory, far denser over
NER than the GLC. `bhukosh.gsi.gov.in` did not respond from this network, so it
is not wired in. `SOURCES` below records what to switch to when it is available
-- the swap is one function, and nothing downstream moves.
"""

from __future__ import annotations

import argparse
import json
import logging
import ssl
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

log = logging.getLogger(__name__)

HERE = Path(__file__).parent
INVENTORY_PATH = HERE / "data" / "landslides_ner.json"

# Bounding box covering all eight NER states, with a margin for the
# West Bengal corridor that carries NH-10 into Sikkim.
NER_BBOX = (88.0, 21.9, 97.5, 29.5)   # min_lon, min_lat, max_lon, max_lat

# A landslide this far from the road is taken as evidence that the corridor runs
# through failure-prone ground. Tighter than this and GPS scatter in the source
# drops real events; wider and a slide in the next valley starts counting.
BUFFER_KM = 3.0

# Feature bound from features.BOUNDS["incident_density"].
MAX_DENSITY = 10.0

SOURCES: dict[str, dict[str, str]] = {
    "nasa_glc": {
        "name": "NASA Global Landslide Catalog",
        "url": ("https://services1.arcgis.com/yFGHRCyBneULM8ci/arcgis/rest/"
                "services/nasa_global_landslide_catalog_point/FeatureServer/0/query"),
        "licence": "NASA open data",
        "note": ("ArcGIS Online mirror of the GLC. NASA's own host "
                 "(maps.nccs.nasa.gov) was unreachable from this network."),
    },
    "gsi_bhukosh": {
        "name": "GSI Bhukosh landslide inventory (PREFERRED, not wired in)",
        "url": "https://bhukosh.gsi.gov.in/",
        "licence": "Geological Survey of India",
        "note": "Authoritative for India and far denser over NER. Host did not "
                "respond when this module was written; swap fetch_events() to it "
                "when it does.",
    },
}


def _ssl_context() -> ssl.SSLContext | None:
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return None


def fetch_events(bbox: Sequence[float] = NER_BBOX,
                 timeout: float = 60.0) -> list[dict[str, Any]]:
    """Pull landslide events inside a bounding box from the NASA GLC."""
    source = SOURCES["nasa_glc"]
    query = urllib.parse.urlencode({
        "where": "1=1",
        "geometry": ",".join(str(v) for v in bbox),
        "geometryType": "esriGeometryEnvelope",
        "inSR": "4326", "outSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": ("event_id,event_date,event_titl,landslide_,landslid_1,"
                      "landslid_2,location_d,fatality_c,source_nam"),
        "returnGeometry": "true",
        "resultRecordCount": 5000,
        "f": "json",
    })
    request = urllib.request.Request(f"{source['url']}?{query}",
                                     headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout,
                                context=_ssl_context()) as response:
        payload = json.loads(response.read())

    if "error" in payload:
        raise RuntimeError(f"{source['name']} error: {payload['error']}")

    events = []
    for feature in payload.get("features", []):
        geometry = feature.get("geometry") or {}
        lon, lat = geometry.get("x"), geometry.get("y")
        if lon is None or lat is None:
            continue
        attributes = feature.get("attributes", {})
        events.append({
            "event_id": attributes.get("event_id"),
            "lat": round(float(lat), 5),
            "lng": round(float(lon), 5),
            "date": attributes.get("event_date"),
            "category": attributes.get("landslide_"),
            "trigger": attributes.get("landslid_1"),
            "size": attributes.get("landslid_2"),
            "location": (attributes.get("location_d") or "")[:120] or None,
            "fatalities": attributes.get("fatality_c"),
        })
    return events


def refresh(path: Path = INVENTORY_PATH,
            bbox: Sequence[float] = NER_BBOX) -> dict[str, Any]:
    """Re-pull the inventory and write it to disk."""
    events = fetch_events(bbox)
    payload = {
        "source": SOURCES["nasa_glc"]["name"],
        "source_url": SOURCES["nasa_glc"]["url"],
        "licence": SOURCES["nasa_glc"]["licence"],
        "note": SOURCES["nasa_glc"]["note"],
        "bbox": list(bbox),
        "count": len(events),
        "events": events,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=1))
    log.info("wrote %d events to %s", len(events), path)
    return payload


_cache: dict[str, Any] | None = None


def load_events(path: Path = INVENTORY_PATH) -> list[dict[str, Any]]:
    """The cached inventory. Empty (with a warning) if it has not been pulled."""
    global _cache
    if _cache is None:
        try:
            _cache = json.loads(Path(path).read_text())
        except (OSError, ValueError):
            log.warning("%s missing - run `python inventory.py --refresh`. "
                        "incident_density will fall back to its caller.", path.name)
            _cache = {"events": []}
    return _cache.get("events", [])


def inventory_info(path: Path = INVENTORY_PATH) -> dict[str, Any]:
    """Provenance, for /health and the pitch: which inventory, how many events."""
    load_events(path)
    meta = dict(_cache or {})
    meta.pop("events", None)
    meta["available"] = bool((_cache or {}).get("events"))
    return meta


def _segment_points(segment: Mapping[str, Any]) -> list[tuple[float, float]]:
    coordinates = (segment.get("geometry") or {}).get("coordinates") or []
    return [(float(lon), float(lat)) for lon, lat, *_ in coordinates]


def count_near(segment: Mapping[str, Any], buffer_km: float = BUFFER_KM,
               events: Iterable[Mapping[str, Any]] | None = None) -> int:
    """How many catalogued landslides lie within `buffer_km` of this segment."""
    from routing import haversine_km

    points = _segment_points(segment)
    if not points:
        return 0
    events = load_events() if events is None else list(events)

    # Cheap degree-box reject before the haversine, so 861 events x 22 segments
    # stays instant.
    lons = [p[0] for p in points]
    lats = [p[1] for p in points]
    pad = buffer_km / 100.0
    lo_lon, hi_lon = min(lons) - pad, max(lons) + pad
    lo_lat, hi_lat = min(lats) - pad, max(lats) + pad

    count = 0
    for event in events:
        lon, lat = event.get("lng"), event.get("lat")
        if lon is None or lat is None:
            continue
        if not (lo_lon <= lon <= hi_lon and lo_lat <= lat <= hi_lat):
            continue
        if any(haversine_km((lon, lat), point) <= buffer_km for point in points):
            count += 1
    return count


def incident_density(segment: Mapping[str, Any], buffer_km: float = BUFFER_KM,
                     events: Iterable[Mapping[str, Any]] | None = None) -> float | None:
    """Catalogued landslides per km of this segment, or None if not derivable.

    None -- not zero -- when the segment has no length or the inventory is
    missing, so a caller can tell "no history" from "no data" and fall back
    instead of feeding the model a confident zero.
    """
    length_km = segment.get("length_km")
    if not length_km:
        points = _segment_points(segment)
        if len(points) < 2:
            return None
        from routing import line_length_km
        length_km = line_length_km([[lon, lat] for lon, lat in points])
    if not length_km:
        return None
    if not (load_events() if events is None else events):
        return None

    count = count_near(segment, buffer_km, events)
    return round(min(count / float(length_km), MAX_DENSITY), 3)


def densities(segments: Sequence[Mapping[str, Any]],
              buffer_km: float = BUFFER_KM) -> dict[str, float]:
    """Density for every segment that has one, keyed by segment id."""
    events = load_events()
    if not events:
        return {}
    out = {}
    for segment in segments:
        value = incident_density(segment, buffer_km, events)
        if value is not None:
            out[str(segment.get("id"))] = value
    return out


def _main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--refresh", action="store_true",
                        help="re-pull the inventory from NASA GLC")
    parser.add_argument("--buffer-km", type=float, default=BUFFER_KM)
    args = parser.parse_args()

    if args.refresh:
        payload = refresh()
        print(f"pulled {payload['count']} events from {payload['source']}")

    info = inventory_info()
    print(f"\ninventory: {info.get('source')}  ({info.get('count', 0)} events)")
    print(f"  {info.get('note')}\n")

    try:
        segments = json.loads(
            (HERE.parent / "mock-data" / "segments.json").read_text())
    except OSError:
        print("no ../mock-data/segments.json to score against")
        return 0

    from routing import line_length_km
    print(f"{'segment':<20} {'km':>6} {'slides':>7} {'per km':>7}")
    for segment in segments:
        km = segment.get("length_km") or line_length_km(
            segment.get("geometry", {}).get("coordinates", []) or [[0, 0], [0, 0]])
        count = count_near(segment, args.buffer_km)
        density = incident_density(segment, args.buffer_km)
        print(f"{str(segment.get('id')):<20} {km:>6.1f} "
              f"{count:>7} {density if density is not None else '-':>7}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
