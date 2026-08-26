"""PostGIS engine/session wiring.

The API never hard-fails on a missing database: if PostGIS is unreachable we log
it once and serve the in-memory seed instead, so `/docs` and every GET still work
on a laptop with nothing running. `db_status()` tells you which mode you are in.
"""

from __future__ import annotations

import logging
import time
from typing import Iterator, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.config import masked_database_url, settings
from app.models import Base

log = logging.getLogger("ner.db")

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    future=True,
    connect_args={"connect_timeout": 5} if "psycopg" in settings.database_url else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

_state = {"available": False, "error": None, "postgis": None}


def _connect_once() -> str:
    """Enable PostGIS and create the tables. Returns the PostGIS version."""
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        version = conn.execute(text("SELECT PostGIS_Lib_Version()")).scalar()
    Base.metadata.create_all(engine)
    return version


def init_db(retries: Optional[int] = None, delay: Optional[float] = None) -> bool:
    """Connect to PostGIS, retrying while it finishes starting up.

    Postgres in a container accepts TCP connections a little after its
    healthcheck first passes, so a single attempt races the database and would
    drop us onto the in-memory seed for the whole process lifetime.
    """
    attempts = settings.db_connect_retries if retries is None else retries
    pause = settings.db_connect_delay if delay is None else delay
    message = "not attempted"

    for attempt in range(1, max(attempts, 1) + 1):
        try:
            version = _connect_once()
        except SQLAlchemyError as exc:
            message = str(exc.__cause__ or exc).strip().splitlines()[0]
            if attempt < attempts:
                log.info(
                    "PostGIS not ready (attempt %d/%d): %s - retrying in %.1fs",
                    attempt, attempts, message, pause,
                )
                time.sleep(pause)
                continue
        else:
            _state.update(available=True, error=None, postgis=version)
            log.info("PostGIS %s ready at %s", version, masked_database_url())
            return True

    _state.update(available=False, error=message, postgis=None)
    if not settings.allow_memory_fallback:
        raise RuntimeError(f"PostGIS unavailable after {attempts} attempts: {message}")
    log.warning(
        "PostGIS unavailable after %d attempts (%s) - serving the in-memory seed. "
        "Start it with: docker run --name ner-db -e POSTGRES_PASSWORD=ner "
        "-e POSTGRES_DB=ner -p 5432:5432 -d postgis/postgis",
        attempts, message,
    )
    return False


def db_available() -> bool:
    return _state["available"]


def db_status() -> dict:
    return {
        "connected": _state["available"],
        "url": masked_database_url(),
        "postgis_version": _state["postgis"],
        "error": _state["error"],
        "mode": "postgis" if _state["available"] else "memory-seed",
    }


def get_db() -> Iterator[Optional[Session]]:
    """FastAPI dependency. Yields a Session, or None when running on the seed."""
    if not _state["available"]:
        yield None
        return
    session = SessionLocal()
    try:
        yield session
    except SQLAlchemyError:
        session.rollback()
        # A mid-request DB failure should degrade, not 500 the whole platform.
        _state.update(available=False)
        raise
    finally:
        session.close()
