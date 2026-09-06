/** Expert review endpoint bindings (Phase 5). */
import { apiGet, apiGetPaginated, apiPost } from '@/api/client'
import type { ObservationOut } from '@/api/endpoints/observations'

export interface ReviewDecisionPayload {
  decision: 'CONFIRM' | 'CORRECT' | 'REJECT'
  corrected_agent_id?: string | null
  note?: string | null
}

export const reviewsApi = {
  queue: (page = 1, pageSize = 20) =>
    apiGetPaginated<ObservationOut>('/reviews/queue', { params: { page, page_size: pageSize } }),

  get: (observationId: string) => apiGet<ObservationOut>(`/reviews/${observationId}`),

  decide: (observationId: string, payload: ReviewDecisionPayload) =>
    apiPost<ObservationOut>(`/reviews/${observationId}/decision`, payload),
}
