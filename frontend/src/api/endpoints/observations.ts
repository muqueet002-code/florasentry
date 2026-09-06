/** Observation endpoint bindings (Phase 2 + 3). */
import { apiGet, apiGetPaginated, http } from '@/api/client'
import type { SuccessEnvelope } from '@/api/types'

export interface ObservationCreatePayload {
  latitude: number
  longitude: number
  field_id?: string | null
  crop_id?: string | null
  variety_id?: string | null
  growth_stage_id?: string | null
  observation_type?: 'IMAGE' | 'MANUAL_REPORT'
  reported_severity?: number | null
  notes?: string | null
}

export interface PredictionOut {
  predicted_class: string
  agent_id: string | null
  confidence: number
  is_low_confidence: boolean
  top_k: Array<{ class: string; confidence: number }> | null
  model_version: string
  inference_ms: number | null
}

export interface WeatherOut {
  available: boolean
  is_stale: boolean
  provider: string
  observed_at: string | null
  temperature_c: number | null
  humidity_pct: number | null
  rainfall_mm: number | null
  wind_speed_ms: number | null
  fetched_at: string | null
  age_hours: number | null
  unavailable_reason: string | null
}

export interface RiskFactor {
  factor: string
  value: unknown
  weight: number
  contribution: number
  explanation_key: string
}

export interface RiskOut {
  risk_score: number
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH'
  contributing_factors: RiskFactor[]
  missing_factors: Array<{ factor: string; reason: string }>
  explanation_key: string
  uncertainty: number | null
  method: string
  ruleset_version: string
  weather_is_stale: boolean
  disclaimer_key: string
}

export interface ObservationOut {
  id: string
  status: string
  verification_status: string
  latitude: number
  longitude: number
  observed_at: string
  reported_severity: number | null
  notes: string | null
  final_agent_id: string | null
  crop_id: string | null
  field_id: string | null
  image: { id: string; url: string; thumbnail_url: string | null } | null
  prediction: PredictionOut | null
  weather: WeatherOut | null
  risk: RiskOut | null
  processing_errors: Record<string, { code: string; reason: string }> | null
  provenance: { source_type: string; created_at: string; model_version: string | null }
}

export interface ObservationCreateResult {
  success: true
  data: ObservationOut
  warnings?: Array<{ code: string; message_key: string; detail?: Record<string, unknown> }>
}

export const observationsApi = {
  /** multipart create: payload (JSON) + optional image file. */
  create: async (
    payload: ObservationCreatePayload,
    image: File | null,
  ): Promise<ObservationCreateResult> => {
    const form = new FormData()
    form.append('payload', JSON.stringify(payload))
    if (image) form.append('image', image)
    const { data } = await http.post<SuccessEnvelope<ObservationOut>>('/observations', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return { success: true, data: data.data, warnings: data.warnings }
  },

  get: (id: string) => apiGet<ObservationOut>(`/observations/${id}`),

  list: (page = 1, pageSize = 20) =>
    apiGetPaginated<ObservationOut>('/observations', { params: { page, page_size: pageSize } }),
}
