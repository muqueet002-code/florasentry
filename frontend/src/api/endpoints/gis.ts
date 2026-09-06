/** GIS map and hotspot endpoint bindings (Phase 4). */
import { apiGet } from '@/api/client'

export interface ObservationFeatureProperties {
  id: string
  source_type: string
  verification_status: string
  crop_code: string | null
  crop_name: string | null
  agent_code: string | null
  agent_name: string | null
  match_basis: 'CONFIRMED_AGENT' | 'PREDICTED_AGENT' | 'NONE'
  confidence: number | null
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH' | null
  risk_score: number | null
  reported_severity: number | null
  observed_at: string
}

export interface ObservationFeature {
  type: 'Feature'
  geometry: { type: 'Point'; coordinates: [number, number] }
  properties: ObservationFeatureProperties
}

export interface ObservationFeatureCollection {
  type: 'FeatureCollection'
  features: ObservationFeature[]
}

export interface Hotspot {
  cluster_id: number
  hotspot_type: 'CONFIRMED' | 'SIGNAL' | 'PREDICTED'
  label: string
  centroid: { latitude: number; longitude: number }
  radius_m: number
  observation_count: number
  confirmed_count: number
  predicted_count: number
  dominant_agent_code: string | null
  dominant_agent_name: string | null
  avg_severity: number | null
  includes_demo_data: boolean
  observation_ids: string[]
  disclaimer_key: string
}

export interface GisObservationFilters {
  bbox?: string
  crop_id?: string
  agent_id?: string
  verification_status?: string
  risk_level?: string
  from?: string
  to?: string
  include_demo?: boolean
}

export const gisApi = {
  observations: (filters: GisObservationFilters = {}) =>
    apiGet<ObservationFeatureCollection>('/gis/observations', { params: filters }),

  hotspots: (
    filters: {
      bbox?: string
      radius_m?: number
      min_points?: number
      window_days?: number
      agent_id?: string
      crop_id?: string
      include_demo?: boolean
    } = {},
  ) => apiGet<Hotspot[]>('/gis/hotspots', { params: filters }),
}
