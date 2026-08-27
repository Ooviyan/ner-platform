import { ChevronRight, Siren, X } from "lucide-react";
import type { LucideIcon } from "lucide-react";

export interface NavItem {
  label: string;
  icon: LucideIcon;
}

interface SidebarProps {
  navItems: NavItem[];
  activePage: string;
  onSelectPage: (label: string) => void;
  mobileOpen: boolean;
  onCloseMobile: () => void;
}

export function Sidebar({ navItems, activePage, onSelectPage, mobileOpen, onCloseMobile }: SidebarProps) {
  return (
    <aside className={`sidebar ${mobileOpen ? "sidebar-open" : ""}`}>
      <div className="brand">
        <div className="brand-mark">
          <Siren size={20} />
        </div>

        <div>
          <div className="brand-title">NER LOGISTICS</div>
          <div className="brand-subtitle">OPERATIONS CENTRE</div>
        </div>

        <button className="mobile-close" aria-label="Close navigation" onClick={onCloseMobile}>
          <X size={20} />
        </button>
      </div>

      <div className="sidebar-section-label">OPERATIONS</div>

      <nav className="navigation" aria-label="Main navigation">
        {navItems.map((item) => {
          const Icon = item.icon;
          const active = activePage === item.label;

          return (
            <button
              key={item.label}
              className={`nav-item ${active ? "active" : ""}`}
              onClick={() => {
                onSelectPage(item.label);
                onCloseMobile();
              }}
            >
              <Icon size={18} />
              <span>{item.label}</span>
              {active && <ChevronRight size={15} className="nav-arrow" />}
            </button>
          );
        })}
      </nav>

      <div className="sidebar-bottom">
        <div className="system-card">
          <div className="system-indicator">
            <span />
            SYSTEM ONLINE
          </div>
          <p>Regional operations network</p>
        </div>

        <div className="region-label">
          <span>REGION</span>
          <strong>North Eastern India</strong>
        </div>
      </div>
    </aside>
  );
}
