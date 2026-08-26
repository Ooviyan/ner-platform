// Central place for everything environment- or device-specific.
// The app must run with no backend at all, so every value has a usable default.

const env = import.meta.env

/** Base URL we read/write platform data from. `/mock-data` = standalone mode. */
export const API_URL = (env.VITE_API_URL || '/mock-data').replace(/\/+$/, '')

/** True when we are pointed at the static fixtures rather than a real backend. */
export const MOCK_MODE = API_URL.endsWith('/mock-data')

/** WebSocket the backend broadcasts simulated-mesh hops on. Empty = tab-local relay. */
export const WS_URL = env.VITE_WS_URL || ''

const LS = {
  nodeId: 'ner.node.id',
  nodeLabel: 'ner.node.label',
  vehicleId: 'ner.vehicle.id',
  deadZone: 'ner.node.deadzone',
  lang: 'ner.lang',
}

function readParam(name) {
  try {
    return new URLSearchParams(window.location.search).get(name)
  } catch {
    return null
  }
}

/**
 * Node identity and the dead-zone switch live in sessionStorage, NOT
 * localStorage: sessionStorage is per-tab, so every open instance is a distinct
 * mesh node with its own signal state. Sharing them across tabs would make the
 * whole app look like one node and break the relay demo.
 */
function persisted(key, make) {
  let v = sessionStorage.getItem(key)
  if (!v) {
    v = make()
    sessionStorage.setItem(key, v)
  }
  return v
}

/**
 * Stable identity for this browser tab acting as a mesh node.
 * `?node=B` lets the demo pin a specific letter when opening several tabs.
 */
export const NODE_ID = persisted(LS.nodeId, () =>
  'node-' + Math.random().toString(36).slice(2, 8)
)

const LETTERS = 'ABCDEFGH'
export const NODE_LABEL = (() => {
  const forced = readParam('node')
  if (forced) {
    sessionStorage.setItem(LS.nodeLabel, forced.toUpperCase().slice(0, 2))
  }
  return persisted(LS.nodeLabel, () => LETTERS[Math.floor(Math.random() * LETTERS.length)])
})()

export const VEHICLE_ID =
  readParam('vehicle') ||
  localStorage.getItem(LS.vehicleId) ||
  env.VITE_VEHICLE_ID ||
  'AS-01-EG-4417'

export function setVehicleId(id) {
  localStorage.setItem(LS.vehicleId, id)
}

/**
 * Manual "no signal" switch used to simulate a dead zone during the demo.
 * Per-tab (sessionStorage) so one node can be in a dead zone while another
 * acts as the online gateway.
 */
export function getDeadZone() {
  return sessionStorage.getItem(LS.deadZone) === '1'
}
export function setDeadZone(on) {
  sessionStorage.setItem(LS.deadZone, on ? '1' : '0')
}

export const STORAGE_KEYS = LS

/** RFC4122-ish id; crypto.randomUUID is unavailable on insecure non-localhost origins. */
export function uuid() {
  if (globalThis.crypto?.randomUUID) return crypto.randomUUID()
  const b = new Uint8Array(16)
  ;(globalThis.crypto || { getRandomValues: a => a.map(() => (Math.random() * 256) | 0) })
    .getRandomValues(b)
  b[6] = (b[6] & 0x0f) | 0x40
  b[8] = (b[8] & 0x3f) | 0x80
  const h = [...b].map(x => x.toString(16).padStart(2, '0')).join('')
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`
}
