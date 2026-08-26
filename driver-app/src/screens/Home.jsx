import { Suspense, lazy } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useLiveQuery } from 'dexie-react-hooks'
import { db } from '../db/db.js'
import { useRoute } from '../hooks/useRoute.js'
import { useGeolocation } from '../hooks/useGeolocation.js'
import {
  formatEta,
  relativeTime,
  riskColor,
  riskLabel,
  riskPillClass,
  StateBadge,
  Stat,
} from '../components/common.jsx'
import { Refresh, Upload } from '../components/icons.jsx'

// Leaflet is the single biggest dependency and only this screen needs it.
const MapView = lazy(() => import('../components/MapView.jsx'))

export default function Home() {
  const { t } = useTranslation()
  const { route, loading, stale, reload } = useRoute()
  const { fix } = useGeolocation()

  const reports = useLiveQuery(
    () => db.reports.orderBy('timestamp').reverse().limit(4).toArray(),
    [],
    []
  )
  const queued = useLiveQuery(
    () => db.reports.where('state').anyOf('pending', 'failed', 'relaying').count(),
    [],
    0
  )

  if (loading && !route) {
    return (
      <main className="screen">
        <div className="empty">{t('app.loading')}</div>
      </main>
    )
  }

  if (!route) {
    return (
      <main className="screen">
        <div className="card">
          <p className="muted">{t('home.no_route')}</p>
          <button className="btn block" onClick={reload}>
            <Refresh width="16" height="16" /> {t('home.retry')}
          </button>
        </div>
      </main>
    )
  }

  const v = route.vehicle || {}
  const totalKm = (route.segments || []).reduce((a, s) => a + (s.distance_km || 0), 0)

  return (
    <main className="screen">
      {stale && <div className="banner warn">{t('home.offline_notice')}</div>}

      {queued > 0 && (
        <Link to="/report" style={{ textDecoration: 'none' }}>
          <div className="banner">
            <Upload width="15" height="15" />
            <span className="grow">{t('home.queue_summary', { count: queued })}</span>
            <span className="pill warn">{queued}</span>
          </div>
        </Link>
      )}

      {/* ---- route + map ---- */}
      <section className="card pad0">
        <Suspense
          fallback={<div style={{ height: 230, background: '#0a2b29' }} />}
        >
          <MapView route={route} position={fix} reports={reports} height={230} />
        </Suspense>
        <div style={{ padding: 14 }}>
          <div className="row between" style={{ marginBottom: 8 }}>
            <span className="pill accent">{t('home.chosen_route')}</span>
            <span className={riskPillClass(route.risk)}>
              {t('home.risk')}: {riskLabel(route.risk, t)}
            </span>
          </div>
          <h2 style={{ fontSize: 16 }}>
            {route.origin?.name} → {route.destination?.name}
          </h2>
          <p className="small muted" style={{ margin: '2px 0 0' }}>
            {route.origin?.state} → {route.destination?.state}
          </p>
          <hr className="sep" />
          <div className="row">
            <Stat value={formatEta(route.eta_min, t)} label={t('home.eta')} />
            <Stat
              value={t('home.delay_value', { m: route.delay_min || 0 })}
              label={t('home.delay')}
              tone={route.delay_min > 30 ? 'var(--warn)' : undefined}
            />
            <Stat value={`${Math.round(totalKm)} km`} label={t('home.distance')} />
          </div>
        </div>
      </section>

      {/* ---- vehicle / cargo ---- */}
      <section className="card">
        <h3>{t('home.vehicle')}</h3>
        <dl className="kv">
          <dt>{t('home.vehicle')}</dt>
          <dd className="mono">{v.vehicle_id}</dd>
          <dt>{t('home.driver')}</dt>
          <dd>{v.driver_name}</dd>
          <dt>{t('home.cargo')}</dt>
          <dd style={{ textAlign: 'right' }}>{v.cargo}</dd>
        </dl>
      </section>

      {/* ---- segments ---- */}
      <section className="card">
        <h3>{t('home.segments')}</h3>
        <div className="col" style={{ gap: 8 }}>
          {(route.segments || []).map((seg, i) => (
            <div
              key={seg.id}
              className="row"
              style={{
                gap: 10,
                padding: '9px 10px',
                borderRadius: 11,
                background: 'var(--bg)',
                border: '1px solid var(--line)',
              }}
            >
              <span
                aria-hidden
                style={{
                  width: 4,
                  alignSelf: 'stretch',
                  borderRadius: 4,
                  background: riskColor(seg.status, seg.risk),
                  flex: 'none',
                }}
              />
              <div className="grow" style={{ minWidth: 0 }}>
                <div className="small" style={{ fontWeight: 650 }}>
                  {i + 1}. {seg.name}
                </div>
                <div className="tiny muted">
                  {seg.distance_km} km · {formatEta(seg.eta_min, t)}
                </div>
              </div>
              <span className={riskPillClass(seg.risk)}>
                {t(`home.status.${seg.status}`, seg.status)}
              </span>
            </div>
          ))}
        </div>
      </section>

      {/* ---- recent reports ---- */}
      {reports.length > 0 && (
        <section className="card">
          <div className="row between">
            <h3 style={{ margin: 0 }}>{t('home.recent')}</h3>
            <Link to="/report" className="tiny" style={{ color: 'var(--accent)' }}>
              {t('home.view_all')}
            </Link>
          </div>
          <div className="col" style={{ gap: 8, marginTop: 10 }}>
            {reports.map(r => (
              <div key={r.event_id} className="row" style={{ gap: 10 }}>
                <span className="grow truncate small">
                  {t(`report.types.${r.type}`, r.type)}
                  <span className="muted tiny"> · {relativeTime(r.timestamp, t)}</span>
                </span>
                <StateBadge state={r.state} />
              </div>
            ))}
          </div>
        </section>
      )}
    </main>
  )
}
