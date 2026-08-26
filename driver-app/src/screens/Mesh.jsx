import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { getMeshState, runRelayDemo, startMesh, subscribeMesh } from '../mesh/mesh.js'
import { toggleDeadZone } from '../net/link.js'
import { useLink } from '../hooks/useLink.js'
import { NODE_LABEL } from '../config.js'
import { MeshIcon, Wifi, WifiOff, Check, Upload } from '../components/icons.jsx'

const STATUS_TONE = {
  searching: 'warn',
  offered: 'warn',
  carrying: 'accent',
  uploading: 'accent',
  delivered: 'ok',
  no_peer: 'danger',
}

/** One node bubble in the hop chain. */
function NodeBubble({ label, tone = 'idle', title }) {
  const bg =
    tone === 'gateway'
      ? 'var(--ok)'
      : tone === 'active'
        ? 'var(--accent)'
        : tone === 'origin'
          ? 'var(--warn)'
          : 'var(--surface-2)'
  const fg = tone === 'idle' ? 'var(--muted)' : '#04201d'
  return (
    <span
      title={title}
      style={{
        width: 30,
        height: 30,
        borderRadius: '50%',
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontWeight: 800,
        fontSize: 13,
        background: bg,
        color: fg,
        border: '1.5px solid var(--line)',
        flex: 'none',
      }}
    >
      {label}
    </span>
  )
}

function HopChain({ relay }) {
  const path = relay.path || []
  const delivered = relay.status === 'delivered'
  return (
    <div className="row" style={{ gap: 5, flexWrap: 'wrap' }}>
      {path.map((label, i) => {
        const isLast = i === path.length - 1
        const tone =
          i === 0 ? 'origin' : isLast && delivered ? 'gateway' : isLast ? 'active' : 'active'
        return (
          <span key={`${label}-${i}`} className="row" style={{ gap: 5 }}>
            {i > 0 && (
              <span
                aria-hidden
                style={{
                  color: 'var(--accent)',
                  fontWeight: 800,
                  animation: delivered ? 'none' : 'pulse 1.4s ease-in-out infinite',
                }}
              >
                →
              </span>
            )}
            <NodeBubble label={label} tone={tone} />
          </span>
        )
      })}
      {relay.status === 'searching' && (
        <span className="row" style={{ gap: 5 }}>
          <span aria-hidden style={{ color: 'var(--muted)' }}>
            →
          </span>
          <NodeBubble label="?" tone="idle" />
        </span>
      )}
      {delivered && (
        <span className="row" style={{ gap: 5 }}>
          <span aria-hidden style={{ color: 'var(--ok)', fontWeight: 800 }}>
            →
          </span>
          <span className="pill ok">
            <Check width="12" height="12" />
            control room
          </span>
        </span>
      )}
    </div>
  )
}

export default function Mesh() {
  const { t } = useTranslation()
  const { deadZone } = useLink()
  const [state, setState] = useState(getMeshState())

  useEffect(() => {
    startMesh()
    setState(getMeshState())
    const un = subscribeMesh(setState)
    // Peers expire on a timer, so refresh even when no message arrives.
    const iv = setInterval(() => setState(getMeshState()), 2000)
    return () => {
      un()
      clearInterval(iv)
    }
  }, [])

  const { self, peers, relays, transport } = state
  const openPeer = () => {
    const next = String.fromCharCode(
      65 + ((NODE_LABEL.charCodeAt(0) - 65 + 1 + peers.length) % 8)
    )
    window.open(`${location.origin}${location.pathname}?node=${next}#/mesh`, '_blank')
  }

  return (
    <main className="screen mesh-screen">
      {/* ---- honest labelling ---- */}
      <section className="card" style={{ borderColor: 'var(--accent-dim)' }}>
        <div className="row between">
          <h2 style={{ margin: 0 }}>
            <MeshIcon width="17" height="17" /> {t('mesh.title')}
          </h2>
          <span className="pill accent">{t('mesh.demo_badge')}</span>
        </div>
        <p className="tiny muted" style={{ margin: '8px 0 0' }}>
          {t('mesh.explainer')}
        </p>
        <div className="tiny" style={{ marginTop: 8, color: 'var(--muted)' }}>
          {transport.mode === 'ws' ? t('mesh.transport_ws') : t('mesh.transport_local')}
        </div>
      </section>

      {/* ---- this node ---- */}
      <section className="card">
        <h3>{t('mesh.this_node')}</h3>
        <div className="row between">
          <div className="row" style={{ gap: 10 }}>
            <NodeBubble label={self.label} tone={self.online ? 'gateway' : 'origin'} />
            <div>
              <div className="small" style={{ fontWeight: 700 }}>
                {t('mesh.node', { label: self.label })}
              </div>
              <div className="tiny muted mono">{self.vehicle_id}</div>
            </div>
          </div>
          <span className={self.online ? 'pill ok' : 'pill warn'}>
            {self.online ? <Wifi width="12" height="12" /> : <WifiOff width="12" height="12" />}
            {self.online ? t('mesh.status_online') : t('mesh.status_offline')}
          </span>
        </div>
        {self.carrying > 0 && (
          <div className="banner" style={{ marginTop: 10 }}>
            <Upload width="14" height="14" />
            {t('mesh.carried', { count: self.carrying })}
          </div>
        )}
        <button
          className={deadZone ? 'btn primary block' : 'btn block'}
          style={{ marginTop: 10 }}
          onClick={() => toggleDeadZone()}
        >
          {deadZone ? t('mesh.status_online') : t('link.toggle_deadzone')}
        </button>
      </section>

      {/* ---- peers ---- */}
      <section className="card">
        <div className="row between" style={{ marginBottom: 10 }}>
          <h3 style={{ margin: 0 }}>{t('mesh.peers')}</h3>
          <button className="btn ghost sm" onClick={openPeer}>
            {t('mesh.open_peer')}
          </button>
        </div>
        {peers.length === 0 ? (
          <p className="empty" style={{ padding: 10 }}>
            {t('mesh.no_peers')}
          </p>
        ) : (
          <div className="col" style={{ gap: 8 }}>
            {peers.map(p => (
              <div
                key={p.nodeId}
                className="row between"
                style={{ opacity: p.inRange ? 1 : 0.45 }}
              >
                <div className="row" style={{ gap: 9 }}>
                  <NodeBubble label={p.label} tone={p.online ? 'gateway' : 'origin'} />
                  <div>
                    <div className="small" style={{ fontWeight: 650 }}>
                      {t('mesh.node', { label: p.label })}
                    </div>
                    <div className="tiny muted">
                      {p.inRange
                        ? p.online
                          ? t('mesh.gateway_hint')
                          : t('mesh.dead_zone_node')
                        : t('mesh.out_of_range')}
                    </div>
                  </div>
                </div>
                <span className={!p.inRange ? 'pill' : p.online ? 'pill ok' : 'pill warn'}>
                  {!p.inRange
                    ? t('mesh.out_of_range_short')
                    : p.online
                      ? t('mesh.gateway')
                      : t('mesh.status_offline')}
                </span>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* ---- relay activity ---- */}
      <section className="card">
        <div className="row between" style={{ marginBottom: 4 }}>
          <h3 style={{ margin: 0 }}>{t('mesh.relays')}</h3>
          <button className="btn primary sm" onClick={() => runRelayDemo()}>
            {t('mesh.demo_run')}
          </button>
        </div>
        <p className="tiny muted" style={{ margin: '0 0 10px' }}>
          {t('mesh.demo_hint')}
        </p>

        {relays.length === 0 ? (
          <p className="empty" style={{ padding: 10 }}>
            {t('mesh.no_relays')}
          </p>
        ) : (
          <div className="col" style={{ gap: 10 }}>
            {relays.map(r => (
              <div
                key={r.event_id}
                style={{
                  padding: '10px 11px',
                  borderRadius: 11,
                  background: 'var(--bg)',
                  border: '1px solid var(--line)',
                }}
              >
                <div className="row between" style={{ marginBottom: 8, gap: 8 }}>
                  <span className="small truncate grow" style={{ fontWeight: 650 }}>
                    {t(`report.types.${r.type}`, r.type || 'report')}
                  </span>
                  <span className={`pill ${STATUS_TONE[r.status] || ''}`}>
                    {r.status === 'delivered' && <Check width="12" height="12" />}
                    {r.status}
                  </span>
                </div>
                <HopChain relay={r} />
                <div className="tiny muted" style={{ marginTop: 7 }}>
                  {r.status === 'delivered'
                    ? t('mesh.relay_delivered', { node: r.gateway || r.path?.at(-1) })
                    : r.status === 'searching'
                      ? t('mesh.relay_started', { from: r.origin })
                      : r.status === 'no_peer'
                        ? t('mesh.relay_waiting')
                        : t('mesh.path') + ': ' + (r.path || []).join(' → ')}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </main>
  )
}
