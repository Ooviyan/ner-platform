#!/usr/bin/env python
"""Verify the API still honours the shared ../mock-data contract.

`mock-data/` is owned by all four of us -- its README requires agreement from
everyone before a field name or type changes -- so this script *checks* against
it and never writes to it. (An earlier version of this file generated those
files; that was wrong and is why this one only reads.)

For every record in ../mock-data it asserts the API returns a record with the
same id and byte-identical values for every contract field. Extra fields the
backend adds are allowed; missing or changed contract fields are failures.

    python check_contract.py                  # against the in-memory seed
    python check_contract.py --url http://localhost:8000
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

from app.config import BASE_DIR

def _find_mock_dir() -> Path:
    """../mock-data locally; /app/mock-data under the repo-root compose mount."""
    for candidate in (BASE_DIR.parent / "mock-data", BASE_DIR / "mock-data"):
        if candidate.is_dir():
            return candidate
    return BASE_DIR.parent / "mock-data"


MOCK_DIR = _find_mock_dir()

# file, API path, key field.
#
# /segments is queried with scored=false. With scoring on, `risk` and
# `accessibility` are what the ML layer computes -- they SHOULD differ from the
# fixture, and freezing them would mean the model could never change a score.
# What this script proves is that the API can still produce exactly the agreed
# contract, field for field, which is the guarantee the frontends actually need.
CHECKS = [
    ("segments.json", "/segments?scored=false", "id"),
    ("routes.json", "/routes?recompute=false", "id"),
    ("vehicles.json", "/vehicles", "vehicle_id"),
    ("reports.json", "/reports", "event_id"),
    ("alerts.json", "/alerts", "id"),
]

# Fields the simulator legitimately moves on every tick.
LIVE_FIELDS = {"progress", "status"}


def _from_api(url: str, path: str) -> list:
    # 1000 is the lowest per-endpoint cap; asking for more is a 422.
    joiner = "&" if "?" in path else "?"
    with urllib.request.urlopen(f"{url}{path}{joiner}limit=1000", timeout=15) as response:
        if response.status != 200:
            raise SystemExit(f"{path} returned HTTP {response.status}")
        payload = json.load(response)
    if not isinstance(payload, list):
        raise SystemExit(f"{path} did not return a list: {payload!r}")
    return payload


def _from_seed(path: str) -> list:
    from app import seed
    return {
        "/segments?scored=false": seed.SEGMENTS,
        "/routes?recompute=false": seed.ROUTES,
        "/segments": seed.SEGMENTS, "/routes": seed.ROUTES,
        "/vehicles": seed.VEHICLES, "/reports": seed.REPORTS,
        "/alerts": seed.ALERTS,
    }[path]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", default=None,
                        help="Check a running API instead of the in-memory seed.")
    parser.add_argument("--mock-dir", default=str(MOCK_DIR))
    parser.add_argument("--allow-live-drift", action="store_true",
                        help="Ignore progress/status on vehicles (they move).")
    args = parser.parse_args()

    mock_dir = Path(args.mock_dir)
    if not mock_dir.exists():
        print(f"mock-data not found at {mock_dir}", file=sys.stderr)
        return 2

    failures = 0
    for filename, path, key in CHECKS:
        contract = json.loads((mock_dir / filename).read_text())
        live = _from_api(args.url, path) if args.url else _from_seed(path)
        index = {r[key]: r for r in live}
        print(f"--- {filename} ({len(contract)} contract records) ---")

        for record in contract:
            ident = record[key]
            got = index.get(ident)
            if got is None:
                print(f"  MISSING  {ident}")
                failures += 1
                continue
            skip = LIVE_FIELDS if (args.allow_live_drift and path == "/vehicles") else set()
            bad = [f for f, v in record.items() if f not in skip and got.get(f) != v]
            if bad:
                failures += len(bad)
                for f in bad:
                    print(f"  CHANGED  {ident}.{f}: "
                          f"contract={record[f]!r} api={got.get(f)!r}")
            else:
                print(f"  OK       {ident}")

    print()
    if failures:
        print(f"FAIL - {failures} contract violation(s). "
              f"mock-data is shared: agree the change with all four before editing it.")
        return 1
    print("PASS - the API is a strict superset of ../mock-data.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
