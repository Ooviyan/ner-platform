"""SQLAlchemy + GeoAlchemy2 tables backing the API (PostGIS, SRID 4326).

Column names follow the shared ../mock-data contract (`risk`, `accessibility`,
`lng`, `eta_min`, `vehicle_id`, `event`) so the JSON the API returns is a direct
projection of these rows. Columns the contract does not define are additions the
backend needs, and are safe to ignore downstream.
"""

from __future__ import annotations

from datetime import datetime, timezone

from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class RoadSegment(Base):
    """One stretch of road: the unit everything else is scored and joined against."""

    __tablename__ = "road_segments"

    # --- contract ---
    id = mapped_column(String(64), primary_key=True)
    name = mapped_column(String(255), nullable=False)
    risk = mapped_column(Float, default=0.0, index=True)
    accessibility = mapped_column(Integer, default=100)
    status = mapped_column(String(16), default="open", index=True)
    geom = mapped_column(Geometry("LINESTRING", srid=4326), nullable=False)

    # --- backend additions ---
    state = mapped_column(String(64), nullable=False, index=True)
    state_code = mapped_column(String(4))
    highway = mapped_column(String(32), index=True)
    road_class = mapped_column(String(64))
    length_km = mapped_column(Float, nullable=False, default=0.0)
    surface = mapped_column(String(32))
    lanes = mapped_column(Integer)
    elevation_m = mapped_column(Float)
    slope_deg = mapped_column(Float)
    rainfall_mm_24h = mapped_column(Float, default=0.0)
    rainfall_mm_72h = mapped_column(Float, default=0.0)
    risk_band = mapped_column(String(16), default="low", index=True)
    source = mapped_column(String(32), default="seed", index=True)
    osm_id = mapped_column(String(64))
    updated_at = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


Index("ix_road_segments_geom", RoadSegment.geom, postgresql_using="gist")


class Route(Base):
    """A computed origin->destination path over road_segments."""

    __tablename__ = "routes"

    # --- contract ---
    id = mapped_column(String(64), primary_key=True)
    origin = mapped_column(String(128))
    destination = mapped_column(String(128))
    chosen = mapped_column(Boolean, default=False)
    eta_min = mapped_column(Integer, default=0)
    delay_min = mapped_column(Integer, default=0)
    risk = mapped_column(Float, default=0.0)
    # Ordered segment ids, JSON-encoded.
    segment_ids = mapped_column(Text, default="[]")

    # --- backend additions ---
    origin_lat = mapped_column(Float)
    origin_lng = mapped_column(Float)
    destination_lat = mapped_column(Float)
    destination_lng = mapped_column(Float)
    distance_km = mapped_column(Float, default=0.0)
    risk_band = mapped_column(String(16), default="low")
    accessibility = mapped_column(Integer, default=100)
    passable = mapped_column(Boolean, default=True)
    closed_segments = mapped_column(Text, default="[]")
    advisories = mapped_column(Text, default="[]")
    profile = mapped_column(String(16), default="safest")
    generated_at = mapped_column(DateTime(timezone=True), default=utcnow)
    geom = mapped_column(Geometry("LINESTRING", srid=4326), nullable=False)


Index("ix_routes_geom", Route.geom, postgresql_using="gist")


class Vehicle(Base):
    """Fleet vehicle with its last known GPS fix. Keyed by registration."""

    __tablename__ = "vehicles"

    # --- contract ---
    vehicle_id = mapped_column(String(64), primary_key=True)
    cargo = mapped_column(String(128))
    route_id = mapped_column(String(64), ForeignKey("routes.id"), nullable=True)
    progress = mapped_column(Float, default=0.0)
    status = mapped_column(String(16), default="idle", index=True)

    # --- backend additions ---
    type = mapped_column(String(32), index=True)
    operator = mapped_column(String(128))
    state = mapped_column(String(64), index=True)
    lat = mapped_column(Float, nullable=False)
    lng = mapped_column(Float, nullable=False)
    heading = mapped_column(Float, default=0.0)
    speed_kmph = mapped_column(Float, default=0.0)
    segment_id = mapped_column(String(64), ForeignKey("road_segments.id"), nullable=True)
    distance_remaining_km = mapped_column(Float)
    eta_min = mapped_column(Integer, nullable=True)
    last_ping = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    geom = mapped_column(Geometry("POINT", srid=4326), nullable=False)


Index("ix_vehicles_geom", Vehicle.geom, postgresql_using="gist")


class Incident(Base):
    """A driver-filed report. Table is `incidents`; the API calls them reports."""

    __tablename__ = "incidents"

    # --- contract ---
    # The driver PWA generates event_id offline; unique so a replayed queue de-dupes.
    event_id = mapped_column(String(128), primary_key=True)
    type = mapped_column(String(32), index=True)
    lat = mapped_column(Float, nullable=False)
    lng = mapped_column(Float, nullable=False)
    timestamp = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    photo = mapped_column(Text, nullable=True)
    vehicle_id = mapped_column(String(64), nullable=True, index=True)
    state = mapped_column(String(64), index=True)

    # --- backend additions ---
    id = mapped_column(String(64), unique=True)
    severity = mapped_column(String(16), default="medium", index=True)
    description = mapped_column(Text)
    segment_id = mapped_column(String(64), ForeignKey("road_segments.id"), nullable=True)
    reporter = mapped_column(String(128), nullable=True)
    status = mapped_column(String(16), default="pending", index=True)
    created_at = mapped_column(DateTime(timezone=True), default=utcnow)
    geom = mapped_column(Geometry("POINT", srid=4326), nullable=False)


Index("ix_incidents_geom", Incident.geom, postgresql_using="gist")


class Alert(Base):
    """Dispatch record for an advisory: who was told, in what language, and did it land."""

    __tablename__ = "alerts"

    # --- contract ---
    id = mapped_column(String(64), primary_key=True)
    event = mapped_column(String(128), nullable=True, index=True)
    severity = mapped_column(String(16), default="medium", index=True)
    # Recipient list (emails and vehicle registrations), JSON-encoded.
    recipients = mapped_column(Text, default="[]")
    lang = mapped_column(String(8), default="en")
    status = mapped_column(String(16), default="pending", index=True)

    # --- backend additions ---
    type = mapped_column(String(32), index=True)
    title = mapped_column(String(255))
    message = mapped_column(Text)
    state = mapped_column(String(64), index=True)
    segment_id = mapped_column(String(64), ForeignKey("road_segments.id"), nullable=True)
    lat = mapped_column(Float, nullable=False)
    lng = mapped_column(Float, nullable=False)
    radius_km = mapped_column(Float, default=20.0)
    source = mapped_column(String(32), default="manual")
    active = mapped_column(Boolean, default=True, index=True)
    issued_at = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at = mapped_column(DateTime(timezone=True), nullable=True)
    geom = mapped_column(Geometry("POINT", srid=4326), nullable=False)


Index("ix_alerts_geom", Alert.geom, postgresql_using="gist")
