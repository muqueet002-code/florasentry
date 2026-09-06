/** Weather display (Phase 3): shows staleness/unavailability explicitly, never hides it. */

import type { WeatherOut } from '@/api/endpoints/observations'

export function WeatherCard({ weather }: { weather: WeatherOut }) {
  if (!weather.available) {
    return (
      <div className="rounded-lg border border-slate-300 bg-slate-50 p-4 text-sm text-slate-600">
        Weather unavailable{weather.unavailable_reason ? `: ${weather.unavailable_reason}` : '.'}
      </div>
    )
  }

  return (
    <div className="rounded-lg border border-sky-200 bg-sky-50 p-4">
      {weather.is_stale && (
        <p className="mb-2 text-xs font-medium text-amber-700">
          Weather data from {weather.fetched_at ? new Date(weather.fetched_at).toLocaleString() : ''} - may be outdated
        </p>
      )}
      <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
        <Metric label="Temperature" value={weather.temperature_c} unit="°C" />
        <Metric label="Humidity" value={weather.humidity_pct} unit="%" />
        <Metric label="Rainfall" value={weather.rainfall_mm} unit="mm" />
        <Metric label="Wind" value={weather.wind_speed_ms} unit="m/s" />
      </div>
      <p className="mt-2 text-xs text-slate-500">
        Source: {weather.provider}
        {weather.age_hours !== null && ` · ${weather.age_hours.toFixed(1)}h ago`}
      </p>
    </div>
  )
}

function Metric({ label, value, unit }: { label: string; value: number | null; unit: string }) {
  return (
    <div>
      <p className="text-xs text-slate-500">{label}</p>
      <p className="font-medium text-slate-900">{value !== null ? `${value}${unit}` : '—'}</p>
    </div>
  )
}
