# driver-app — Person 4

**Owner:** Person 4. Nobody else edits this folder.

## Purpose
The driver-facing React PWA (web only, installable, offline-tolerant). Shows
the assigned route and hazards ahead, and lets drivers submit incident reports
with a photo and location.

## Runs on
`http://localhost:3001` (fixed).

## Setup
Copy `.env.example` to `.env`. Build against the mock data — `VITE_API_URL`
stays `/mock-data` until Person 1's API is ready, then it becomes
`http://localhost:8000`. Never hardcode a URL; always read `VITE_API_URL`.

## Contract
`../mock-data/reports.json` defines the report payload;
`../mock-data/routes.json` and `segments.json` define what the driver sees.
