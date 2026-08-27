import { useEffect, useRef, useState } from "react";
import { X } from "lucide-react";
import type { Report } from "../../types/api";
import { incidentTypeLabel } from "../../lib/domain";
import { formatTimestamp } from "../../lib/format";
import "./PhotoLightbox.css";

interface PhotoLightboxProps {
  report: Report;
  onClose: () => void;
}

export function PhotoLightbox({ report, onClose }: PhotoLightboxProps) {
  const closeButtonRef = useRef<HTMLButtonElement | null>(null);
  const [imageFailed, setImageFailed] = useState(false);

  // Focus the dialog on open and restore focus to whatever triggered it on
  // close, so keyboard/screen-reader users aren't dropped back at <body>.
  useEffect(() => {
    const previouslyFocused = document.activeElement as HTMLElement | null;
    closeButtonRef.current?.focus();
    return () => {
      previouslyFocused?.focus?.();
    };
  }, []);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  return (
    <div className="photo-lightbox-backdrop" onClick={onClose}>
      <div
        className="photo-lightbox"
        role="dialog"
        aria-modal="true"
        aria-label={`Field photo for ${incidentTypeLabel(report.type)} event ${report.event_id}`}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="photo-lightbox-header">
          <div>
            <span className="photo-lightbox-kicker">FIELD REPORT PHOTO</span>
            <strong>{incidentTypeLabel(report.type)}</strong>
          </div>
          <button type="button" className="photo-lightbox-close" onClick={onClose} ref={closeButtonRef} aria-label="Close photo preview">
            <X size={18} />
          </button>
        </div>

        <div className="photo-lightbox-body">
          {imageFailed ? (
            <div className="photo-lightbox-fallback">Photo unavailable</div>
          ) : (
            <img
              src={report.photo}
              alt={`Field photo for ${incidentTypeLabel(report.type)} at ${report.state}`}
              onError={() => setImageFailed(true)}
            />
          )}
        </div>

        <div className="photo-lightbox-footer">
          <span>{report.event_id}</span>
          <span>{formatTimestamp(report.timestamp)}</span>
          <span>{report.vehicle_id}</span>
          <span>{report.state}</span>
        </div>
      </div>
    </div>
  );
}
