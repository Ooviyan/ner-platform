import { useEffect, useMemo } from 'react'
import { MapContainer, TileLayer, Polyline, CircleMarker, Tooltip, useMap } from 'react-leaflet'
import { useTranslation } from 'react-i18next'
import { useLink } from '../hooks/useLink.js'
import { riskColor } from './common.jsx'

/**
 * Keeps the viewport on the whole route whenever the geometry changes.
 *
 * The map mounts inside a lazy Suspense boundary, so Leaflet often measures the
 * container before it has reached its final width and then frames the route
 * against the top-left corner. invalidateSize() re-measures before fitting, and
 * a ResizeObserver re-fits on any later size change (orientation, keyboard,
 * the card growing as data arrives).
 */
function FitBounds({ points }) {
  const map = useMap()
  useEffect(() => {
    if (!points || points.length < 2) return undefined

    const el = map.getContainer()
    let lastW = 0
    let lastH = 0

    // Re-fit only when the container's size genuinely changed. fitBounds itself
    // mutates the panes, so an unguarded ResizeObserver re-enters this and
    // re-fits against a transient size, which lands on the wrong zoom.
    const fit = () => {
      const w = el.clientWidth
      const h = el.clientHeight
      if (!w || !h || (w === lastW && h === lastH)) return
      lastW = w
      lastH = h
      map.invalidateSize({ animate: false })
      map.fitBounds(points, { padding: [26, 26], maxZoom: 11, animate: false })
    }

    fit()
    const ro = new ResizeObserver(fit)
    ro.observe(el)
    return () => ro.disconnect()
  }, [map, points])
  return null
}

export default function MapView({ route, position, reports = [], height = 240 }) {
  const { t } = useTranslation()
  const { linkUp } = useLink()

  const segments = route?.segments || []
  const allPoints = useMemo(
    () => segments.flatMap(s => s.path || []),
    [segments]
  )
  const center = allPoints[0] || [26.1445, 91.7362]

  return (
    <div style={{ position: 'relative', height, background: '#0a2b29' }}>
      <MapContainer
        center={center}
        zoom={8}
        scrollWheelZoom={false}
        style={{ height: '100%', width: '100%', background: '#0a2b29' }}
        attributionControl={false}
      >
        <TileLayer
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
          maxZoom={18}
          // Dimmed so the coloured route reads clearly on the dark UI.
          className="ner-tiles"
        />
        <FitBounds points={allPoints} />

        {segments.map(seg => (
          <Polyline
            key={seg.id}
            positions={seg.path || []}
            pathOptions={{
              color: riskColor(seg.status, seg.risk),
              weight: 5,
              opacity: 0.95,
              lineCap: 'round',
            }}
          >
            <Tooltip sticky>
              {seg.name} · {t('home.risk')} {Math.round((seg.risk || 0) * 100)}%
            </Tooltip>
          </Polyline>
        ))}

        {allPoints.length > 0 && (
          <CircleMarker
            center={allPoints[0]}
            radius={6}
            pathOptions={{ color: '#f2fbfa', fillColor: '#2dd4bf', fillOpacity: 1, weight: 2 }}
          >
            <Tooltip>{route?.origin?.name}</Tooltip>
          </CircleMarker>
        )}
        {allPoints.length > 1 && (
          <CircleMarker
            center={allPoints[allPoints.length - 1]}
            radius={6}
            pathOptions={{ color: '#f2fbfa', fillColor: '#f43f5e', fillOpacity: 1, weight: 2 }}
          >
            <Tooltip>{route?.destination?.name}</Tooltip>
          </CircleMarker>
        )}

        {reports.map(r => (
          <CircleMarker
            key={r.event_id}
            center={[r.lat, r.lng]}
            radius={5}
            pathOptions={{ color: '#fbbf24', fillColor: '#fbbf24', fillOpacity: 0.85, weight: 1.5 }}
          >
            <Tooltip>{t(`report.types.${r.type}`, r.type)}</Tooltip>
          </CircleMarker>
        ))}

        {position && (
          <CircleMarker
            center={[position.lat, position.lng]}
            radius={7}
            pathOptions={{ color: '#ffffff', fillColor: '#38bdf8', fillOpacity: 1, weight: 3 }}
          >
            <Tooltip>{t('report.location')}</Tooltip>
          </CircleMarker>
        )}
      </MapContainer>

      {!linkUp && (
        <div
          style={{
            position: 'absolute',
            left: 8,
            right: 8,
            bottom: 8,
            zIndex: 500,
            pointerEvents: 'none',
          }}
        >
          <div className="banner warn tiny" style={{ padding: '6px 10px' }}>
            {t('home.map_offline')}
          </div>
        </div>
      )}
    </div>
  )
}
