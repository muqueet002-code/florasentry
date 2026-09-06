/**
 * My Observations (farmer history list). Reuses the existing `GET /observations`
 * endpoint (already scoped to the caller) - no new backend surface.
 */

import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import { ApiError, serverUrl } from '@/api/client'
import { catalogApi } from '@/api/endpoints/catalog'
import { observationsApi } from '@/api/endpoints/observations'
import { useAuthStore } from '@/stores/auth'
import { VerificationChip } from '@/components/provenance/ProvenanceBadge'
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/States'
import { AuthedImage } from '@/features/farmer/ObservationResultPage'

export function MyObservationsPage() {
  const { t } = useTranslation()
  const accessToken = useAuthStore((s) => s.accessToken)
  const query = useQuery({
    queryKey: ['observations', 'history'],
    queryFn: () => observationsApi.list(1, 50),
  })
  const cropsQuery = useQuery({ queryKey: ['crops'], queryFn: catalogApi.crops })
  const cropName = (cropId: string | null) =>
    cropId ? (cropsQuery.data?.find((c) => c.id === cropId)?.name ?? null) : null

  if (query.isLoading) return <LoadingState rows={5} />
  if (query.isError) {
    return (
      <ErrorState
        message={query.error instanceof ApiError ? query.error.message : 'Something went wrong.'}
        onRetry={() => void query.refetch()}
      />
    )
  }

  const items = query.data?.items ?? []

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-slate-900">{t('nav.myObservations')}</h1>

      {items.length === 0 ? (
        <EmptyState
          title={t('dashboard.empty')}
          hint={t('dashboard.newObservationHint')}
          action={
            <Link to="/app/check" className="text-sm font-medium text-brand hover:underline">
              {t('dashboard.startObservation')}
            </Link>
          }
        />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {items.map((o) => (
            <Link
              key={o.id}
              to={`/app/observations/${o.id}`}
              className="block rounded-lg border border-slate-200 bg-white p-3 hover:border-brand hover:shadow-sm"
            >
              {o.image && (
                <div className="mb-2">
                  <AuthedImage
                    src={serverUrl(o.image.thumbnail_url ?? o.image.url)}
                    token={accessToken}
                    className="h-32 w-full rounded object-cover"
                    skeletonClassName="h-32 w-full animate-pulse rounded bg-slate-200"
                  />
                </div>
              )}
              <div className="flex items-center justify-between">
                <p className="text-sm font-medium text-slate-900">
                  {cropName(o.crop_id) ?? t('dashboard.cropUnknown')}
                </p>
                <VerificationChip status={o.verification_status as never} />
              </div>
              <p className="mt-1 text-xs text-slate-500">
                {o.prediction ? o.prediction.predicted_class.replaceAll('_', ' ') : '—'}
                {o.risk && ` · ${o.risk.risk_level}`}
              </p>
              <p className="mt-1 text-xs text-slate-400">
                {new Date(o.observed_at).toLocaleDateString()}
              </p>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
