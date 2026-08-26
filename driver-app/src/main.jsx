import React from 'react'
import { createRoot } from 'react-dom/client'
import { HashRouter } from 'react-router-dom'
import 'leaflet/dist/leaflet.css'
import './styles.css'
import './i18n/index.js'
import App from './App.jsx'
import ErrorBoundary from './components/ErrorBoundary.jsx'
import { startAutoSync } from './db/queue.js'
import { startMesh } from './mesh/mesh.js'
import { installRecoveryHandlers, markBootHealthy } from './recovery.js'

// Catch a stale service-worker cache before it can present a blank page.
installRecoveryHandlers()

// HashRouter keeps deep links working when the PWA is opened from the home
// screen or served from a sub-path, with no server rewrite rules required.
createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ErrorBoundary>
      <HashRouter>
        <App />
      </HashRouter>
    </ErrorBoundary>
  </React.StrictMode>
)

// We got far enough to render, so this boot was not a stale-cache failure.
markBootHealthy()

startAutoSync()
// Every open instance is a mesh node, whichever screen it is showing, so a tab
// sitting on Home can still act as the gateway for a peer in a dead zone.
startMesh()
