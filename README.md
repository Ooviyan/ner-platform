# ner-platform

A web-only logistics and road-accessibility platform for India's North Eastern
Region — Arunachal Pradesh, Assam, Manipur, Meghalaya, Mizoram, Nagaland,
Sikkim, and Tripura.

This repository is currently a **skeleton**. No features are built yet. It
exists so four people can start working in parallel without colliding.

---

## The four-folder rule

Each person owns exactly one folder and edits only that folder.

| Folder        | Owner    | Becomes                    |
| ------------- | -------- | -------------------------- |
| `backend/`    | Person 1 | FastAPI + PostGIS API      |
| `ml/`         | Person 2 | XGBoost risk + routing     |
| `dashboard/`  | Person 3 | React + MapLibre ops UI    |
| `driver-app/` | Person 4 | React PWA for drivers      |

Shared files — the root `README.md`, `docker-compose.yml`, and `mock-data/` —
belong to everyone. Changing them affects all four people, so announce the
change first and keep it small. Everything else: stay in your own folder.

If you need something from another folder, ask its owner for it. Do not reach
in and edit their code.

---

## Fixed ports

These are fixed. Do not change them — the other three are wired to them.

| Service      | Port | URL                     |
| ------------ | ---- | ----------------------- |
| `backend`    | 8000 | http://localhost:8000   |
| `dashboard`  | 3000 | http://localhost:3000   |
| `driver-app` | 3001 | http://localhost:3001   |
| `db` (PostGIS) | 5432 | localhost:5432        |
| `redis`      | 6379 | localhost:6379          |

Bring up the shared infrastructure:

```bash
docker compose up -d db redis
```

`db` and `redis` run today. The `backend`, `dashboard`, and `driver-app`
services need a `Dockerfile` in their own folder first — each owner adds
theirs, and then their service starts with the rest.

---

## Mock data, and the switch to the real API

`mock-data/` holds shared fake JSON with realistic NER coordinates. It is the
**API contract**: the field names and types in those files are exactly what the
backend will return.

Both frontends read a single environment variable:

```
VITE_API_URL=/mock-data
```

Build everything against that. The frontends load `${VITE_API_URL}/segments`,
`${VITE_API_URL}/routes`, and so on, which resolves to the static JSON files
while the API does not exist yet.

At integration time, one line changes in each frontend's `.env`:

```
VITE_API_URL=http://localhost:8000
```

Nothing else should need to change. That only holds if you never hardcode a
URL — always read `VITE_API_URL`.

### Contract files

- `mock-data/segments.json` — `id`, `name`, `risk` (0–1), `accessibility`
  (0–100), `status`, `geometry` (GeoJSON LineString)
- `mock-data/routes.json` — `id`, `origin`, `destination`, `chosen`,
  `eta_min`, `delay_min`, `risk`, `segments[]`
- `mock-data/reports.json` — `event_id`, `type`, `lat`, `lng`, `timestamp`,
  `photo`, `vehicle_id`, `state`
- `mock-data/alerts.json` — `id`, `event`, `severity`, `recipients[]`, `lang`,
  `status`

To change a field: update `mock-data/` first, tell the other three, then change
code.

---

## Getting started

1. Clone the repo and `cd ner-platform`.
2. `docker compose up -d db redis`
3. Go into your own folder, copy `.env.example` to `.env`, and read that
   folder's `README.md`.
4. Build. Stay in your folder.
