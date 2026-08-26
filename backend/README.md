# NER Road Accessibility API — Person 1 (Backend & Data)

FastAPI + PostGIS backend for the SIH 2026 / PS26002 (MDoNER) road-accessibility
platform, covering all eight North East India states.

Runs on **http://localhost:8000** · docs at **/docs**

---

## Quick start

```bash
cd ner-platform/backend
python -m venv venv && source venv/bin/activate    # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

Open <http://localhost:8000/docs>.

**PostGIS is optional to get started.** If the database is unreachable the API
serves a pre-seeded sample of real NH corridors from memory and says so in
`GET /health` (`database.mode`). Every endpoint returns the same JSON either way,
so the dashboard and driver app can be built against a running API from day one.

### With PostGIS

```bash
docker run --name ner-db -e POSTGRES_PASSWORD=ner -e POSTGRES_DB=ner \
  -p 5432:5432 -d postgis/postgis
```

The tables are created and seeded on startup. `GET /health` then reports
`"mode": "postgis"`.

### Everything at once

```bash
docker compose up --build
```

Starts PostGIS, Redis and the API together. Verified working: the backend comes up
on PostGIS 3.4.3 and seeds all five tables on first boot.

**No Docker Desktop?** Colima is a drop-in runtime that installs without an admin
password:

```bash
brew install colima docker docker-compose
mkdir -p ~/.docker && echo '{"cliPluginsExtraDirs":["/opt/homebrew/lib/docker/cli-plugins"]}' > ~/.docker/config.json
colima start --cpu 2 --memory 4 --disk 20
```

`docker` and `docker compose` then work normally. On Apple Silicon the PostGIS
image is amd64-only and runs emulated — correct, just slower to start.

---

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/segments` | Road network with risk + accessibility scores |
| `GET` | `/segments/{id}` | One segment |
| `GET` | `/route?from=&to=` | Best route between two points |
| `GET` | `/routes`, `/routes/{id}` | Pre-computed corridors |
| `GET` | `/vehicles` | Fleet positions |
| `POST` | `/reports` | File a driver incident report |
| `GET` | `/reports`, `/reports/{event_id}` | Read reports / confirm a queued one landed |
| `GET` | `/alerts` | Advisories (dashboard feed, driver push) |
| `POST` | `/alerts` | Raise an alert from the control centre |
| `GET` | `/states` | The eight NER states with map bounds |
| `GET` | `/summary` | Network totals for the dashboard header |
| `GET` | `/health` | Status, DB mode, record counts |
| `WS` | `/ws/vehicles` | Live simulated GPS stream |

### Driver-app routes (`/api/*`)

The driver PWA was built against its own fixtures before this API existed, so it
speaks a slightly different dialect. Rather than rewrite a working app — or bend
the shared contract to one client — `app/routers/compat.py` translates:

| Method | Path | Notes |
| --- | --- | --- |
| `GET` | `/api/routes/current` | Route for a vehicle, nested shape, `path` as `[lat, lng]` |
| `GET` | `/api/reports` | Same data as `/reports` |
| `POST` | `/api/reports` | Accepts `note`, `accuracy`, and aliased types |
| `POST` | `/api/alerts` | One-tap SOS: no coordinates or title needed |
| `POST` | `/api/alerts/location` | Position ping while an SOS is running |
| `GET` | `/api/alerts/location` | The trail of fixes for an alert |

Translations applied:

| Driver app sends | Stored as |
| --- | --- |
| `type: flood` | `flooding` |
| `type: blocked_road` | `traffic_block` |
| `note` | `description` (with GPS accuracy appended) |
| `status: raised` | `pending` |
| SOS with no `lat`/`lng` | position taken from the vehicle's last fix |
| SOS with no `title` | synthesised from `event` (`sos_accident` → "SOS - accident reported") |
| segment `status` | `clear` / `caution` / `high_risk` / `blocked` for the map |

`heavy_rain` was added to the accepted report types. The canonical routes are
untouched — `tests/test_driver_api.py` asserts the dialect does not leak into
them.

**One change still needed on the app side:** `fetchRoute()` in
`src/api/client.js` calls `/api/routes/current` with no parameters, so the
backend picks a vehicle rather than *the* vehicle. One line fixes it:

```js
return request(`/api/routes/current?vehicle_id=${encodeURIComponent(VEHICLE_ID)}`)
```

Until then an unknown or missing id resolves to a vehicle on a chosen route, and
the response names which one under `vehicle.vehicle_id`.

### Useful query parameters

```
/segments?state=Sikkim&status=closed&min_risk=0.6
/segments?bbox=88.0,27.0,89.0,28.2          # map viewport
/route?from=Siliguri&to=Gangtok&profile=safest
/route?from=26.7271,88.4275&to=27.3314,88.6138
/vehicles?type=ambulance&status=en_route
/alerts?near=27.33,88.61&radius_km=60       # what to push to a driver
/alerts?active=true                         # live feed only (bare /alerts = all)
```

`state` accepts a name, slug or code — `Sikkim`, `sikkim`, `SK` all work.
`from`/`to` accept a known place name or `lat,lng`.

### WebSocket

```js
const ws = new WebSocket("ws://localhost:8000/ws/vehicles");
ws.onmessage = (e) => {
  const { type, tick, vehicles } = JSON.parse(e.data);
  // type: "snapshot" on connect, then "vehicle_positions" every 2s
};
```

Vehicles move along their assigned route geometry, slowing on high-risk segments
and halting at blocked ones. Tune with `WS_BROADCAST_SECONDS` and `WS_TIME_SCALE`.

---

## Loading the real road network

```bash
python load_ner.py --sample           # built-in corridors, instant, no download
python load_ner.py --states sikkim    # one state — start here
python load_ner.py --states all       # full NER, slow, gigabytes
python load_ner.py --states assam --replace --dry-run
```

`--states` takes a name, slug, code, a comma-separated list, or `all`.
Downloads drivable OSM roads with osmnx, scores each edge, and writes to
`road_segments`. Failures on one state are logged and the rest continue.

---

## The API contract

`../mock-data/*.json` is **owned by all four of us** — its README requires
agreement from everyone before a field name or type changes, and Person 2's
`ml/routing.py` reads `mock-data/segments.json` directly. This backend never
writes to that folder.

The API is a **strict superset** of it: every record in `mock-data` comes back
from the matching endpoint with the same id and byte-identical contract fields,
plus extra fields the backend adds (geometry, state, length, ETA detail) that a
contract client can ignore.

```bash
python check_contract.py                          # against the in-memory seed
python check_contract.py --url http://localhost:8000 --allow-live-drift
```

`tests/test_api.py::test_api_is_a_superset_of_mock_data` asserts the same thing
in CI. Contract field names, for reference:

| Resource | Contract fields |
| --- | --- |
| segment | `id`, `name`, `risk` (0–1), `accessibility` (0–100), `status`, `geometry` |
| route | `id`, `origin`, `destination`, `chosen`, `eta_min`, `delay_min`, `risk`, `segments[]` |
| vehicle | `vehicle_id`, `cargo`, `route_id`, `progress`, `status` |
| report | `event_id`, `type`, `lat`, `lng`, `timestamp`, `photo`, `vehicle_id`, `state` |
| alert | `id`, `event`, `severity`, `recipients[]`, `lang`, `status` |

Vocabularies: segment status `open|restricted|closed`; severity
`low|medium|high|critical`; vehicle status `en_route|idle|halted|offline`; alert
status `pending|sent|acknowledged|failed`. Timestamps are ISO-8601 in IST.

---

## Layout

```
backend/
├── app/
│   ├── main.py          FastAPI app, CORS, lifespan
│   ├── config.py        settings from .env
│   ├── database.py      PostGIS engine + memory fallback
│   ├── models.py        road_segments, routes, vehicles, incidents, alerts
│   ├── schemas.py       request/response models (drives /docs)
│   ├── store.py         repository — one shape, either backend
│   ├── seed.py          pre-seeded NER corridors
│   ├── bootstrap.py     seeds PostGIS when tables are empty
│   ├── simulation.py    fleet GPS simulator
│   ├── geo.py           haversine, interpolation, WKT
│   ├── places.py        place-name resolution for ?from=/?to=
│   ├── ner_states.py    the eight states
│   └── routers/         segments, routes, vehicles, reports, alerts, ws,
│                        compat (the /api/* driver-app dialect)
├── load_ner.py          OSM loader
├── check_contract.py    verifies the API still matches ../mock-data
├── tests/               64 tests, no database needed
├── Dockerfile
└── docker-compose.yml
```

## Tests

```bash
pytest
```

64 tests, ~1.5s. `tests/conftest.py` points `DATABASE_URL` at a closed port, so the
suite always runs on the in-memory seed and passes whether or not the compose
stack is up — otherwise a developer with `load_ner.py` data loaded would see
every count assertion fail.

---

## Merging with the rest of the team

- **Person 2 (ML)** — `ml/risk.py`, `ml/score.py`, `ml/routing.py` are already on
  `main`. `store.find_route()` is the seam for their `safest_route()`; the `risk`
  and `accessibility` columns on `road_segments` are what their `score()` and
  `accessibility()` fill in. Field names already line up — both sides read the
  `mock-data` contract.
- **Persons 3 & 4** — flip `VITE_API_URL` from `/mock-data` to
  `http://localhost:8000`. Both origins are already in `CORS_ORIGINS`.

## Configuration

| Variable | Default | Meaning |
| --- | --- | --- |
| `DATABASE_URL` | `postgresql+psycopg://postgres:ner@localhost:5432/ner` | PostGIS DSN |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis |
| `CORS_ORIGINS` | `http://localhost:3000,http://localhost:3001` | Allowed browser origins |
| `AUTO_SEED` | `true` | Seed PostGIS when tables are empty |
| `ALLOW_MEMORY_FALLBACK` | `true` | Serve the sample when PostGIS is down |
| `DB_CONNECT_RETRIES` | `10` | Startup connect attempts before falling back |
| `DB_CONNECT_DELAY` | `1.5` | Seconds between those attempts |
| `WS_BROADCAST_SECONDS` | `2.0` | Seconds between stream frames |
| `WS_TIME_SCALE` | `60` | Simulated seconds per real second |
