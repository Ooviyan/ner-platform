"""Simulated fleet movement for WS /ws/vehicles.

Vehicles advance along the geometry of the route they are assigned to. One shared
simulator instance drives both the WebSocket stream and GET /vehicles, so the
dashboard's map and its table never disagree.
"""

from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Set

from app import geo
from app.config import settings

log = logging.getLogger("ner.sim")

# Cruising speed a vehicle aims for on a segment of each risk level (km/h).
_TARGET_SPEED = {"low": 55.0, "medium": 42.0, "high": 26.0, "critical": 16.0}


IST = timezone(timedelta(hours=5, minutes=30))


def _iso_now() -> str:
    """IST, matching the timestamps in ../mock-data."""
    return datetime.now(IST).isoformat()


@dataclass
class VehicleState:
    vehicle: dict
    coords: List[geo.Coord]
    route_length_km: float
    segment_ids: List[str] = field(default_factory=list)
    direction: int = 1
    stopped_ticks: int = 0


class FleetSimulator:
    """Moves the seeded fleet along its routes and broadcasts each tick."""

    def __init__(self) -> None:
        self._vehicles: Dict[str, VehicleState] = {}
        self._clients: Set = set()
        self._task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        self.tick = 0
        self._closed_segments: Set[str] = set()
        self._on_tick = None

    # ------------------------------------------------------------- setup ---
    def load(self, vehicles: List[dict], routes: List[dict], segments: List[dict]) -> None:
        by_route = {r["id"]: r for r in routes}
        segment_status = {s["id"]: s for s in segments}
        self._closed_segments = {
            s["id"] for s in segments if s["status"] == "closed"
        }
        self._segments = segment_status
        self._vehicles = {}
        for vehicle in vehicles:
            route = by_route.get(vehicle.get("route_id"))
            if not route:
                continue
            coords = geo.densify(
                [tuple(c) for c in route["geometry"]["coordinates"]], max_step_km=2.0
            )
            self._vehicles[vehicle["vehicle_id"]] = VehicleState(
                vehicle=dict(vehicle),
                coords=coords,
                route_length_km=route["distance_km"] or geo.line_length_km(coords),
                segment_ids=list(route["segments"]),
            )
        log.info("simulator loaded %d vehicles", len(self._vehicles))

    def set_tick_callback(self, callback) -> None:
        """Called with the position list after each tick, to persist it."""
        self._on_tick = callback

    # ------------------------------------------------------------- motion ---
    def _segment_for(self, state: VehicleState, position: geo.Coord) -> Optional[str]:
        if not state.segment_ids:
            return None
        return min(
            state.segment_ids,
            key=lambda sid: min(
                geo.haversine_km(position, tuple(c))
                for c in self._segments[sid]["geometry"]["coordinates"]
            ) if sid in self._segments else float("inf"),
        )

    def _advance(self, state: VehicleState, elapsed_hours: float) -> dict:
        vehicle = state.vehicle
        position, heading = geo.interpolate(state.coords, vehicle["progress"])
        segment_id = self._segment_for(state, position) or vehicle.get("segment_id")
        segment = self._segments.get(segment_id)
        band = segment["risk_band"] if segment else "medium"

        if segment_id in self._closed_segments:
            # Held at a blockage: stays put, reports stopped.
            vehicle.update(
                speed_kmph=0.0, status="halted", segment_id=segment_id,
                lat=round(position[1], 6), lng=round(position[0], 6),
                heading=round(heading, 1),
                geometry=geo.point(position), last_ping=_iso_now(),
            )
            return vehicle

        if vehicle["status"] == "idle":
            state.stopped_ticks += 1
            if state.stopped_ticks > 12:  # resume after a rest
                vehicle["status"] = "en_route"
                state.stopped_ticks = 0
        elif random.random() < 0.01:  # occasional halt, keeps the demo honest
            vehicle["status"] = "idle"

        if vehicle["status"] == "en_route":
            target = _TARGET_SPEED.get(band, 40.0)
            speed = max(8.0, min(target * 1.15, random.gauss(target, target * 0.08)))
            travelled = speed * elapsed_hours
            progress = vehicle["progress"] + state.direction * (
                travelled / max(state.route_length_km, 0.1)
            )
            if progress >= 1.0:
                progress, state.direction = 1.0, -1  # turn round and run it back
            elif progress <= 0.0:
                progress, state.direction = 0.0, 1
            vehicle["progress"] = round(progress, 5)
            vehicle["speed_kmph"] = round(speed, 1)
            position, heading = geo.interpolate(state.coords, vehicle["progress"])
            segment_id = self._segment_for(state, position) or segment_id
        else:
            vehicle["speed_kmph"] = 0.0

        remaining_fraction = (
            1.0 - vehicle["progress"] if state.direction > 0 else vehicle["progress"]
        )
        remaining = state.route_length_km * remaining_fraction
        speed = vehicle["speed_kmph"]
        vehicle.update(
            lat=round(position[1], 6),
            lng=round(position[0], 6),
            heading=round(heading if state.direction > 0 else (heading + 180) % 360, 1),
            segment_id=segment_id,
            state=self._segments[segment_id]["state"] if segment_id in self._segments
            else vehicle.get("state"),
            distance_remaining_km=round(remaining, 2),
            eta_min=round(remaining / speed * 60) if speed > 0 else None,
            last_ping=_iso_now(),
            geometry=geo.point(position),
        )
        return vehicle

    def step(self, elapsed_hours: float) -> List[dict]:
        self.tick += 1
        return [
            dict(self._advance(state, elapsed_hours))
            for state in self._vehicles.values()
        ]

    def snapshot(self) -> List[dict]:
        return [dict(state.vehicle) for state in self._vehicles.values()]

    def frame(self, vehicles: List[dict], kind: str = "vehicle_positions") -> dict:
        return {
            "type": kind,
            "timestamp": _iso_now(),
            "tick": self.tick,
            "vehicles": vehicles,
        }

    # -------------------------------------------------------- websocket ---
    async def connect(self, websocket) -> None:
        async with self._lock:
            self._clients.add(websocket)
        await websocket.send_json(self.frame(self.snapshot(), kind="snapshot"))

    async def disconnect(self, websocket) -> None:
        async with self._lock:
            self._clients.discard(websocket)

    @property
    def client_count(self) -> int:
        return len(self._clients)

    async def _broadcast(self, payload: dict) -> None:
        async with self._lock:
            clients = list(self._clients)
        dead = []
        for client in clients:
            try:
                await client.send_json(payload)
            except Exception:
                dead.append(client)
        if dead:
            async with self._lock:
                for client in dead:
                    self._clients.discard(client)

    async def _run(self) -> None:
        interval = settings.ws_broadcast_seconds
        # One wall-clock second of streaming covers `ws_time_scale` seconds of travel,
        # so a 200 km corridor is visibly traversed during a demo.
        elapsed_hours = interval * settings.ws_time_scale / 3600.0
        while True:
            try:
                await asyncio.sleep(interval)
                positions = self.step(elapsed_hours)
                if self._on_tick:
                    try:
                        self._on_tick(positions)
                    except Exception:
                        log.exception("tick callback failed")
                if self._clients:
                    await self._broadcast(self.frame(positions))
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("simulator tick failed")

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run())
            log.info("simulator started (%.1fs tick)", settings.ws_broadcast_seconds)

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None


simulator = FleetSimulator()
