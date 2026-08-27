import { RISK_COLORS, RISK_LABELS, STATUS_DASH_LABELS, STATUS_LABELS } from "../../lib/domain";
import "./OperationsMap.css";

const STATUS_ORDER = ["open", "restricted", "closed"] as const;
const RISK_ORDER = ["normal", "warning", "critical"] as const;

export function MapLegend() {
  return (
    <div className="map-legend-panel" aria-label="Map legend">
      <div className="map-legend-block">
        <span className="map-legend-heading">Road status (line pattern)</span>
        {STATUS_ORDER.map((status) => (
          <div className="map-legend-row" key={status}>
            <span className={`map-legend-line pattern-${status}`} aria-hidden="true" />
            <span>{STATUS_LABELS[status]}</span>
            <span className="map-legend-pattern">{STATUS_DASH_LABELS[status]}</span>
          </div>
        ))}
      </div>

      <div className="map-legend-block">
        <span className="map-legend-heading">Road risk (line color)</span>
        {RISK_ORDER.map((risk) => (
          <div className="map-legend-row" key={risk}>
            <span className="map-legend-swatch" style={{ background: RISK_COLORS[risk] }} aria-hidden="true" />
            <span>{RISK_LABELS[risk]}</span>
          </div>
        ))}
      </div>

      <div className="map-legend-block">
        <span className="map-legend-heading">Routes &amp; incidents</span>
        <div className="map-legend-row">
          <span className="map-legend-swatch route-chosen" aria-hidden="true" />
          <span>Chosen route</span>
        </div>
        <div className="map-legend-row">
          <span className="map-legend-swatch route-alt" aria-hidden="true" />
          <span>Alternate route</span>
        </div>
        <div className="map-legend-row">
          <span className="map-legend-dot" aria-hidden="true" />
          <span>Field incident report</span>
        </div>
      </div>
    </div>
  );
}
