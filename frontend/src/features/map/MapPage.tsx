/**
 * Observation map with filters and hotspot toggle (Phase 4).
 *
 * Shared by /expert/map and /official/map - both roles hold VIEW_HOTSPOTS, and the
 * backend applies its own role-based visibility scope regardless of who is looking.
 */

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import { ApiError } from '@/api/client'
import { gisApi } from '@/api/endpoints/gis'
import { catalogApi } from '@/api/endpoints/catalog'
import { useAuthStore } from '@/stores/auth'
import { ObservationMap } from '@/components/map/ObservationMap'
import { DemoDataBanner } from '@/components/provenance/ProvenanceBadge'
import { ErrorState, LoadingState } from '@/components/ui/States'

const VERIFICATION_OPTIONS = [
  'PREDICTED',
  'PENDING_REVIEW',
  'CONFIRMED',
  'CORRECTED',
  'REJECTED',
  'LAB_REFERRED',
]
const RISK_OPTIONS = ['LOW', 'MEDIUM', 'HIGH']

export function MapPage() {
  const { t } = useTranslation()
  const role = useAuthStore((s) => s.user?.role)
  // Hotspot detection is gated server-side by VIEW_HOTSPOTS (RBAC) - a farmer never
  // holds it, so this shared map page must not even attempt that request for them
  // (it would just surface as a confusing 403).
  const canViewHotspots = role === 'EXTENSION_WORKER' || role === 'OFFICIAL' || role === 'ADMIN'
  const [cropId, setCropId] = useState('')
  const [verificationStatus, setVerificationStatus] = useState('')
  const [riskLevel, setRiskLevel] = useState('')
  const [showHotspots, setShowHotspots] = useState(canViewHotspots)
  const [includeDemo, setIncludeDemo] = useState(false)

  const cropsQuery = useQuery({ queryKey: ['crops'], queryFn: catalogApi.crops })

  const observationsQuery = useQuery({
    queryKey: ['gis-observations', cropId, verificationStatus, riskLevel, includeDemo],
    queryFn: () =>
      gisApi.observations({
        crop_id: cropId || undefined,
        verification_status: verificationStatus || undefined,
        risk_level: riskLevel || undefined,
        include_demo: includeDemo,
      }),
  })

  const hotspotsQuery = useQuery({
    queryKey: ['gis-hotspots', cropId, includeDemo],
    queryFn: () => gisApi.hotspots({ crop_id: cropId || undefined, include_demo: includeDemo }),
    enabled: showHotspots && canViewHotspots,
  })

  const hasDemo =
    (observationsQuery.data?.features.some((f) => f.properties.source_type === 'DEMO_SIMULATION') ??
      false) || (hotspotsQuery.data?.some((h) => h.includes_demo_data) ?? false)

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-slate-900">{t('nav.map')}</h1>

      <DemoDataBanner visible={hasDemo} />

      <div className="flex flex-wrap items-center gap-3 rounded-lg border border-slate-200 bg-white p-3">
        <select
          value={cropId}
          onChange={(e) => setCropId(e.target.value)}
          className="rounded border border-slate-300 px-2 py-1.5 text-sm"
        >
          <option value="">{t('fields.crop')}: all</option>
          {cropsQuery.data?.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>

        <select
          value={verificationStatus}
          onChange={(e) => setVerificationStatus(e.target.value)}
          className="rounded border border-slate-300 px-2 py-1.5 text-sm"
        >
          <option value="">Status: all</option>
          {VERIFICATION_OPTIONS.map((s) => (
            <option key={s} value={s}>
              {t(`verification.${s}`)}
            </option>
          ))}
        </select>

        <select
          value={riskLevel}
          onChange={(e) => setRiskLevel(e.target.value)}
          className="rounded border border-slate-300 px-2 py-1.5 text-sm"
        >
          <option value="">Risk: all</option>
          {RISK_OPTIONS.map((r) => (
            <option key={r} value={r}>
              {r}
            </option>
          ))}
        </select>

        {canViewHotspots && (
          <label className="flex items-center gap-1.5 text-sm text-slate-700">
            <input
              type="checkbox"
              checked={showHotspots}
              onChange={(e) => setShowHotspots(e.target.checked)}
            />
            Hotspots
          </label>
        )}

        <label className="flex items-center gap-1.5 text-sm text-slate-700">
          <input
            type="checkbox"
            checked={includeDemo}
            onChange={(e) => setIncludeDemo(e.target.checked)}
          />
          Include demo data
        </label>
      </div>

      {observationsQuery.isLoading && <LoadingState rows={3} />}
      {observationsQuery.isError && (
        <ErrorState
          message={
            observationsQuery.error instanceof ApiError
              ? observationsQuery.error.message
              : 'Could not load the map.'
          }
          onRetry={() => void observationsQuery.refetch()}
        />
      )}

      {observationsQuery.isSuccess && (
        <>
          {observationsQuery.data.features.length === 0 && (
            <p className="rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600">
              {t('map.noObservations')}
            </p>
          )}
          <ObservationMap
            features={observationsQuery.data.features}
            hotspots={showHotspots ? (hotspotsQuery.data ?? []) : []}
          />
        </>
      )}
    </div>
  )
}
