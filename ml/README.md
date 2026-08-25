# ml — Person 2

**Owner:** Person 2. Nobody else edits this folder.

## Purpose
Models and routing logic: XGBoost risk scoring for road segments, plus the
route engine that scores and ranks candidate paths.

Produces:
- `risk` (0–1) and `accessibility` (0–100) per segment
- ranked routes with `eta_min`, `delay_min`, `risk`

## Runs on
No port of its own. Consumed by `backend` (Person 1) — as an importable module
or a batch job that writes scores to the database. Agree the handoff with
Person 1 before wiring it.

## Contract
Outputs must match the fields in `../mock-data/segments.json` and
`../mock-data/routes.json`.
