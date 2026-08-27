import "./ui.css";

export type BadgeTone = "normal" | "warning" | "critical" | "info" | "neutral";

interface StatusBadgeProps {
  tone: BadgeTone;
  label: string;
  patternLabel?: string;
}

// Never a color swatch alone: every badge carries a text label, and roads
// additionally carry a dash-pattern description so status reads without
// relying on hue.
export function StatusBadge({ tone, label, patternLabel }: StatusBadgeProps) {
  return (
    <span className={`status-badge tone-${tone}`} title={patternLabel}>
      <span className="status-badge-mark" aria-hidden="true" />
      {label}
    </span>
  );
}
