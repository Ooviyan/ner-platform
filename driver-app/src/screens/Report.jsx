import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useLiveQuery } from 'dexie-react-hooks'
import { db, INCIDENT_TYPES, REPORT_STATE } from '../db/db.js'
import {
  enqueueReport,
  syncNow,
  retryReport,
  deleteReport,
  onQueueEvent,
} from '../db/queue.js'
import { getCurrentFix } from '../hooks/useGeolocation.js'
import { useLink } from '../hooks/useLink.js'
import { VEHICLE_ID, uuid } from '../config.js'
import { relayReport } from '../mesh/mesh.js'
import { StateBadge, relativeTime } from '../components/common.jsx'
import { Camera, Pin, Refresh, Upload } from '../components/icons.jsx'

const MAX_PHOTO_BYTES = 8 * 1024 * 1024

/** Downscale to keep IndexedDB rows small and uploads viable on 2G. */
function compressImage(file, maxEdge = 1280, quality = 0.72) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file)
    const img = new Image()
    img.onload = () => {
      URL.revokeObjectURL(url)
      const scale = Math.min(1, maxEdge / Math.max(img.width, img.height))
      const canvas = document.createElement('canvas')
      canvas.width = Math.round(img.width * scale)
      canvas.height = Math.round(img.height * scale)
      canvas.getContext('2d').drawImage(img, 0, 0, canvas.width, canvas.height)
      resolve(canvas.toDataURL('image/jpeg', quality))
    }
    img.onerror = () => {
      URL.revokeObjectURL(url)
      reject(new Error('image decode failed'))
    }
    img.src = url
  })
}

export default function Report() {
  const { t } = useTranslation()
  const { linkUp, deadZone } = useLink()

  const [type, setType] = useState(null)
  const [photo, setPhoto] = useState(null)
  const [note, setNote] = useState('')
  const [fix, setFix] = useState(null)
  const [locating, setLocating] = useState(true)
  const [busy, setBusy] = useState(false)
  const [toast, setToast] = useState(null)
  const [syncing, setSyncing] = useState(false)
  const fileRef = useRef(null)
  const cameraRef = useRef(null)

  const rows = useLiveQuery(() => db.reports.orderBy('timestamp').reverse().toArray(), [], [])

  const refreshLocation = async () => {
    setLocating(true)
    setFix(await getCurrentFix())
    setLocating(false)
  }

  useEffect(() => {
    refreshLocation()
  }, [])

  useEffect(
    () =>
      onQueueEvent(e => {
        if (e.type === 'sync:start') setSyncing(true)
        if (e.type === 'sync:done') setSyncing(false)
      }),
    []
  )

  const onPickPhoto = async e => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    if (file.size > MAX_PHOTO_BYTES) {
      setToast({ kind: 'danger', text: t('report.photo_too_large') })
      return
    }
    try {
      setPhoto(await compressImage(file))
    } catch {
      setToast({ kind: 'danger', text: t('common.error') })
    }
  }

  const submit = async () => {
    if (!type) {
      setToast({ kind: 'warn', text: t('report.select_type_first') })
      return
    }
    setBusy(true)
    // Re-read position at submit time so the coordinate matches the incident.
    const current = fix || (await getCurrentFix())
    const draft = {
      event_id: uuid(),
      type,
      lat: current.lat,
      lng: current.lng,
      accuracy: current.accuracy,
      timestamp: new Date().toISOString(),
      photo,
      note,
      vehicle_id: VEHICLE_ID,
    }

    try {
      if (!linkUp) {
        // No signal: hold it locally as pending, then offer it to the simulated
        // mesh. The mesh promotes it to `relaying` only if a peer is actually
        // reachable, so a report that finds no peer still uploads normally the
        // moment this device regains signal.
        const row = await enqueueReport(draft)
        relayReport(row)
        setToast({
          kind: 'warn',
          text: deadZone ? t('report.queued_relay') : t('report.queued_offline'),
        })
      } else {
        await enqueueReport(draft)
        const res = await syncNow()
        setToast(
          res.uploaded > 0
            ? { kind: 'ok', text: t('report.sent') }
            : { kind: 'warn', text: t('report.queued_offline') }
        )
      }
      setType(null)
      setPhoto(null)
      setNote('')
    } catch {
      setToast({ kind: 'danger', text: t('common.error') })
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="screen report-screen">
      <section className="card">
        <h2>{t('report.title')}</h2>
        <p className="small muted" style={{ margin: '0 0 12px' }}>
          {t('report.subtitle')}
        </p>

        <h3>{t('report.type_label')}</h3>
        <div className="chips">
          {INCIDENT_TYPES.map(it => (
            <button
              key={it.id}
              className="chip"
              aria-pressed={type === it.id}
              onClick={() => setType(type === it.id ? null : it.id)}
            >
              <span className="ico" aria-hidden>
                {it.icon}
              </span>
              <span>{t(`report.types.${it.id}`)}</span>
            </button>
          ))}
        </div>

        <hr className="sep" />

        {/* ---- photo ---- */}
        <h3>{t('report.photo')}</h3>
        {photo ? (
          <div className="col" style={{ gap: 8 }}>
            <img
              src={photo}
              alt=""
              style={{
                width: '100%',
                borderRadius: 11,
                border: '1px solid var(--line)',
                maxHeight: 220,
                objectFit: 'cover',
              }}
            />
            <button className="btn ghost sm" onClick={() => setPhoto(null)}>
              {t('report.remove_photo')}
            </button>
          </div>
        ) : (
          <div className="row" style={{ gap: 8 }}>
            <button className="btn grow" onClick={() => cameraRef.current?.click()}>
              <Camera width="17" height="17" /> {t('report.take_photo')}
            </button>
            <button className="btn ghost grow" onClick={() => fileRef.current?.click()}>
              {t('report.choose_photo')}
            </button>
          </div>
        )}
        <input
          ref={cameraRef}
          type="file"
          accept="image/*"
          capture="environment"
          hidden
          onChange={onPickPhoto}
        />
        <input ref={fileRef} type="file" accept="image/*" hidden onChange={onPickPhoto} />

      </section>

      {/* Second card: what the driver types and confirms, then sends. Split from
          the card above so a wide screen can put the two side by side -- on a
          dash tablet they stack again and read as one flow. */}
      <section className="card report-detail">
        <label className="field">
          {t('report.note')}
          <textarea
            className="input"
            value={note}
            maxLength={400}
            placeholder={t('report.note_placeholder')}
            onChange={e => setNote(e.target.value)}
          />
        </label>

        <hr className="sep" />

        {/* ---- auto-captured context ---- */}
        <h3>{t('report.location')}</h3>
        <div className="row between" style={{ gap: 10 }}>
          <div className="grow" style={{ minWidth: 0 }}>
            {locating ? (
              <span className="small muted">{t('report.locating')}</span>
            ) : (
              <>
                <div className="small mono">
                  <Pin width="13" height="13" /> {fix?.lat?.toFixed(5)}, {fix?.lng?.toFixed(5)}
                </div>
                <div className="tiny muted">
                  {fix?.accuracy != null && t('report.accuracy', { m: fix.accuracy })}
                  {fix?.error === 'denied' && ` · ${t('report.location_denied')}`}
                </div>
              </>
            )}
          </div>
          <button className="btn ghost sm" onClick={refreshLocation} disabled={locating}>
            <Refresh width="14" height="14" /> {t('report.refresh_location')}
          </button>
        </div>
        <div className="row between small muted" style={{ marginTop: 8 }}>
          <span>{t('report.vehicle')}</span>
          <span className="mono">{VEHICLE_ID}</span>
        </div>

        {toast && (
          <div className={`banner ${toast.kind}`} style={{ marginTop: 12 }}>
            {toast.text}
          </div>
        )}

        <button
          className="btn primary block"
          style={{ marginTop: 12 }}
          onClick={submit}
          disabled={busy}
        >
          {busy ? t('report.submitting') : t('report.submit')}
        </button>
      </section>

      {/* ---- queue ---- */}
      <section className="card">
        <div className="row between" style={{ marginBottom: 10 }}>
          <h3 style={{ margin: 0 }}>{t('report.queue_title')}</h3>
          <button
            className="btn ghost sm"
            onClick={() => syncNow()}
            disabled={syncing || !linkUp}
          >
            <Upload width="14" height="14" />
            {syncing ? t('report.syncing') : t('report.sync_now')}
          </button>
        </div>

        {rows.length === 0 ? (
          <p className="empty" style={{ padding: 14 }}>
            {t('report.queue_empty')}
          </p>
        ) : (
          <div className="col" style={{ gap: 9 }}>
            {rows.map(r => (
              <div
                key={r.event_id}
                style={{
                  padding: '10px 11px',
                  borderRadius: 11,
                  background: 'var(--bg)',
                  border: '1px solid var(--line)',
                }}
              >
                <div className="row between" style={{ gap: 8 }}>
                  <span className="small truncate grow" style={{ fontWeight: 650 }}>
                    {t(`report.types.${r.type}`, r.type)}
                  </span>
                  <StateBadge state={r.state} />
                </div>
                <div className="tiny muted" style={{ marginTop: 3 }}>
                  {relativeTime(r.timestamp, t)} · {r.lat?.toFixed(4)}, {r.lng?.toFixed(4)}
                  {r.attempts > 0 && ` · ${t('report.attempts', { count: r.attempts })}`}
                </div>
                {r.relay_path?.length > 0 && (
                  <div className="tiny" style={{ color: 'var(--accent)', marginTop: 3 }}>
                    {t('mesh.path')}: {r.relay_path.join(' → ')}
                  </div>
                )}
                {r.last_error && (
                  <div className="tiny" style={{ color: 'var(--danger)', marginTop: 3 }}>
                    {r.last_error}
                  </div>
                )}
                <div className="row" style={{ gap: 7, marginTop: 8 }}>
                  {(r.state === REPORT_STATE.FAILED || r.state === REPORT_STATE.PENDING) && (
                    <button
                      className="btn ghost sm"
                      onClick={() => retryReport(r.event_id)}
                      disabled={!linkUp}
                    >
                      {t('report.retry')}
                    </button>
                  )}
                  <button className="btn ghost sm" onClick={() => deleteReport(r.event_id)}>
                    {t('report.delete')}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </main>
  )
}
