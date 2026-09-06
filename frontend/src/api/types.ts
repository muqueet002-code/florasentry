/**
 * Shared API types (TRD 11).
 *
 * These mirror the backend envelope. Phase 9 should replace the hand-written parts
 * with types generated from the backend's OpenAPI schema (`openapi-typescript`), so
 * contract drift becomes a build error rather than a runtime surprise.
 */

export type UserRole = 'FARMER' | 'EXTENSION_WORKER' | 'LAB_EXPERT' | 'OFFICIAL' | 'ADMIN'

/** Provenance: where a record came from (TRD 10.1). */
export type SourceType =
  | 'FIELD_OBSERVATION'
  | 'PUBLIC_DATA'
  | 'GOVERNMENT_DATA'
  | 'EXPERT_VALIDATION'
  | 'DEMO_SIMULATION'

/** Truth state. Distinct from pipeline status - never merge the two (TRD 20.2). */
export type VerificationStatus =
  | 'PREDICTED'
  | 'PENDING_REVIEW'
  | 'CONFIRMED'
  | 'CORRECTED'
  | 'REJECTED'
  | 'LAB_REFERRED'

/** GeoJSON Polygon, as sent to and received from the API (SRID 4326, lon/lat order). */
export interface GeoJsonPolygon {
  type: 'Polygon'
  coordinates: number[][][]
}

export interface Pagination {
  page: number
  page_size: number
  total_items: number
  total_pages: number
}

export interface ResponseMeta {
  trace_id: string
  timestamp: string
  pagination?: Pagination
  filters_applied?: Record<string, unknown>
  truncated?: boolean
}

/** A degraded-success warning. NOT an error - the request succeeded (TRD 11.5). */
export interface ApiWarning {
  code: string
  message_key: string
  detail?: Record<string, unknown>
}

export interface SuccessEnvelope<T> {
  success: true
  data: T
  meta: ResponseMeta
  warnings?: ApiWarning[]
}

export interface ErrorEnvelope {
  success: false
  error: {
    code: string
    message: string
    message_key: string
    details: Array<Record<string, unknown>>
    retriable: boolean
  }
  meta: ResponseMeta
}

/** Present on every provenance-bearing record. Required, never optional. */
export interface Provenance {
  source_type: SourceType
  created_by: string | null
  created_at: string
  verified_by?: string | null
  verified_at?: string | null
  model_version?: string | null
  original_source_ref?: string | null
}

export interface User {
  id: string
  full_name: string
  phone: string | null
  email: string | null
  username: string | null
  role: UserRole
  preferred_language: string
  district_code: string | null
  is_active: boolean
  created_at: string
}

export interface TokenPair {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

export interface Field {
  id: string
  farmer_id: string
  name: string
  latitude: number
  longitude: number
  boundary: GeoJsonPolygon | null
  area_ha: number | null
  soil_type: string | null
  irrigation_type: string | null
  district_code: string | null
  current_crop_id: string | null
  current_variety_id: string | null
  sowing_date: string | null
  provenance: Provenance
}

export interface Crop {
  id: string
  code: string
  name: string
  scientific_name: string | null
  available_languages: string[]
}

export interface GrowthStage {
  id: string
  crop_id: string
  code: string
  name: string
  sequence: number
}

export interface Agent {
  id: string
  code: string
  kind: 'DISEASE' | 'PEST' | 'DISORDER' | 'HEALTHY' | 'UNKNOWN'
  name: string
  scientific_name: string | null
  /** False for every entry in Phase 1: no model is registered. */
  is_ai_supported: boolean
}

