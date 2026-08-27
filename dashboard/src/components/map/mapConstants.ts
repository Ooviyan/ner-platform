import type { StyleSpecification } from "maplibre-gl";

// North Eastern Region bounding envelope, used both for the initial camera
// and to size the reference graticule. Loose enough to comfortably contain
// all eight NER states plus the Siliguri approach corridor.
export const NER_BOUNDS: [number, number] = [88, 96];
export const NER_LAT_RANGE: [number, number] = [21.5, 29.5];
export const NER_CENTER: [number, number] = [91.8, 25.8];
export const NER_INITIAL_ZOOM = 5.6;

// No external tile service is used (no API key, no network dependency) —
// the map is a plain background plus a generated lat/lng reference grid.
// A FUNCTION, not a shared const.
//
// MapLibre takes ownership of the style object it is given and mutates it as
// the style loads. Handing the same object to a second Map - which React
// StrictMode guarantees in development, and any remount causes in production -
// gives that map an already-consumed style, and it renders nothing at all.
// Returning a fresh object per call makes each map independent.
export function createEmptyStyle(): StyleSpecification {
  return {
    version: 8,
    sources: {},
    layers: [
      {
        id: "background",
        type: "background",
        paint: {
          "background-color": "#0b1119",
        },
      },
    ],
  };
}

export const SOURCE_IDS = {
  graticule: "graticule",
  segments: "segments",
  routes: "routes",
  reports: "reports",
} as const;

export const SEGMENT_STATUS_LAYERS = {
  open: "segments-open",
  restricted: "segments-restricted",
  closed: "segments-closed",
} as const;

export const ROUTES_LAYER = "routes-line";
export const ROUTES_CASING_LAYER = "routes-line-casing";
export const REPORTS_LAYER = "reports-circle";
export const REPORTS_STROKE_LAYER = "reports-circle-stroke";

export const SEGMENT_INTERACTIVE_LAYERS = Object.values(SEGMENT_STATUS_LAYERS);
