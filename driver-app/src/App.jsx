import { Suspense } from 'react'
import { NavLink, Navigate, Route, Routes } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useLink } from './hooks/useLink.js'
import { toggleDeadZone } from './net/link.js'
import { NODE_LABEL } from './config.js'
import {
  RouteIcon,
  ReportIcon,
  SosIcon,
  MeshIcon,
  SettingsIcon,
  Wifi,
  WifiOff,
} from './components/icons.jsx'

import Home from './screens/Home.jsx'
import Report from './screens/Report.jsx'
import Sos from './screens/Sos.jsx'
import Mesh from './screens/Mesh.jsx'
import Settings from './screens/Settings.jsx'

function LinkPill() {
  const { t } = useTranslation()
  const { linkUp, deadZone, browserOnline } = useLink()
  const label = deadZone ? t('link.deadzone') : linkUp ? t('link.online') : t('link.offline')
  const cls = deadZone ? 'pill warn' : linkUp ? 'pill ok' : 'pill danger'
  return (
    <button
      className={cls}
      style={{ cursor: 'pointer' }}
      onClick={() => toggleDeadZone()}
      title={
        deadZone
          ? t('link.deadzone_on')
          : browserOnline
            ? t('link.toggle_deadzone')
            : t('link.browser_offline')
      }
    >
      {linkUp ? <Wifi width="13" height="13" /> : <WifiOff width="13" height="13" />}
      {label}
    </button>
  )
}

export default function App() {
  const { t } = useTranslation()
  const { linkUp, deadZone } = useLink()

  const tabs = [
    { to: '/home', icon: RouteIcon, label: t('nav.home') },
    { to: '/report', icon: ReportIcon, label: t('nav.report') },
    { to: '/sos', icon: SosIcon, label: t('nav.sos'), cls: 'sos' },
    { to: '/mesh', icon: MeshIcon, label: t('nav.mesh') },
    { to: '/settings', icon: SettingsIcon, label: t('nav.settings') },
  ]

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <img src="/icons/pwa-192.png" alt="" width="30" height="30" />
          <div className="truncate">
            <b>{t('app.name')}</b>
            <span className="truncate">{t('app.tagline')}</span>
          </div>
        </div>
        <div className="spacer" />
        <span className="pill accent" title={t('mesh.this_node')}>
          {t('mesh.node', { label: NODE_LABEL })}
        </span>
        <LinkPill />
      </header>

      {deadZone && (
        <div className="banner warn" style={{ margin: '10px 14px 0', borderRadius: 11 }}>
          <span className="dot pulse" />
          {t('link.deadzone_on')}
        </div>
      )}
      {!linkUp && !deadZone && (
        <div className="banner danger" style={{ margin: '10px 14px 0', borderRadius: 11 }}>
          <WifiOff width="15" height="15" />
          {t('link.browser_offline')}
        </div>
      )}

      <Suspense fallback={<div className="empty">{t('app.loading')}</div>}>
        <Routes>
          <Route path="/" element={<Navigate to="/home" replace />} />
          <Route path="/home" element={<Home />} />
          <Route path="/report" element={<Report />} />
          <Route path="/sos" element={<Sos />} />
          <Route path="/mesh" element={<Mesh />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="*" element={<Navigate to="/home" replace />} />
        </Routes>
      </Suspense>

      <nav className="tabbar">
        {tabs.map(({ to, icon: Icon, label, cls }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) => [cls, isActive ? 'active' : ''].filter(Boolean).join(' ')}
          >
            <Icon />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>
    </div>
  )
}
