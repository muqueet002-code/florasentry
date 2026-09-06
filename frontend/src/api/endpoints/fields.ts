/** Field endpoint bindings (TRD 12.4). */
import { apiDelete, apiGetPaginated, apiGet, apiPatch, apiPost } from '@/api/client'
import type { Field } from '@/api/types'

export interface FieldCreatePayload {
  name: string
  latitude: number
  longitude: number
  area_ha?: number | null
  soil_type?: string | null
  irrigation_type?: string | null
  current_crop_id?: string | null
  sowing_date?: string | null
}

export const fieldsApi = {
  list: (page = 1, pageSize = 20) =>
    apiGetPaginated<Field>('/fields', { params: { page, page_size: pageSize } }),
  get: (id: string) => apiGet<Field>(`/fields/${id}`),
  create: (payload: FieldCreatePayload) => apiPost<Field>('/fields', payload),
  update: (id: string, payload: Partial<FieldCreatePayload>) =>
    apiPatch<Field>(`/fields/${id}`, payload),
  remove: (id: string) => apiDelete(`/fields/${id}`),
}
