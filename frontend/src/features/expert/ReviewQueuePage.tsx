/** Expert review queue (Phase 5). Priority-ordered by the backend already. */

import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import { ApiError } from '@/api/client'
import { reviewsApi } from '@/api/endpoints/reviews'
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/States'
import { ProvenanceBadge, VerificationChip } from '@/components/provenance/ProvenanceBadge'

export function ReviewQueuePage() {
  const { t } = useTranslation()
  const query = useQuery({ queryKey: ['review-queue'], queryFn: () => reviewsApi.queue() })

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-slate-900">{t('nav.queue')}</h1>

      {query.isLoading && <LoadingState rows={4} />}
      {query.isError && (
        <ErrorState
          message={query.error instanceof ApiError ? query.error.message : 'Something went wrong.'}
          onRetry={() => void query.refetch()}
        />
      )}
      {query.isSuccess && query.data.items.length === 0 && (
        <EmptyState title="Nothing awaiting review" hint="New low-confidence reports appear here." />
      )}

      <ul className="space-y-3">
        {query.data?.items.map((obs) => (
          <li key={obs.id}>
            <Link
              to={`/expert/cases/${obs.id}`}
              className="block rounded-lg border border-slate-200 bg-white p-4 hover:border-brand"
            >
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="font-medium text-slate-900">
                    {obs.prediction ? obs.prediction.predicted_class.replaceAll('_', ' ') : 'No prediction'}
                  </p>
                  {obs.prediction && (
                    <p className="text-sm text-slate-500">
                      {(obs.prediction.confidence * 100).toFixed(0)}% confidence · model{' '}
                      {obs.prediction.model_version}
                    </p>
                  )}
                  <p className="mt-1 text-xs text-slate-400">
                    Reported {new Date(obs.observed_at).toLocaleString()}
                  </p>
                </div>
                <VerificationChip status={obs.verification_status as never} />
              </div>
              <ProvenanceBadge
                provenance={{
                  source_type: obs.provenance.source_type as never,
                  created_by: null,
                  created_at: obs.provenance.created_at,
                }}
                className="mt-3"
              />
            </Link>
          </li>
        ))}
      </ul>
    </div>
  )
}
