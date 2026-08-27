import { useMemo } from "react";
import { Activity } from "lucide-react";
import type { Route, Segment } from "../../types/api";
import type { ApiResourceState } from "../../hooks/useApiResource";
import { RISK_LABELS, riskLevel } from "../../lib/domain";
import { formatDuration } from "../../lib/format";
import { DataState } from "../ui/DataState";
import { StatusBadge } from "../ui/StatusBadge";
import "./RouteIntelligencePanel.css";

interface RouteIntelligencePanelProps {
  resource: ApiResourceState<Route>;
  segments: Segment[];
  selectedRouteId: string | null;
  selectedSegmentId: string | null;
  onSelectRoute: (id: string) => void;
  onFocusSegment: (id: string) => void;
  compact?: boolean;
}

export function RouteIntelligencePanel({
  resource,
  segments,
  selectedRouteId,
  selectedSegmentId,
  onSelectRoute,
  onFocusSegment,
  compact = false,
}: RouteIntelligencePanelProps) {
  const sorted = [...(resource.data ?? [])].sort((a, b) => Number(b.chosen) - Number(a.chosen));
  const segmentsById = useMemo(() => new Map(segments.map((s) => [s.id, s])), [segments]);

  return (
    <div className={`route-panel ${compact ? "compact" : ""}`}>
      <DataState
        status={resource.status}
        data={resource.data}
        error={resource.error}
        onRetry={resource.retry}
        compact={compact}
        skeletonRows={compact ? 3 : 4}
        errorTitle="Route data unavailable"
        errorDetailFallback="Unable to load route options."
        emptyIcon={<Activity size={22} />}
        emptyTitle="No routes available"
        emptyDetail="No route options are currently defined for this network."
      >
        {() => (
          <ul className="route-list" role="listbox" aria-label="Routes">
            {sorted.map((route) => {
              const level = riskLevel(route.risk);
              const selected = route.id === selectedRouteId;
              return (
                <li key={route.id}>
                  <button
                    type="button"
                    role="option"
                    aria-selected={selected}
                    className={`route-row ${selected ? "selected" : ""}`}
                    onClick={() => onSelectRoute(route.id)}
                  >
                    <div className="route-row-top">
                      <span className="route-row-path">
                        {route.origin} <span className="route-arrow">→</span> {route.destination}
                      </span>
                      {route.chosen ? (
                        <StatusBadge tone="info" label="Chosen" />
                      ) : (
                        <StatusBadge tone="neutral" label="Alternate" />
                      )}
                    </div>
                    <div className="route-row-stats">
                      <span>
                        <b>{formatDuration(route.eta_min)}</b> ETA
                      </span>
                      <span>
                        <b>{route.delay_min} min</b> delay
                      </span>
                      <StatusBadge tone={level} label={`${RISK_LABELS[level]} · ${route.risk.toFixed(2)}`} />
                    </div>
                  </button>

                  {route.segments.length > 0 && (
                    <div className="route-row-segments" role="group" aria-label={`Segments used by route ${route.id}`}>
                      {route.segments.map((segId) => {
                        const segment = segmentsById.get(segId);
                        const segSelected = segId === selectedSegmentId;
                        return (
                          <button
                            key={segId}
                            type="button"
                            className={`route-segment-chip ${segSelected ? "selected" : ""} ${segment ? "" : "unresolved"}`}
                            onClick={() => onFocusSegment(segId)}
                            disabled={!segment}
                            title={segment ? segment.name : `Segment ${segId} is not in the loaded network`}
                          >
                            {segment ? segment.name : `${segId} (unavailable)`}
                          </button>
                        );
                      })}
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </DataState>
    </div>
  );
}
