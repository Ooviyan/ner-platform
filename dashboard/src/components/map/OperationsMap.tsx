import { useEffect, useMemo, useRef, useState } from "react";
import * as maplibregl from "maplibre-gl";
import type { MapLayerMouseEvent, MapLibreMap } from "maplibre-gl";
import type { Position } from "geojson";
import "maplibre-gl/dist/maplibre-gl.css";
import { LoaderCircle, TriangleAlert } from "lucide-react";
import type { Report, Route, Segment } from "../../types/api";
import type { FocusRequest, RiskFilterValue, StatusFilterValue } from "../../types/map";
import {
  buildGraticule,
  reportsToFeatureCollection,
  routesToFeatureCollection,
  segmentsToFeatureCollection,
} from "../../lib/geo";
import { INCIDENT_TYPE_DEFAULT_COLOR, RISK_COLORS, incidentTypeColor } from "../../lib/domain";
import { buildReportPopup, buildRoutePopup, buildSegmentPopup } from "./mapPopupContent";
import {
  createEmptyStyle,
  NER_BOUNDS,
  NER_CENTER,
  NER_INITIAL_ZOOM,
  NER_LAT_RANGE,
  REPORTS_LAYER,
  REPORTS_STROKE_LAYER,
  ROUTES_CASING_LAYER,
  ROUTES_LAYER,
  SEGMENT_INTERACTIVE_LAYERS,
  SEGMENT_STATUS_LAYERS,
  SOURCE_IDS,
} from "./mapConstants";
import "./OperationsMap.css";

interface OperationsMapProps {
  segments: Segment[];
  routes: Route[];
  reports: Report[];
  statusFilter: StatusFilterValue;
  riskFilter: RiskFilterValue;
  showRoutes: boolean;
  showReports: boolean;
  selectedSegmentId: string | null;
  selectedRouteId: string | null;
  selectedReportId: string | null;
  onSelectSegment: (id: string | null) => void;
  onSelectRoute: (id: string | null) => void;
  onSelectReport: (id: string | null) => void;
  focusRequest: FocusRequest | null;
}

type FeatureStateId = string | number;

function boundsFromCoordinates(coordinatesList: Position[][]): maplibregl.LngLatBounds | null {
  let bounds: maplibregl.LngLatBounds | null = null;
  for (const coords of coordinatesList) {
    for (const position of coords) {
      const lng = position[0];
      const lat = position[1];
      if (!bounds) {
        bounds = new maplibregl.LngLatBounds([lng, lat], [lng, lat]);
      } else {
        bounds.extend([lng, lat]);
      }
    }
  }
  return bounds;
}

export default function OperationsMap({
  segments,
  routes,
  reports,
  statusFilter,
  riskFilter,
  showRoutes,
  showReports,
  selectedSegmentId,
  selectedRouteId,
  selectedReportId,
  onSelectSegment,
  onSelectRoute,
  onSelectReport,
  focusRequest,
}: OperationsMapProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const popupRef = useRef<maplibregl.Popup | null>(null);
  const tooltipRef = useRef<HTMLDivElement | null>(null);
  const hoveredRef = useRef<{ source: string; id: FeatureStateId } | null>(null);
  const selectedRefs = useRef<{ segment: string | null; route: string | null; report: string | null }>({
    segment: null,
    route: null,
    report: null,
  });
  const lastFocusToken = useRef<number | null>(null);

  const [ready, setReady] = useState(false);
  const [initError, setInitError] = useState<string | null>(null);

  const segmentsById = useMemo(() => new Map(segments.map((s) => [s.id, s])), [segments]);
  const segmentsFC = useMemo(() => segmentsToFeatureCollection(segments), [segments]);
  const routesFC = useMemo(() => routesToFeatureCollection(routes, segmentsById), [routes, segmentsById]);
  const reportsFC = useMemo(() => reportsToFeatureCollection(reports), [reports]);

  // ---- Map lifecycle: created exactly once, torn down on unmount --------
  //
  // React 19 StrictMode intentionally mounts every effect twice in dev
  // (mount -> cleanup -> mount) to surface missing cleanup. Deferring the
  // real construction by a tick means the phantom first mount's cleanup
  // cancels the pending timer before a MapLibre Map (a WebGL context) is
  // ever created, so a real map is constructed exactly once per true mount
  // instead of being built and immediately torn down.
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    let cancelled = false;

    const timer = setTimeout(() => {
      if (cancelled || !containerRef.current) return;

      let map: MapLibreMap;
      try {
        map = new maplibregl.Map({
          container: containerRef.current,
          style: createEmptyStyle(),
          center: NER_CENTER,
          zoom: NER_INITIAL_ZOOM,
          attributionControl: false,
        });
      } catch (err) {
        const message = err instanceof Error ? err.message : "Map failed to initialize.";
        setInitError(message);
        return;
      }
      mapRef.current = map;
      map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");

      map.on("error", (event) => {
        console.error("MapLibre error", event.error);
      });

      map.on("load", () => {
      map.addSource(SOURCE_IDS.graticule, {
        type: "geojson",
        data: buildGraticule(NER_BOUNDS, NER_LAT_RANGE, 2),
      });
      map.addLayer({
        id: "graticule-line",
        type: "line",
        source: SOURCE_IDS.graticule,
        paint: {
          "line-color": "#1b2733",
          "line-width": 1,
        },
      });

      map.addSource(SOURCE_IDS.segments, {
        type: "geojson",
        data: segmentsFC,
        // Feature ids must be integers, or integer-castable strings. Ours are
        // "SEG-SK-NH10-001", so MapLibre discards them and every
        // setFeatureState({id}) call below silently does nothing - hover and
        // selection highlighting included. promoteId lifts the id out of
        // properties instead, which accepts arbitrary strings.
        promoteId: "id",
      });

      const riskColorExpression: maplibregl.ExpressionSpecification = [
        "match",
        ["get", "riskLevel"],
        "critical",
        RISK_COLORS.critical,
        "warning",
        RISK_COLORS.warning,
        RISK_COLORS.normal,
      ];

      const segmentColorExpr: maplibregl.ExpressionSpecification = [
        "case",
        ["boolean", ["feature-state", "selected"], false],
        "#f4f8fc",
        ["boolean", ["feature-state", "hover"], false],
        "#ffffff",
        riskColorExpression,
      ];

      const segmentWidthExpr: maplibregl.ExpressionSpecification = [
        "interpolate",
        ["linear"],
        ["zoom"],
        5,
        ["case", ["boolean", ["feature-state", "selected"], false], 4.5, ["boolean", ["feature-state", "hover"], false], 3.5, 2],
        10,
        ["case", ["boolean", ["feature-state", "selected"], false], 7.5, ["boolean", ["feature-state", "hover"], false], 6, 3.5],
      ];

      (
        [
          { status: "open", layerId: SEGMENT_STATUS_LAYERS.open, dasharray: undefined },
          { status: "restricted", layerId: SEGMENT_STATUS_LAYERS.restricted, dasharray: [3, 1.6] },
          { status: "closed", layerId: SEGMENT_STATUS_LAYERS.closed, dasharray: [0.4, 1.8] },
        ] as const
      ).forEach(({ status, layerId, dasharray }) => {
        map.addLayer({
          id: layerId,
          type: "line",
          source: SOURCE_IDS.segments,
          filter: ["==", ["get", "status"], status],
          layout: {
            "line-cap": "round",
            "line-join": "round",
          },
          paint: {
            "line-color": segmentColorExpr,
            "line-width": segmentWidthExpr,
            "line-opacity": 0.95,
            ...(dasharray ? { "line-dasharray": [...dasharray] } : {}),
          },
        });
      });

      map.addSource(SOURCE_IDS.routes, {
        type: "geojson",
        data: routesFC,
        promoteId: "id",
      });

      map.addLayer({
        id: ROUTES_CASING_LAYER,
        type: "line",
        source: SOURCE_IDS.routes,
        filter: ["==", ["get", "chosen"], true],
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-color": "#e8b34d",
          "line-opacity": 0.18,
          "line-width": [
            "case",
            ["boolean", ["feature-state", "selected"], false],
            13,
            9,
          ],
        },
      });

      map.addLayer({
        id: ROUTES_LAYER,
        type: "line",
        source: SOURCE_IDS.routes,
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-color": [
            "case",
            ["boolean", ["feature-state", "selected"], false],
            "#ffffff",
            ["==", ["get", "chosen"], true],
            "#e8b34d",
            "#5b7fa6",
          ],
          "line-width": [
            "case",
            ["boolean", ["feature-state", "selected"], false],
            5,
            ["boolean", ["feature-state", "hover"], false],
            4,
            ["case", ["==", ["get", "chosen"], true], 3.5, 1.8],
          ],
          "line-dasharray": ["case", ["==", ["get", "chosen"], true], ["literal", [1, 0]], ["literal", [2, 1.4]]],
          "line-opacity": 0.9,
        },
      });

      map.addSource(SOURCE_IDS.reports, {
        type: "geojson",
        data: reportsFC,
        promoteId: "event_id",
      });

      const incidentColorExpr: maplibregl.ExpressionSpecification = [
        "match",
        ["get", "type"],
        "landslide",
        incidentTypeColor("landslide"),
        "road_damage",
        incidentTypeColor("road_damage"),
        "flooding",
        incidentTypeColor("flooding"),
        "traffic_block",
        incidentTypeColor("traffic_block"),
        INCIDENT_TYPE_DEFAULT_COLOR,
      ];

      map.addLayer({
        id: REPORTS_STROKE_LAYER,
        type: "circle",
        source: SOURCE_IDS.reports,
        paint: {
          "circle-radius": ["case", ["boolean", ["feature-state", "selected"], false], 12, 9],
          "circle-color": "#050708",
          "circle-opacity": 0.55,
        },
      });

      map.addLayer({
        id: REPORTS_LAYER,
        type: "circle",
        source: SOURCE_IDS.reports,
        paint: {
          "circle-radius": [
            "case",
            ["boolean", ["feature-state", "selected"], false],
            8,
            ["boolean", ["feature-state", "hover"], false],
            7,
            5.5,
          ],
          "circle-color": incidentColorExpr,
          "circle-stroke-width": 2,
          "circle-stroke-color": "#0b1119",
        },
      });

      const interactiveLayers = [...SEGMENT_INTERACTIVE_LAYERS, ROUTES_LAYER, REPORTS_LAYER];

      map.on("mousemove", (event: MapLayerMouseEvent) => {
        const features = map.queryRenderedFeatures(event.point, { layers: interactiveLayers });
        const top = features[0];

        if (hoveredRef.current) {
          map.setFeatureState({ source: hoveredRef.current.source, id: hoveredRef.current.id }, { hover: false });
          hoveredRef.current = null;
        }

        if (!top || top.id === undefined) {
          map.getCanvas().style.cursor = "";
          if (tooltipRef.current) tooltipRef.current.style.display = "none";
          return;
        }

        map.getCanvas().style.cursor = "pointer";
        map.setFeatureState({ source: top.source, id: top.id }, { hover: true });
        hoveredRef.current = { source: top.source, id: top.id };

        if (tooltipRef.current) {
          const props = top.properties as Record<string, unknown>;
          const label =
            (props.name as string | undefined) ??
            (props.event_id as string | undefined) ??
            (props.id as string | undefined) ??
            "";
          const sub =
            top.source === SOURCE_IDS.segments
              ? `${String(props.status)} · risk ${Number(props.risk).toFixed(2)}`
              : top.source === SOURCE_IDS.routes
                ? `${props.chosen ? "Chosen" : "Alternate"} · ${String(props.eta_min)} min`
                : String(props.type ?? "");

          tooltipRef.current.style.display = "block";
          tooltipRef.current.style.left = `${event.point.x + 14}px`;
          tooltipRef.current.style.top = `${event.point.y + 14}px`;
          tooltipRef.current.innerHTML = "";
          const titleEl = document.createElement("strong");
          titleEl.textContent = label;
          const subEl = document.createElement("span");
          subEl.textContent = sub;
          tooltipRef.current.append(titleEl, subEl);
        }
      });

      map.on("mouseout", () => {
        map.getCanvas().style.cursor = "";
        if (tooltipRef.current) tooltipRef.current.style.display = "none";
      });

      map.on("click", (event: MapLayerMouseEvent) => {
        const features = map.queryRenderedFeatures(event.point, { layers: interactiveLayers });
        const top = features[0];

        if (!top) {
          onSelectSegment(null);
          onSelectRoute(null);
          onSelectReport(null);
          popupRef.current?.remove();
          return;
        }

        const props = top.properties as Record<string, unknown>;

        if (!popupRef.current) {
          popupRef.current = new maplibregl.Popup({ closeButton: true, maxWidth: "260px" });
        }

        if (top.source === SOURCE_IDS.segments) {
          onSelectSegment(String(props.id));
          onSelectRoute(null);
          onSelectReport(null);
          popupRef.current.setLngLat(event.lngLat).setDOMContent(
            buildSegmentPopup({
              id: String(props.id),
              name: String(props.name),
              risk: Number(props.risk),
              accessibility: Number(props.accessibility),
              status: String(props.status),
              riskLevel: String(props.riskLevel),
            }),
          ).addTo(map);
        } else if (top.source === SOURCE_IDS.routes) {
          onSelectRoute(String(props.id));
          onSelectSegment(null);
          onSelectReport(null);
          popupRef.current.setLngLat(event.lngLat).setDOMContent(
            buildRoutePopup({
              id: String(props.id),
              origin: String(props.origin),
              destination: String(props.destination),
              chosen: Boolean(props.chosen),
              eta_min: Number(props.eta_min),
              delay_min: Number(props.delay_min),
              risk: Number(props.risk),
              riskLevel: String(props.riskLevel),
            }),
          ).addTo(map);
        } else if (top.source === SOURCE_IDS.reports) {
          onSelectReport(String(props.event_id));
          onSelectSegment(null);
          onSelectRoute(null);
          popupRef.current.setLngLat(event.lngLat).setDOMContent(
            buildReportPopup({
              event_id: String(props.event_id),
              type: String(props.type),
              vehicle_id: String(props.vehicle_id),
              state: String(props.state),
              timestamp: String(props.timestamp),
              photo: String(props.photo),
            }),
          ).addTo(map);
        }
      });

      setReady(true);
      });
    }, 0);

    return () => {
      cancelled = true;
      clearTimeout(timer);
      if (mapRef.current) {
        popupRef.current?.remove();
        popupRef.current = null;
        mapRef.current.remove();
        mapRef.current = null;
        setReady(false);
      }
    };
    // Intentionally created once; data/filter/selection updates flow through
    // the effects below rather than recreating the map instance.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ---- Data updates -------------------------------------------------------
  useEffect(() => {
    if (!ready || !mapRef.current) return;
    const source = mapRef.current.getSource(SOURCE_IDS.segments) as maplibregl.GeoJSONSource | undefined;
    source?.setData(segmentsFC);
  }, [ready, segmentsFC]);

  useEffect(() => {
    if (!ready || !mapRef.current) return;
    const source = mapRef.current.getSource(SOURCE_IDS.routes) as maplibregl.GeoJSONSource | undefined;
    source?.setData(routesFC);
  }, [ready, routesFC]);

  useEffect(() => {
    if (!ready || !mapRef.current) return;
    const source = mapRef.current.getSource(SOURCE_IDS.reports) as maplibregl.GeoJSONSource | undefined;
    source?.setData(reportsFC);
  }, [ready, reportsFC]);

  // ---- Filters --------------------------------------------------------------
  useEffect(() => {
    if (!ready || !mapRef.current) return;
    const map = mapRef.current;

    (Object.entries(SEGMENT_STATUS_LAYERS) as [keyof typeof SEGMENT_STATUS_LAYERS, string][]).forEach(
      ([status, layerId]) => {
        const statusVisible = statusFilter === "all" || statusFilter === status;
        map.setLayoutProperty(layerId, "visibility", statusVisible ? "visible" : "none");

        const filter: maplibregl.ExpressionSpecification =
          riskFilter === "all"
            ? ["==", ["get", "status"], status]
            : ["all", ["==", ["get", "status"], status], ["==", ["get", "riskLevel"], riskFilter]];

        map.setFilter(layerId, filter);
      },
    );
  }, [ready, statusFilter, riskFilter]);

  useEffect(() => {
    if (!ready || !mapRef.current) return;
    const visibility = showRoutes ? "visible" : "none";
    mapRef.current.setLayoutProperty(ROUTES_LAYER, "visibility", visibility);
    mapRef.current.setLayoutProperty(ROUTES_CASING_LAYER, "visibility", visibility);
  }, [ready, showRoutes]);

  useEffect(() => {
    if (!ready || !mapRef.current) return;
    const visibility = showReports ? "visible" : "none";
    mapRef.current.setLayoutProperty(REPORTS_LAYER, "visibility", visibility);
    mapRef.current.setLayoutProperty(REPORTS_STROKE_LAYER, "visibility", visibility);
  }, [ready, showReports]);

  // ---- Selection sync (feature-state) ---------------------------------------
  useEffect(() => {
    if (!ready || !mapRef.current) return;
    const map = mapRef.current;
    const prev = selectedRefs.current.segment;
    if (prev && prev !== selectedSegmentId) {
      map.setFeatureState({ source: SOURCE_IDS.segments, id: prev }, { selected: false });
    }
    if (selectedSegmentId) {
      map.setFeatureState({ source: SOURCE_IDS.segments, id: selectedSegmentId }, { selected: true });
    }
    selectedRefs.current.segment = selectedSegmentId;
  }, [ready, selectedSegmentId]);

  useEffect(() => {
    if (!ready || !mapRef.current) return;
    const map = mapRef.current;
    const prev = selectedRefs.current.route;
    if (prev && prev !== selectedRouteId) {
      map.setFeatureState({ source: SOURCE_IDS.routes, id: prev }, { selected: false });
    }
    if (selectedRouteId) {
      map.setFeatureState({ source: SOURCE_IDS.routes, id: selectedRouteId }, { selected: true });
    }
    selectedRefs.current.route = selectedRouteId;
  }, [ready, selectedRouteId]);

  useEffect(() => {
    if (!ready || !mapRef.current) return;
    const map = mapRef.current;
    const prev = selectedRefs.current.report;
    if (prev && prev !== selectedReportId) {
      map.setFeatureState({ source: SOURCE_IDS.reports, id: prev }, { selected: false });
    }
    if (selectedReportId) {
      map.setFeatureState({ source: SOURCE_IDS.reports, id: selectedReportId }, { selected: true });
    }
    selectedRefs.current.report = selectedReportId;
  }, [ready, selectedReportId]);

  // ---- Camera focus requests (from side panels, not from map clicks) --------
  useEffect(() => {
    if (!ready || !mapRef.current || !focusRequest) return;
    if (lastFocusToken.current === focusRequest.token) return;
    lastFocusToken.current = focusRequest.token;

    const map = mapRef.current;

    if (focusRequest.kind === "segment") {
      const segment = segmentsById.get(focusRequest.id);
      if (!segment) return;
      const bounds = boundsFromCoordinates([segment.geometry.coordinates]);
      if (bounds) map.fitBounds(bounds, { padding: 90, maxZoom: 12, duration: 700 });
    } else if (focusRequest.kind === "route") {
      const feature = routesFC.features.find((f) => f.properties.id === focusRequest.id);
      if (!feature) return;
      const bounds = boundsFromCoordinates([feature.geometry.coordinates]);
      if (bounds) map.fitBounds(bounds, { padding: 90, maxZoom: 11, duration: 700 });
    } else if (focusRequest.kind === "report") {
      const report = reports.find((r) => r.event_id === focusRequest.id);
      if (!report) return;
      map.flyTo({ center: [report.lng, report.lat], zoom: Math.max(map.getZoom(), 9.5), duration: 700 });
    }
  }, [focusRequest, ready, segmentsById, routesFC, reports]);

  return (
    <div className="operations-map">
      {initError ? (
        <div className="operations-map-error" role="alert">
          <TriangleAlert size={26} />
          <strong>Map failed to initialize</strong>
          <span>{initError}</span>
        </div>
      ) : (
        <>
          <div ref={containerRef} className="operations-map-canvas" aria-label="North Eastern Region operations map" />
          <div ref={tooltipRef} className="operations-map-tooltip" style={{ display: "none" }} />
          {!ready && (
            <div className="operations-map-loading" role="status">
              <LoaderCircle size={20} className="data-state-spinner" aria-hidden="true" />
              <span>Loading operational map…</span>
            </div>
          )}
        </>
      )}
    </div>
  );
}
