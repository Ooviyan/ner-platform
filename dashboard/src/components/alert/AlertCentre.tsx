import { Bell, Languages, Users } from "lucide-react";
import type { Alert } from "../../types/api";
import type { ApiResourceState } from "../../hooks/useApiResource";
import { SEVERITY_COLORS, severityRank } from "../../lib/domain";
import { DataState } from "../ui/DataState";
import "./AlertCentre.css";

interface AlertCentreProps {
  resource: ApiResourceState<Alert>;
  compact?: boolean;
}

const STATUS_TONE: Record<string, string> = {
  sent: "status-sent",
  acknowledged: "status-acknowledged",
  pending: "status-pending",
  failed: "status-failed",
};

export function AlertCentre({ resource, compact = false }: AlertCentreProps) {
  const sorted = [...(resource.data ?? [])].sort((a, b) => severityRank(b.severity) - severityRank(a.severity));

  return (
    <div className={`alert-panel ${compact ? "compact" : ""}`}>
      <DataState
        status={resource.status}
        data={resource.data}
        error={resource.error}
        onRetry={resource.retry}
        compact={compact}
        skeletonRows={compact ? 3 : 4}
        errorTitle="Alert data unavailable"
        errorDetailFallback="Unable to load alert information."
        emptyIcon={<Bell size={22} />}
        emptyTitle="No active alerts"
        emptyDetail="No alerts are currently pending in the communications feed."
      >
        {() => (
          <ul className="alert-list" role="list" aria-label="Alerts">
            {sorted.map((alert) => (
              <li key={alert.id} className="alert-row">
                <div className="alert-row-top">
                  <span
                    className="alert-severity-mark"
                    style={{ background: SEVERITY_COLORS[alert.severity.toLowerCase()] ?? "#8b95a0" }}
                    aria-hidden="true"
                  />
                  <strong className="alert-severity-label">{alert.severity}</strong>
                  <span className={`alert-status ${STATUS_TONE[alert.status] ?? ""}`}>{alert.status}</span>
                </div>
                <div className="alert-event">Event {alert.event}</div>
                <div className="alert-row-meta">
                  <span className="alert-meta-item">
                    <Users size={11} aria-hidden="true" />
                    {alert.recipients.length} recipient{alert.recipients.length === 1 ? "" : "s"}
                  </span>
                  <span className="alert-meta-item">
                    <Languages size={11} aria-hidden="true" />
                    {alert.lang.toUpperCase()}
                  </span>
                </div>
                <div className="alert-recipients">{alert.recipients.join(", ")}</div>
              </li>
            ))}
          </ul>
        )}
      </DataState>
    </div>
  );
}
