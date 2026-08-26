import { publish, onMessage, transportStatus, subscribeTransport } from './transport.js'
import { NODE_ID, NODE_LABEL, VEHICLE_ID, uuid } from '../config.js'
import { isLinkUp, subscribeLink, toggleDeadZone } from '../net/link.js'
import { REPORT_STATE, toContract } from '../db/db.js'
import {
  markState,
  mergeIncomingReport,
  syncNow,
  getReport,
  enqueueReport,
} from '../db/queue.js'
import { postReport } from '../api/client.js'

/**
 * Simulated mesh relay.
 *
 * A report filed by a node with no signal is offered to the mesh. Peers that
 * hear the offer bid to carry it: a peer WITH signal bids fast and becomes the
 * gateway; peers WITHOUT signal bid slower, accept the report, and re-offer it
 * one hop further. The result is a visible A → B → C chain ending at whichever
 * node can actually reach the platform, which then uploads it.
 *
 * This is an honest simulation for the demo — see transport.js. Real BLE mesh
 * is Phase 2.
 */

const HEARTBEAT_MS = 3000
const PEER_TTL_MS = 25000
const MAX_HOPS = 6
/** A node with signal bids in this window; a node without signal waits longer. */
const BID_GATEWAY_MS = [120, 260]
const BID_CARRIER_MS = [650, 950]
/** If nobody carries it onward, the report reverts to the normal upload queue. */
const OFFER_GIVEUP_MS = 4000

const peers = new Map() // nodeId -> { nodeId, label, online, vehicle_id, lastSeen }
const relays = new Map() // event_id -> { event_id, type, path, status, hops[], started_at }
const pendingBids = new Map() // event_id -> timeout id
const carrying = new Set() // event_ids this node accepted while offline
const giveUpTimers = new Map()

const listeners = new Set()

function rand([lo, hi]) {
  return lo + Math.random() * (hi - lo)
}

/**
 * Radio range, simulated as a chain topology: a node only hears its immediate
 * letter-neighbours (A↔B↔C↔D…).
 *
 * Without a range model every node would hear every offer and an online node
 * would always win the very first bid, so a report could never visibly travel
 * more than one hop. The chain is what makes A → B → C real: A cannot reach the
 * gateway itself, so B must carry the report the rest of the way.
 */
export function inRange(a, b) {
  if (!a || !b) return false
  return Math.abs(a.charCodeAt(0) - b.charCodeAt(0)) === 1
}

function emit() {
  const snap = getMeshState()
  for (const fn of listeners) {
    try {
      fn(snap)
    } catch {
      /* ignore */
    }
  }
}

export function subscribeMesh(fn) {
  listeners.add(fn)
  return () => listeners.delete(fn)
}

export function getMeshState() {
  prunePeers()
  return {
    self: {
      nodeId: NODE_ID,
      label: NODE_LABEL,
      online: isLinkUp(),
      vehicle_id: VEHICLE_ID,
      carrying: carrying.size,
    },
    peers: [...peers.values()]
      .map(p => ({ ...p, inRange: inRange(NODE_LABEL, p.label) }))
      .sort((a, b) => a.label.localeCompare(b.label)),
    relays: [...relays.values()].sort((a, b) => b.started_at - a.started_at).slice(0, 8),
    transport: transportStatus(),
  }
}

function prunePeers() {
  const now = Date.now()
  let changed = false
  for (const [id, p] of peers) {
    if (now - p.lastSeen > PEER_TTL_MS) {
      peers.delete(id)
      changed = true
    }
  }
  return changed
}

function track(event_id, patch) {
  const existing = relays.get(event_id) || {
    event_id,
    path: [],
    hops: [],
    status: 'offered',
    started_at: Date.now(),
  }
  const next = { ...existing, ...patch }
  relays.set(event_id, next)
  if (relays.size > 40) relays.delete([...relays.keys()][0])
  emit()
  return next
}

/* ------------------------------------------------------------- heartbeat */

function announce(isReply = false) {
  publish('hello', {
    nodeId: NODE_ID,
    label: NODE_LABEL,
    online: isLinkUp(),
    vehicle_id: VEHICLE_ID,
    reply: isReply,
  })
}

/** Announce immediately — used on mount and when returning to the foreground. */
export function pokeMesh() {
  announce()
}

/* ------------------------------------------------------------ relay entry */

/**
 * Offer a locally-filed report to the mesh. Called when this device has no
 * signal. If no peer takes it, the report simply stays in the normal upload
 * queue and goes out when signal returns.
 */
export function relayReport(row) {
  if (!row?.event_id) return
  const path = [NODE_LABEL]
  // Only promote to `relaying` when there is actually somebody to relay to;
  // otherwise it stays `pending` and the normal queue owns it.
  const reachable = [...peers.values()].some(p => inRange(NODE_LABEL, p.label))
  if (reachable) markState(row.event_id, REPORT_STATE.RELAYING)
  track(row.event_id, {
    event_id: row.event_id,
    type: row.type,
    path,
    status: 'searching',
    origin: NODE_LABEL,
    started_at: Date.now(),
  })
  offer(row, path)
  armGiveUp(row.event_id)
}

function armGiveUp(event_id) {
  clearTimeout(giveUpTimers.get(event_id))
  giveUpTimers.set(
    event_id,
    setTimeout(async () => {
      const rel = relays.get(event_id)
      if (rel && (rel.status === 'searching' || rel.status === 'offered')) {
        track(event_id, { status: 'no_peer' })
        // Fall back to the ordinary offline queue.
        const row = await getReport(event_id)
        if (row && row.state === REPORT_STATE.RELAYING) {
          await markState(event_id, REPORT_STATE.PENDING)
        }
      }
    }, OFFER_GIVEUP_MS)
  )
}

function offer(row, path) {
  publish('relay_offer', {
    from: NODE_LABEL,
    fromId: NODE_ID,
    path,
    hop: path.length,
    report: toContract({ ...row, state: REPORT_STATE.PENDING }),
    // local-only extras the carrier needs to render the card
    note: row.note || '',
    accuracy: row.accuracy ?? null,
  })
}

/* --------------------------------------------------------- message handling */

async function handleOffer(msg) {
  const { report, path = [], from } = msg
  if (!report?.event_id) return
  if (path.includes(NODE_LABEL)) return // already carried it; don't loop
  if (path.length >= MAX_HOPS) return
  // Only the current holder's radio neighbours can hear this offer.
  const holder = path[path.length - 1] || from
  if (!inRange(holder, NODE_LABEL)) return

  const eventId = report.event_id
  track(eventId, {
    event_id: eventId,
    type: report.type,
    path,
    status: 'offered',
    origin: path[0] || from,
  })

  // Bid to carry. A node with signal bids fast so it wins and becomes the
  // gateway; a node without signal bids slower and merely carries it onward.
  const online = isLinkUp()
  const wait = rand(online ? BID_GATEWAY_MS : BID_CARRIER_MS)

  clearTimeout(pendingBids.get(eventId))
  pendingBids.set(
    eventId,
    setTimeout(() => claim(msg, online), wait)
  )
}

async function claim(msg, online) {
  const { report, path = [] } = msg
  const eventId = report.event_id
  pendingBids.delete(eventId)

  const nextPath = [...path, NODE_LABEL]

  // Announce the hop first so every node (and the dashboard) animates it.
  publish('relay_hop', {
    event_id: eventId,
    from: path[path.length - 1] || msg.from,
    to: NODE_LABEL,
    toId: NODE_ID,
    hop: nextPath.length - 1,
    path: nextPath,
    gateway: online,
  })

  // Keep a local copy so the report survives even if this carrier is closed.
  await mergeIncomingReport({
    ...report,
    state: online ? REPORT_STATE.PENDING : REPORT_STATE.RELAYING,
    note: msg.note || '',
    accuracy: msg.accuracy ?? null,
    relay_path: nextPath,
    origin_node: path[0] || msg.from,
    carried: true,
    created_at: Date.now(),
  })

  if (online) {
    // We are the gateway: upload on the origin's behalf.
    track(eventId, { status: 'uploading', path: nextPath })
    try {
      const ack = await postReport({ ...report, state: REPORT_STATE.PENDING })
      await markState(eventId, REPORT_STATE.SYNCED, {
        server_id: ack?.server_id || null,
        synced_at: new Date().toISOString(),
        relay_path: nextPath,
      })
      publish('relay_delivered', {
        event_id: eventId,
        by: NODE_LABEL,
        path: nextPath,
        server_id: ack?.server_id || null,
      })
      track(eventId, { status: 'delivered', path: nextPath, gateway: NODE_LABEL })
    } catch {
      // Signal died mid-upload — keep carrying and let the queue retry.
      carrying.add(eventId)
      track(eventId, { status: 'carrying', path: nextPath })
      offer({ ...report, note: msg.note }, nextPath)
    }
  } else {
    // No signal here either: carry it and pass it one hop further.
    carrying.add(eventId)
    track(eventId, { status: 'carrying', path: nextPath })
    setTimeout(() => offer({ ...report, note: msg.note }, nextPath), 500)
  }
  emit()
}

function handleHop(msg) {
  const { event_id, path = [], to, from, gateway } = msg
  // Someone else already took this hop — stand down our own bid.
  const mine = pendingBids.get(event_id)
  if (mine && to !== NODE_LABEL) {
    clearTimeout(mine)
    pendingBids.delete(event_id)
  }
  const rel = relays.get(event_id)
  const hops = [...(rel?.hops || []), { from, to, at: Date.now(), gateway }]
  track(event_id, {
    path,
    hops,
    status: gateway ? 'uploading' : 'carrying',
  })
  clearTimeout(giveUpTimers.get(event_id))
}

async function handleDelivered(msg) {
  const { event_id, path = [], by, server_id } = msg
  clearTimeout(pendingBids.get(event_id))
  pendingBids.delete(event_id)
  clearTimeout(giveUpTimers.get(event_id))
  carrying.delete(event_id)
  track(event_id, { status: 'delivered', path, gateway: by })

  // If this node holds a copy (as origin or carrier), mark it synced — the
  // report reached the platform, just via a different radio.
  const row = await getReport(event_id)
  if (row && row.state !== REPORT_STATE.SYNCED) {
    await markState(event_id, REPORT_STATE.SYNCED, {
      server_id: server_id || row.server_id || null,
      synced_at: new Date().toISOString(),
      relay_path: path,
      delivered_by: by,
    })
  }
  emit()
}

function handleHello(msg) {
  if (msg.nodeId === NODE_ID) return
  const isNew = !peers.has(msg.nodeId)
  peers.set(msg.nodeId, {
    nodeId: msg.nodeId,
    label: msg.label,
    online: !!msg.online,
    vehicle_id: msg.vehicle_id,
    lastSeen: Date.now(),
  })
  // Answer a stranger straight away rather than waiting for the next heartbeat.
  // Browsers throttle timers in background tabs, so discovery must not depend on
  // the two nodes' intervals lining up. `reply` stops the greeting ping-ponging.
  if (isNew && !msg.reply) announce(true)
  emit()
}

/* ---------------------------------------------------------------- startup */

let started = false

export function startMesh() {
  if (started) return
  started = true

  onMessage(msg => {
    // Any traffic proves the sender is still in range.
    if (msg.nodeId && msg.nodeId !== NODE_ID && peers.has(msg.nodeId)) {
      peers.get(msg.nodeId).lastSeen = Date.now()
    }
    switch (msg.type) {
      case 'hello':
        handleHello(msg)
        break
      case 'bye':
        peers.delete(msg.nodeId)
        emit()
        break
      case 'relay_offer':
        handleOffer(msg)
        break
      case 'relay_hop':
        handleHop(msg)
        break
      case 'relay_delivered':
        handleDelivered(msg)
        break
      default:
        break
    }
  })

  announce()
  setInterval(() => announce(), HEARTBEAT_MS)
  // Timers are throttled while hidden, so re-announce the moment we are shown.
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') announce()
  })
  setInterval(() => {
    if (prunePeers()) emit()
  }, PEER_TTL_MS / 2)

  // Coming back into coverage: re-announce, flush anything we carried, and
  // push our own queue.
  subscribeLink(() => {
    announce()
    if (isLinkUp()) flushCarried()
    emit()
  })
  subscribeTransport(emit)

  window.addEventListener('beforeunload', () => {
    publish('bye', { nodeId: NODE_ID, label: NODE_LABEL })
  })
}

/** Upload every report we accepted for a peer, now that we have signal. */
export async function flushCarried() {
  if (!isLinkUp() || carrying.size === 0) return
  for (const eventId of [...carrying]) {
    const row = await getReport(eventId)
    if (!row) {
      carrying.delete(eventId)
      continue
    }
    if (row.state === REPORT_STATE.RELAYING) {
      await markState(eventId, REPORT_STATE.PENDING)
    }
  }
  const res = await syncNow()
  for (const eventId of [...carrying]) {
    const row = await getReport(eventId)
    if (row?.state === REPORT_STATE.SYNCED) {
      carrying.delete(eventId)
      publish('relay_delivered', {
        event_id: eventId,
        by: NODE_LABEL,
        path: row.relay_path || [NODE_LABEL],
        server_id: row.server_id || null,
      })
      track(eventId, { status: 'delivered', gateway: NODE_LABEL, path: row.relay_path || [] })
    }
  }
  return res
}

/**
 * Demo helper: file a synthetic report from this node as if it had no signal,
 * so the A → B → C relay can be shown on demand.
 */
export async function runRelayDemo({ lat = 27.2648, lng = 92.416 } = {}) {
  // The whole point is to show a report escaping a dead zone, so make sure this
  // node is in one before filing.
  if (isLinkUp()) toggleDeadZone(true)
  const row = await enqueueReport(
    {
      event_id: uuid(),
      type: 'landslide',
      lat,
      lng,
      timestamp: new Date().toISOString(),
      photo: null,
      vehicle_id: VEHICLE_ID,
      note: 'Simulated mesh relay demo',
    },
    { state: REPORT_STATE.RELAYING }
  )
  relayReport(row)
  return row
}
