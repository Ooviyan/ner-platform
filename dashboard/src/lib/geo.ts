import type { Feature, FeatureCollection, LineString, Point } from "geojson";
import type { Report, Route, Segment } from "../types/api";
import { riskLevel } from "./domain";

export interface SegmentFeatureProperties {
  id: string;
  name: string;
  risk: number;
  accessibility: number;
  status: string;
  riskLevel: string;
}

export type SegmentFeatureCollection = FeatureCollection<LineString, SegmentFeatureProperties>;

export function segmentsToFeatureCollection(segments: Segment[]): SegmentFeatureCollection {
  return {
    type: "FeatureCollection",
    features: segments.map(
      (segment): Feature<LineString, SegmentFeatureProperties> => ({
        type: "Feature",
        id: segment.id,
        geometry: segment.geometry,
        properties: {
          id: segment.id,
          name: segment.name,
          risk: segment.risk,
          accessibility: segment.accessibility,
          status: segment.status,
          riskLevel: riskLevel(segment.risk),
        },
      }),
    ),
  };
}

export interface RouteFeatureProperties {
  id: string;
  origin: string;
  destination: string;
  chosen: boolean;
  eta_min: number;
  delay_min: number;
  risk: number;
  riskLevel: string;
}

export type RouteFeatureCollection = FeatureCollection<LineString, RouteFeatureProperties>;

// routes.json carries no geometry of its own — a route's shape is the
// concatenation of the geometries of the segments it references, in order.
// Adjacent duplicate points (where two segments share an endpoint) are
// collapsed so the line doesn't double back on itself.
export function routesToFeatureCollection(
  routes: Route[],
  segmentsById: Map<string, Segment>,
): RouteFeatureCollection {
  const features: Feature<LineString, RouteFeatureProperties>[] = [];

  for (const route of routes) {
    const coordinates: [number, number][] = [];

    for (const segmentId of route.segments) {
      const segment = segmentsById.get(segmentId);
      if (!segment) continue;

      for (const coord of segment.geometry.coordinates) {
        const last = coordinates[coordinates.length - 1];
        if (!last || last[0] !== coord[0] || last[1] !== coord[1]) {
          coordinates.push(coord);
        }
      }
    }

    if (coordinates.length < 2) continue;

    features.push({
      type: "Feature",
      id: route.id,
      geometry: { type: "LineString", coordinates },
      properties: {
        id: route.id,
        origin: route.origin,
        destination: route.destination,
        chosen: route.chosen,
        eta_min: route.eta_min,
        delay_min: route.delay_min,
        risk: route.risk,
        riskLevel: riskLevel(route.risk),
      },
    });
  }

  return { type: "FeatureCollection", features };
}

export interface ReportFeatureProperties {
  event_id: string;
  type: string;
  vehicle_id: string;
  state: string;
  timestamp: string;
  photo: string;
}

export type ReportFeatureCollection = FeatureCollection<Point, ReportFeatureProperties>;

export function reportsToFeatureCollection(reports: Report[]): ReportFeatureCollection {
  return {
    type: "FeatureCollection",
    features: reports.map(
      (report): Feature<Point, ReportFeatureProperties> => ({
        type: "Feature",
        id: report.event_id,
        geometry: { type: "Point", coordinates: [report.lng, report.lat] },
        properties: {
          event_id: report.event_id,
          type: report.type,
          vehicle_id: report.vehicle_id,
          state: report.state,
          timestamp: report.timestamp,
          photo: report.photo,
        },
      }),
    ),
  };
}

// A lightweight lat/lng reference grid so the map reads as a real geospatial
// surface without depending on an external basemap/tile service (no API key,
// no network dependency, nothing outside dashboard/).
export function buildGraticule(
  lngRange: [number, number],
  latRange: [number, number],
  stepDeg: number,
): FeatureCollection<LineString, Record<string, never>> {
  const features: Feature<LineString, Record<string, never>>[] = [];

  for (let lng = Math.ceil(lngRange[0] / stepDeg) * stepDeg; lng <= lngRange[1]; lng += stepDeg) {
    features.push({
      type: "Feature",
      properties: {},
      geometry: {
        type: "LineString",
        coordinates: [
          [lng, latRange[0]],
          [lng, latRange[1]],
        ],
      },
    });
  }

  for (let lat = Math.ceil(latRange[0] / stepDeg) * stepDeg; lat <= latRange[1]; lat += stepDeg) {
    features.push({
      type: "Feature",
      properties: {},
      geometry: {
        type: "LineString",
        coordinates: [
          [lngRange[0], lat],
          [lngRange[1], lat],
        ],
      },
    });
  }

  return { type: "FeatureCollection", features };
}
