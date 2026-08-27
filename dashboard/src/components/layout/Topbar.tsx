import { Menu } from "lucide-react";

interface TopbarProps {
  activePage: string;
  onOpenMobile: () => void;
  degraded: boolean;
}

export function Topbar({ activePage, onOpenMobile, degraded }: TopbarProps) {
  return (
    <header className="topbar">
      <button className="menu-button" aria-label="Open navigation" onClick={onOpenMobile}>
        <Menu size={22} />
      </button>

      <div>
        <div className="breadcrumb">OPERATIONS / DASHBOARD</div>
        <h1>{activePage}</h1>
      </div>

      <div className="topbar-status">
        <span className={`status-dot ${degraded ? "status-dot-warning" : ""}`} />
        <span>{degraded ? "Degraded" : "Operational"}</span>
        <span className="status-divider" />
        <span>NE Region</span>
      </div>
    </header>
  );
}
