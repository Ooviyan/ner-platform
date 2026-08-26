"""Pydantic request/response models.

Field names are the shared ../mock-data contract. Anything marked "backend
addition" is extra information the API supplies on top; a client written against
the contract can ignore those fields entirely.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

Geometry = Dict[str, Any]

Severity = Literal["low", "medium", "high", "critical"]
SegmentStatus = Literal["open", "restricted", "closed"]
VehicleStatus = Literal["en_route", "idle", "halted", "offline"]
AlertStatus = Literal["pending", "sent", "acknowledged", "failed"]
ReportStatus = Literal["pending", "verified", "resolved", "rejected"]
ReportType = Literal[
    "landslide", "flooding", "road_damage", "traffic_block",
    "accident", "bridge_damage", "snow", "sos", "other",
]
Language = Literal["en", "as", "bn", "hi", "ne", "lus", "mni"]


class Segment(BaseModel):
    # --- contract ---
    id: str = Field(examples=["SEG-SK-NH10-001"])
    name: str
    risk: float = Field(ge=0.0, le=1.0, description="0-1; higher is more dangerous.")
    accessibility: int = Field(ge=0, le=100, description="0 impassable, 100 fully usable.")
    status: SegmentStatus
    geometry: Geometry
    # --- backend additions ---
    state: Optional[str] = None
    state_code: Optional[str] = None
    highway: Optional[str] = None
    road_class: Optional[str] = None
    length_km: Optional[float] = None
    surface: Optional[str] = None
    lanes: Optional[int] = None
    elevation_m: Optional[float] = None
    slope_deg: Optional[float] = None
    rainfall_mm_24h: Optional[float] = None
    rainfall_mm_72h: Optional[float] = None
    risk_band: Optional[Severity] = None
    source: Optional[str] = None
    updated_at: Optional[str] = None


class Point(BaseModel):
    lng: float
    lat: float


class Route(BaseModel):
    # --- contract ---
    id: str = Field(examples=["RTE-1001"])
    origin: str = Field(examples=["Siliguri, West Bengal"])
    destination: str = Field(examples=["Gangtok, Sikkim"])
    chosen: bool = Field(description="True for the recommended route.")
    eta_min: int
    delay_min: int = Field(description="Minutes lost to risk vs a clear run.")
    risk: float
    segments: List[str] = []
    # --- backend additions ---
    geometry: Optional[Geometry] = None
    origin_point: Optional[Point] = None
    destination_point: Optional[Point] = None
    distance_km: Optional[float] = None
    risk_band: Optional[Severity] = None
    accessibility: Optional[int] = None
    passable: Optional[bool] = None
    closed_segments: List[str] = []
    advisories: List[str] = []
    profile: Optional[str] = None
    generated_at: Optional[str] = None
    alternatives: List["RouteSummary"] = []


class RouteSummary(BaseModel):
    id: str
    eta_min: int
    delay_min: int
    risk: float
    risk_band: Optional[Severity] = None
    passable: Optional[bool] = None
    distance_km: Optional[float] = None


class Vehicle(BaseModel):
    # --- contract ---
    vehicle_id: str = Field(examples=["SK-01-J-4471"])
    cargo: Optional[str] = None
    route_id: Optional[str] = None
    progress: float = Field(ge=0.0, le=1.0)
    status: VehicleStatus
    # --- backend additions ---
    type: Optional[str] = None
    operator: Optional[str] = None
    state: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    heading: Optional[float] = None
    speed_kmph: Optional[float] = None
    segment_id: Optional[str] = None
    distance_remaining_km: Optional[float] = None
    eta_min: Optional[int] = None
    last_ping: Optional[str] = None
    geometry: Optional[Geometry] = None


class ReportCreate(BaseModel):
    """What the driver PWA posts.

    `event_id` is generated on the device so a queued report replayed after the
    driver comes back online is recognised instead of duplicated.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "event_id": "EVT-90231",
                "type": "landslide",
                "lat": 27.1935,
                "lng": 88.5142,
                "severity": "critical",
                "description": "Mud and boulders across both lanes, cannot pass.",
                "vehicle_id": "SK-01-J-4471",
                "photo": "/uploads/evt-90231.jpg",
                "timestamp": "2026-08-26T11:42:11+05:30",
            }
        },
    )

    event_id: Optional[str] = Field(
        default=None, description="Client-generated id; replays are de-duplicated."
    )
    type: ReportType
    lat: float = Field(ge=-90, le=90)
    # `lon` is accepted as an alias so a client using the GeoJSON spelling works.
    lng: float = Field(ge=-180, le=180, alias="lng", validation_alias="lng")
    timestamp: Optional[str] = Field(
        default=None, description="When the driver filed it, ISO-8601. Defaults to now."
    )
    photo: Optional[str] = None
    vehicle_id: Optional[str] = None
    severity: Severity = "medium"
    description: Optional[str] = None
    reporter: Optional[str] = None


class Report(BaseModel):
    # --- contract ---
    event_id: str
    type: str
    lat: float
    lng: float
    timestamp: Optional[str] = None
    photo: Optional[str] = None
    vehicle_id: Optional[str] = None
    state: Optional[str] = None
    # --- backend additions ---
    id: Optional[str] = None
    severity: Optional[Severity] = None
    description: Optional[str] = None
    segment_id: Optional[str] = None
    reporter: Optional[str] = None
    status: ReportStatus = "pending"
    created_at: Optional[str] = None
    geometry: Optional[Geometry] = None


class Alert(BaseModel):
    # --- contract ---
    id: str = Field(examples=["ALT-5001"])
    event: Optional[str] = Field(default=None, description="event_id of the report behind it.")
    severity: Severity
    recipients: List[str] = Field(
        default=[], description="Emails and vehicle registrations to notify."
    )
    lang: Language = "en"
    status: AlertStatus = "pending"
    # --- backend additions ---
    type: Optional[str] = None
    title: Optional[str] = None
    message: Optional[str] = None
    state: Optional[str] = None
    segment_id: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    radius_km: Optional[float] = None
    source: Optional[str] = None
    active: Optional[bool] = None
    issued_at: Optional[str] = None
    expires_at: Optional[str] = None
    geometry: Optional[Geometry] = None


class AlertCreate(BaseModel):
    severity: Severity = "medium"
    title: str
    message: Optional[str] = None
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    event: Optional[str] = None
    recipients: List[str] = []
    lang: Language = "en"
    type: str = "advisory"
    segment_id: Optional[str] = None
    radius_km: float = 20.0
    source: str = "manual"
    expires_at: Optional[str] = None


class StateInfo(BaseModel):
    slug: str
    name: str
    code: str
    capital: str
    center: List[float]
    bbox: List[float]
    segments: int


class Health(BaseModel):
    status: str
    version: str
    database: Dict[str, Any]
    counts: Dict[str, int]


class VehicleStream(BaseModel):
    """One frame pushed over WS /ws/vehicles."""

    type: Literal["vehicle_positions", "snapshot"]
    timestamp: str
    tick: int
    vehicles: List[Vehicle]


Route.model_rebuild()
