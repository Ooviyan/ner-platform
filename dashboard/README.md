# dashboard — Person 3

**Owner:** Person 3. Nobody else edits this folder.

## Purpose
The operations web dashboard: React + MapLibre. Map of the eight NER states
with road segments coloured by risk, route comparison, incident feed, and
alert status.

## Runs on
`http://localhost:3000` (fixed).

## Setup
Copy `.env.example` to `.env`. Build against the mock data — `VITE_API_URL`
stays `/mock-data` until Person 1's API is ready, then it becomes
`http://localhost:8000`. Never hardcode a URL; always read `VITE_API_URL`.

## Contract
`../mock-data/` is the source of truth for response shapes. Do not invent
fields — ask for them to be added to `mock-data/` first.
