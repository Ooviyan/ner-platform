import { useEffect, useRef, useState } from "react";
import {
  Activity,
  Bell,
  ChevronRight,
  CircleAlert,
  Gauge,
  Map,
  Route,
  ShieldCheck,
  Truck,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { Sidebar, type NavItem } from "./components/layout/Sidebar";
import { Topbar } from "./components/layout/Topbar";
import { KpiGrid } from "./components/kpi/KpiGrid";
import { MapPanel } from "./components/map/MapPanel";
import { RoadIntelligencePanel } from "./components/road/RoadIntelligencePanel";
import { IncidentCentre } from "./components/incident/IncidentCentre";
import { RouteIntelligencePanel } from "./components/route/RouteIntelligencePanel";
import { AlertCentre } from "./components/alert/AlertCentre";
import { AnalyticsPanel } from "./components/analytics/AnalyticsPanel";
import { useDashboardData } from "./hooks/useDashboardData";
import { RISK_LABELS, riskLevel } from "./lib/domain";
import type { FocusRequest, RiskFilterValue, SelectionKind, StatusFilterValue } from "./types/map";

const navItems: NavItem[] = [
  { label: "Command Centre", icon: Gauge },
  { label: "Live Operations", icon: Map },
  { label: "Road Intelligence", icon: Route },
  { label: "Route Intelligence", icon: Activity },
  { label: "Incident Centre", icon: CircleAlert },
  { label: "Alerts", icon: Bell },
  { label: "Analytics", icon: ShieldCheck },
];

const RESOURCE_LABELS: { key: "segments" | "routes" | "reports" | "alerts"; label: string; icon: LucideIcon }[] = [
  { key: "segments", label: "Road segments", icon: Route },
  { key: "routes", label: "Routes", icon: Activity },
  { key: "reports", label: "Field reports", icon: CircleAlert },
  { key: "alerts", label: "Alerts", icon: Bell },
];

function App() {
  const [activePage, setActivePage] = useState("Command Centre");
  const [mobileOpen, setMobileOpen] = useState(false);

  const { segments, routes, reports, alerts } = useDashboardData();

  const [statusFilter, setStatusFilter] = useState<StatusFilterValue>("all");
  const [riskFilter, setRiskFilter] = useState<RiskFilterValue>("all");
  const [showRoutes, setShowRoutes] = useState(true);
  const [showReports, setShowReports] = useState(true);

  const [selectedSegmentId, setSelectedSegmentId] = useState<string | null>(null);
  const [selectedRouteId, setSelectedRouteId] = useState<string | null>(null);
  const [selectedReportId, setSelectedReportId] = useState<string | null>(null);
  const [focusRequest, setFocusRequest] = useState<FocusRequest | null>(null);
  const focusTokenRef = useRef(0);

  const focusOn = (kind: SelectionKind, id: string) => {
    setSelectedSegmentId(kind === "segment" ? id : null);
    setSelectedRouteId(kind === "route" ? id : null);
    setSelectedReportId(kind === "report" ? id : null);
    focusTokenRef.current += 1;
    setFocusRequest({ kind, id, token: focusTokenRef.current });
  };

  useEffect(() => {
    if (!mobileOpen) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMobileOpen(false);
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [mobileOpen]);

  const degraded = [segments, routes, reports, alerts].some((r) => r.status === "error");

  const mapCommonProps = {
    segments: segments.data ?? [],
    routes: routes.data ?? [],
    reports: reports.data ?? [],
    statusFilter,
    riskFilter,
    onStatusFilterChange: setStatusFilter,
    onRiskFilterChange: setRiskFilter,
    showRoutes,
    showReports,
    onToggleRoutes: () => setShowRoutes((v) => !v),
    onToggleReports: () => setShowReports((v) => !v),
    selectedSegmentId,
    selectedRouteId,
    selectedReportId,
    onSelectSegment: setSelectedSegmentId,
    onSelectRoute: setSelectedRouteId,
    onSelectReport: setSelectedReportId,
    focusRequest,
  };

  const riskCounts = (["normal", "warning", "critical"] as const).map((level) => ({
    level,
    label: RISK_LABELS[level],
    count: (segments.data ?? []).filter((s) => riskLevel(s.risk) === level).length,
  }));

  return (
    <div className="app-shell">
      {mobileOpen && (
        <button className="mobile-overlay" aria-label="Close navigation" onClick={() => setMobileOpen(false)} />
      )}

      <Sidebar
        navItems={navItems}
        activePage={activePage}
        onSelectPage={setActivePage}
        mobileOpen={mobileOpen}
        onCloseMobile={() => setMobileOpen(false)}
      />

      <main className="main-content">
        <Topbar activePage={activePage} onOpenMobile={() => setMobileOpen(true)} degraded={degraded} />

        <section className="page-content">
          <div className="page-intro">
            <div>
              <p className="eyebrow">REGIONAL SITUATIONAL AWARENESS</p>
              <h2>{activePage}</h2>
              <p className="intro-text">
                Monitor road accessibility, risk, incidents and route conditions across the North Eastern Region.
              </p>
            </div>

            <div className="last-updated">
              <span className="live-dot" />
              <span>MOCK DATA MONITORING</span>
            </div>
          </div>

          {activePage === "Command Centre" && (
            <>
              <KpiGrid segments={segments} routes={routes} reports={reports} alerts={alerts} />

              <section className="operations-grid">
                <article className="panel map-panel">
                  <div className="panel-header">
                    <div>
                      <span className="panel-kicker">GEOSPATIAL VIEW</span>
                      <h3>Operational Map</h3>
                    </div>
                    <button className="panel-action" onClick={() => setActivePage("Live Operations")}>
                      Full screen
                      <ChevronRight size={15} />
                    </button>
                  </div>
                  <div className="map-frame">
                    <MapPanel {...mapCommonProps} />
                  </div>
                </article>

                <article className="panel incident-panel-card">
                  <div className="panel-header">
                    <div>
                      <span className="panel-kicker">FIELD REPORTING</span>
                      <h3>Incident Feed</h3>
                    </div>
                    <button className="text-button" onClick={() => setActivePage("Incident Centre")}>
                      View all
                    </button>
                  </div>
                  <div className="panel-body-scroll">
                    <IncidentCentre
                      resource={reports}
                      selectedReportId={selectedReportId}
                      onSelectReport={(id) => focusOn("report", id)}
                      compact
                    />
                  </div>
                </article>
              </section>

              <section className="bottom-grid">
                <article className="panel">
                  <div className="panel-header">
                    <div>
                      <span className="panel-kicker">ROAD NETWORK</span>
                      <h3>Risk Overview</h3>
                    </div>
                    <Route size={18} />
                  </div>

                  <div className="risk-list">
                    {riskCounts.map(({ level, label, count }) => (
                      <div className="risk-row" key={level}>
                        <span className={`risk-marker ${level === "normal" ? "safe-marker" : `${level}-marker`}`} />
                        <div>
                          <strong>{label}</strong>
                          <span>
                            {level === "normal" && "Low operational risk"}
                            {level === "warning" && "Monitor conditions"}
                            {level === "critical" && "Immediate attention"}
                          </span>
                        </div>
                        <b>{segments.status === "loading" ? "—" : count}</b>
                      </div>
                    ))}
                  </div>
                </article>

                <article className="panel">
                  <div className="panel-header">
                    <div>
                      <span className="panel-kicker">COMMUNICATIONS</span>
                      <h3>Alert Centre</h3>
                    </div>
                    <Bell size={18} />
                  </div>
                  <div className="panel-body-scroll compact-scroll">
                    <AlertCentre resource={alerts} compact />
                  </div>
                </article>

                <article className="panel">
                  <div className="panel-header">
                    <div>
                      <span className="panel-kicker">LOGISTICS</span>
                      <h3>Operational Status</h3>
                    </div>
                    <Truck size={18} />
                  </div>

                  <div className="operational-status">
                    {RESOURCE_LABELS.map(({ key, label }) => {
                      const resource = { segments, routes, reports, alerts }[key];
                      const ok = resource.status === "success" || resource.status === "empty";
                      return (
                        <div className="status-row" key={key}>
                          <span>{label}</span>
                          <strong className={ok ? "status-good" : resource.status === "error" ? "status-bad" : ""}>
                            {resource.status === "loading" ? "LOADING" : ok ? "ONLINE" : "OFFLINE"}
                          </strong>
                        </div>
                      );
                    })}
                    <div className="status-row">
                      <span>Data source</span>
                      <strong>MOCK DATA</strong>
                    </div>
                  </div>
                </article>
              </section>
            </>
          )}

          {activePage === "Live Operations" && (
            <div className="full-map-frame">
              <MapPanel {...mapCommonProps} />
            </div>
          )}

          {activePage === "Road Intelligence" && (
            <div className="intel-grid">
              <div className="intel-map">
                <MapPanel {...mapCommonProps} showLegend={false} />
              </div>
              <div className="panel intel-side">
                <div className="panel-header">
                  <div>
                    <span className="panel-kicker">ROAD NETWORK</span>
                    <h3>Segments ({segments.data?.length ?? 0})</h3>
                  </div>
                </div>
                <RoadIntelligencePanel
                  resource={segments}
                  statusFilter={statusFilter}
                  riskFilter={riskFilter}
                  selectedSegmentId={selectedSegmentId}
                  onSelectSegment={(id) => focusOn("segment", id)}
                />
              </div>
            </div>
          )}

          {activePage === "Route Intelligence" && (
            <div className="intel-grid">
              <div className="intel-map">
                <MapPanel {...mapCommonProps} showLegend={false} />
              </div>
              <div className="panel intel-side">
                <div className="panel-header">
                  <div>
                    <span className="panel-kicker">LOGISTICS</span>
                    <h3>Routes ({routes.data?.length ?? 0})</h3>
                  </div>
                </div>
                <RouteIntelligencePanel
                  resource={routes}
                  segments={segments.data ?? []}
                  selectedRouteId={selectedRouteId}
                  selectedSegmentId={selectedSegmentId}
                  onSelectRoute={(id) => focusOn("route", id)}
                  onFocusSegment={(id) => focusOn("segment", id)}
                />
              </div>
            </div>
          )}

          {activePage === "Incident Centre" && (
            <div className="intel-grid">
              <div className="intel-map">
                <MapPanel {...mapCommonProps} showLegend={false} />
              </div>
              <div className="panel intel-side">
                <div className="panel-header">
                  <div>
                    <span className="panel-kicker">FIELD REPORTING</span>
                    <h3>Incidents ({reports.data?.length ?? 0})</h3>
                  </div>
                </div>
                <IncidentCentre
                  resource={reports}
                  selectedReportId={selectedReportId}
                  onSelectReport={(id) => focusOn("report", id)}
                />
              </div>
            </div>
          )}

          {activePage === "Alerts" && (
            <div className="panel alerts-page-panel">
              <div className="panel-header">
                <div>
                  <span className="panel-kicker">COMMUNICATIONS</span>
                  <h3>Alert Centre ({alerts.data?.length ?? 0})</h3>
                </div>
              </div>
              <AlertCentre resource={alerts} />
            </div>
          )}

          {activePage === "Analytics" && (
            <AnalyticsPanel segments={segments} routes={routes} reports={reports} alerts={alerts} />
          )}
        </section>
      </main>
    </div>
  );
}

export default App;
