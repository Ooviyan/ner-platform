import { useCallback, useEffect, useState } from 'react'
import { fetchRoute } from '../api/client.js'

const CACHE_KEY = 'ner.route.cache'

function readCache() {
  try {
    const raw = localStorage.getItem(CACHE_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

/**
 * The assigned route, served from cache first so the Home screen paints
 * instantly and still shows something useful with no signal.
 */
export function useRoute() {
  const cached = readCache()
  const [route, setRoute] = useState(cached?.route || null)
  const [stale, setStale] = useState(Boolean(cached))
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(!cached)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await fetchRoute()
      setRoute(data)
      setStale(false)
      setError(null)
      localStorage.setItem(CACHE_KEY, JSON.stringify({ route: data, at: Date.now() }))
    } catch (err) {
      setError(String(err?.message || err))
      // Keep whatever we already had on screen rather than blanking it.
      const c = readCache()
      if (c?.route) {
        setRoute(c.route)
        setStale(true)
      }
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
    const onOnline = () => load()
    window.addEventListener('online', onOnline)
    return () => window.removeEventListener('online', onOnline)
  }, [load])

  return { route, loading, error, stale, reload: load }
}
