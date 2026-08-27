import { useMemo } from "react";
import { Route as RouteIcon } from "lucide-react";
import type { Segment } from "../../types/api";
import type { ApiResourceState } from "../../hooks/useApiResource";
import type { RiskFilterValue, StatusFilterValue } from "../../types/map";
import { RISK_LABELS, STATUS_LABELS, riskLevel } from "../../lib/domain";
import { DataState } from "../ui/DataState";
import { StatusBadge } from "../ui/StatusBadge";
import { MetricBar } from "../ui/MetricBar";
import "./RoadIntelligencePanel.css";

interface RoadIntelligencePanelProps {
  resource: ApiResourceState<Segment>;
  statusFilter: StatusFilterValue;
  riskFilter: RiskFilterValue;
  selectedSegmentId: string | null;
  onSelectSegment: (id: string) => void;
  compact?: boolean;
}

export function RoadIntelligencePanel({
  resource,
  statusFilter,
  riskFilter,
  selectedSegmentId,
  onSelectSegment,
  compact = false,
}: RoadIntelligencePanelProps) {
  const filtered = useMemo(() => {
    const all = resource.data ?? [];
    return all
      .filter((s) => statusFilter === "all" || s.status === statusFilter)
      .filter((s) => riskFilter === "all" || riskLevel(s.risk) === riskFilter)
      .sort((a, b) => b.risk - a.risk);
  }, [resource.data, statusFilter, riskFilter]);

  return (
    <div className={`road-panel ${compact ? "compact" : ""}`}>
      <DataState
        status={resource.status}
        data={resource.data}
        error={resource.error}
        onRetry={resource.retry}
        compact={compact}
        skeletonRows={compact ? 3 : 5}
        errorTitle="Road data unavailable"
        errorDetailFallback="Unable to load road segment information."
        emptyIcon={<RouteIcon size={22} />}
        emptyTitle="No road segments"
        emptyDetail="No road segments are currently available in the network."
      >
        {() =>
          filtered.length === 0 ? (
            <div className="road-panel-no-match">No segments match the current filters.</div>
          ) : (
            <ul className="road-list" role="listbox" aria-label="Road segments">
              {filtered.map((segment) => {
                const level = riskLevel(segment.risk);
                const selected = segment.id === selectedSegmentId;
                return (
                  <li key={segment.id}>
                    <button
                      type="button"
                      role="option"
                      aria-selected={selected}
                      className={`road-row ${selected ? "selected" : ""}`}
                      onClick={() => onSelectSegment(segment.id)}
                    >
                      <div className="road-row-top">
                        <span className="road-row-name">{segment.name}</span>
                        <StatusBadge
                          tone={segment.status === "open" ? "info" : segment.status === "restricted" ? "warning" : "critical"}
                          label={STATUS_LABELS[segment.status] ?? segment.status}
                        />
                      </div>
                      <div className="road-row-meta">
                        <span className="road-row-id">{segment.id}</span>
                        <StatusBadge tone={level} label={`${RISK_LABELS[level]} risk · ${segment.risk.toFixed(2)}`} />
                      </div>
                      <MetricBar
                        value={segment.accessibility}
                        tone={segment.accessibility < 40 ? "critical" : segment.accessibility < 70 ? "warning" : "normal"}
                      />
                    </button>
                  </li>
                );
              })}
            </ul>
          )
        }
      </DataState>
    </div>
  );
}
