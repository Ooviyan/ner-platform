import type { Alert, Report, Route, Segment } from "../../types/api";
import type { ApiResourceState } from "../../hooks/useApiResource";
import { computeKpis } from "../../lib/domain";

interface KpiGridProps {
  segments: ApiResourceState<Segment>;
  routes: ApiResourceState<Route>;
  reports: ApiResourceState<Report>;
  alerts: ApiResourceState<Alert>;
}

function isLoaded(status: ApiResourceState<unknown>["status"]) {
  return status === "success" || status === "empty";
}

export function KpiGrid({ segments, routes, reports, alerts }: KpiGridProps) {
  const kpis = computeKpis(
    isLoaded(segments.status) ? segments.data : null,
    isLoaded(routes.status) ? routes.data : null,
    isLoaded(reports.status) ? reports.data : null,
    isLoaded(alerts.status) ? alerts.data : null,
  );

  const cards = [
    {
      label: "Road Accessibility",
      value: kpis.avgAccessibility !== null ? `${kpis.avgAccessibility}%` : "—",
      detail: isLoaded(segments.status)
        ? `Avg. across ${kpis.totalSegments} segment${kpis.totalSegments === 1 ? "" : "s"}`
        : segments.status === "error"
          ? "Failed to load segments"
          : "Loading…",
      loading: segments.status === "loading",
      failed: segments.status === "error",
      tone: kpis.avgAccessibility === null ? "info" : kpis.avgAccessibility < 50 ? "critical" : kpis.avgAccessibility < 75 ? "warning" : "safe",
    },
    {
      label: "Active Incidents",
      value: isLoaded(reports.status) ? String(kpis.activeIncidents) : "—",
      detail: isLoaded(reports.status)
        ? "Open field reports"
        : reports.status === "error"
          ? "Failed to load reports"
          : "Loading…",
      loading: reports.status === "loading",
      failed: reports.status === "error",
      tone: !isLoaded(reports.status) ? "info" : kpis.activeIncidents > 0 ? "critical" : "safe",
    },
    {
      label: "High-Risk Segments",
      value: isLoaded(segments.status) ? `${kpis.highRiskSegments} / ${kpis.totalSegments}` : "—",
      detail: isLoaded(segments.status)
        ? `${kpis.restrictedSegments} restricted · ${kpis.closedSegments} closed`
        : segments.status === "error"
          ? "Failed to load segments"
          : "Loading…",
      loading: segments.status === "loading",
      failed: segments.status === "error",
      tone: !isLoaded(segments.status) ? "info" : kpis.highRiskSegments > 0 ? "critical" : "safe",
    },
    {
      label: "Active Alerts",
      value: isLoaded(alerts.status) ? `${kpis.activeAlerts} / ${kpis.totalAlerts}` : "—",
      detail: isLoaded(alerts.status)
        ? "Pending or sent alerts"
        : alerts.status === "error"
          ? "Failed to load alerts"
          : "Loading…",
      loading: alerts.status === "loading",
      failed: alerts.status === "error",
      tone: !isLoaded(alerts.status) ? "info" : kpis.activeAlerts > 0 ? "warning" : "safe",
    },
  ];

  return (
    <section className="kpi-grid" aria-label="Operational overview">
      {cards.map((kpi) => (
        <article className={`kpi-card ${kpi.tone} ${kpi.failed ? "kpi-card-failed" : ""}`} key={kpi.label}>
          <div className="kpi-top">
            <span>{kpi.label}</span>
            <span className="kpi-status" />
          </div>
          <strong className={kpi.loading ? "kpi-value-loading" : ""}>{kpi.value}</strong>
          <p>{kpi.detail}</p>
        </article>
      ))}
    </section>
  );
}
