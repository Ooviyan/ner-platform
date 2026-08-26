"""The bridge to Person 2's models in `ml/`.

    from app.intelligence import ml

    ml.available()                       # is the intelligence layer loaded?
    ml.score(segments, reports)          # risk + accessibility from the model
    ml.route(segments, origin, dest)     # A* over a live risk-weighted graph

Why a bridge at all
-------------------
`ml/` is deliberately standalone: flat imports, no package, every module runs on
its own with `python risk.py`. That is a good property and this module does not
break it -- it puts `ml/` on `sys.path` and imports the flat names, rather than
asking Person 2 to restructure their folder around us.

Everything here is optional. If `ml/` is absent, or xgboost will not import, or
a model call raises, the API keeps serving its stored values and says so in
`/health`. A missing model degrades the answer; it must never take the platform
down, because a control room with a slightly stale risk score is still useful
and one returning 500 is not.
"""

from __future__ import annotations

import logging
import os
import sys
import threading
from pathlib import Path
from typing import Any, Optional, Sequence

log = logging.getLogger("ner.ml")

# What a blockage costs, in minutes, per routing profile.
#
# ml/routing.py prices risk as expected delay: cost = travel + risk * this. Its
# default of 240 (4h) is a balanced cargo-truck figure. The profiles differ only
# in risk appetite, which is exactly the knob ml/routing.py documents:
#
#   safest    12h. An NH-10 Teesta-gorge closure routinely lasts overnight or
#             longer, so 4h flatters a short dangerous segment -- it let the
#             router send trucks through a 0.97-risk gorge because it was only
#             7 km, over a bypass whose worst stretch was 0.64.
#   balanced  the tuned default.
#   fastest   ignores risk entirely (a plain navigation answer).
DISRUPTION_COST_BY_PROFILE = {"safest": 720.0, "balanced": 240.0, "shortest": 240.0}

# backend/app/intelligence.py -> repo root -> ml/. In the container the folder is
# mounted at /ml, so ML_DIR overrides the relative guess.
ML_DIR = Path(os.getenv("ML_DIR")
               or Path(__file__).resolve().parent.parent.parent / "ml")


class Intelligence:
    """Lazily-loaded handle on the ml/ package, with every call guarded."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._loaded = False
        self._modules: dict[str, Any] = {}
        self._error: Optional[str] = None

    # ------------------------------------------------------------ loading --
    def _load(self) -> bool:
        if self._loaded or self._error:
            return self._loaded
        with self._lock:
            if self._loaded or self._error:
                return self._loaded
            if not ML_DIR.is_dir():
                self._error = f"{ML_DIR} not found"
                log.warning("intelligence layer unavailable: %s", self._error)
                return False
            path = str(ML_DIR)
            if path not in sys.path:
                sys.path.insert(0, path)
            try:
                import connect, explain, risk, routing, score  # noqa: E401
                self._modules = {"connect": connect, "explain": explain,
                                 "risk": risk, "routing": routing, "score": score}
                self._loaded = True
                log.info("intelligence layer loaded from %s (model: %s)",
                         ML_DIR, risk.model_info().get("mode"))
            except Exception as exc:
                self._error = f"{type(exc).__name__}: {exc}"
                log.warning("intelligence layer unavailable (%s) - serving stored "
                            "risk and accessibility instead", self._error)
        return self._loaded

    def available(self) -> bool:
        return self._load()

    def status(self) -> dict[str, Any]:
        """For /health, so the team can see whether the model is actually live."""
        if not self._load():
            return {"loaded": False, "error": self._error, "path": str(ML_DIR)}
        info = self._modules["risk"].model_info()
        out = {"loaded": True, "path": str(ML_DIR), "mode": info.get("mode"),
               "model_version": info.get("model_version"),
               "trained_at": info.get("trained_at")}
        try:
            import inventory
            out["landslide_inventory"] = inventory.inventory_info().get("count", 0)
        except Exception:
            pass
        return out

    # ------------------------------------------------------------ scoring --
    def score(self, segments: Sequence[dict], reports: Sequence[dict] | None = None,
              live_weather: bool = False) -> list[dict]:
        """Segments with `risk` and `accessibility` from the model.

        `live_weather=False` by default: the API answers on the rainfall it
        already holds rather than blocking a request on an outbound HTTP call.
        A scheduled refresh is the right place to pull real weather.
        """
        if not self._load() or not segments:
            return list(segments)
        try:
            return self._modules["connect"].enrich_segments(
                list(segments), None, list(reports or []), live=live_weather)
        except Exception:
            log.exception("model scoring failed - returning stored values")
            return list(segments)

    # ------------------------------------------------------------ routing --
    def route(self, segments: Sequence[dict], origin: tuple[float, float],
              destination: tuple[float, float],
              reports: Sequence[dict] | None = None,
              profile: str = "safest",
              live_weather: bool = False) -> Optional[dict]:
        """Genuine A* between two points, or None if no path exists.

        Nodes in the graph are junctions snapped from segment endpoints, so the
        origin and destination are resolved to their nearest junction first --
        a caller passing arbitrary coordinates should still get a route.
        """
        if not self._load() or not segments:
            return None
        routing = self._modules["routing"]
        connect = self._modules["connect"]
        try:
            kwargs = {}
            if profile in DISRUPTION_COST_BY_PROFILE:
                kwargs["disruption_cost_min"] = DISRUPTION_COST_BY_PROFILE[profile]
            graph = connect.live_graph(list(segments), None, list(reports or []),
                                       live=live_weather, **kwargs)
            if graph.number_of_nodes() == 0:
                return None

            start = self._nearest_node(graph, origin)
            end = self._nearest_node(graph, destination)
            if start is None or end is None or start == end:
                return None

            import networkx as nx
            if not nx.has_path(graph, start, end):
                log.info("no path between %s and %s", start, end)
                return None

            if profile == "fastest":
                return routing.fastest_route(graph, start, end)
            return routing.safest_route(graph, start, end)
        except Exception:
            log.exception("model routing failed")
            return None

    def alternatives(self, segments: Sequence[dict], origin: tuple[float, float],
                     destination: tuple[float, float],
                     reports: Sequence[dict] | None = None,
                     k: int = 3, live_weather: bool = False) -> list[dict]:
        """Risk-ranked alternatives, for the dashboard's comparison panel."""
        if not self._load() or not segments:
            return []
        try:
            graph = self._modules["connect"].live_graph(
                list(segments), None, list(reports or []), live=live_weather)
            start = self._nearest_node(graph, origin)
            end = self._nearest_node(graph, destination)
            if start is None or end is None or start == end:
                return []
            import networkx as nx
            if not nx.has_path(graph, start, end):
                return []
            return self._modules["routing"].alternatives(graph, start, end, k=k)
        except Exception:
            log.exception("model alternatives failed")
            return []

    @staticmethod
    def _nearest_node(graph, point: tuple[float, float]) -> Optional[str]:
        """Closest graph junction to a (lon, lat) point."""
        from app.geo import haversine_km

        best, best_km = None, float("inf")
        for node, data in graph.nodes(data=True):
            coordinates = data.get("coordinates")
            if not coordinates:
                continue
            km = haversine_km(point, (float(coordinates[0]), float(coordinates[1])))
            if km < best_km:
                best, best_km = node, km
        return best

    def explain_text(self, features: dict) -> Optional[str]:
        if not self._load():
            return None
        try:
            return self._modules["explain"].explain_text(features)
        except Exception:
            return None


ml = Intelligence()
