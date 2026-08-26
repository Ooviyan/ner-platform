# NER Driver PWA

Driver-facing Progressive Web App for the MDoNER road-accessibility & logistics
platform for India's North Eastern Region (SIH 2026, PS 26002).

Runs on **port 3001**. Works fully standalone against `../mock-data` — no
backend, dashboard or ML service required.

```bash
npm install
npm run dev -- --port 3001
```

Then open <http://localhost:3001>.

---

## What it does

| Feature | Where | Notes |
|---|---|---|
| Assigned route, live map, ETA, vehicle & cargo | `src/screens/Home.jsx` | Route cached locally; renders with no signal |
| One-tap SOS + continuous location sharing | `src/screens/Sos.jsx`, `src/sos/sos.js` | Hold-to-arm; survives reload; queues when offline |
| Road-blockage report with photo + auto GPS | `src/screens/Report.jsx` | Photo downscaled to ≤1280px JPEG before storage |
| Offline queue (IndexedDB, auto-upload) | `src/db/queue.js` | `pending → synced`, dedupe by `event_id` |
| Simulated mesh relay (A→B→C) | `src/mesh/` | See the honesty note below |
| 5 languages | `src/i18n/` | English, Assamese, Bengali, Nepali, Mizo |
| Installable PWA, offline shell | `vite.config.js` | `vite-plugin-pwa`, Workbox precache |

## Configuration

Copy `.env.example` to `.env`. Everything has a working default.

| Variable | Default | Meaning |
|---|---|---|
| `VITE_API_URL` | `/mock-data` | Backend base URL. `/mock-data` = standalone mode against the static fixtures. |
| `VITE_WS_URL` | *(empty)* | Backend WebSocket for mesh coordination. Empty ⇒ tab-local `BroadcastChannel`. |
| `VITE_VEHICLE_ID` | `AS-01-EG-4417` | Vehicle this device is assigned to. |

URL overrides, useful for demos: `?node=B` pins the mesh node label,
`?vehicle=AS-01-XX-0000` overrides the vehicle.

---

## Simulated mesh relay — please read this before demoing

**This is a simulation, and the UI says so on screen.**

Real phone-to-phone relaying needs native Bluetooth LE mesh. Browsers cannot do
it: the Web Bluetooth API cannot advertise, cannot run in the background, and
cannot form a mesh. Claiming otherwise would be dishonest.

What this feature actually does:

- Every open instance of the app is a **mesh node** with its own id, label and
  signal state (identity lives in `sessionStorage`, so each tab is a separate node).
- A manual **dead-zone switch** simulates having no signal.
- A report filed by a node in a dead zone is offered to the mesh. Peers bid to
  carry it: a peer **with** signal bids fast and becomes the **gateway**; a peer
  **without** signal bids slower, accepts the report, and re-offers it one hop
  further. The gateway uploads it and broadcasts delivery.
- Nodes only hear their immediate letter-neighbours (`A↔B↔C`) — a simulated
  radio range. Without it an online node would always win the first bid and a
  report could never visibly travel more than one hop.
- Hop events are broadcast so **every driver app and the dashboard animate the
  same relay**, via `VITE_WS_URL` when the backend is up, and via
  `BroadcastChannel` between tabs when it is not.

Real BLE mesh is our documented **Phase 2** item.

### Demoing it

1. Open <http://localhost:3001/?node=A#/mesh>
2. Open <http://localhost:3001/?node=B#/mesh> in a second tab, and put **B** in a
   dead zone too.
3. Open <http://localhost:3001/?node=C#/mesh> in a third tab and leave **C** online.
4. On **A**, press **Run relay demo**.

A files the report with no signal → B carries it → C uploads it. All three tabs
animate `A → B → C → control room`, and the report ends up `synced`.

Skip step 2 for the short version: `A → B → control room`.

---

## Data contract

The app reads and writes exactly the shapes agreed with the backend. Sample
fixtures live in `../mock-data/`.

```jsonc
// report.json — `state` is the sync state: pending | relaying | synced | failed
{ "event_id": "", "type": "", "lat": 0, "lng": 0, "timestamp": "",
  "photo": null, "vehicle_id": "", "state": "pending" }

// route.json
{ "id": "", "origin": {}, "destination": {}, "chosen": true, "eta_min": 0,
  "delay_min": 0, "risk": 0.0, "segments": [] }

// alert.json
{ "id": "", "event": "", "severity": "", "recipients": [], "lang": "", "status": "" }
```

Local-only bookkeeping (`attempts`, `last_error`, `relay_path`, `note`, …) is
kept on the IndexedDB row and **stripped before upload** by `toContract()` in
`src/db/db.js`, so the backend only ever sees the agreed fields.

### Endpoints expected from the backend

Once `VITE_API_URL` points at FastAPI instead of `/mock-data`:

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/routes/current` | route.json for the assigned vehicle |
| `GET` | `/api/reports` | list of report.json |
| `POST` | `/api/reports` | one report.json — should be **idempotent on `event_id`** (the mesh can deliver the same event from more than one carrier) |
| `POST` | `/api/alerts` | one alert.json |
| `POST` | `/api/alerts/location` | `{ alert_id, vehicle_id, node, lat, lng, accuracy, at }` |
| `WS` | `VITE_WS_URL` | re-broadcast mesh frames verbatim to all clients + dashboard |

**The WebSocket only has to fan out.** Mesh frames are JSON with a `mid`
(de-dupe id) and a `type` of `hello`, `bye`, `relay_offer`, `relay_hop` or
`relay_delivered`. The backend does not need to understand them — echo every
frame to every other connected client. The dashboard can listen for
`relay_hop` / `relay_delivered` to animate the same A→B→C sequence.

---

## Offline behaviour

- Reports are written to IndexedDB **before** any upload is attempted, so a
  submit never depends on the network.
- `event_id` is the primary key, so re-filing or re-receiving the same event
  updates the row instead of duplicating it.
- Uploads retry on `online`, on tab focus, on a 30s timer, and on manual
  "Sync now". After 5 failed attempts a report is marked `failed` and can be
  retried by hand.
- A report handed to the mesh that finds no peer reverts to `pending`, so it
  still uploads normally once signal returns.
- The route, map tiles you have already seen, and the app shell are cached by
  the service worker.

## Build & deploy

```bash
npm run build      # -> dist/
npm run preview    # serve dist/ on 3001
```

Docker — **build from the repo root**, since `../mock-data` is baked in:

```bash
docker build -f driver-app/Dockerfile -t ner-driver-app .
```

```bash
docker run --rm -p 3001:3001 ner-driver-app
```

Point it at a live backend at build time:

```bash
docker build -f driver-app/Dockerfile --build-arg VITE_API_URL=http://backend:8000 --build-arg VITE_WS_URL=ws://backend:8000/ws/mesh -t ner-driver-app .
```

## Notes for the team

- This folder is self-contained; nothing outside `driver-app/` is modified
  except the shared fixtures in `../mock-data/`.
- Geolocation needs a secure context. `localhost` counts; testing on a phone
  over LAN IP does not — use HTTPS or a tunnel. The app degrades gracefully to
  a known corridor coordinate when permission is denied, so the demo never blocks.
- `POST /api/reports` must be idempotent on `event_id` — the mesh may deliver
  the same report from more than one carrier.
