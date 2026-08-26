import { useCallback, useEffect, useRef, useState } from 'react'

const GEO_OPTS = { enableHighAccuracy: true, timeout: 15000, maximumAge: 10000 }

/** Fallback position so the demo still works on a desktop that denies geolocation. */
export const FALLBACK_FIX = {
  lat: 27.013,
  lng: 92.64,
  accuracy: null,
  simulated: true,
}

function toFix(pos) {
  return {
    lat: +pos.coords.latitude.toFixed(6),
    lng: +pos.coords.longitude.toFixed(6),
    accuracy: pos.coords.accuracy != null ? Math.round(pos.coords.accuracy) : null,
    heading: pos.coords.heading ?? null,
    speed: pos.coords.speed ?? null,
    at: new Date(pos.timestamp).toISOString(),
    simulated: false,
  }
}

function describe(err) {
  if (!err) return null
  if (err.code === 1) return 'denied'
  if (err.code === 2) return 'unavailable'
  if (err.code === 3) return 'timeout'
  return 'error'
}

/**
 * One-shot position read.
 * Resolves with a fix, or with FALLBACK_FIX when the device refuses — a driver
 * filing a landslide report must never be blocked by a permission prompt.
 */
export function getCurrentFix() {
  return new Promise(resolve => {
    if (!('geolocation' in navigator)) {
      resolve({ ...FALLBACK_FIX, at: new Date().toISOString(), error: 'unsupported' })
      return
    }
    navigator.geolocation.getCurrentPosition(
      pos => resolve(toFix(pos)),
      err =>
        resolve({ ...FALLBACK_FIX, at: new Date().toISOString(), error: describe(err) }),
      GEO_OPTS
    )
  })
}

/**
 * Live position. `watch: true` starts a continuous watchPosition — used by SOS
 * to share the driver's location until the alert is stood down.
 */
export function useGeolocation({ watch = false, immediate = true } = {}) {
  const [fix, setFix] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const watchId = useRef(null)

  const refresh = useCallback(async () => {
    setBusy(true)
    const f = await getCurrentFix()
    setFix(f)
    setError(f.error || null)
    setBusy(false)
    return f
  }, [])

  useEffect(() => {
    if (immediate && !watch) refresh()
  }, [immediate, watch, refresh])

  useEffect(() => {
    if (!watch || !('geolocation' in navigator)) return undefined
    setBusy(true)
    watchId.current = navigator.geolocation.watchPosition(
      pos => {
        setFix(toFix(pos))
        setError(null)
        setBusy(false)
      },
      err => {
        setError(describe(err))
        setBusy(false)
        // Keep a usable coordinate on screen even if the OS denies the watch.
        setFix(prev => prev || { ...FALLBACK_FIX, at: new Date().toISOString() })
      },
      GEO_OPTS
    )
    return () => {
      if (watchId.current != null) navigator.geolocation.clearWatch(watchId.current)
      watchId.current = null
    }
  }, [watch])

  return { fix, error, busy, refresh }
}
