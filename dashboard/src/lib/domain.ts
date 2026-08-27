import type { Alert, Report, Route, Segment } from "../types/api";
import type { RiskLevel } from "../types/map";

// Thresholds are the only place risk buckets are defined — every panel and
// map layer derives its category from these instead of re-guessing bounds.
export const RISK_WARNING_THRESHOLD = 0.4;
export const RISK_CRITICAL_THRESHOLD = 0.7;

export function riskLevel(risk: number): RiskLevel {
  if (risk >= RISK_CRITICAL_THRESHOLD) return "critical";
  if (risk >= RISK_WARNING_THRESHOLD) return "warning";
  return "normal";
}

// Saturated on purpose. The earlier muted set (#71a985 / #c19a58 / #c66b6b)
// was chosen against a flat background; over map tiles it sat at roughly the
// same luminance as the terrain and the roads disappeared into it. These read
// at a glance from across a control room, which is the actual requirement.
export const RISK_COLORS: Record<RiskLevel, string> = {
  normal: "#34d399",
  warning: "#fbbf24",
  critical: "#fb5a68",
};

export const RISK_LABELS: Record<RiskLevel, string> = {
  normal: "Normal",
  warning: "Warning",
  critical: "Critical",
};

export const STATUS_COLORS: Record<string, string> = {
  open: "#6d9ec5",
  restricted: "#c19a58",
  closed: "#8b95a0",
};

export const STATUS_LABELS: Record<string, string> = {
  open: "Open",
  restricted: "Restricted",
  closed: "Closed",
};

// Roads never rely on color alone: each status also gets a distinct dash
// pattern so the map and legend read correctly without color vision.
export const STATUS_DASH_LABELS: Record<string, string> = {
  open: "solid line",
  restricted: "dashed line",
  closed: "dotted line",
};

const SEVERITY_ORDER: Record<string, number> = {
  critical: 4,
  high: 3,
  medium: 2,
  low: 1,
};

export function severityRank(severity: string): number {
  return SEVERITY_ORDER[severity.toLowerCase()] ?? 0;
}

export const SEVERITY_COLORS: Record<string, string> = {
  critical: "#c66b6b",
  high: "#cf8a57",
  medium: "#c19a58",
  low: "#6d9ec5",
};

export const INCIDENT_TYPE_LABELS: Record<string, string> = {
  landslide: "Landslide",
  road_damage: "Road damage",
  flooding: "Flooding",
  traffic_block: "Traffic block",
};

export function incidentTypeLabel(type: string): string {
  return INCIDENT_TYPE_LABELS[type] ?? type.replace(/_/g, " ");
}

export const INCIDENT_TYPE_COLORS: Record<string, string> = {
  landslide: "#c66b6b",
  road_damage: "#c19a58",
  flooding: "#6d9ec5",
  traffic_block: "#9a7fc4",
};

export const INCIDENT_TYPE_DEFAULT_COLOR = "#8b95a0";

export function incidentTypeColor(type: string): string {
  return INCIDENT_TYPE_COLORS[type] ?? INCIDENT_TYPE_DEFAULT_COLOR;
}

export interface DashboardKpis {
  totalSegments: number;
  openSegments: number;
  restrictedSegments: number;
  closedSegments: number;
  highRiskSegments: number;
  avgAccessibility: number | null;
  activeIncidents: number;
  avgRouteDelay: number | null;
  totalAlerts: number;
  activeAlerts: number;
}

export function computeKpis(
  segments: Segment[] | null,
  routes: Route[] | null,
  reports: Report[] | null,
  alerts: Alert[] | null,
): DashboardKpis {
  const totalSegments = segments?.length ?? 0;
  const openSegments = segments?.filter((s) => s.status === "open").length ?? 0;
  const restrictedSegments = segments?.filter((s) => s.status === "restricted").length ?? 0;
  const closedSegments = segments?.filter((s) => s.status === "closed").length ?? 0;
  const highRiskSegments = segments?.filter((s) => riskLevel(s.risk) === "critical").length ?? 0;

  const avgAccessibility =
    segments && segments.length > 0
      ? Math.round(segments.reduce((sum, s) => sum + s.accessibility, 0) / segments.length)
      : null;

  const activeIncidents = reports?.length ?? 0;

  const avgRouteDelay =
    routes && routes.length > 0
      ? Math.round(routes.reduce((sum, r) => sum + r.delay_min, 0) / routes.length)
      : null;

  const totalAlerts = alerts?.length ?? 0;
  const activeAlerts = alerts?.filter((a) => a.status === "pending" || a.status === "sent").length ?? 0;

  return {
    totalSegments,
    openSegments,
    restrictedSegments,
    closedSegments,
    highRiskSegments,
    avgAccessibility,
    activeIncidents,
    avgRouteDelay,
    totalAlerts,
    activeAlerts,
  };
}
