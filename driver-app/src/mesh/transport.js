import { WS_URL, uuid } from '../config.js'

/**
 * Message bus for the simulated mesh.
 *
 * Two transports run side by side and every message goes out on both:
 *
 *  - BroadcastChannel: reaches other tabs/windows on this machine. This is what
 *    makes the demo work with no backend at all.
 *  - WebSocket (VITE_WS_URL): reaches the backend, which re-broadcasts to the
 *    other driver apps AND to the dashboard, so both animate the same relay.
 *
 * Inbound messages are de-duplicated by `mid`, so a message that arrives over
 * both transports is only handled once.
 *
 * NOTE: this bus stands in for a BLE radio. A node in the simulated dead zone
 * still uses it — that is the point of the simulation, and it is labelled as
 * such in the UI. Real phone-to-phone BLE mesh is documented Phase 2 work.
 */

const CHANNEL = 'ner-mesh'
const SEEN_LIMIT = 400

const handlers = new Set()
const seen = new Set()
const seenOrder = []

let bc = null
let ws = null
let wsState = WS_URL ? 'connecting' : 'disabled'
let reconnectAttempt = 0
let reconnectTimer = null

const statusListeners = new Set()

export function transportStatus() {
  return {
    ws: wsState,
    wsUrl: WS_URL || null,
    broadcast: bc ? 'open' : 'unavailable',
    // What the UI should tell the user is coordinating the relay.
    mode: wsState === 'open' ? 'ws' : 'local',
  }
}

export function subscribeTransport(fn) {
  statusListeners.add(fn)
  return () => statusListeners.delete(fn)
}

function notifyStatus() {
  const s = transportStatus()
  for (const fn of statusListeners) {
    try {
      fn(s)
    } catch {
      /* ignore */
    }
  }
}

function deliver(msg) {
  if (!msg || typeof msg !== 'object' || !msg.mid) return
  if (seen.has(msg.mid)) return
  seen.add(msg.mid)
  seenOrder.push(msg.mid)
  if (seenOrder.length > SEEN_LIMIT) seen.delete(seenOrder.shift())
  for (const fn of handlers) {
    try {
      fn(msg)
    } catch (err) {
      console.error('[mesh] handler failed', err)
    }
  }
}

/* ------------------------------------------------------- BroadcastChannel */

if ('BroadcastChannel' in globalThis) {
  bc = new BroadcastChannel(CHANNEL)
  bc.onmessage = e => deliver(e.data)
}

/* -------------------------------------------------------------- WebSocket */

function connectWs() {
  if (!WS_URL) return
  clearTimeout(reconnectTimer)
  try {
    ws = new WebSocket(WS_URL)
  } catch {
    scheduleReconnect()
    return
  }
  wsState = 'connecting'
  notifyStatus()

  ws.onopen = () => {
    wsState = 'open'
    reconnectAttempt = 0
    notifyStatus()
  }
  ws.onmessage = e => {
    try {
      deliver(JSON.parse(e.data))
    } catch {
      /* ignore malformed frames */
    }
  }
  ws.onclose = () => {
    wsState = 'closed'
    notifyStatus()
    scheduleReconnect()
  }
  ws.onerror = () => {
    wsState = 'error'
    notifyStatus()
  }
}

function scheduleReconnect() {
  if (!WS_URL) return
  reconnectAttempt++
  const delay = Math.min(15000, 800 * 2 ** Math.min(reconnectAttempt, 4))
  reconnectTimer = setTimeout(connectWs, delay)
}

connectWs()

/* ------------------------------------------------------------------- API */

/** Broadcast a mesh message on every available transport. */
export function publish(type, payload) {
  const msg = { mid: uuid(), type, at: Date.now(), ...payload }
  try {
    bc?.postMessage(msg)
  } catch {
    /* channel closed */
  }
  if (ws && ws.readyState === WebSocket.OPEN) {
    try {
      ws.send(JSON.stringify(msg))
    } catch {
      /* dropped frame; BroadcastChannel still carried it locally */
    }
  }
  // Mark as seen so our own broadcast does not loop back through the WS relay.
  seen.add(msg.mid)
  seenOrder.push(msg.mid)
  // Same eviction as deliver(): without it a long-running node grows `seen`
  // by one entry per published message and never gives the memory back.
  if (seenOrder.length > SEEN_LIMIT) seen.delete(seenOrder.shift())
  return msg
}

export function onMessage(fn) {
  handlers.add(fn)
  return () => handlers.delete(fn)
}
