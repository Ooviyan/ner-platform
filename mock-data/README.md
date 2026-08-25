# mock-data — shared, owned by everyone

Fake but realistically-shaped JSON that both frontends build against before the
API exists. These files ARE the API contract.

- `segments.json` — road segments: `id`, `name`, `risk` (0–1),
  `accessibility` (0–100), `status`, `geometry` (GeoJSON LineString)
- `routes.json` — `id`, `origin`, `destination`, `chosen`, `eta_min`,
  `delay_min`, `risk`, `segments[]`
- `reports.json` — `event_id`, `type`, `lat`, `lng`, `timestamp`, `photo`,
  `vehicle_id`, `state`
- `alerts.json` — `id`, `event`, `severity`, `recipients[]`, `lang`, `status`

## Rule
This is the one folder that is not owned by a single person, so changes here
break other people. Changing a field name or type needs agreement from all
four — announce it, then update this folder first and the code after.
