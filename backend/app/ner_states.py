"""The eight North East India states, with the metadata the loader and API need.

`osm_query` is what osmnx passes to Nominatim; `bbox` is a cheap fallback used for
sanity-checking geometry and for centring the dashboard map per state.
"""

from __future__ import annotations

from typing import Dict, List

NER_STATES: Dict[str, dict] = {
    "arunachal_pradesh": {
        "name": "Arunachal Pradesh",
        "code": "AR",
        "osm_query": "Arunachal Pradesh, India",
        "capital": "Itanagar",
        "center": [94.7278, 28.2180],
        "bbox": [91.5606, 26.6300, 97.4026, 29.4519],
    },
    "assam": {
        "name": "Assam",
        "code": "AS",
        "osm_query": "Assam, India",
        "capital": "Dispur",
        "center": [92.9376, 26.2006],
        "bbox": [89.6867, 24.1266, 96.0257, 27.9720],
    },
    "manipur": {
        "name": "Manipur",
        "code": "MN",
        "osm_query": "Manipur, India",
        "capital": "Imphal",
        "center": [93.9063, 24.6637],
        "bbox": [92.9700, 23.8300, 94.7800, 25.6800],
    },
    "meghalaya": {
        "name": "Meghalaya",
        "code": "ML",
        "osm_query": "Meghalaya, India",
        "capital": "Shillong",
        "center": [91.3662, 25.4670],
        "bbox": [89.8200, 25.0300, 92.8000, 26.1200],
    },
    "mizoram": {
        "name": "Mizoram",
        "code": "MZ",
        "osm_query": "Mizoram, India",
        "capital": "Aizawl",
        "center": [92.9376, 23.1645],
        "bbox": [92.1500, 21.9400, 93.4500, 24.5200],
    },
    "nagaland": {
        "name": "Nagaland",
        "code": "NL",
        "osm_query": "Nagaland, India",
        "capital": "Kohima",
        "center": [94.5624, 26.1584],
        "bbox": [93.3300, 25.2000, 95.2500, 27.0400],
    },
    "sikkim": {
        "name": "Sikkim",
        "code": "SK",
        "osm_query": "Sikkim, India",
        "capital": "Gangtok",
        "center": [88.5122, 27.5330],
        "bbox": [88.0060, 27.0800, 88.9200, 28.1300],
    },
    "tripura": {
        "name": "Tripura",
        "code": "TR",
        "osm_query": "Tripura, India",
        "capital": "Agartala",
        "center": [91.9882, 23.9408],
        "bbox": [91.0900, 22.9400, 92.3400, 24.5300],
    },
}

# Display name -> slug, so callers may pass either "Sikkim" or "sikkim".
_BY_NAME = {meta["name"].lower(): slug for slug, meta in NER_STATES.items()}
_BY_CODE = {meta["code"].lower(): slug for slug, meta in NER_STATES.items()}


def normalize_state(value: str) -> str | None:
    """Return the canonical slug for a state name, slug or 2-letter code."""
    if not value:
        return None
    key = value.strip().lower().replace(" ", "_").replace("-", "_")
    if key in NER_STATES:
        return key
    flat = key.replace("_", " ")
    if flat in _BY_NAME:
        return _BY_NAME[flat]
    if key in _BY_CODE:
        return _BY_CODE[key]
    return None


def resolve_states(values: List[str]) -> List[str]:
    """Expand a --states argument into a list of slugs. "all" means all eight."""
    if not values:
        return []
    if any(v.strip().lower() == "all" for v in values):
        return list(NER_STATES)
    resolved: List[str] = []
    for value in values:
        for part in value.split(","):
            slug = normalize_state(part)
            if slug is None:
                raise ValueError(
                    f"unknown state {part.strip()!r}; "
                    f"choose from: {', '.join(NER_STATES)} or 'all'"
                )
            if slug not in resolved:
                resolved.append(slug)
    return resolved


def state_name(slug: str) -> str:
    return NER_STATES[slug]["name"]
