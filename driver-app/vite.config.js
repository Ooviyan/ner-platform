import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
// The mock fixtures are shared with the rest of the team and live outside this
// folder (repo-root/mock-data), so they are not inside `public/`. This plugin
// serves them at /mock-data in dev and copies them into dist/ on build, which
// makes VITE_API_URL=/mock-data work with no backend running.
const MOCK_DIR = path.resolve(here, '..', 'mock-data')

function serveMockData() {
  return {
    name: 'ner-serve-mock-data',
    configureServer(server) {
      server.middlewares.use('/mock-data', (req, res, next) => {
        const rel = decodeURIComponent((req.url || '/').split('?')[0]).replace(/^\/+/, '')
        const file = path.resolve(MOCK_DIR, rel)
        if (!file.startsWith(MOCK_DIR) || !fs.existsSync(file) || !fs.statSync(file).isFile()) return next()
        res.setHeader('Content-Type', 'application/json; charset=utf-8')
        res.setHeader('Cache-Control', 'no-store')
        res.end(fs.readFileSync(file))
      })
    },
    closeBundle() {
      if (!fs.existsSync(MOCK_DIR)) return
      const out = path.resolve(here, 'dist', 'mock-data')
      fs.mkdirSync(out, { recursive: true })
      for (const f of fs.readdirSync(MOCK_DIR)) {
        fs.copyFileSync(path.join(MOCK_DIR, f), path.join(out, f))
      }
    },
  }
}

const pkg = JSON.parse(fs.readFileSync(path.resolve(here, 'package.json'), 'utf8'))

/**
 * The dev server and a production build share one origin (localhost:3001), but
 * they serve completely different files: dev serves /src/main.jsx, a build
 * serves /assets/index-<hash>.js. A service worker left behind by a previous
 * `npm run preview` (or by an installed copy of the app) keeps answering
 * navigations from its cache, handing the browser production HTML that the dev
 * server cannot satisfy — the result is a blank white page every time you
 * restart into dev.
 *
 * This injects a dev-only script that evicts any such service worker before it
 * can do that, so the dev server always owns its own origin.
 */
function evictStaleServiceWorkerInDev() {
  // A self-destroying service worker. The browser revalidates /sw.js on every
  // navigation, so an old production worker that is currently hijacking this
  // origin will pick this up, wipe every cache, unregister itself and reload
  // its clients. This is the only path that works when the stale worker is
  // already serving cached HTML, because in that case nothing we inject into
  // the dev server's own index.html ever reaches the browser.
  const SELF_DESTROY_SW = `self.addEventListener('install', function () { self.skipWaiting() })
self.addEventListener('activate', function (event) {
  event.waitUntil((async function () {
    try {
      const keys = await caches.keys()
      await Promise.all(keys.map(function (k) { return caches.delete(k) }))
    } catch (e) {}
    await self.registration.unregister()
    const clients = await self.clients.matchAll({ type: 'window' })
    clients.forEach(function (c) { c.navigate(c.url) })
  })())
})`

  return {
    name: 'ner-evict-stale-sw-in-dev',
    apply: 'serve',
    configureServer(server) {
      for (const p of ['/sw.js', '/dev-sw.js', '/registerSW.js']) {
        server.middlewares.use(p, (req, res) => {
          res.setHeader('Content-Type', 'text/javascript; charset=utf-8')
          res.setHeader('Cache-Control', 'no-store')
          res.end(p === '/registerSW.js' ? '' : SELF_DESTROY_SW)
        })
      }
    },
    transformIndexHtml() {
      return [
        {
          tag: 'script',
          injectTo: 'head-prepend',
          children: `(function () {
  if (!('serviceWorker' in navigator)) return
  navigator.serviceWorker.getRegistrations().then(function (regs) {
    if (!regs.length) return
    console.warn('[dev] evicting ' + regs.length + ' stale service worker(s) left by a production build')
    Promise.all(regs.map(function (r) { return r.unregister() }))
      .then(function () {
        if (!window.caches) return null
        return caches.keys().then(function (ks) {
          return Promise.all(ks.map(function (k) { return caches.delete(k) }))
        })
      })
      .then(function () { location.reload() })
      .catch(function (e) { console.error('[dev] eviction failed', e) })
  })
})()`,
        },
      ]
    },
  }
}

export default defineConfig({
  define: { __APP_VERSION__: JSON.stringify(pkg.version) },
  build: {
    // Drivers load this over patchy 2G/3G, so keep the first paint small and
    // push the map engine into its own chunk that only the Route screen pulls.
    rollupOptions: {
      output: {
        manualChunks: {
          react: ['react', 'react-dom', 'react-router-dom'],
          map: ['leaflet', 'react-leaflet'],
          i18n: ['i18next', 'react-i18next', 'i18next-browser-languagedetector'],
          db: ['dexie', 'dexie-react-hooks'],
        },
      },
    },
    chunkSizeWarningLimit: 700,
  },
  server: { port: 3001, strictPort: true },
  preview: { port: 3001, strictPort: true },
  plugins: [
    react(),
    serveMockData(),
    evictStaleServiceWorkerInDev(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['icons/favicon.svg', 'icons/apple-touch-icon.png'],
      manifest: {
        name: 'NER Driver — Route & Road Reports',
        short_name: 'NER Driver',
        description:
          'Driver companion for essential-goods vehicles in the North Eastern Region: live safest route, one-tap SOS and offline road-blockage reporting.',
        theme_color: '#0b3d3b',
        background_color: '#07211f',
        display: 'standalone',
        orientation: 'portrait',
        start_url: '/',
        scope: '/',
        lang: 'en',
        categories: ['navigation', 'travel', 'utilities'],
        icons: [
          { src: 'icons/pwa-192.png', sizes: '192x192', type: 'image/png' },
          { src: 'icons/pwa-512.png', sizes: '512x512', type: 'image/png' },
          { src: 'icons/pwa-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },
      workbox: {
        globPatterns: ['**/*.{js,css,html,svg,png,woff2}'],
        navigateFallback: 'index.html',
        cleanupOutdatedCaches: true,
        runtimeCaching: [
          {
            // Mock/contract JSON — keep the last good copy readable offline.
            urlPattern: ({ url }) => url.pathname.startsWith('/mock-data'),
            handler: 'NetworkFirst',
            options: {
              cacheName: 'ner-contract-json',
              expiration: { maxEntries: 20, maxAgeSeconds: 60 * 60 * 24 * 7 },
            },
          },
          {
            // Map tiles: best-effort cache so a previously seen area still draws.
            urlPattern: ({ url }) => /tile\.openstreetmap\.org$/.test(url.hostname),
            handler: 'CacheFirst',
            options: {
              cacheName: 'ner-map-tiles',
              expiration: { maxEntries: 400, maxAgeSeconds: 60 * 60 * 24 * 30 },
              cacheableResponse: { statuses: [0, 200] },
            },
          },
        ],
      },
      // Deliberately OFF. A service worker registered by the dev server fights
      // with the one from a production build on the same origin (localhost:3001):
      // the cached index.html ends up pointing at hashed assets the other server
      // does not serve, and the app boots to a blank white screen. Test PWA
      // behaviour against `npm run preview`, never against `npm run dev`.
      devOptions: { enabled: false },
    }),
  ],
})
