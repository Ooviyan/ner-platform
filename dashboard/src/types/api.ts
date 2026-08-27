export interface Segment {
  id: string;
  name: string;
  risk: number;
  accessibility: number;
  status: string;
  geometry: {
    type: "LineString";
    coordinates: [number, number][];
  };
  /**
   * Added by the ML layer when the backend scores a segment with the model
   * (GET /segments, which is the default). A plain-English reading of the SHAP
   * attribution behind `risk` — "driven by 402 mm of rain over 72h and a 26
   * degree slope". Optional: `?scored=false` and the static fixtures omit it.
   */
  why?: string;
  /** Model detail: SHAP contributions, penalty breakdown, and which source
   *  each feature came from (open-meteo / nasa-glc / backend). */
  ml?: {
    band?: string;
    report_signal?: number;
    sources?: Record<string, string>;
    shap?: { feature: string; value: number; contribution: number; direction: string }[];
  };
}

export interface Route {
  id: string;
  origin: string;
  destination: string;
  chosen: boolean;
  eta_min: number;
  delay_min: number;
  risk: number;
  segments: string[];
}

export interface Report {
  event_id: string;
  type: string;
  lat: number;
  lng: number;
  timestamp: string;
  photo: string;
  vehicle_id: string;
  state: string;
}

export interface Alert {
  id: string;
  event: string;
  severity: string;
  recipients: string[];
  lang: string;
  status: string;
}