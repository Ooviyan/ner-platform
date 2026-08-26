#!/usr/bin/env python
"""Load the North East India road network into PostGIS.

    python load_ner.py --states sikkim          # one state, quick test
    python load_ner.py --states sikkim,assam    # a couple
    python load_ner.py --states all             # full NER (slow, gigabytes)
    python load_ner.py --sample                 # just the pre-seeded sample, instant

Downloads drivable OpenStreetMap roads per state with osmnx, derives a risk and
accessibility score for every edge, and writes them to the `road_segments` table.

The `--sample` mode needs no network access and no osmnx: it inserts the small
hand-checked set of real NH corridors that ships in `app/seed.py`, so the API
returns data immediately. That is also what the API falls back to in memory when
PostGIS is not running.
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Iterable, List

from sqlalchemy import delete, func, select

from app import geo, seed
from app.bootstrap import seed_database, segment_row
from app.config import BASE_DIR, masked_database_url
from app.database import SessionLocal, engine, init_db
from app.models import RoadSegment
from app.ner_states import NER_STATES, resolve_states, state_name

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s")
log = logging.getLogger("load_ner")

# Only these OSM highway classes matter for relief and freight movement.
CUSTOM_FILTER = (
    '["highway"~"motorway|trunk|primary|secondary|tertiary|unclassified"]'
)

# Rough terrain-risk weight per highway class: smaller roads in NER are the ones
# that get cut off first. Person 2's risk_model.pkl replaces this at merge time.
_CLASS_RISK = {
    "motorway": 0.08, "trunk": 0.15, "primary": 0.22, "secondary": 0.34,
    "tertiary": 0.46, "unclassified": 0.58, "residential": 0.5, "track": 0.72,
}
_SURFACE_RISK = {
    "asphalt": 0.0, "paved": 0.02, "concrete": 0.02, "compacted": 0.12,
    "gravel": 0.22, "unpaved": 0.3, "dirt": 0.36, "ground": 0.36,
}


def _first(value):
    """OSM tags come back as a scalar, a list, or NaN; return a usable value or None."""
    if isinstance(value, (list, tuple, set)):
        value = next(iter(value), None)
    if value is None:
        return None
    # pandas fills missing tags with NaN, which str()s to the literal "nan".
    if isinstance(value, float) and value != value:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "<na>"}:
        return None
    return value


def _score(highway: str, surface: str | None, length_km: float) -> tuple[float, str, int]:
    risk = _CLASS_RISK.get(highway, 0.4)
    risk += _SURFACE_RISK.get((surface or "").lower(), 0.08)
    # Long unbroken stretches with no alternative are more exposed.
    risk += min(0.12, length_km / 250.0)
    risk = round(min(max(risk, 0.0), 1.0), 3)
    accessibility = max(0, min(100, round(100 - risk * 70)))
    return risk, seed.risk_level_for(risk), accessibility


def _import_osmnx():
    try:
        import osmnx as ox
    except ImportError:  # pragma: no cover - depends on the local install
        log.error(
            "osmnx is not installed. Either `pip install -r requirements.txt`, "
            "or run `python load_ner.py --sample` to load the built-in corridors."
        )
        sys.exit(2)
    # osmnx caches downloads, so re-running a state is cheap.
    ox.settings.use_cache = True
    ox.settings.log_console = False
    ox.settings.cache_folder = str(BASE_DIR / ".osmnx-cache")
    return ox


def download_state(ox, slug: str) -> List[dict]:
    """Fetch one state's drivable network and shape it into segment dicts."""
    meta = NER_STATES[slug]
    log.info("downloading OSM roads for %s ...", meta["name"])
    graph = ox.graph_from_place(
        meta["osm_query"], custom_filter=CUSTOM_FILTER, simplify=True, retain_all=False
    )
    nodes, edges = ox.graph_to_gdfs(graph)
    log.info("  %s: %d edges", meta["name"], len(edges))

    segments: List[dict] = []
    seen_pairs: set = set()
    for index, (key, row) in enumerate(edges.iterrows()):
        geometry = row.get("geometry")
        if geometry is None or geometry.geom_type != "LineString":
            continue
        coords = [(float(x), float(y)) for x, y in geometry.coords]
        if len(coords) < 2:
            continue

        # A two-way road appears twice, once per direction. Keep one: the network
        # length would otherwise be double the real thing.
        if isinstance(key, tuple) and len(key) >= 2:
            pair = (frozenset(key[:2]), key[2] if len(key) > 2 else 0)
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)

        highway = str(_first(row.get("highway")) or "unclassified")
        surface = _first(row.get("surface"))
        ref = _first(row.get("ref"))
        name = _first(row.get("name")) or ref or f"Unnamed {highway.replace('_', ' ')}"
        length_km = round(float(row.get("length", 0.0)) / 1000.0 or
                          geo.line_length_km(coords), 3)
        risk, level, accessibility = _score(highway, surface, length_km)

        segments.append({
            "id": f"SEG-{meta['code']}-OSM-{index:06d}",
            "name": str(name)[:255],
            "state": meta["name"],
            "state_code": meta["code"],
            "highway": str(ref or highway)[:32],
            "road_class": highway,
            "length_km": length_km,
            "surface": str(surface)[:32] if surface else None,
            "lanes": int(_lanes) if (_lanes := _first(row.get("lanes"))) is not None
            and str(_lanes).isdigit() else None,
            "elevation_m": None,
            "slope_deg": None,
            "rainfall_mm_24h": 0.0,
            "rainfall_mm_72h": 0.0,
            "risk_score": risk,
            "risk_level": level,
            "accessibility_score": accessibility,
            "status": "open",
            "source": "osm",
            "osm_id": str(_first(row.get("osmid"))),
            "last_updated": None,
            "geometry": geo.linestring(coords),
        })
    return segments


def write_segments(segments: Iterable[dict], state: str, replace: bool) -> int:
    """Insert one state's segments, in batches so a big state does not blow memory."""
    written = 0
    with SessionLocal() as session:
        if replace:
            removed = session.execute(
                delete(RoadSegment).where(
                    RoadSegment.state == state, RoadSegment.source == "osm"
                )
            ).rowcount
            session.commit()
            if removed:
                log.info("  removed %d existing OSM rows for %s", removed, state)

        batch = []
        for data in segments:
            batch.append(segment_row(data))
            if len(batch) >= 2000:
                session.add_all(batch)
                session.commit()
                written += len(batch)
                log.info("  ... %d written", written)
                batch = []
        if batch:
            session.add_all(batch)
            session.commit()
            written += len(batch)
    return written


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Load NER road networks from OpenStreetMap into PostGIS.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="states: " + ", ".join(NER_STATES) + ", all",
    )
    parser.add_argument(
        "--states",
        default=None,
        help='State name, slug or code -- comma-separated, or "all" for all eight.',
    )
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Load only the built-in sample corridors (no download, no osmnx).",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Delete existing OSM rows for each state before loading.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Download and score, but do not write to the database.",
    )
    args = parser.parse_args(argv)

    if not args.states and not args.sample:
        parser.error("pass --states <name|all> or --sample")

    log.info("database: %s", masked_database_url())
    if not args.dry_run and not init_db():
        log.error(
            "cannot reach PostGIS. Start it with:\n"
            "  docker run --name ner-db -e POSTGRES_PASSWORD=ner -e POSTGRES_DB=ner "
            "-p 5432:5432 -d postgis/postgis"
        )
        return 1

    if args.sample:
        with SessionLocal() as session:
            inserted = seed_database(session, force=args.replace)
        log.info("sample loaded: %s", inserted)
        if not args.states:
            return 0

    try:
        slugs = resolve_states([args.states]) if args.states else []
    except ValueError as exc:
        parser.error(str(exc))
        return 2

    ox = _import_osmnx()
    total = 0
    for slug in slugs:
        name = state_name(slug)
        try:
            segments = download_state(ox, slug)
        except Exception:
            log.exception("failed to load %s -- continuing with the rest", name)
            continue
        if args.dry_run:
            log.info("  %s: %d segments (dry run, nothing written)", name, len(segments))
            continue
        written = write_segments(segments, name, replace=args.replace)
        total += written
        log.info("  %s: %d segments written", name, written)

    if not args.dry_run:
        with engine.connect() as conn:
            count = conn.execute(
                select(func.count()).select_from(RoadSegment)
            ).scalar_one()
        log.info("done -- %d segments written, %d in road_segments", total, count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
