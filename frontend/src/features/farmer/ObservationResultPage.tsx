/**
 * Observation result (Phase 2 + 3).
 *
 * Renders every element the pipeline produces: image, AI prediction + confidence,
 * verification status (always shown separately from the prediction), weather, risk
 * level + explanation, contributing/missing factors, and any processing errors.
 */

import { useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import type { TFunction } from 'i18next'

import { ApiError, serverUrl } from '@/api/client'
import { advisoryApi } from '@/api/endpoints/advisory'
import { observationsApi, type PredictionOut } from '@/api/endpoints/observations'
import { useAuthStore } from '@/stores/auth'
import { useLanguageStore } from '@/stores/language'
import { ErrorState, LoadingState } from '@/components/ui/States'
import { AdvisoryCard } from '@/components/provenance/AdvisoryCard'
import { FollowupPanel } from '@/components/provenance/FollowupPanel'
import { ProvenanceBadge, VerificationChip } from '@/components/provenance/ProvenanceBadge'
import { RiskCard } from '@/components/provenance/RiskCard'
import { WeatherCard } from '@/components/provenance/WeatherCard'

const PROCESSING_ERROR_LABELS: Record<string, string> = {
  AI_MODEL_UNAVAILABLE: 'No AI model is currently available. This report has been sent for expert review.',
  AI_INFERENCE_FAILED: 'AI analysis failed on this image. This report has been sent for expert review.',
  CONTEXT_FAILED: 'Some contextual data could not be assembled.',
  RISK_UNAVAILABLE: 'Risk could not be calculated for this report.',
}

/** Wording-only tiering (TRD-style honesty rule): the actual PENDING_REVIEW/PREDICTED
 * gate stays entirely backend-driven (see `app.ai.inference_service`) - this only
 * chooses which sentence introduces the same unconfirmed prediction. Never implies
 * a confirmed diagnosis at any tier. */
function confidenceTierLabel(
  prediction: PredictionOut,
  verificationStatus: string,
  t: TFunction,
): string {
  const name = prediction.predicted_class.replaceAll('_', ' ')
  if (verificationStatus === 'CONFIRMED' || verificationStatus === 'CORRECTED') return name
  if (prediction.confidence < 0.5 || verificationStatus === 'PENDING_REVIEW') {
    return t('ai.uncertain')
  }
  if (prediction.is_low_confidence) return t('ai.possible', { name })
  return t('ai.likely', { name })
}

export function ObservationResultPage() {
  const { t } = useTranslation()
  const { id } = useParams<{ id: string }>()
  const accessToken = useAuthStore((s) => s.accessToken)
  const language = useLanguageStore((s) => s.language)

  const query = useQuery({
    queryKey: ['observation', id],
    queryFn: () => observationsApi.get(id!),
    enabled: Boolean(id),
    // Poll while still processing; stop once the pipeline has a terminal status.
    refetchInterval: (q) => (q.state.data?.status === 'PROCESSING' ? 1500 : false),
  })

  const advisoryQuery = useQuery({
    queryKey: ['advisory', id, language],
    queryFn: () => advisoryApi.get(id!, language),
    // The advisory is only meaningful once the pipeline has finished.
    enabled: Boolean(id) && query.data?.status !== 'PROCESSING',
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
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-slate-900">Crop health report</h1>

      {observation.image && (
        <AuthedImage src={serverUrl(observation.image.url)} token={accessToken} />
      )}

      {/* Processing errors: the observation survived, but a stage degraded. */}
      {observation.processing_errors &&
        Object.entries(observation.processing_errors).map(([stage, err]) => (
          <div
            key={stage}
            className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900"
          >
            {PROCESSING_ERROR_LABELS[err.code] ?? `${stage}: ${err.code}`}
          </div>
        ))}

      {/* Prediction + verification status, always shown together (TRD 20.2). */}
      <div className="rounded-lg border border-slate-200 bg-white p-4">
        <div className="mb-3 flex items-center justify-between gap-2">
          <h2 className="text-sm font-semibold text-emerald-800">🤖 {t('ai.analysis')}</h2>
          <VerificationChip status={observation.verification_status as never} />
        </div>
        {observation.prediction ? (
          <div>
            <p className="text-lg font-medium text-slate-900">
              {confidenceTierLabel(observation.prediction, observation.verification_status, t)}
            </p>
            <p className="text-sm text-slate-500">
              {observation.prediction.predicted_class.replaceAll('_', ' ')}
            </p>
            <div className="mt-2 flex items-center gap-2">
              <span className="h-1.5 w-32 overflow-hidden rounded-full bg-slate-200">
                <span
                  className="block h-full rounded-full bg-amber-500"
                  style={{ width: `${observation.prediction.confidence * 100}%` }}
                />
              </span>
              <span className="text-sm text-slate-600">
                {(observation.prediction.confidence * 100).toFixed(0)}% {t('ai.confidence')}
              </span>
            </div>
            <p className="mt-2 text-xs text-slate-500">
              Model: {observation.prediction.model_version}
              {observation.prediction.inference_ms !== null &&
                ` · ${observation.prediction.inference_ms}ms`}
            </p>
            {observation.prediction.top_k && observation.prediction.top_k.length > 1 && (
              <ul className="mt-2 text-xs text-slate-500">
                {observation.prediction.top_k.map((k) => (
                  <li key={k.class}>
                    {k.class}: {(k.confidence * 100).toFixed(0)}%
                  </li>
                ))}
              </ul>
            )}
            {/* An AI prediction is never presented as a diagnosis. */}
            <p className="mt-3 rounded bg-amber-50 p-2 text-xs text-amber-800">
              {t('ai.notDiagnosis')}
            </p>
          </div>
        ) : (
          <p className="text-sm text-slate-600">
            No AI prediction is available for this report yet.
          </p>
        )}
      </div>

      {observation.weather && <WeatherCard weather={observation.weather} />}
      {observation.risk && <RiskCard risk={observation.risk} />}
      {advisoryQuery.data && <AdvisoryCard advisory={advisoryQuery.data} />}
      {observation.status !== 'PROCESSING' && <FollowupPanel observationId={observation.id} />}

      <ProvenanceBadge
        provenance={{
          source_type: observation.provenance.source_type as never,
          created_by: null,
          created_at: observation.provenance.created_at,
          model_version: observation.provenance.model_version,
        }}
      />
    </div>
  )
}

/** Images require the bearer token; fetch as a blob rather than a bare <img src>.
 * Shared by every screen that shows an observation photo (result, review, official
 * detail, dashboard, history) so none of them re-implement the auth handshake. */
export function AuthedImage({
  src,
  token,
  className = 'max-h-96 w-full rounded-lg object-cover',
  skeletonClassName = 'h-64 w-full animate-pulse rounded-lg bg-slate-200',
}: {
  src: string
  token: string | null
  className?: string
  skeletonClassName?: string
}) {
  const query = useQuery({
    queryKey: ['image', src],
    queryFn: async () => {
      const response = await fetch(src, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      if (!response.ok) throw new Error(`Image request failed: ${response.status}`)
      const blob = await response.blob()
      return URL.createObjectURL(blob)
    },
    retry: false,
  })

  if (query.isError) {
    return (
      <div
        className={`${skeletonClassName} flex animate-none items-center justify-center text-2xl`}
        aria-label="Image unavailable"
      >
        🌱
      </div>
    )
  }
  if (!query.data) return <div className={skeletonClassName} />
  return <img src={query.data} alt="Submitted crop observation" className={className} />
}
