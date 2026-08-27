import { useState } from "react";
import { CircleAlert, Image } from "lucide-react";
import type { Report } from "../../types/api";
import type { ApiResourceState } from "../../hooks/useApiResource";
import { incidentTypeColor, incidentTypeLabel } from "../../lib/domain";
import { formatTimestamp } from "../../lib/format";
import { DataState } from "../ui/DataState";
import { PhotoLightbox } from "./PhotoLightbox";
import "./IncidentCentre.css";

interface IncidentCentreProps {
  resource: ApiResourceState<Report>;
  selectedReportId: string | null;
  onSelectReport: (id: string) => void;
  compact?: boolean;
}

export function IncidentCentre({ resource, selectedReportId, onSelectReport, compact = false }: IncidentCentreProps) {
  const [photoReport, setPhotoReport] = useState<Report | null>(null);

  const sorted = [...(resource.data ?? [])].sort(
    (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime(),
  );

  return (
    <div className={`incident-panel ${compact ? "compact" : ""}`}>
      <DataState
        status={resource.status}
        data={resource.data}
        error={resource.error}
        onRetry={resource.retry}
        compact={compact}
        skeletonRows={compact ? 3 : 5}
        errorTitle="Incident data unavailable"
        errorDetailFallback="Unable to load field incident reports."
        emptyIcon={<CircleAlert size={22} />}
        emptyTitle="No active incidents"
        emptyDetail="No incidents are currently available in the operational feed."
      >
        {() => (
          <ul className="incident-list" role="listbox" aria-label="Field incident reports">
            {sorted.map((report) => {
              const selected = report.event_id === selectedReportId;
              return (
                <li key={report.event_id} className="incident-row-container">
                  <button
                    type="button"
                    role="option"
                    aria-selected={selected}
                    className={`incident-row ${selected ? "selected" : ""}`}
                    onClick={() => onSelectReport(report.event_id)}
                  >
                    <span className="incident-marker" style={{ background: incidentTypeColor(report.type) }} aria-hidden="true" />
                    <div className="incident-row-body">
                      <div className="incident-row-top">
                        <strong>{incidentTypeLabel(report.type)}</strong>
                        <span className="incident-row-time">{formatTimestamp(report.timestamp)}</span>
                      </div>
                      <div className="incident-row-meta">
                        <span>{report.state}</span>
                        <span className="incident-row-dot" aria-hidden="true" />
                        <span>{report.vehicle_id}</span>
                      </div>
                    </div>
                  </button>

                  {report.photo && (
                    <button
                      type="button"
                      className="incident-photo-button"
                      aria-label={`View photo for ${incidentTypeLabel(report.type)} event ${report.event_id}`}
                      onClick={() => setPhotoReport(report)}
                    >
                      <Image size={14} aria-hidden="true" />
                    </button>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </DataState>

      {photoReport && <PhotoLightbox report={photoReport} onClose={() => setPhotoReport(null)} />}
    </div>
  );
}
