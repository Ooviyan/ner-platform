import "./ui.css";

interface MetricBarProps {
  value: number;
  max?: number;
  suffix?: string;
  tone?: "normal" | "warning" | "critical";
}

export function MetricBar({ value, max = 100, suffix = "%", tone = "normal" }: MetricBarProps) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  return (
    <div className="metric-bar">
      <div className="metric-bar-track">
        <div className={`metric-bar-fill tone-${tone}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="metric-bar-value">
        {Math.round(value)}
        {suffix}
      </span>
    </div>
  );
}
