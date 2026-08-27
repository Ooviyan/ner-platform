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
// OpenStreetMap raster tiles - the same source the driver app already uses, so
// the two views show the same basemap. No API key and no account needed.
//
// Dimmed through MapLibre's own raster paint properties rather than a CSS
// filter: a filter on the canvas would wash out the road lines drawn on top,
// which are the whole point of the view.
export const BASEMAP_SOURCE = "osm-basemap";
export const BASEMAP_LAYER = "osm-basemap-layer";
export const BASEMAP_ATTRIBUTION =
  '<a href="https://www.openstreetmap.org/copyright">© OpenStreetMap</a> contributors';

// A FUNCTION, not a shared const.
//
// MapLibre takes ownership of the style object it is given and mutates it as
// the style loads. Handing the same object to a second Map gives that map an
// already-consumed style and it renders nothing. This app renders MapPanel on
// five pages, so switching pages remounts the map - a fresh object per call
// keeps each instance independent.
export function createEmptyStyle(): StyleSpecification {
  return {
    version: 8,
    // Deliberately no sources here. MapLibre's "load" event waits for the
    // initial style's sources to fetch their tiles, so putting the basemap in
    // here means a control centre with slow or no internet never becomes
    // ready - and the road network, which is the point of the view, never
    // draws. The basemap is added afterwards instead, and streams in beneath.
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

/** Source and layer for the basemap, added after the map is ready. */
export const BASEMAP_SOURCE_SPEC = {
  type: "raster" as const,
  tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
  tileSize: 256,
  maxzoom: 18,
  attribution: BASEMAP_ATTRIBUTION,
};

export const BASEMAP_PAINT = {
  "raster-opacity": 0.82,
  "raster-saturation": -0.55,
  "raster-contrast": 0.1,
  "raster-brightness-max": 0.66,
};

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
