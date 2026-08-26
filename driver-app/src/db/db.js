import Dexie from 'dexie'

/**
 * Offline store for the driver app.
 *
 * `reports` mirrors the agreed report.json contract:
 *   { event_id, type, lat, lng, timestamp, photo, vehicle_id, state }
 * where `state` is the sync state: pending | relaying | synced | failed.
 * `event_id` is the primary key, so re-inserting the same report (e.g. the same
 * event arriving again over the simulated mesh) is a no-op rather than a duplicate.
 *
 * Local-only bookkeeping (attempts, last_error, relay_path, ...) is kept on the
 * same row but stripped before upload by toContract().
 */
export const db = new Dexie('ner-driver')

db.version(1).stores({
  reports: '&event_id, state, timestamp, type',
  alerts: '&id, event, status, created_at',
  outbox: '++seq, kind, created_at',
})

export const REPORT_STATE = {
  PENDING: 'pending',
  RELAYING: 'relaying',
  SYNCED: 'synced',
  FAILED: 'failed',
}

export const INCIDENT_TYPES = [
  { id: 'landslide', icon: '⛰️' },
  { id: 'flood', icon: '🌊' },
  { id: 'blocked_road', icon: '🚧' },
  { id: 'bridge_damage', icon: '🌉' },
  { id: 'heavy_rain', icon: '🌧️' },
]

export const SOS_TYPES = [
  { id: 'accident', icon: '💥' },
  { id: 'breakdown', icon: '🔧' },
  { id: 'medical', icon: '🚑' },
  { id: 'danger', icon: '⚠️' },
]

/** Strip local bookkeeping so we POST exactly the agreed contract shape.
 *
 * `row.state` is deliberately NOT sent. Here it is this device's sync status
 * (pending | relaying | synced | failed), but in the shared contract `state` is
 * the Indian state a report happened in -- the backend fills that in from the
 * nearest road segment. Sending ours would put "synced" where "Sikkim" belongs.
 */
export function toContract(row) {
  return {
    event_id: row.event_id,
    type: row.type,
    lat: row.lat,
    lng: row.lng,
    timestamp: row.timestamp,
    photo: row.photo ?? null,
    vehicle_id: row.vehicle_id,
  }
}
