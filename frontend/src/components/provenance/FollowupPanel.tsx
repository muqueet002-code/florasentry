/**
 * Follow-up panel (Phase 7).
 *
 * Embedded directly in the farmer's observation result screen (Part B/F: reuse the
 * existing result UI rather than building a separate page). Shows whether a
 * follow-up is scheduled/due, and lets the farmer submit one with an optional photo -
 * reusing the same multipart pattern as the original report.
 */

import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { ApiError } from '@/api/client'
import { followupsApi, type FollowupOutcome } from '@/api/endpoints/followups'
import { Button } from '@/components/ui/Button'
import { ErrorState, LoadingState } from '@/components/ui/States'

const OUTCOMES: FollowupOutcome[] = [
  'IMPROVED',
  'UNCHANGED',
  'WORSENED',
  'RESOLVED',
  'NEEDS_EXPERT_REVIEW',
]

export function FollowupPanel({ observationId }: { observationId: string }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [outcome, setOutcome] = useState<FollowupOutcome>('IMPROVED')
  const [notes, setNotes] = useState('')
  const [image, setImage] = useState<File | null>(null)
  const [error, setError] = useState<string | null>(null)

  const query = useQuery({
    queryKey: ['followups', observationId],
    queryFn: () => followupsApi.listForObservation(observationId),
  })

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ['followups', observationId] })

  const create = useMutation({
    mutationFn: () => followupsApi.create(observationId),
    onSuccess: invalidate,
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : 'Could not schedule a follow-up.'),
  })

  const submit = useMutation({
    mutationFn: (followupId: string) =>
      followupsApi.submit(followupId, { outcome, notes: notes || null }, image),
    onSuccess: () => {
      setNotes('')
      setImage(null)
      void invalidate()
    },
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : 'Could not submit the follow-up.'),
  })

  if (query.isLoading) return <LoadingState rows={1} />
  if (query.isError) {
    return (
      <ErrorState
        message={query.error instanceof ApiError ? query.error.message : 'Something went wrong.'}
        onRetry={() => void query.refetch()}
      />
    )
  }

  const followup = query.data?.items[0] ?? null

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <h2 className="font-semibold text-slate-900">{t('followup.title')}</h2>

      {!followup && (
        <div className="mt-2">
          <p className="text-sm text-slate-600">{t('followup.none')}</p>
          <Button
            variant="secondary"
            className="mt-2"
            onClick={() => create.mutate()}
            disabled={create.isPending}
          >
            {t('followup.schedule')}
          </Button>
        </div>
      )}

      {followup && followup.status === 'SUBMITTED' && (
        <div className="mt-2 space-y-1">
          <p className="text-sm text-slate-700">
            {t('followup.status.SUBMITTED')}:{' '}
            <span className="font-medium">
              {followup.outcome && t(`followup.outcome.${followup.outcome}`)}
            </span>
          </p>
          {followup.notes && <p className="text-sm text-slate-600">{followup.notes}</p>}
        </div>
      )}

      {followup && followup.status === 'SCHEDULED' && (
        <div className="mt-3 space-y-3">
          <p className="text-sm text-slate-600">
            {followup.is_due
              ? t('followup.due')
              : t('followup.notDue', {
                  date: new Date(followup.scheduled_for).toLocaleDateString(),
                })}
          </p>

          <div>
            <label className="block text-sm font-medium text-slate-700">
              {t('followup.condition')}
            </label>
            <select
              value={outcome}
              onChange={(e) => setOutcome(e.target.value as FollowupOutcome)}
              className="mt-1 block w-full rounded border border-slate-300 px-3 py-2 text-sm"
            >
              {OUTCOMES.map((o) => (
                <option key={o} value={o}>
                  {t(`followup.outcome.${o}`)}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700">
              {t('followup.photoOptional')}
            </label>
            <input
              type="file"
              accept="image/*"
              capture="environment"
              onChange={(e) => setImage(e.target.files?.[0] ?? null)}
              className="mt-1 block w-full text-sm"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700">
              {t('followup.notes')}
            </label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder={t('followup.notesPlaceholder')}
              rows={2}
              className="mt-1 block w-full rounded border border-slate-300 px-3 py-2 text-sm"
            />
          </div>

          {error && <ErrorState message={error} />}

          <Button onClick={() => submit.mutate(followup.id)} disabled={submit.isPending}>
            {submit.isPending ? t('followup.submitting') : t('followup.submit')}
          </Button>
        </div>
      )}
    </div>
  )
}
