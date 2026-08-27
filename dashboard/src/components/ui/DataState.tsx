import type { ReactNode } from "react";
import { LoaderCircle, TriangleAlert } from "lucide-react";
import type { ResourceStatus } from "../../types/map";
import "./ui.css";

interface DataStateProps<T> {
  status: ResourceStatus;
  data: T[] | null;
  error?: string | null;
  onRetry?: () => void;
  loadingLabel?: string;
  /** Row count for a skeleton list instead of a spinner while loading. */
  skeletonRows?: number;
  errorTitle?: string;
  errorDetailFallback?: string;
  emptyIcon?: ReactNode;
  emptyTitle?: string;
  emptyDetail?: string;
  compact?: boolean;
  children: (data: T[]) => ReactNode;
}

function SkeletonRows({ rows }: { rows: number }) {
  return (
    <div className="skeleton-list" role="status" aria-label="Loading">
      {Array.from({ length: rows }, (_, i) => (
        <div className="skeleton-row" key={i}>
          <span className="skeleton-bar skeleton-bar-wide" />
          <span className="skeleton-bar skeleton-bar-narrow" />
        </div>
      ))}
    </div>
  );
}

export function DataState<T>({
  status,
  data,
  error,
  onRetry,
  loadingLabel = "Loading…",
  skeletonRows,
  errorTitle = "Data unavailable",
  errorDetailFallback = "Unable to load this data. Check the connection and retry.",
  emptyIcon,
  emptyTitle = "No data available",
  emptyDetail,
  compact = false,
  children,
}: DataStateProps<T>) {
  const sizeClass = compact ? "compact" : "";

  if (status === "loading") {
    if (skeletonRows) return <SkeletonRows rows={skeletonRows} />;
    return (
      <div className={`data-state ${sizeClass}`} role="status">
        <LoaderCircle size={20} className="data-state-spinner" aria-hidden="true" />
        <span>{loadingLabel}</span>
      </div>
    );
  }

  if (status === "error") {
    return (
      <div className={`data-state data-state-error ${sizeClass}`} role="alert">
        <TriangleAlert size={20} aria-hidden="true" />
        <strong>{errorTitle}</strong>
        {/* Operator-facing copy stays plain-language; the raw error (network
            detail, parse failure, etc.) is available on hover for anyone
            debugging, never shown as the primary message. */}
        <span className="data-state-detail" title={error ?? undefined}>
          {errorDetailFallback}
        </span>
        {onRetry && (
          <button type="button" className="retry-button" onClick={onRetry}>
            Retry
          </button>
        )}
      </div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <div className={`data-state ${sizeClass}`}>
        {emptyIcon}
        <strong>{emptyTitle}</strong>
        {emptyDetail && <span>{emptyDetail}</span>}
      </div>
    );
  }

  return <>{children(data)}</>;
}
