# backend — Person 1

**Owner:** Person 1. Nobody else edits this folder.

## Purpose
The API for the NER logistics platform: FastAPI + PostGIS. Owns the database
schema, all spatial queries over road segments, and every HTTP endpoint the
dashboard and driver-app call.

Eventually serves (shapes are fixed by `../mock-data/`):
- `GET /segments` — road segments with risk, accessibility, status, geometry
- `GET /routes` — candidate routes with ETA, delay, risk
- `POST /reports` — driver-submitted incident reports
- `GET /alerts` — dispatched alerts and their delivery status

## Runs on
`http://localhost:8000` (fixed).

## Setup
Copy `.env.example` to `.env`. Add a `Dockerfile` here and the `backend`
service in the root `docker-compose.yml` comes up.

## Contract
The JSON in `../mock-data/` is the agreed contract. If a field has to change,
change it in `mock-data/` first and tell the other three — the two frontends
are built against those files.
