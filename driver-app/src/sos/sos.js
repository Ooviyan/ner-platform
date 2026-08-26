import { db } from '../db/db.js'
import { postAlert, postLocationPing, isOnline } from '../api/client.js'
import { uuid, VEHICLE_ID, NODE_LABEL } from '../config.js'
import i18n from '../i18n/index.js'

/**
 * Active-SOS state machine.
 *
 * Lives outside React so an alert keeps running (and keeps sharing location)
 * while the driver moves between screens, and survives a reload — an emergency
 * must not be cancelled by a stray navigation.
 */

const ACTIVE_KEY = 'ner.sos.active'
const PING_INTERVAL_MS = 15000

const SEVERITY = {
  accident: 'critical',
  medical: 'critical',
  danger: 'high',
  breakdown: 'medium',
}

const RECIPIENTS = [
  'mdoner-control-room',
  'district-admin',
  'nearest-patrol-unit',
  'fleet-operator',
]

let active = null
let watchId = null
let pingTimer = null
const listeners = new Set()

function load() {
  try {
    const raw = localStorage.getItem(ACTIVE_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

function persist() {
  if (active) localStorage.setItem(ACTIVE_KEY, JSON.stringify(active))
  else localStorage.removeItem(ACTIVE_KEY)
}

function emit() {
  persist()
  const snap = getActive()
  for (const fn of listeners) {
    try {
      fn(snap)
    } catch {
      /* ignore */
    }
  }
}

export function subscribeSos(fn) {
  listeners.add(fn)
  return () => listeners.delete(fn)
}

export function getActive() {
  return active ? { ...active } : null
}

/** Build the alert.json contract payload for an SOS. */
function buildAlert(type) {
  return {
    id: `alt-${uuid().slice(0, 8)}`,
    event: `sos_${type}`,
    severity: SEVERITY[type] || 'high',
    recipients: RECIPIENTS,
    lang: (i18n.resolvedLanguage || i18n.language || 'en').split('-')[0],
    status: 'raised',
  }
}

function startWatching() {
  if (!('geolocation' in navigator)) return
  watchId = navigator.geolocation.watchPosition(
    pos => {
      if (!active) return
      active.fix = {
        lat: +pos.coords.latitude.toFixed(6),
        lng: +pos.coords.longitude.toFixed(6),
        accuracy: pos.coords.accuracy != null ? Math.round(pos.coords.accuracy) : null,
        at: new Date(pos.timestamp).toISOString(),
      }
      emit()
    },
    err => {
      if (!active) return
      active.geo_error = err.code === 1 ? 'denied' : 'unavailable'
      emit()
    },
    { enableHighAccuracy: true, timeout: 20000, maximumAge: 5000 }
  )
}

async function sendPing() {
  if (!active) return
  const ping = {
    alert_id: active.alert.id,
    vehicle_id: VEHICLE_ID,
    node: NODE_LABEL,
    lat: active.fix?.lat ?? null,
    lng: active.fix?.lng ?? null,
    accuracy: active.fix?.accuracy ?? null,
    at: new Date().toISOString(),
  }
  if (!isOnline()) {
    active.unsent_pings = (active.unsent_pings || 0) + 1
    emit()
    return
  }
  const ack = await postLocationPing(ping)
  if (ack) {
    active.pings = (active.pings || 0) + 1
    // Anything buffered during the outage counts as delivered on reconnect.
    active.pings += active.unsent_pings || 0
    active.unsent_pings = 0
    emit()
  }
}

/**
 * Raise an emergency alert and begin sharing live location.
 * Never rejects — an SOS with no signal is queued, not lost.
 */
export async function startSos(type) {
  if (active) return getActive()
  const alert = buildAlert(type)
  active = {
    type,
    alert,
    started_at: new Date().toISOString(),
    pings: 0,
    unsent_pings: 0,
    delivered: false,
    fix: null,
  }
  emit()

  startWatching()
  clearInterval(pingTimer)
  pingTimer = setInterval(sendPing, PING_INTERVAL_MS)

  await db.alerts.put({ ...alert, created_at: Date.now(), vehicle_id: VEHICLE_ID })

  try {
    if (!isOnline()) throw new Error('offline')
    await postAlert(alert)
    active.delivered = true
    active.alert = { ...alert, status: 'delivered' }
    await db.alerts.put({
      ...active.alert,
      created_at: Date.now(),
      vehicle_id: VEHICLE_ID,
    })
  } catch {
    active.delivered = false
    active.queued = true
  }
  emit()
  // First fix often arrives after the alert; ping straight away regardless.
  sendPing()
  return getActive()
}

/** Stand down the active SOS. */
export async function stopSos() {
  if (!active) return
  const { alert } = active
  clearInterval(pingTimer)
  pingTimer = null
  if (watchId != null && 'geolocation' in navigator) {
    navigator.geolocation.clearWatch(watchId)
    watchId = null
  }
  const closed = { ...alert, status: 'stood_down' }
  await db.alerts.put({
    ...closed,
    created_at: Date.now(),
    vehicle_id: VEHICLE_ID,
    ended_at: new Date().toISOString(),
  })
  if (isOnline()) {
    try {
      await postAlert(closed)
    } catch {
      /* the control room still has the raise; best effort */
    }
  }
  active = null
  emit()
}

/** Re-attach watchers to an SOS that was running before a reload. */
export function resumeSos() {
  const saved = load()
  if (!saved || active) return
  active = saved
  startWatching()
  clearInterval(pingTimer)
  pingTimer = setInterval(sendPing, PING_INTERVAL_MS)
  emit()
}

/** Retry delivery of an SOS that was raised with no signal. */
export async function retryDelivery() {
  if (!active || active.delivered || !isOnline()) return
  try {
    await postAlert(active.alert)
    active.delivered = true
    active.queued = false
    active.alert = { ...active.alert, status: 'delivered' }
    emit()
  } catch {
    /* stay queued */
  }
}

window.addEventListener('online', () => retryDelivery())

export { SEVERITY, RECIPIENTS }
