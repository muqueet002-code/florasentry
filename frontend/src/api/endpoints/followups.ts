/** Follow-up endpoint bindings (Phase 7). */
import { apiGet, apiGetPaginated, apiPost, http } from '@/api/client'
import type { ObservationOut } from '@/api/endpoints/observations'
import type { SuccessEnvelope } from '@/api/types'

export type FollowupOutcome = 'IMPROVED' | 'UNCHANGED' | 'WORSENED' | 'RESOLVED' | 'NEEDS_EXPERT_REVIEW'
export type FollowupStatus = 'SCHEDULED' | 'SUBMITTED'

export interface FollowupOut {
  id: string
  parent_observation_id: string
  followup_observation_id: string | null
  scheduled_for: string
  status: FollowupStatus
  is_due: boolean
  outcome: FollowupOutcome | null
  notes: string | null
  submitted_at: string | null
  created_at: string
  linked_observation: ObservationOut | null
}

export const followupsApi = {
  create: (observationId: string, scheduledFor?: string) =>
    apiPost<FollowupOut>('/followups', {
      observation_id: observationId,
      scheduled_for: scheduledFor ?? null,
    }),

  get: (id: string) => apiGet<FollowupOut>(`/followups/${id}`),

  listForObservation: (observationId: string) =>
    apiGetPaginated<FollowupOut>('/followups', { params: { observation_id: observationId } }),

  listByOutcome: (outcome: FollowupOutcome) =>
    apiGetPaginated<FollowupOut>('/followups', { params: { outcome } }),

  submit: async (
    id: string,
    payload: { outcome: FollowupOutcome; notes?: string | null },
    image: File | null,
  ): Promise<FollowupOut> => {
    const form = new FormData()
    form.append('payload', JSON.stringify(payload))
    if (image) form.append('image', image)
    const { data } = await http.post<SuccessEnvelope<FollowupOut>>(
      `/followups/${id}/submit`,
      form,
      { headers: { 'Content-Type': 'multipart/form-data' } },
    )
    return data.data
  },
}
