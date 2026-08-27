import type { Report, Route, Segment } from "../../types/api";
import type { FocusRequest, RiskFilterValue, StatusFilterValue } from "../../types/map";
import OperationsMap from "./OperationsMap";
import { MapFilters } from "./MapFilters";
import { MapLegend } from "./MapLegend";
import "./OperationsMap.css";

interface MapPanelProps {
  segments: Segment[];
  routes: Route[];
  reports: Report[];
  statusFilter: StatusFilterValue;
  riskFilter: RiskFilterValue;
  onStatusFilterChange: (value: StatusFilterValue) => void;
  onRiskFilterChange: (value: RiskFilterValue) => void;
  showRoutes: boolean;
  showReports: boolean;
  onToggleRoutes: () => void;
  onToggleReports: () => void;
  selectedSegmentId: string | null;
  selectedRouteId: string | null;
  selectedReportId: string | null;
  onSelectSegment: (id: string | null) => void;
  onSelectRoute: (id: string | null) => void;
  onSelectReport: (id: string | null) => void;
  focusRequest: FocusRequest | null;
  showLegend?: boolean;
}

export function MapPanel({ showLegend = true, ...mapProps }: MapPanelProps) {
  return (
    <div className="map-panel-surface">
      <OperationsMap {...mapProps} />
      <MapFilters
        statusFilter={mapProps.statusFilter}
        riskFilter={mapProps.riskFilter}
        onStatusFilterChange={mapProps.onStatusFilterChange}
        onRiskFilterChange={mapProps.onRiskFilterChange}
        showRoutes={mapProps.showRoutes}
        showReports={mapProps.showReports}
        onToggleRoutes={mapProps.onToggleRoutes}
        onToggleReports={mapProps.onToggleReports}
      />
      {showLegend && <MapLegend />}
    </div>
  );
}
