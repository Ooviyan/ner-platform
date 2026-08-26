import { useSyncExternalStore } from 'react'
import { subscribeLink, snapshot } from '../net/link.js'

let cached = snapshot()
let cachedKey = JSON.stringify(cached)

function getSnapshot() {
  const next = snapshot()
  const key = JSON.stringify(next)
  // useSyncExternalStore requires a referentially stable snapshot between changes.
  if (key !== cachedKey) {
    cached = next
    cachedKey = key
  }
  return cached
}

/** { browserOnline, deadZone, linkUp } — re-renders on any connectivity change. */
export function useLink() {
  return useSyncExternalStore(subscribeLink, getSnapshot, getSnapshot)
}
