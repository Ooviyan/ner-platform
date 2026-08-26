import { db, REPORT_STATE, toContract } from './db.js'
import { postReport, isOnline } from '../api/client.js'
import { uuid, VEHICLE_ID } from '../config.js'

const MAX_ATTEMPTS = 5

/** Fired whenever the queue changes state, so the UI can show sync progress. */
const listeners = new Set()
export function onQueueEvent(fn) {
  listeners.add(fn)
  return () => listeners.delete(fn)
}
function emit(type, detail) {
  for (const fn of listeners) {
    try {
      fn({ type, ...detail })
    } catch {
      /* a broken listener must not break syncing */
    }
  }
}

/**
 * Persist a new road report locally. Nothing is uploaded here — the queue owns
 * that — so this resolves fast enough to use straight from a form submit.
 *
 * @param {object} draft  { type, lat, lng, photo?, note?, accuracy? }
 * @param {object} opts   { state } to force an initial state (mesh uses 'relaying')
 */
export async function enqueueReport(draft, opts = {}) {
  const row = {
    event_id: draft.event_id || uuid(),
    type: draft.type,
    lat: draft.lat,
    lng: draft.lng,
    timestamp: draft.timestamp || new Date().toISOString(),
    photo: draft.photo ?? null,
    vehicle_id: draft.vehicle_id || VEHICLE_ID,
    state: opts.state || REPORT_STATE.PENDING,
    // local-only bookkeeping
    note: draft.note || '',
    accuracy: draft.accuracy ?? null,
    attempts: 0,
    last_error: null,
    created_at: Date.now(),
    origin_node: draft.origin_node || null,
    relay_path: draft.relay_path || null,
  }
  // put() rather than add(): re-filing the same event_id updates instead of duplicating.
  await db.reports.put(row)
  emit('enqueued', { report: row })
  scheduleSync()
  return row
}

/** Merge a report that arrived from another node without clobbering a synced copy. */
export async function mergeIncomingReport(row) {
  const existing = await db.reports.get(row.event_id)
  if (existing?.state === REPORT_STATE.SYNCED) return existing
  const merged = { ...(existing || {}), ...row }
  await db.reports.put(merged)
  emit('merged', { report: merged })
  return merged
}

export async function markState(event_id, state, patch = {}) {
  const row = await db.reports.get(event_id)
  if (!row) return null
  const next = { ...row, ...patch, state }
  await db.reports.put(next)
  emit('state', { report: next })
  return next
}

export async function getReport(event_id) {
  return db.reports.get(event_id)
}

export async function allReports() {
  return db.reports.orderBy('timestamp').reverse().toArray()
}

export async function pendingReports() {
  return db.reports.where('state').anyOf(REPORT_STATE.PENDING, REPORT_STATE.FAILED).toArray()
}

export async function counts() {
  const all = await db.reports.toArray()
  return all.reduce(
    (acc, r) => ({ ...acc, [r.state]: (acc[r.state] || 0) + 1, total: acc.total + 1 }),
    { total: 0 }
  )
}

export async function deleteReport(event_id) {
  await db.reports.delete(event_id)
  emit('deleted', { event_id })
}

/* -------------------------------------------------------------- syncing */

let syncing = false
let queuedRun = false

/**
 * Upload every pending/failed report. Safe to call at any time and from any
 * trigger (app start, `online` event, manual retry, poll) — it self-serialises.
 */
export async function syncNow({ force = false } = {}) {
  if (!isOnline() && !force) return { skipped: 'offline' }
  if (syncing) {
    queuedRun = true
    return { skipped: 'busy' }
  }
  syncing = true
  emit('sync:start', {})
  const result = { uploaded: 0, failed: 0 }
  try {
    const batch = await pendingReports()
    for (const row of batch) {
      if (!isOnline()) break
      try {
        emit('sync:uploading', { report: row })
        const ack = await postReport(toContract({ ...row, state: REPORT_STATE.PENDING }))
        await markState(row.event_id, REPORT_STATE.SYNCED, {
          attempts: (row.attempts || 0) + 1,
          last_error: null,
          server_id: ack?.server_id || null,
          synced_at: new Date().toISOString(),
        })
        result.uploaded++
      } catch (err) {
        const attempts = (row.attempts || 0) + 1
        await markState(
          row.event_id,
          attempts >= MAX_ATTEMPTS ? REPORT_STATE.FAILED : REPORT_STATE.PENDING,
          { attempts, last_error: String(err?.message || err) }
        )
        result.failed++
      }
    }
  } finally {
    syncing = false
    emit('sync:done', result)
    if (queuedRun) {
      queuedRun = false
      setTimeout(() => syncNow(), 0)
    }
  }
  return result
}

let debounce = null
function scheduleSync(delay = 400) {
  clearTimeout(debounce)
  debounce = setTimeout(() => syncNow(), delay)
}

/** Retry a report the queue gave up on. */
export async function retryReport(event_id) {
  await markState(event_id, REPORT_STATE.PENDING, { attempts: 0, last_error: null })
  return syncNow()
}

let started = false
/** Wire the automatic triggers exactly once per page load. */
export function startAutoSync() {
  if (started) return
  started = true
  window.addEventListener('online', () => {
    emit('connectivity', { online: true })
    scheduleSync(300)
  })
  window.addEventListener('offline', () => emit('connectivity', { online: false }))
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') scheduleSync(200)
  })
  // Safety net: navigator.onLine lies on captive portals and flaky mobile data.
  setInterval(() => {
    if (isOnline()) syncNow()
  }, 30000)
  scheduleSync(800)
}
