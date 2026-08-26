"""Test configuration.

This suite asserts the API contract against the deterministic seed in
`app/seed.py`, so it must not touch a real database -- a developer with the
compose stack running has PostGIS on localhost:5432 and, once `load_ner.py` has
run, thousands of OSM rows that would break every count assertion.

Pointing DATABASE_URL at a closed port (and disabling the connect retry) makes
the run hermetic and fast: the API falls back to the in-memory seed exactly as it
does on a laptop with nothing running.

These are set before `app.config` is imported -- pytest loads conftest first.
"""

from __future__ import annotations

import os

os.environ["DATABASE_URL"] = "postgresql+psycopg://ner:ner@127.0.0.1:1/ner_no_db"
os.environ["ALLOW_MEMORY_FALLBACK"] = "true"
os.environ["DB_CONNECT_RETRIES"] = "1"
os.environ["DB_CONNECT_DELAY"] = "0"
os.environ["AUTO_SEED"] = "false"
# Keep the websocket tests quick without making the movement assertions flaky.
os.environ.setdefault("WS_BROADCAST_SECONDS", "0.15")
os.environ.setdefault("WS_TIME_SCALE", "400")
