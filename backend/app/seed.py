"""Pre-seeded NER sample data, in the shared ../mock-data contract shape.

Two rules govern this file:

1. **The contract wins.** `../mock-data/*.json` is owned by all four of us and
   Person 2's `ml/routing.py` reads it directly, so the field names here are
   theirs: `risk`, `accessibility`, `origin`/`destination`, `eta_min`, `lng`,
   `type`, `timestamp`, `vehicle_id`, `event`. Extra fields the backend needs
   (geometry, state, length, ETA detail) are *added* alongside them, never
   instead of them -- so anything reading the contract keeps working.

2. **It is a superset.** Every record in `../mock-data` appears here with the
   same id, coordinates and values, so a frontend that hardcoded
   `SEG-SK-NH10-001` or `RTE-1001` still resolves against the live API.

The rest fills the network out to all eight NER states so the map is not two
states of road. `load_ner.py` replaces/extends it with real OSM geometry.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, List

from app import geo
from app.ner_states import NER_STATES

IST = timezone(timedelta(hours=5, minutes=30))
NOW = datetime(2026, 8, 26, 12, 0, tzinfo=IST)

# The contract's vocabularies. Deviating from these breaks the frontends.
SEGMENT_STATUSES = ("open", "restricted", "closed")
SEVERITIES = ("low", "medium", "high", "critical")
ALERT_STATUSES = ("pending", "sent", "acknowledged", "failed")
REPORT_TYPES = (
    "landslide", "flooding", "road_damage", "traffic_block",
    "accident", "bridge_damage", "snow", "sos", "other",
)
VEHICLE_STATUSES = ("en_route", "idle", "halted", "offline")
# Assamese, Bengali, Hindi, Nepali, Mizo, Manipuri -- Person 4's i18n set.
LANGUAGES = ("en", "as", "bn", "hi", "ne", "lus", "mni")


def iso(dt: datetime) -> str:
    """ISO-8601 in IST, matching the timestamps already in ../mock-data."""
    return dt.astimezone(IST).isoformat()


def risk_band(score: float) -> str:
    """Bucket a 0-1 risk into the contract's severity vocabulary."""
    if score >= 0.75:
        return "critical"
    if score >= 0.5:
        return "high"
    if score >= 0.25:
        return "medium"
    return "low"


# ------------------------------------------------------------- segments ----
# id, name, state, highway, road_class, coords, surface, lanes, elevation,
# slope, rain24, rain72, risk, accessibility, status
#
# The first four are the contract's own segments, values untouched.
_SEGMENTS = [
    ("SEG-SK-NH10-001", "NH-10 Rangpo - Singtam (Teesta Corridor, Sikkim)",
     "sikkim", "NH-10", "national_highway",
     [(88.5290, 27.1760), (88.5142, 27.1935), (88.5031, 27.2148), (88.4980, 27.2340)],
     "asphalt", 2, 380, 18.2, 86.0, 214.0, 0.82, 34, "restricted"),
    ("SEG-SK-NH10-002", "NH-10 Singtam - Ranipool - Gangtok (Sikkim)",
     "sikkim", "NH-10", "national_highway",
     [(88.4980, 27.2340), (88.5416, 27.2701), (88.5877, 27.3062), (88.6138, 27.3314)],
     "asphalt", 2, 1420, 14.8, 62.0, 151.0, 0.47, 71, "open"),
    ("SEG-AS-NH27-014", "NH-27 Jalukbari - Khanapara (Guwahati, Assam)",
     "assam", "NH-27", "national_highway",
     [(91.6650, 26.1520), (91.7096, 26.1461), (91.7580, 26.1372), (91.8000, 26.1290)],
     "asphalt", 4, 55, 1.1, 48.0, 132.0, 0.19, 93, "open"),
    ("SEG-AS-NH715-007", "NH-715 Tezpur - Balipara Approach (Assam)",
     "assam", "NH-715", "national_highway",
     [(92.7930, 26.6330), (92.8188, 26.6541), (92.8402, 26.6733), (92.8600, 26.6900)],
     "asphalt", 2, 78, 2.4, 118.0, 302.0, 0.64, 52, "closed"),

    # --- added: the rest of the NER network ---
    ("SEG-SK-NH10-003", "NH-10 Sevoke - Rangpo (Teesta Valley, Sikkim)",
     "sikkim", "NH-10", "national_highway",
     [(88.4275, 26.7271), (88.4720, 26.9010), (88.5290, 27.1760)],
     "asphalt", 2, 310, 21.5, 86.0, 214.0, 0.71, 44, "restricted"),
    ("SEG-SK-NH310-001", "NH-310 Gangtok - Nathu La (Sikkim)",
     "sikkim", "NH-310", "national_highway",
     [(88.6138, 27.3314), (88.7400, 27.3700), (88.8300, 27.3870)],
     "asphalt", 1, 3800, 27.4, 41.0, 96.0, 0.69, 46, "restricted"),
    ("SEG-AS-NH27-021", "NH-27 Nagaon - Jorhat (Assam)",
     "assam", "NH-27", "national_highway",
     [(92.6840, 26.3464), (93.4500, 26.5500), (94.2037, 26.7509)],
     "asphalt", 4, 88, 0.9, 55.0, 168.0, 0.28, 84, "open"),
    ("SEG-AS-NH27-033", "NH-27 Jorhat - Dibrugarh (Assam)",
     "assam", "NH-27", "national_highway",
     [(94.2037, 26.7509), (94.5600, 27.1000), (94.9120, 27.4728)],
     "asphalt", 2, 104, 1.4, 91.0, 246.0, 0.57, 58, "restricted"),
    ("SEG-ML-NH6-004", "NH-6 Guwahati - Shillong (Meghalaya)",
     "meghalaya", "NH-6", "national_highway",
     [(91.7362, 26.1445), (91.8000, 25.9000), (91.8933, 25.5788)],
     "asphalt", 4, 980, 7.3, 96.0, 258.0, 0.38, 76, "open"),
    ("SEG-ML-NH6-011", "NH-6 Shillong - Jowai (Meghalaya)",
     "meghalaya", "NH-6", "national_highway",
     [(91.8933, 25.5788), (92.0400, 25.5200), (92.2000, 25.4500)],
     "asphalt", 2, 1490, 9.6, 118.0, 322.0, 0.63, 53, "open"),
    ("SEG-ML-NH6-018", "NH-6 Jowai - Badarpur (Meghalaya)",
     "meghalaya", "NH-6", "national_highway",
     [(92.2000, 25.4500), (92.4000, 25.1500), (92.5900, 24.8700)],
     "asphalt", 2, 620, 16.9, 141.0, 388.0, 0.79, 12, "closed"),
    ("SEG-NL-NH2-006", "NH-2 Dimapur - Kohima (Nagaland)",
     "nagaland", "NH-2", "national_highway",
     [(93.7278, 25.9063), (93.9200, 25.7800), (94.1100, 25.6751)],
     "asphalt", 2, 1240, 15.1, 72.0, 197.0, 0.52, 64, "open"),
    ("SEG-NL-NH2-013", "NH-2 Kohima - Mao Gate (Nagaland)",
     "nagaland", "NH-2", "national_highway",
     [(94.1100, 25.6751), (94.1000, 25.5000), (94.1200, 25.3900)],
     "asphalt", 2, 1580, 19.4, 68.0, 182.0, 0.61, 51, "restricted"),
    ("SEG-MN-NH2-002", "NH-2 Mao Gate - Senapati (Manipur)",
     "manipur", "NH-2", "national_highway",
     [(94.1200, 25.3900), (94.0700, 25.2700)],
     "asphalt", 2, 1640, 17.8, 58.0, 149.0, 0.49, 68, "open"),
    ("SEG-MN-NH2-009", "NH-2 Senapati - Imphal (Manipur)",
     "manipur", "NH-2", "national_highway",
     [(94.0700, 25.2700), (93.9900, 25.0500), (93.9368, 24.8170)],
     "asphalt", 2, 820, 11.2, 44.0, 118.0, 0.29, 82, "open"),
    ("SEG-MZ-NH306-003", "NH-306 Aizawl - Kolasib (Mizoram)",
     "mizoram", "NH-306", "national_highway",
     [(92.7176, 23.7271), (92.7000, 23.9800), (92.6790, 24.2260)],
     "asphalt", 2, 1010, 20.3, 103.0, 281.0, 0.66, 49, "open"),
    ("SEG-MZ-NH306-010", "NH-306 Kolasib - Silchar (Mizoram)",
     "mizoram", "NH-306", "national_highway",
     [(92.6790, 24.2260), (92.7300, 24.5300), (92.7789, 24.8333)],
     "gravel", 2, 340, 12.7, 124.0, 335.0, 0.74, 38, "restricted"),
    ("SEG-TR-NH8-005", "NH-8 Agartala - Kumarghat (Tripura)",
     "tripura", "NH-8", "national_highway",
     [(91.2868, 23.8315), (91.6500, 23.9800), (92.0300, 24.1300)],
     "asphalt", 2, 42, 2.1, 67.0, 176.0, 0.27, 85, "open"),
    ("SEG-TR-NH8-012", "NH-8 Kumarghat - Churaibari (Tripura)",
     "tripura", "NH-8", "national_highway",
     [(92.0300, 24.1300), (92.1900, 24.3000), (92.3500, 24.4700)],
     "asphalt", 2, 78, 4.6, 88.0, 231.0, 0.46, 72, "open"),
    ("SEG-AR-NH415-002", "NH-415 Banderdewa - Itanagar (Arunachal Pradesh)",
     "arunachal_pradesh", "NH-415", "national_highway",
     [(93.7900, 27.0500), (93.6800, 27.0700), (93.6053, 27.0844)],
     "asphalt", 2, 340, 5.8, 109.0, 288.0, 0.35, 78, "open"),
    ("SEG-AR-NH415-008", "NH-415 Itanagar - Ziro (Arunachal Pradesh)",
     "arunachal_pradesh", "NH-415", "national_highway",
     [(93.6053, 27.0844), (93.7200, 27.3200), (93.8300, 27.5400)],
     "asphalt", 2, 1560, 22.9, 132.0, 356.0, 0.77, 31, "restricted"),
    ("SEG-AR-NH13-004", "NH-13 Ziro - Daporijo (Trans-Arunachal)",
     "arunachal_pradesh", "NH-13", "national_highway",
     [(93.8300, 27.5400), (94.1500, 27.7500), (94.2200, 27.9800)],
     "gravel", 1, 1180, 25.6, 147.0, 402.0, 0.88, 8, "closed"),
]


def _build_segment(row) -> dict:
    (sid, name, state, highway, road_class, coords, surface, lanes,
     elevation, slope, rain24, rain72, risk, accessibility, status) = row
    return {
        # --- contract fields ---
        "id": sid,
        "name": name,
        "risk": risk,
        "accessibility": accessibility,
        "status": status,
        "geometry": geo.linestring(coords),
        # --- backend additions ---
        "state": NER_STATES[state]["name"],
        "state_code": NER_STATES[state]["code"],
        "highway": highway,
        "road_class": road_class,
        "length_km": round(geo.line_length_km(coords), 2),
        "surface": surface,
        "lanes": lanes,
        "elevation_m": elevation,
        "slope_deg": slope,
        "rainfall_mm_24h": rain24,
        "rainfall_mm_72h": rain72,
        "risk_band": risk_band(risk),
        "source": "seed",
        "updated_at": iso(NOW),
    }


SEGMENTS: List[dict] = [_build_segment(r) for r in _SEGMENTS]
SEGMENTS_BY_ID: Dict[str, dict] = {s["id"]: s for s in SEGMENTS}


# --------------------------------------------------------------- routes ----
# id, origin, destination, chosen, eta_min, delay_min, risk, segment ids, advisories
_ROUTES = [
    ("RTE-1001", "Siliguri, West Bengal", "Gangtok, Sikkim", True, 214, 46, 0.68,
     ["SEG-SK-NH10-001", "SEG-SK-NH10-002"],
     ["Single-lane working in the Teesta corridor",
      "Convoy movement only between 06:00 and 17:00 IST"]),
    ("RTE-1002", "Siliguri, West Bengal", "Gangtok, Sikkim", False, 268, 12, 0.31,
     ["SEG-SK-NH10-002"], ["Longer but avoids the Rangpo - Singtam slip zone"]),
    ("RTE-2007", "Guwahati, Assam", "Tezpur, Assam", True, 178, 25, 0.42,
     ["SEG-AS-NH27-014", "SEG-AS-NH715-007"],
     ["NH-715 Balipara approach is CLOSED - clearance in progress"]),
    ("RTE-2008", "Guwahati, Assam", "Shillong, Meghalaya", False, 149, 0, 0.22,
     ["SEG-AS-NH27-014"], []),

    # --- added ---
    ("RTE-1003", "Siliguri, West Bengal", "Nathu La, Sikkim", False, 402, 88, 0.71,
     ["SEG-SK-NH10-003", "SEG-SK-NH10-001", "SEG-SK-NH10-002", "SEG-SK-NH310-001"],
     ["High-altitude axis; visibility above 15 km required"]),
    ("RTE-2011", "Guwahati, Assam", "Dibrugarh, Assam", True, 388, 54, 0.57,
     ["SEG-AS-NH27-014", "SEG-AS-NH27-021", "SEG-AS-NH27-033"],
     ["Brahmaputra flood watch active near Jorhat"]),
    ("RTE-3001", "Guwahati, Assam", "Badarpur, Assam", False, 396, 132, 0.79,
     ["SEG-ML-NH6-004", "SEG-ML-NH6-011", "SEG-ML-NH6-018"],
     ["Jowai - Badarpur is CLOSED by an active landslide",
      "Divert via the NH-27 / Silchar approach"]),
    ("RTE-4001", "Dimapur, Nagaland", "Imphal, Manipur", True, 268, 41, 0.61,
     ["SEG-NL-NH2-006", "SEG-NL-NH2-013", "SEG-MN-NH2-002", "SEG-MN-NH2-009"],
     ["Restricted stretch at Mao Gate - expect 40 min delay"]),
    ("RTE-5001", "Aizawl, Mizoram", "Silchar, Assam", True, 232, 37, 0.74,
     ["SEG-MZ-NH306-003", "SEG-MZ-NH306-010"],
     ["Gravel surface north of Kolasib - reduce to 30 km/h"]),
    ("RTE-6001", "Agartala, Tripura", "Churaibari, Tripura", True, 186, 8, 0.46,
     ["SEG-TR-NH8-005", "SEG-TR-NH8-012"], []),
    ("RTE-7001", "Banderdewa, Arunachal Pradesh", "Daporijo, Arunachal Pradesh",
     True, 421, 165, 0.88,
     ["SEG-AR-NH415-002", "SEG-AR-NH415-008", "SEG-AR-NH13-004"],
     ["Ziro - Daporijo CLOSED; no relief movement until clearance"]),
]


def _build_route(row) -> dict:
    rid, origin, destination, chosen, eta_min, delay_min, risk, seg_ids, advisories = row
    segs = [SEGMENTS_BY_ID[s] for s in seg_ids]
    coords: List[geo.Coord] = []
    for seg in segs:
        pts = [tuple(c) for c in seg["geometry"]["coordinates"]]
        if coords and coords[-1] == pts[0]:
            pts = pts[1:]
        coords.extend(pts)
    closed = [s["id"] for s in segs if s["status"] == "closed"]
    return {
        # --- contract fields ---
        "id": rid,
        "origin": origin,
        "destination": destination,
        "chosen": chosen,
        "eta_min": eta_min,
        "delay_min": delay_min,
        "risk": risk,
        "segments": seg_ids,
        # --- backend additions ---
        "geometry": geo.linestring(coords),
        "origin_point": {"lng": coords[0][0], "lat": coords[0][1]},
        "destination_point": {"lng": coords[-1][0], "lat": coords[-1][1]},
        "distance_km": round(sum(s["length_km"] for s in segs), 2),
        "risk_band": risk_band(risk),
        "accessibility": round(sum(s["accessibility"] for s in segs) / len(segs)),
        "passable": not closed,
        "closed_segments": closed,
        "advisories": advisories,
        "profile": "safest" if chosen else "alternative",
        "generated_at": iso(NOW),
    }


ROUTES: List[dict] = [_build_route(r) for r in _ROUTES]
ROUTES_BY_ID: Dict[str, dict] = {r["id"]: r for r in ROUTES}


# ------------------------------------------------------------- vehicles ----
# vehicle_id, cargo, route_id, progress, status, type, operator, speed
_VEHICLES = [
    ("SK-01-J-4471", "Medicines", "RTE-1001", 0.15, "en_route", "ambulance",
     "Sikkim Health Services", 34.0),
    ("SK-04-B-1120", "Construction materials", "RTE-1002", 0.60, "en_route", "truck",
     "NHIDCL Logistics", 28.0),
    ("AS-01-CC-7783", "Food supplies", "RTE-2007", 0.40, "en_route", "truck",
     "FCI Assam", 47.0),

    # --- added ---
    ("SK-06-A-2288", "Relief rations", "RTE-1003", 0.28, "en_route", "truck",
     "MDoNER Relief Fleet", 31.0),
    ("AS-25-C-9034", "Fuel", "RTE-2011", 0.72, "en_route", "truck",
     "IOCL Guwahati", 52.0),
    ("ML-05-K-6612", "Excavator", "RTE-3001", 0.52, "halted", "truck",
     "Meghalaya PWD", 0.0),
    ("NL-07-G-3345", "Rescue team", "RTE-4001", 0.45, "en_route", "relief",
     "NDRF 1st Battalion", 26.0),
    ("MZ-01-H-8890", "Patient transfer", "RTE-5001", 0.29, "en_route", "ambulance",
     "Mizoram Health Services", 33.0),
    ("TR-01-N-5567", "Civil supplies", "RTE-6001", 0.66, "en_route", "truck",
     "Tripura Civil Supplies", 49.0),
    ("AR-02-L-7712", "Clearance crew", "RTE-7001", 0.41, "idle", "relief",
     "SDRF Arunachal", 0.0),
]


def _build_vehicle(row) -> dict:
    vid, cargo, route_id, progress, status, vtype, operator, speed = row
    route = ROUTES_BY_ID[route_id]
    coords = [tuple(c) for c in route["geometry"]["coordinates"]]
    (lng, lat), heading = geo.interpolate(coords, progress)
    remaining_km = route["distance_km"] * (1 - progress)
    seg_id = min(
        route["segments"],
        key=lambda s: min(
            geo.haversine_km((lng, lat), tuple(c))
            for c in SEGMENTS_BY_ID[s]["geometry"]["coordinates"]
        ),
    )
    return {
        # --- contract fields ---
        "vehicle_id": vid,
        "cargo": cargo,
        "route_id": route_id,
        "progress": round(progress, 4),
        "status": status,
        # --- backend additions ---
        "type": vtype,
        "operator": operator,
        "state": SEGMENTS_BY_ID[seg_id]["state"],
        "lat": round(lat, 6),
        "lng": round(lng, 6),
        "heading": round(heading, 1),
        "speed_kmph": speed,
        "segment_id": seg_id,
        "distance_remaining_km": round(remaining_km, 2),
        "eta_min": round(remaining_km / speed * 60) if speed > 0 else None,
        "last_ping": iso(NOW),
        "geometry": geo.point((lng, lat)),
    }


VEHICLES: List[dict] = [_build_vehicle(v) for v in _VEHICLES]


# -------------------------------------------------------------- reports ----
# event_id, type, lat, lng, timestamp, photo, vehicle_id, state, severity,
# description, segment_id, status
_REPORTS = [
    ("EVT-88231", "landslide", 27.1935, 88.5142, "2026-08-24T06:42:11+05:30",
     "/mock-data/photos/evt-88231.jpg", "SK-01-J-4471", "Sikkim", "critical",
     "Boulders and mud across the carriageway, roughly 30 m wide. Cannot pass.",
     "SEG-SK-NH10-001", "verified"),
    ("EVT-88245", "road_damage", 27.2701, 88.5416, "2026-08-24T09:15:03+05:30",
     "/mock-data/photos/evt-88245.jpg", "SK-04-B-1120", "Sikkim", "medium",
     "Surface cracking and subsidence on the uphill lane.",
     "SEG-SK-NH10-002", "verified"),
    ("EVT-90114", "flooding", 26.6541, 92.8188, "2026-08-24T17:58:40+05:30",
     "/mock-data/photos/evt-90114.jpg", "AS-01-CC-7783", "Assam", "high",
     "Knee-deep water over about 200 m. Passable for trucks, not for cars.",
     "SEG-AS-NH715-007", "verified"),
    ("EVT-90152", "traffic_block", 26.1461, 91.7096, "2026-08-25T07:22:57+05:30",
     "/mock-data/photos/evt-90152.jpg", "AS-25-C-9034", "Assam", "low",
     "Stalled goods vehicle blocking the left lane at Jalukbari.",
     "SEG-AS-NH27-014", "resolved"),

    # --- added ---
    ("EVT-90188", "landslide", 25.1500, 92.4000, "2026-08-25T19:04:22+05:30",
     None, "ML-05-K-6612", "Meghalaya", "critical",
     "Slope failure has taken out both lanes. Two trucks stranded beyond it.",
     "SEG-ML-NH6-018", "verified"),
    ("EVT-90203", "road_damage", 27.7500, 94.1500, "2026-08-26T03:11:09+05:30",
     None, "AR-02-L-7712", "Arunachal Pradesh", "critical",
     "Road completely gone at the hairpin. No vehicle movement possible.",
     "SEG-AR-NH13-004", "pending"),
]


def _build_report(row) -> dict:
    (event_id, rtype, lat, lng, timestamp, photo, vehicle_id, state,
     severity, description, segment_id, status) = row
    return {
        # --- contract fields ---
        "event_id": event_id,
        "type": rtype,
        "lat": lat,
        "lng": lng,
        "timestamp": timestamp,
        "photo": photo,
        "vehicle_id": vehicle_id,
        "state": state,
        # --- backend additions ---
        "id": f"RPT-{event_id.split('-')[1]}",
        "severity": severity,
        "description": description,
        "segment_id": segment_id,
        "reporter": vehicle_id,
        "status": status,
        "created_at": timestamp,
        "geometry": geo.point((lng, lat)),
    }


REPORTS: List[dict] = [_build_report(r) for r in _REPORTS]


# --------------------------------------------------------------- alerts ----
# id, event, severity, recipients, lang, status, type, title, message, hours_ago
_ALERTS = [
    ("ALT-5001", "EVT-88231", "critical",
     ["fleet-ops@ner-logistics.in", "SK-01-J-4471", "sdm-rangpo@sikkim.gov.in"],
     "en", "sent", "landslide", "Landslide blocking NH-10 in the Teesta corridor",
     "Debris across both lanes between Rangpo and Singtam. Clearance crews on "
     "site; no through movement expected before 18:00 IST.", 30),
    ("ALT-5002", "EVT-88245", "medium", ["SK-04-B-1120", "SK-06-A-2288"],
     "ne", "acknowledged", "road_damage", "Surface damage near Ranipool",
     "Subsidence on the uphill lane. Single-file working; reduce to 20 km/h.", 27),
    ("ALT-5003", "EVT-90114", "high",
     ["fleet-ops@ner-logistics.in", "AS-01-CC-7783"], "as", "pending", "flooding",
     "NH-715 Balipara approach under water",
     "Standing water over 200 m of carriageway. Light vehicles should divert.", 18),
    ("ALT-5004", "EVT-90152", "low", ["AS-25-C-9034"], "hi", "failed",
     "traffic_block", "Lane blocked at Jalukbari",
     "Stalled goods vehicle on the left lane. Recovery under way.", 5),

    # --- added ---
    ("ALT-5005", "EVT-90188", "critical",
     ["fleet-ops@ner-logistics.in", "ML-05-K-6612", "dc-jowai@meghalaya.gov.in"],
     "en", "sent", "landslide", "NH-6 Jowai - Badarpur closed by landslide",
     "Corridor severed. Divert all relief movement via the NH-27 / Silchar "
     "approach until further notice.", 16),
    ("ALT-5006", "EVT-90203", "critical",
     ["fleet-ops@ner-logistics.in", "AR-02-L-7712"], "en", "pending", "landslide",
     "Trans-Arunachal NH-13 cut off at Ziro - Daporijo",
     "Slope failure at km 47. Relief movement suspended; use the Along axis.", 9),
]


def _build_alert(row) -> dict:
    (aid, event, severity, recipients, lang, status, atype, title,
     message, hours_ago) = row
    report = next((r for r in REPORTS if r["event_id"] == event), None)
    issued = NOW - timedelta(hours=hours_ago)
    lat = report["lat"] if report else 26.2006
    lng = report["lng"] if report else 92.9376
    return {
        # --- contract fields ---
        "id": aid,
        "event": event,
        "severity": severity,
        "recipients": recipients,
        "lang": lang,
        "status": status,
        # --- backend additions ---
        "type": atype,
        "title": title,
        "message": message,
        "state": report["state"] if report else None,
        "segment_id": report["segment_id"] if report else None,
        "lat": lat,
        "lng": lng,
        "radius_km": 20.0,
        "source": "report",
        "active": status in {"pending", "sent", "acknowledged"},
        "issued_at": iso(issued),
        "expires_at": iso(issued + timedelta(hours=24)),
        "geometry": geo.point((lng, lat)),
    }


ALERTS: List[dict] = [_build_alert(a) for a in _ALERTS]
