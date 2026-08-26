import { useCallback, useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useLiveQuery } from 'dexie-react-hooks'
import { db, SOS_TYPES } from '../db/db.js'
import { getActive, resumeSos, startSos, stopSos, subscribeSos } from '../sos/sos.js'
import { useLink } from '../hooks/useLink.js'
import { relativeTime } from '../components/common.jsx'
import { Pin } from '../components/icons.jsx'

const HOLD_MS = 1500

export default function Sos() {
  const { t } = useTranslation()
  const { linkUp } = useLink()
  const [type, setType] = useState('accident')
  const [active, setActive] = useState(getActive())
  const [held, setHeld] = useState(0)
  const holdStart = useRef(null)
  const fillTimer = useRef(null)
  const armTimer = useRef(null)

  const alerts = useLiveQuery(
    () => db.alerts.orderBy('created_at').reverse().limit(6).toArray(),
    [],
    []
  )

  useEffect(() => {
    resumeSos()
    return subscribeSos(setActive)
  }, [])

  const endHold = useCallback(() => {
    clearTimeout(armTimer.current)
    armTimer.current = null
    clearInterval(fillTimer.current)
    fillTimer.current = null
    holdStart.current = null
    setHeld(0)
  }, [])

  const beginHold = useCallback(() => {
    if (active) return
    holdStart.current = Date.now()
    navigator.vibrate?.(30)

    // Arming is driven by a timer, never by requestAnimationFrame: browsers
    // suspend rAF entirely while a page is hidden or throttled, and an SOS must
    // never silently fail to fire. The interval below only paints the fill.
    armTimer.current = setTimeout(() => {
      endHold()
      navigator.vibrate?.([60, 40, 120])
      startSos(type)
    }, HOLD_MS)

    clearInterval(fillTimer.current)
    fillTimer.current = setInterval(() => {
      if (holdStart.current == null) return
      setHeld(Math.min(1, (Date.now() - holdStart.current) / HOLD_MS))
    }, 50)
  }, [active, type, endHold])

  useEffect(() => endHold, [endHold])

  /* ---------------------------------------------------------- active view */
  if (active) {
    const started = new Date(active.started_at)
    return (
      <main className="screen">
        <section
          className="card"
          style={{
            borderColor: 'var(--danger)',
            background: 'linear-gradient(180deg, rgba(244,63,94,.18), var(--surface))',
          }}
        >
          <div className="row between">
            <span className="pill danger">
              <span className="dot pulse" />
              {t('sos.active')}
            </span>
            <span className="tiny muted">
              {t('sos.active_since', { time: started.toLocaleTimeString() })}
            </span>
          </div>
          <h2 style={{ fontSize: 20, marginTop: 10 }}>{t(`sos.types.${active.type}`)}</h2>
          <p className="small" style={{ margin: '2px 0 0', color: '#ffdbe2' }}>
            {active.delivered ? t('sos.sent') : t('sos.queued')}
          </p>

          <hr className="sep" />

          <div className="col" style={{ gap: 7 }}>
            <div className="row between small">
              <span className="muted">{t('sos.sharing')}</span>
              <span className="pill ok">
                <span className="dot pulse" />
                {t('sos.pings_sent', { count: active.pings || 0 })}
              </span>
            </div>
            {active.fix && (
              <div className="row between small">
                <span className="muted">
                  <Pin width="13" height="13" /> {t('report.location')}
                </span>
                <span className="mono">
                  {active.fix.lat.toFixed(5)}, {active.fix.lng.toFixed(5)}
                </span>
              </div>
            )}
            {active.fix?.at && (
              <div className="row between tiny muted">
                <span>{t('sos.last_fix', { time: new Date(active.fix.at).toLocaleTimeString() })}</span>
                {active.fix.accuracy != null && (
                  <span>{t('report.accuracy', { m: active.fix.accuracy })}</span>
                )}
              </div>
            )}
            {active.geo_error === 'denied' && (
              <div className="banner warn tiny">{t('report.location_denied')}</div>
            )}
          </div>

          <hr className="sep" />

          <h3>{t('sos.recipients')}</h3>
          <div className="row wrap" style={{ gap: 6 }}>
            {(active.alert.recipients || []).map(r => (
              <span key={r} className="pill">
                {r}
              </span>
            ))}
          </div>

          <button
            className="btn block"
            style={{ marginTop: 14 }}
            onClick={() => {
              if (confirm(t('sos.cancel_confirm'))) stopSos()
            }}
          >
            {t('sos.cancel')}
          </button>
        </section>

        <a className="btn danger block" href="tel:112">
          {t('sos.call')} · 112
        </a>
      </main>
    )
  }

  /* ------------------------------------------------------------ idle view */
  return (
    <main className="screen">
      <section className="card">
        <h2>{t('sos.title')}</h2>
        <p className="small muted" style={{ margin: '0 0 12px' }}>
          {t('sos.subtitle')}
        </p>

        <h3>{t('sos.type_label')}</h3>
        <div className="chips">
          {SOS_TYPES.map(s => (
            <button
              key={s.id}
              className="chip"
              aria-pressed={type === s.id}
              onClick={() => setType(s.id)}
            >
              <span className="ico" aria-hidden>
                {s.icon}
              </span>
              <span>{t(`sos.types.${s.id}`)}</span>
            </button>
          ))}
        </div>

        {!linkUp && (
          <div className="banner warn" style={{ marginTop: 12 }}>
            {t('sos.queued')}
          </div>
        )}
      </section>

      <button
        className="btn danger"
        style={{
          height: 190,
          borderRadius: 22,
          fontSize: 19,
          flexDirection: 'column',
          gap: 10,
          position: 'relative',
          overflow: 'hidden',
        }}
        onPointerDown={beginHold}
        onPointerUp={endHold}
        onPointerLeave={endHold}
        onPointerCancel={endHold}
        onContextMenu={e => e.preventDefault()}
      >
        {/* fill sweeps across as the driver holds */}
        <span
          aria-hidden
          style={{
            position: 'absolute',
            inset: 0,
            background: 'rgba(255,255,255,.28)',
            transform: `scaleX(${held})`,
            transformOrigin: 'left',
            transition: held === 0 ? 'transform .2s ease' : 'none',
          }}
        />
        <span style={{ position: 'relative', fontSize: 46, lineHeight: 1 }} aria-hidden>
          🆘
        </span>
        <span style={{ position: 'relative' }}>
          {held > 0
            ? t('sos.holding', { s: Math.max(0, ((1 - held) * HOLD_MS) / 1000).toFixed(1) })
            : t('sos.hold')}
        </span>
      </button>

      <section className="card">
        <h3>{t('sos.history')}</h3>
        {alerts.length === 0 ? (
          <p className="empty" style={{ padding: 10 }}>
            {t('sos.no_history')}
          </p>
        ) : (
          <div className="col" style={{ gap: 8 }}>
            {alerts.map(a => (
              <div key={a.id + a.status} className="row between small">
                <span className="truncate grow">
                  {t(`sos.types.${a.event.replace('sos_', '')}`, a.event)}
                  <span className="muted tiny"> · {relativeTime(new Date(a.created_at).toISOString(), t)}</span>
                </span>
                <span className={a.status === 'stood_down' ? 'pill' : 'pill danger'}>
                  {a.status}
                </span>
              </div>
            ))}
          </div>
        )}
      </section>
    </main>
  )
}
