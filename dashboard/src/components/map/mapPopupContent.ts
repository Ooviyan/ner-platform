import { RISK_LABELS, STATUS_LABELS, incidentTypeLabel, riskLevel } from "../../lib/domain";
import { formatTimestamp } from "../../lib/format";
import type { ReportFeatureProperties, RouteFeatureProperties, SegmentFeatureProperties } from "../../lib/geo";

function row(label: string, value: string): HTMLDivElement {
  const el = document.createElement("div");
  el.className = "map-popup-row";
  const labelEl = document.createElement("span");
  labelEl.textContent = label;
  const valueEl = document.createElement("strong");
  valueEl.textContent = value;
  el.append(labelEl, valueEl);
  return el;
}

function title(text: string, kicker: string): HTMLDivElement {
  const el = document.createElement("div");
  el.className = "map-popup-title";
  const kickerEl = document.createElement("span");
  kickerEl.className = "map-popup-kicker";
  kickerEl.textContent = kicker;
  const textEl = document.createElement("strong");
  textEl.textContent = text;
  el.append(kickerEl, textEl);
  return el;
}

export function buildSegmentPopup(props: SegmentFeatureProperties): HTMLElement {
  const root = document.createElement("div");
  root.className = "map-popup";
  root.append(title(props.name, "ROAD SEGMENT"));
  root.append(row("Segment ID", props.id));
  root.append(row("Status", STATUS_LABELS[props.status] ?? props.status));
  root.append(row("Risk", `${RISK_LABELS[riskLevel(props.risk)]} (${props.risk.toFixed(2)})`));
  root.append(row("Accessibility", `${props.accessibility}%`));
  if (props.why) root.append(row("Why", props.why));
  return root;
}

export function buildRoutePopup(props: RouteFeatureProperties): HTMLElement {
  const root = document.createElement("div");
  root.className = "map-popup";
  root.append(title(`${props.origin} → ${props.destination}`, props.chosen ? "CHOSEN ROUTE" : "ALTERNATE ROUTE"));
  root.append(row("Route ID", props.id));
  root.append(row("ETA", `${props.eta_min} min`));
  root.append(row("Delay", `${props.delay_min} min`));
  root.append(row("Risk", `${RISK_LABELS[riskLevel(props.risk)]} (${props.risk.toFixed(2)})`));
  return root;
}

export function buildReportPopup(props: ReportFeatureProperties): HTMLElement {
  const root = document.createElement("div");
  root.className = "map-popup";
  root.append(title(incidentTypeLabel(props.type), "FIELD REPORT"));
  root.append(row("Event ID", props.event_id));
  root.append(row("Reported", formatTimestamp(props.timestamp)));
  root.append(row("Vehicle", props.vehicle_id));
  root.append(row("State", props.state));

  const img = document.createElement("img");
  img.className = "map-popup-photo";
  img.alt = `Field photo for ${props.event_id}`;
  img.src = props.photo;
  img.addEventListener("error", () => {
    img.replaceWith(Object.assign(document.createElement("div"), {
      className: "map-popup-photo-fallback",
      textContent: "Photo unavailable",
    }));
  });
  root.append(img);

  return root;
}
