/** Reference-data endpoint bindings (TRD 12.5). */
import { apiGet } from '@/api/client'
import type { Agent, Crop, GrowthStage } from '@/api/types'

export const catalogApi = {
  crops: () => apiGet<Crop[]>('/crops'),
  growthStages: (cropId: string) => apiGet<GrowthStage[]>(`/crops/${cropId}/growth-stages`),
  agents: (params?: { kind?: string; is_ai_supported?: boolean }) =>
    apiGet<Agent[]>('/catalog/agents', { params }),
  roles: () => apiGet<Array<{ role: string; permissions: string[] }>>('/roles'),
}
