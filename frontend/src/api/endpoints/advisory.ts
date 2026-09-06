/** Advisory endpoint binding (Phase 6). */
import { apiGet } from '@/api/client'

export interface AdvisorySection {
  key: string
  params: Record<string, unknown>
}

export interface AdvisoryOut {
  observation_id: string
  verification_status: string
  tier: 'confirmed' | 'ai_unconfirmed' | 'awaiting_review' | 'rejected' | 'unavailable'
  agent_code: string | null
  agent_name: string | null
  match_basis: 'CONFIRMED_AGENT' | 'PREDICTED_AGENT' | 'NONE'
  confidence: number | null
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH' | null
  sections: AdvisorySection[]
  method: string
  ruleset_version: string
  disclaimer_key: string
  language: string
}

export const advisoryApi = {
  get: (observationId: string, lang?: string) =>
    apiGet<AdvisoryOut>(`/observations/${observationId}/advisory`, {
      params: lang ? { lang } : undefined,
    }),
}
