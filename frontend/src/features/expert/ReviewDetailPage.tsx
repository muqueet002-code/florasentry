/**
 * Expert review screen (Phase 5).
 *
 * Shows exactly what the farmer's own result screen shows (image, prediction,
 * confidence, weather, risk) plus the confirm/correct/reject actions. The AI
 * prediction is rendered read-only - the decision buttons only ever change the
 * observation's own verification columns (TRD 20.2), never the prediction itself.
 */

import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { useTranslation } from 'react-i18next'

import { ApiError, serverUrl } from '@/api/client'
import { catalogApi } from '@/api/endpoints/catalog'
import { followupsApi } from '@/api/endpoints/followups'
import { reviewsApi } from '@/api/endpoints/reviews'
import { useAuthStore } from '@/stores/auth'
import { Button } from '@/components/ui/Button'
import { ErrorState, LoadingState } from '@/components/ui/States'
import { ProvenanceBadge, VerificationChip } from '@/components/provenance/ProvenanceBadge'
import { RiskCard } from '@/components/provenance/RiskCard'
import { WeatherCard } from '@/components/provenance/WeatherCard'
import { AuthedImage } from '@/features/farmer/ObservationResultPage'

type Decision = 'CONFIRM' | 'CORRECT' | 'REJECT'

export function ReviewDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const accessToken = useAuthStore((s) => s.accessToken)
  const { t } = useTranslation()

  const [note, setNote] = useState('')
  const [correctedAgentId, setCorrectedAgentId] = useState('')
  const [error, setError] = useState<string | null>(null)

  const query = useQuery({
    queryKey: ['review', id],
    queryFn: () => reviewsApi.get(id!),
    enabled: Boolean(id),
  })
  const agentsQuery = useQuery({ queryKey: ['agents'], queryFn: () => catalogApi.agents() })

  // Part F: experts see follow-up info while reviewing, so worsened/uncertain
  // cases are identifiable without a separate dashboard. Read-only here - the
  // review screen never edits a follow-up, only the observation's verification.
  const followupsQuery = useQuery({
    queryKey: ['followups', id],
    queryFn: () => followupsApi.listForObservation(id!),
    enabled: Boolean(id),
  })

  const decide = useMutation({
    mutationFn: (decision: Decision) =>
      reviewsApi.decide(id!, {
        decision,
        corrected_agent_id: decision === 'CORRECT' ? correctedAgentId || null : null,
        note: note || null,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['review-queue'] })
      navigate('/expert/queue')
    },
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : 'Could not submit the decision.'),
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
  const canDecide = observation.verification_status === 'PENDING_REVIEW'

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <div className="space-y-4">
        <h1 className="text-xl font-semibold text-slate-900">Review case</h1>

        {observation.image && (
          <AuthedImage
            src={serverUrl(observation.image.url)}
            token={accessToken}
          />
        )}

        <div className="rounded-lg border border-slate-200 bg-white p-4">
          <div className="mb-2 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-emerald-800">🤖 {t('ai.prediction')}</h2>
            <VerificationChip status={observation.verification_status as never} />
          </div>
          {observation.prediction ? (
            <div>
              <p className="text-lg font-medium text-slate-900">
                {observation.prediction.predicted_class.replaceAll('_', ' ')}
              </p>
              <p className="text-sm text-slate-600">
                {(observation.prediction.confidence * 100).toFixed(0)}% {t('ai.confidence')} · model{' '}
                {observation.prediction.model_version}
              </p>
              {/* Read-only: the review action never edits this. */}
              <p className="mt-2 rounded bg-amber-50 p-2 text-xs text-amber-800">
                {t('ai.notDiagnosis')} Shown as originally produced - not editable here.
              </p>
            </div>
          ) : (
            <p className="mt-2 text-sm text-slate-600">No AI prediction is available.</p>
          )}
          {(observation.verification_status === 'CONFIRMED' ||
            observation.verification_status === 'CORRECTED') && (
            <p className="mt-3 border-t border-slate-100 pt-2 text-sm font-medium text-emerald-700">
              ✓ {t('verification.CONFIRMED')}
              {observation.verification_status === 'CORRECTED' && ` (${t('verification.CORRECTED')})`}
            </p>
          )}
        </div>

        {observation.weather && <WeatherCard weather={observation.weather} />}
        {observation.risk && <RiskCard risk={observation.risk} />}

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
          <h2 className="font-medium text-slate-900">Decision</h2>

          {!canDecide && (
            <p className="mt-2 text-sm text-slate-600">
              This observation is already {observation.verification_status.toLowerCase()} and can
              no longer be decided.
            </p>
          )}

          {canDecide && (
            <div className="mt-3 space-y-3">
              <div>
                <label className="block text-sm font-medium text-slate-700">
                  Correct diagnosis (only needed for "Correct")
                </label>
                <select
                  value={correctedAgentId}
                  onChange={(e) => setCorrectedAgentId(e.target.value)}
                  className="mt-1 block w-full rounded border border-slate-300 px-3 py-2 text-sm"
                >
                  <option value="">Select a diagnosis...</option>
                  {agentsQuery.data?.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700">Note (optional)</label>
                <textarea
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  rows={2}
                  className="mt-1 block w-full rounded border border-slate-300 px-3 py-2 text-sm"
                />
              </div>

              {error && <ErrorState message={error} />}

              <div className="flex flex-wrap gap-2">
                <Button onClick={() => decide.mutate('CONFIRM')} disabled={decide.isPending}>
                  Confirm
                </Button>
                <Button
                  variant="secondary"
                  onClick={() => decide.mutate('CORRECT')}
                  disabled={decide.isPending || !correctedAgentId}
                >
                  Correct
                </Button>
                <Button
                  variant="danger"
                  onClick={() => decide.mutate('REJECT')}
                  disabled={decide.isPending}
                >
                  Reject
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
