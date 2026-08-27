"""Runtime configuration, read from the environment (.env is loaded if present)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

BASE_DIR = Path(__file__).resolve().parent.parent  # ner-platform/backend

try:  # python-dotenv is in requirements, but never make it fatal
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / ".env")
except Exception:  # pragma: no cover
    pass


def _csv(name: str, default: str) -> List[str]:
    return [v.strip() for v in os.getenv(name, default).split(",") if v.strip()]


def _flag(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def _normalize_dsn(url: str) -> str:
    """Force the psycopg3 driver.

    The repo-root docker-compose.yml sets `postgresql://...`, which SQLAlchemy
    resolves to psycopg2 -- a package we deliberately do not install (we use
    `psycopg[binary]`, i.e. psycopg3). Without this the shared stack dies with
    ModuleNotFoundError instead of connecting.
    """
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    if url.startswith("postgres://"):  # the old Heroku-style scheme
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    return url


@dataclass(frozen=True)
class Settings:
    app_name: str = "NER Road Accessibility API"
    version: str = "0.1.0"

    # PostGIS. Falls back to the in-memory seed store when unreachable.
    database_url: str = _normalize_dsn(os.getenv(
        "DATABASE_URL", "postgresql+psycopg://ner:ner@localhost:5432/ner"
    ))
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # The dashboard (3000) and driver PWA (3001) both call this API from a browser.
    cors_origins: List[str] = field(
        default_factory=lambda: _csv(
            "CORS_ORIGINS", "http://localhost:3000,http://localhost:3001"
        )
    )

    # Seed PostGIS with the sample corridors on startup when the tables are empty.
    auto_seed: bool = _flag("AUTO_SEED", True)
    # Serve the in-memory seed when PostGIS is unavailable, so /docs always works.
    allow_memory_fallback: bool = _flag("ALLOW_MEMORY_FALLBACK", True)

    # A container-started Postgres accepts connections a few seconds after the
    # healthcheck first passes, so retry before giving up on it.
    # Pull real rainfall from Open-Meteo into road_segments on this cadence.
    # Off means the seeded values stand, and every risk score is fiction.
    weather_refresh_enabled: bool = _flag("WEATHER_REFRESH_ENABLED", True)
    weather_refresh_minutes: int = int(os.getenv("WEATHER_REFRESH_MINUTES", "30"))

    db_connect_retries: int = int(os.getenv("DB_CONNECT_RETRIES", "10"))
    db_connect_delay: float = float(os.getenv("DB_CONNECT_DELAY", "1.5"))

    ws_broadcast_seconds: float = float(os.getenv("WS_BROADCAST_SECONDS", "2.0"))
    ws_time_scale: float = float(os.getenv("WS_TIME_SCALE", "60.0"))


settings = Settings()


def masked_database_url() -> str:
    """DSN with the password removed, safe to log or return from /health."""
    url = settings.database_url
    if "@" not in url or "://" not in url:
        return url
    scheme, rest = url.split("://", 1)
    creds, host = rest.rsplit("@", 1)
    user = creds.split(":", 1)[0]
    return f"{scheme}://{user}:***@{host}"
