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