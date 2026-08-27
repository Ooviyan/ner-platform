import { useMemo } from "react";
import type { Alert, Report, Route, Segment } from "../../types/api";
import type { ApiResourceState } from "../../hooks/useApiResource";
import {
  RISK_COLORS,
  RISK_LABELS,
  SEVERITY_COLORS,
  STATUS_COLORS,
  STATUS_LABELS,
  incidentTypeColor,
  incidentTypeLabel,
  riskLevel,
} from "../../lib/domain";
import "./AnalyticsPanel.css";

interface AnalyticsPanelProps {
  segments: ApiResourceState<Segment>;
  routes: ApiResourceState<Route>;
  reports: ApiResourceState<Report>;
  alerts: ApiResourceState<Alert>;
}

interface DistItem {
  key: string;
  label: string;
  count: number;
  color: string;
}

function DistributionBar({ items, unit }: { items: DistItem[]; unit: string }) {
  const total = items.reduce((sum, i) => sum + i.count, 0);

  if (total === 0) {
    return <div className="analytics-empty">No {unit} to analyze yet.</div>;
  }

  return (
    <div className="analytics-distribution">
      <div className="analytics-bar" role="img" aria-label={`${unit} distribution`}>
        {items
          .filter((i) => i.count > 0)
          .map((item) => (
            <span
              key={item.key}
              className="analytics-bar-segment"
              style={{ width: `${(item.count / total) * 100}%`, background: item.color }}
              title={`${item.label}: ${item.count}`}
            />
          ))}
      </div>
      <ul className="analytics-legend">
        {items.map((item) => (
          <li key={item.key}>
            <span className="analytics-legend-swatch" style={{ background: item.color }} aria-hidden="true" />
            <span className="analytics-legend-label">{item.label}</span>
            <span className="analytics-legend-count">{item.count}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function AnalyticsPanel({ segments, routes, reports, alerts }: AnalyticsPanelProps) {
  const statusDist = useMemo<DistItem[]>(() => {
    const data = segments.data ?? [];
    return (["open", "restricted", "closed"] as const).map((status) => ({
      key: status,
      label: STATUS_LABELS[status],
      count: data.filter((s) => s.status === status).length,
      color: STATUS_COLORS[status],
    }));
  }, [segments.data]);

  const riskDist = useMemo<DistItem[]>(() => {
    const data = segments.data ?? [];
    return (["normal", "warning", "critical"] as const).map((level) => ({
      key: level,
      label: RISK_LABELS[level],
      count: data.filter((s) => riskLevel(s.risk) === level).length,
      color: RISK_COLORS[level],
    }));
  }, [segments.data]);

  const incidentDist = useMemo<DistItem[]>(() => {
    const data = reports.data ?? [];
    const types = Array.from(new Set(data.map((r) => r.type)));
    return types.map((type) => ({
      key: type,
      label: incidentTypeLabel(type),
      count: data.filter((r) => r.type === type).length,
      color: incidentTypeColor(type),
    }));
  }, [reports.data]);

  const alertDist = useMemo<DistItem[]>(() => {
    const data = alerts.data ?? [];
    const severities = Array.from(new Set(data.map((a) => a.severity.toLowerCase())));
    return severities.map((severity) => ({
      key: severity,
      label: severity,
      count: data.filter((a) => a.severity.toLowerCase() === severity).length,
      color: SEVERITY_COLORS[severity] ?? "#8b95a0",
    }));
  }, [alerts.data]);

  const avgAccessibility = useMemo(() => {
    const data = segments.data ?? [];
    if (data.length === 0) return null;
    return Math.round(data.reduce((sum, s) => sum + s.accessibility, 0) / data.length);
  }, [segments.data]);

  const routeRows = routes.data ?? [];

  return (
    <div className="analytics-panel">
      <div className="analytics-grid">
        <section className="analytics-card">
          <h4>Road status distribution</h4>
          <DistributionBar items={statusDist} unit="segments" />
        </section>

        <section className="analytics-card">
          <h4>Road risk distribution</h4>
          <DistributionBar items={riskDist} unit="segments" />
          {avgAccessibility !== null && (
            <p className="analytics-footnote">Average accessibility across all segments: {avgAccessibility}%</p>
          )}
        </section>

        <section className="analytics-card">
          <h4>Incident type breakdown</h4>
          <DistributionBar items={incidentDist} unit="incidents" />
        </section>

        <section className="analytics-card">
          <h4>Alert severity breakdown</h4>
          <DistributionBar items={alertDist} unit="alerts" />
        </section>

        <section className="analytics-card analytics-card-wide">
          <h4>Route delay &amp; risk overview</h4>
          {routeRows.length === 0 ? (
            <div className="analytics-empty">No routes to analyze yet.</div>
          ) : (
            <table className="analytics-table">
              <thead>
                <tr>
                  <th>Route</th>
                  <th>ETA</th>
                  <th>Delay</th>
                  <th>Risk</th>
                  <th>State</th>
                </tr>
              </thead>
              <tbody>
                {routeRows.map((route) => (
                  <tr key={route.id}>
                    <td>
                      {route.origin} → {route.destination}
                    </td>
                    <td>{route.eta_min} min</td>
                    <td>{route.delay_min} min</td>
                    <td>{route.risk.toFixed(2)}</td>
                    <td>{route.chosen ? "Chosen" : "Alternate"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      </div>
    </div>
  );
}
