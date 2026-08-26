import { API_URL, MOCK_MODE, uuid } from '../config.js'
import { isLinkUp } from '../net/link.js'

class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/**
 * Network reachability as far as this app is concerned: the real browser state
 * AND the demo's simulated dead-zone switch. See net/link.js.
 */
export function isOnline() {
  return isLinkUp()
}

async function request(path, options = {}, timeoutMs = 12000) {
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), timeoutMs)
  try {
    const res = await fetch(`${API_URL}${path}`, {
      ...options,
      signal: ctrl.signal,
      headers: { Accept: 'application/json', ...(options.headers || {}) },
    })
    if (!res.ok) throw new ApiError(`${res.status} ${res.statusText}`, res.status)
    const text = await res.text()
    return text ? JSON.parse(text) : null
  } finally {
    clearTimeout(timer)
  }
}

/**
 * Stand-in for a write the static fixtures cannot actually accept.
 * It deliberately fails while the browser is offline so the offline queue,
 * the retry path and the mesh relay all behave exactly as they will against
 * the real FastAPI backend.
 */
function simulateWrite(payload, { latency = 700 } = {}) {
  return new Promise((resolve, reject) => {
    setTimeout(() => {
      if (!isOnline()) {
        reject(new ApiError('offline: simulated upload refused', 0))
        return
      }
      resolve({
        ...payload,
        server_id: `srv-${uuid().slice(0, 8)}`,
        received_at: new Date().toISOString(),
        simulated: true,
      })
    }, latency)
  })
}

/* ------------------------------------------------------------------ reads */

/** Current route assignment for this vehicle (route.json contract). */
export async function fetchRoute() {
  return MOCK_MODE ? request('/route.json') : request('/api/routes/current')
}

/** Reports already known to the platform (report.json contract, as a list). */
export async function fetchReports() {
  if (MOCK_MODE) {
    try {
      return await request('/reports.json')
    } catch {
      return []
    }
  }
  return request('/api/reports')
}

/* ----------------------------------------------------------------- writes */

/** POST one road report. Resolves with the server's acknowledgement. */
export async function postReport(report) {
  if (MOCK_MODE) return simulateWrite(report)
  return request('/api/reports', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(report),
  })
}

/** POST an emergency alert (alert.json contract). */
export async function postAlert(alert) {
  if (MOCK_MODE) return simulateWrite(alert, { latency: 500 })
  return request('/api/alerts', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(alert),
  })
}

/** Continuous location sharing while an SOS is active. Best-effort, never throws. */
export async function postLocationPing(ping) {
  try {
    if (MOCK_MODE) return await simulateWrite(ping, { latency: 120 })
    return await request('/api/alerts/location', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(ping),
    })
  } catch {
    return null
  }
}

export { ApiError }
