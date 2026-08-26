"""Named places used to resolve ?from= / ?to= when the caller passes a town name."""

from __future__ import annotations

from typing import Dict, Optional, Tuple

from app.geo import Coord
from app.ner_states import NER_STATES

PLACES: Dict[str, Coord] = {
    # Sikkim / North Bengal gateway
    "siliguri": (88.4275, 26.7271),
    "sevoke": (88.4720, 26.9010),
    "rangpo": (88.5347, 27.1750),
    "singtam": (88.4986, 27.2350),
    "gangtok": (88.6138, 27.3314),
    "nathu la": (88.8300, 27.3870),
    # Assam
    "guwahati": (91.7362, 26.1445),
    "dispur": (91.7898, 26.1433),
    "nagaon": (92.6840, 26.3464),
    "jorhat": (94.2037, 26.7509),
    "dibrugarh": (94.9120, 27.4728),
    "goalpara": (90.6260, 26.1760),
    "silchar": (92.7789, 24.8333),
    # Meghalaya
    "shillong": (91.8933, 25.5788),
    "jowai": (92.2000, 25.4500),
    "badarpur": (92.5900, 24.8700),
    # Nagaland
    "dimapur": (93.7278, 25.9063),
    "kohima": (94.1100, 25.6751),
    "mao gate": (94.1200, 25.3900),
    # Manipur
    "senapati": (94.0700, 25.2700),
    "imphal": (93.9368, 24.8170),
    # Mizoram
    "aizawl": (92.7176, 23.7271),
    "kolasib": (92.6790, 24.2260),
    # Tripura
    "agartala": (91.2868, 23.8315),
    "kumarghat": (92.0300, 24.1300),
    "churaibari": (92.3500, 24.4700),
    # Arunachal Pradesh
    "itanagar": (93.6053, 27.0844),
    "banderdewa": (93.7900, 27.0500),
    "ziro": (93.8300, 27.5400),
    "daporijo": (94.2200, 27.9800),
}

# State names resolve to their centroid, so ?from=Assam still works.
for _slug, _meta in NER_STATES.items():
    PLACES.setdefault(_meta["name"].lower(), tuple(_meta["center"]))


def resolve(value: str) -> Optional[Tuple[Coord, str]]:
    """Resolve "lat,lon" or a place name to ((lon, lat), display name)."""
    if not value:
        return None
    raw = value.strip()
    if "," in raw:
        a, b = raw.split(",", 1)
        try:
            lat, lon = float(a), float(b)
        except ValueError:
            pass
        else:
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                return (lon, lat), f"{lat:.4f},{lon:.4f}"
    key = raw.lower()
    if key in PLACES:
        return PLACES[key], raw.title()
    # Tolerate "Gangtok, Sikkim" style input by trying the leading token.
    head = key.split(",")[0].strip()
    if head in PLACES:
        return PLACES[head], head.title()
    return None
