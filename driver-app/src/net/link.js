import { getDeadZone, setDeadZone } from '../config.js'

/**
 * The app has two independent reasons to consider itself unreachable:
 *   1. the browser really is offline (navigator.onLine / SW fetch failures)
 *   2. the demo's manual "dead zone" switch is on, simulating no signal
 *
 * Everything that touches the network asks this module rather than
 * navigator.onLine directly, so flipping the dead-zone switch behaves exactly
 * like driving into a valley with no coverage.
 */

let deadZone = getDeadZone()
const listeners = new Set()

function notify() {
  const s = snapshot()
  for (const fn of listeners) {
    try {
      fn(s)
    } catch {
      /* ignore listener errors */
    }
  }
}

export function snapshot() {
  return {
    browserOnline: navigator.onLine !== false,
    deadZone,
    linkUp: navigator.onLine !== false && !deadZone,
  }
}

/** True when this device can actually reach the platform. */
export function isLinkUp() {
  return snapshot().linkUp
}

export function isDeadZone() {
  return deadZone
}

export function toggleDeadZone(on) {
  deadZone = on === undefined ? !deadZone : !!on
  setDeadZone(deadZone)
  notify()
  return deadZone
}

export function subscribeLink(fn) {
  listeners.add(fn)
  return () => listeners.delete(fn)
}

window.addEventListener('online', notify)
window.addEventListener('offline', notify)
