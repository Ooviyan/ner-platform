/**
 * Self-healing for a stale service-worker cache.
 *
 * Failure mode this exists for: the service worker holds an index.html that
 * references hashed assets (/assets/index-<hash>.js) which no longer exist —
 * because the app was rebuilt, or because it was installed against one build
 * and is now being served another. The browser then fails to load the entry
 * chunk and renders a blank white page with no error anyone can see.
 *
 * When we detect that, we tear down the service worker and every cache, then
 * reload exactly once. A one-shot flag in sessionStorage stops a reload loop if
 * the failure is actually something else.
 */

const FLAG = 'ner.recovery.attempted'

export async function hardReset({ reload = true } = {}) {
  try {
    if ('serviceWorker' in navigator) {
      const regs = await navigator.serviceWorker.getRegistrations()
      await Promise.all(regs.map(r => r.unregister()))
    }
    if ('caches' in window) {
      const keys = await caches.keys()
      await Promise.all(keys.map(k => caches.delete(k)))
    }
  } catch (err) {
    console.error('[recovery] teardown failed', err)
  }
  // Reports and the active SOS live in IndexedDB/localStorage and are NOT
  // touched here — recovery must never destroy a driver's unsent reports.
  if (reload) window.location.reload()
}

function alreadyTried() {
  return sessionStorage.getItem(FLAG) === '1'
}

function markTried() {
  try {
    sessionStorage.setItem(FLAG, '1')
  } catch {
    /* private mode */
  }
}

/** Clear the one-shot flags once the app has successfully mounted. */
export function markBootHealthy() {
  try {
    sessionStorage.removeItem(FLAG)
  } catch {
    /* ignore */
  }
  // Also clear the inline boot guard in index.html, which is what actually
  // rescues a failed bundle load.
  window.__nerBootOk?.()
}

function recover(reason) {
  if (alreadyTried()) {
    console.error('[recovery] already attempted this session; not looping.', reason)
    return
  }
  markTried()
  console.warn('[recovery] stale cache suspected, resetting service worker:', reason)
  hardReset()
}

export function installRecoveryHandlers() {
  // A module/chunk that 404s or fails to parse.
  window.addEventListener(
    'error',
    e => {
      const el = e.target
      if (el && (el.tagName === 'SCRIPT' || el.tagName === 'LINK')) {
        const url = el.src || el.href || ''
        if (url.includes('/assets/')) recover(`asset failed to load: ${url}`)
      }
    },
    true // capture: resource errors do not bubble
  )

  // Vite's dynamic-import preload failure (our lazily loaded map chunk).
  window.addEventListener('vite:preloadError', e => {
    recover('vite:preloadError ' + (e?.payload?.message || ''))
  })

  window.addEventListener('unhandledrejection', e => {
    const msg = String(e?.reason?.message || e?.reason || '')
    if (/Failed to fetch dynamically imported module|Importing a module script failed/i.test(msg)) {
      recover(msg)
    }
  })
}
