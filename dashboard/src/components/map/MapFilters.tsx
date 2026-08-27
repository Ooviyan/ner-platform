import { Eye, EyeOff, Route as RouteIcon, Siren } from "lucide-react";
import type { RiskFilterValue, StatusFilterValue } from "../../types/map";
import "./OperationsMap.css";

interface MapFiltersProps {
  statusFilter: StatusFilterValue;
  riskFilter: RiskFilterValue;
  onStatusFilterChange: (value: StatusFilterValue) => void;
  onRiskFilterChange: (value: RiskFilterValue) => void;
  showRoutes: boolean;
  showReports: boolean;
  onToggleRoutes: () => void;
  onToggleReports: () => void;
}

const STATUS_OPTIONS: { value: StatusFilterValue; label: string }[] = [
  { value: "all", label: "All" },
  { value: "open", label: "Open" },
  { value: "restricted", label: "Restricted" },
  { value: "closed", label: "Closed" },
];

const RISK_OPTIONS: { value: RiskFilterValue; label: string }[] = [
  { value: "all", label: "All risk" },
  { value: "normal", label: "Normal" },
  { value: "warning", label: "Warning" },
  { value: "critical", label: "Critical" },
];

export function MapFilters({
  statusFilter,
  riskFilter,
  onStatusFilterChange,
  onRiskFilterChange,
  showRoutes,
  showReports,
  onToggleRoutes,
  onToggleReports,
}: MapFiltersProps) {
  return (
    <div className="map-filters" role="group" aria-label="Map filters">
      <div className="map-filter-row">
        <span className="map-filter-label">Status</span>
        <div className="map-filter-group" role="radiogroup" aria-label="Road status filter">
          {STATUS_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              type="button"
              role="radio"
              aria-checked={statusFilter === opt.value}
              className={`map-filter-chip ${statusFilter === opt.value ? "active" : ""}`}
              onClick={() => onStatusFilterChange(opt.value)}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      <div className="map-filter-row">
        <span className="map-filter-label">Risk</span>
        <div className="map-filter-group" role="radiogroup" aria-label="Road risk filter">
          {RISK_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              type="button"
              role="radio"
              aria-checked={riskFilter === opt.value}
              className={`map-filter-chip ${riskFilter === opt.value ? "active" : ""}`}
              onClick={() => onRiskFilterChange(opt.value)}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      <div className="map-filter-row">
        <span className="map-filter-label">Layers</span>
        <div className="map-filter-group">
          <button
            type="button"
            className={`map-filter-chip map-filter-icon-chip ${showRoutes ? "active" : ""}`}
            aria-pressed={showRoutes}
            onClick={onToggleRoutes}
          >
            {showRoutes ? <Eye size={12} /> : <EyeOff size={12} />}
            <RouteIcon size={12} />
            Routes
          </button>
          <button
            type="button"
            className={`map-filter-chip map-filter-icon-chip ${showReports ? "active" : ""}`}
            aria-pressed={showReports}
            onClick={onToggleReports}
          >
            {showReports ? <Eye size={12} /> : <EyeOff size={12} />}
            <Siren size={12} />
            Incidents
          </button>
        </div>
      </div>
    </div>
  );
}
