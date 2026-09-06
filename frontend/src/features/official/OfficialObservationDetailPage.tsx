/**
 * Official observation detail (Phase 8).
 *
 * Read-only. Reuses exactly the same endpoints the farmer's result page and the
 * expert's review screen use (`GET /observations/{id}`, `/advisory`,
 * `/followups?observation_id=`) - an official looks at the same record, not a copy of
 * it, and cannot decide/correct/reject (that stays an expert-only action).
 */

import { useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import { ApiError, serverUrl } from '@/api/client'
import { advisoryApi } from '@/api/endpoints/advisory'
import { followupsApi } from '@/api/endpoints/followups'
import { observationsApi } from '@/api/endpoints/observations'
import { useAuthStore } from '@/stores/auth'
import { useLanguageStore } from '@/stores/language'
import { AdvisoryCard } from '@/components/provenance/AdvisoryCard'
import { ProvenanceBadge, VerificationChip } from '@/components/provenance/ProvenanceBadge'
import { RiskCard } from '@/components/provenance/RiskCard'
import { WeatherCard } from '@/components/provenance/WeatherCard'
import { ErrorState, LoadingState } from '@/components/ui/States'
import { AuthedImage } from '@/features/farmer/ObservationResultPage'

export function OfficialObservationDetailPage() {
  const { id } = useParams<{ id: string }>()
  const { t } = useTranslation()
  const accessToken = useAuthStore((s) => s.accessToken)
  const language = useLanguageStore((s) => s.language)

  const query = useQuery({
    queryKey: ['observation', id],
    queryFn: () => observationsApi.get(id!),
    enabled: Boolean(id),
  })

  const advisoryQuery = useQuery({
    queryKey: ['advisory', id, language],
    queryFn: () => advisoryApi.get(id!, language),
    enabled: Boolean(id) && query.data?.status !== 'PROCESSING',
  })

  const followupsQuery = useQuery({
    queryKey: ['followups', id],
    queryFn: () => followupsApi.listForObservation(id!),
    enabled: Boolean(id),
  })

  if (query.isLoading) return <LoadingState rows={4} />
  if (query.isError) {
    return (
      <ErrorState
        message={query.error instanceof ApiError ? query.error.message : 'Something went wrong.'}
        onRetry={() => void query.refetch()}
      />
    )
  }

  const observation = query.data!

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <div className="space-y-4">
        <h1 className="text-xl font-semibold text-slate-900">{t('dashboard.caseDetail')}</h1>

        {observation.image && (
          <AuthedImage src={serverUrl(observation.image.url)} token={accessToken} />
        )}

        <div className="rounded-lg border border-slate-200 bg-white p-4">
          <div className="mb-3 flex items-center gap-2">
            <VerificationChip status={observation.verification_status as never} />
          </div>
          {observation.prediction ? (
            <div>
              <p className="text-lg font-medium text-slate-900">
                {observation.prediction.predicted_class.replaceAll('_', ' ')}
              </p>
              <p className="text-sm text-slate-600">
                {(observation.prediction.confidence * 100).toFixed(0)}% {t('dashboard.confidence')}{' '}
                · {t('provenance.modelVersion')} {observation.prediction.model_version}
              </p>
              <p className="mt-2 rounded bg-amber-50 p-2 text-xs text-amber-800">
                {t('dashboard.aiNotDiagnosis')}
              </p>
            </div>
          ) : (
            <p className="text-sm text-slate-600">{t('dashboard.noPrediction')}</p>
          )}
        </div>

        {observation.weather && <WeatherCard weather={observation.weather} />}
        {observation.risk && <RiskCard risk={observation.risk} />}
        {advisoryQuery.data && <AdvisoryCard advisory={advisoryQuery.data} />}

        <ProvenanceBadge
          provenance={{
            source_type: observation.provenance.source_type as never,
            created_by: null,
            created_at: observation.provenance.created_at,
            model_version: observation.provenance.model_version,
          }}
        />
      </div>

      <div className="space-y-4">
        <div className="rounded-lg border border-slate-200 bg-white p-4">
          <h2 className="font-medium text-slate-900">{t('dashboard.context')}</h2>
          <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
            <dt className="text-slate-500">{t('fields.coordinates')}</dt>
            <dd className="tabular-nums text-slate-800">
              {observation.latitude.toFixed(5)}, {observation.longitude.toFixed(5)}
            </dd>
            <dt className="text-slate-500">{t('dashboard.reportedAt')}</dt>
            <dd className="text-slate-800">
              {new Date(observation.observed_at).toLocaleString()}
            </dd>
            {observation.reported_severity !== null && (
              <>
                <dt className="text-slate-500">{t('dashboard.reportedSeverity')}</dt>
                <dd className="text-slate-800">{observation.reported_severity}/5</dd>
              </>
            )}
            {observation.notes && (
              <>
                <dt className="text-slate-500">{t('common.notes', 'Notes')}</dt>
                <dd className="text-slate-800">{observation.notes}</dd>
              </>
            )}
          </dl>
        </div>

        <div className="rounded-lg border border-slate-200 bg-white p-4">
          <h2 className="font-medium text-slate-900">{t('followup.expertView.title')}</h2>
          {followupsQuery.isLoading && <p className="mt-2 text-sm text-slate-500">…</p>}
          {followupsQuery.data && followupsQuery.data.items.length === 0 && (
            <p className="mt-2 text-sm text-slate-600">{t('followup.expertView.none')}</p>
          )}
          {followupsQuery.data?.items.map((f) => {
            const needsAttention = f.outcome === 'WORSENED' || f.outcome === 'NEEDS_EXPERT_REVIEW'
            return (
              <div
                key={f.id}
                className={
                  'mt-2 rounded border p-2 text-sm ' +
                  (needsAttention
                    ? 'border-red-300 bg-red-50 text-red-900'
                    : 'border-slate-200 bg-slate-50 text-slate-700')
                }
              >
                <p className="font-medium">
                  {t(`followup.status.${f.status}`)}
                  {f.outcome && `: ${t(`followup.outcome.${f.outcome}`)}`}
                  {needsAttention && ` — ${t('followup.expertView.attentionNeeded')}`}
                </p>
                {f.notes && <p className="mt-1">{f.notes}</p>}
                {f.submitted_at && (
                  <p className="mt-1 text-xs opacity-70">
                    {new Date(f.submitted_at).toLocaleString()}
                  </p>
                )}
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
