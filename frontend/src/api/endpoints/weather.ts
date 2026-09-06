/** Standalone weather binding (Phase 3's `/weather/current`), for surfaces that show
 * conditions independent of any one observation - e.g. the dashboard's weather card. */
import { apiGet } from '@/api/client'
import type { WeatherOut } from '@/api/endpoints/observations'

interface CurrentWeatherResponse {
  provider: string
  observed_at: string
  temperature_c: number | null
  humidity_pct: number | null
  rainfall_mm: number | null
  wind_speed_ms: number | null
  pressure_hpa: number | null
  is_stale: boolean
  cache_hit: boolean
  fetched_at: string | null
}

export const weatherApi = {
  /** Adapted into the same `WeatherOut` shape `WeatherCard` already renders, so the
   * dashboard reuses that component rather than a second weather widget. */
  current: async (lat: number, lon: number): Promise<WeatherOut> => {
    const w = await apiGet<CurrentWeatherResponse>('/weather/current', {
      params: { lat, lon },
    })
    return {
      available: true,
      is_stale: w.is_stale,
      provider: w.provider,
      observed_at: w.observed_at,
      temperature_c: w.temperature_c,
      humidity_pct: w.humidity_pct,
      rainfall_mm: w.rainfall_mm,
      wind_speed_ms: w.wind_speed_ms,
      fetched_at: w.fetched_at,
      age_hours: null,
      unavailable_reason: null,
    }
  },
}
