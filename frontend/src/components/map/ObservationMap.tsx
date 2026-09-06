/**
 * Observation map (Phase 4).
 *
 * Renders observation points and hotspot clusters over Leaflet. Marker colour encodes
 * `verification_status` so a confirmed case is never visually indistinguishable from
 * an unconfirmed AI prediction (TRD 10.4) - the same rule the provenance chips follow
 * elsewhere in this app.
 *
 * The tile layer is opt-in: VITE_MAP_TILE_URL is unset by default (no provider's
 * terms have been verified yet), so with no configured tiles the map still renders
 * its data layers over a blank base rather than silently calling a third party.
 */

import { useEffect, useMemo } from 'react'
import { CircleMarker, MapContainer, Popup, TileLayer, Circle, useMap } from 'react-leaflet'
import { useTranslation } from 'react-i18next'
import type { ObservationFeature, Hotspot } from '@/api/endpoints/gis'

const STATUS_COLORS: Record<string, string> = {
  CONFIRMED: '#059669',
  CORRECTED: '#059669',
  PREDICTED: '#d97706',
  PENDING_REVIEW: '#2563eb',
  REJECTED: '#94a3b8',
  LAB_REFERRED: '#7c3aed',
}

const HOTSPOT_COLORS: Record<Hotspot['hotspot_type'], string> = {
  CONFIRMED: '#059669',
  SIGNAL: '#d97706',
  PREDICTED: '#dc2626',
}

const TILE_URL = import.meta.env.VITE_MAP_TILE_URL as string | undefined
const TILE_ATTRIBUTION = import.meta.env.VITE_MAP_ATTRIBUTION as string | undefined

const DEFAULT_CENTER = ((import.meta.env.VITE_MAP_DEFAULT_CENTER as string) ?? '19.75,75.71')
  .split(',')
  .map(Number) as [number, number]
const DEFAULT_ZOOM = Number(import.meta.env.VITE_MAP_DEFAULT_ZOOM ?? 7)

/**
 * Leaflet measures its container once, at init. Inside a flex/grid dashboard the
 * final size often lands a frame later, which leaves the map convinced it is smaller
 * than it is and so only requesting a corner of the tiles it needs (the classic
 * "grey map" symptom). Re-measure after mount and on resize.
 */
function KeepSized() {
  const map = useMap()
  useEffect(() => {
    const resize = () => map.invalidateSize()
    const raf = requestAnimationFrame(resize)
    const timer = setTimeout(resize, 300)
    window.addEventListener('resize', resize)
    return () => {
      cancelAnimationFrame(raf)
      clearTimeout(timer)
      window.removeEventListener('resize', resize)
    }
  }, [map])
  return null
}

function FitOnData({ features }: { features: ObservationFeature[] }) {
  const map = useMap()
  useEffect(() => {
    if (features.length === 0) return
    const bounds = features.map((f) => [f.geometry.coordinates[1], f.geometry.coordinates[0]]) as [
      number,
      number,
    ][]
    if (bounds.length === 1) {
      map.setView(bounds[0], 13)
    } else {
      map.fitBounds(bounds, { padding: [40, 40], maxZoom: 14 })
    }
    // Only refit when the feature set actually changes, not on every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [features.length])
  return null
}

export function ObservationMap({
  features,
  hotspots = [],
  height = 500,
}: {
  features: ObservationFeature[]
  hotspots?: Hotspot[]
  height?: number
}) {
  const { t } = useTranslation()

  const legend = useMemo(
    () => [
      { label: t('verification.CONFIRMED'), color: STATUS_COLORS.CONFIRMED },
      { label: t('verification.PREDICTED'), color: STATUS_COLORS.PREDICTED },
      { label: t('verification.PENDING_REVIEW'), color: STATUS_COLORS.PENDING_REVIEW },
    ],
    [t],
  )

  return (
    <div className="space-y-2">
      <div
        style={{ height }}
        className="overflow-hidden rounded-lg border border-slate-200"
        data-testid="observation-map"
      >
        <MapContainer center={DEFAULT_CENTER} zoom={DEFAULT_ZOOM} style={{ height: '100%', width: '100%' }}>
          {TILE_URL && <TileLayer url={TILE_URL} attribution={TILE_ATTRIBUTION ?? ''} />}
          <KeepSized />
          <FitOnData features={features} />

          {hotspots.map((h) => (
            <Circle
              key={h.cluster_id}
              center={[h.centroid.latitude, h.centroid.longitude]}
              radius={h.radius_m}
              pathOptions={{
                color: HOTSPOT_COLORS[h.hotspot_type],
                fillColor: HOTSPOT_COLORS[h.hotspot_type],
                fillOpacity: 0.12,
                weight: 2,
              }}
            >
              <Popup>
                <div className="text-sm">
                  <p className="font-semibold">{h.label}</p>
                  <p>{h.observation_count} observations</p>
                  <p>
                    {h.confirmed_count} confirmed · {h.predicted_count} unconfirmed
                  </p>
                  {h.dominant_agent_name && <p>Likely: {h.dominant_agent_name}</p>}
                  {h.includes_demo_data && (
                    <p className="mt-1 font-semibold text-fuchsia-700">
                      {t('provenance.demoWarning')}
                    </p>
                  )}
                </div>
              </Popup>
            </Circle>
          ))}

          {features.map((f) => (
            <CircleMarker
              key={f.properties.id}
              center={[f.geometry.coordinates[1], f.geometry.coordinates[0]]}
              radius={7}
              pathOptions={{
                color: STATUS_COLORS[f.properties.verification_status] ?? '#334155',
                fillColor: STATUS_COLORS[f.properties.verification_status] ?? '#334155',
                fillOpacity: f.properties.source_type === 'DEMO_SIMULATION' ? 0.35 : 0.85,
                dashArray: f.properties.source_type === 'DEMO_SIMULATION' ? '3,3' : undefined,
              }}
            >
              <Popup>
                <div className="min-w-40 text-sm">
                  <p className="font-semibold">
                    {f.properties.agent_name ?? t('nav.checkHealth')}
                    {f.properties.match_basis === 'PREDICTED_AGENT' && ' (AI)'}
                  </p>
                  {f.properties.crop_name && <p>{f.properties.crop_name}</p>}
                  {f.properties.confidence !== null && (
                    <p>Confidence: {(f.properties.confidence * 100).toFixed(0)}%</p>
                  )}
                  {f.properties.risk_level && <p>Risk: {f.properties.risk_level}</p>}
                  <p>{t(`verification.${f.properties.verification_status}`)}</p>
                  <p className="text-xs text-slate-500">
                    {new Date(f.properties.observed_at).toLocaleDateString()}
                  </p>
                  {f.properties.source_type === 'DEMO_SIMULATION' && (
                    <p className="mt-1 font-semibold text-fuchsia-700">
                      {t('provenance.demoWarning')}
                    </p>
                  )}
                </div>
              </Popup>
            </CircleMarker>
          ))}
        </MapContainer>
      </div>

      {!TILE_URL && (
        <p className="text-xs text-slate-500">
          No map tile provider is configured - showing data layers on a blank base.
        </p>
      )}

      <div className="flex flex-wrap gap-3 text-xs text-slate-600">
        {legend.map((item) => (
          <span key={item.label} className="flex items-center gap-1">
            <span
              className="inline-block h-2.5 w-2.5 rounded-full"
              style={{ backgroundColor: item.color }}
            />
            {item.label}
          </span>
        ))}
      </div>
    </div>
  )
}
