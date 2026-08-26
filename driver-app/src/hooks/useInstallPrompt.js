import { useEffect, useState } from 'react'

/**
 * Wraps the `beforeinstallprompt` event so Settings can offer a real install
 * button on Chromium, and fall back to instructions elsewhere (iOS Safari
 * never fires this event).
 */
let deferred = null

// Capture the event even if it fires before Settings has ever mounted.
if (typeof window !== 'undefined') {
  window.addEventListener('beforeinstallprompt', e => {
    e.preventDefault()
    deferred = e
    window.dispatchEvent(new Event('ner:installable'))
  })
}

function standalone() {
  return (
    window.matchMedia?.('(display-mode: standalone)').matches ||
    window.navigator.standalone === true
  )
}

export function useInstallPrompt() {
  const [canInstall, setCanInstall] = useState(Boolean(deferred))
  const [installed, setInstalled] = useState(standalone())

  useEffect(() => {
    const onAvailable = () => setCanInstall(true)
    const onInstalled = () => {
      setInstalled(true)
      setCanInstall(false)
      deferred = null
    }
    window.addEventListener('ner:installable', onAvailable)
    window.addEventListener('appinstalled', onInstalled)
    return () => {
      window.removeEventListener('ner:installable', onAvailable)
      window.removeEventListener('appinstalled', onInstalled)
    }
  }, [])

  const install = async () => {
    if (!deferred) return null
    deferred.prompt()
    const { outcome } = await deferred.userChoice
    if (outcome === 'accepted') {
      setInstalled(true)
      setCanInstall(false)
    }
    deferred = null
    return outcome
  }

  return { canInstall, installed, install }
}
