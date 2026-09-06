/**
 * Risk display (Phase 3).
 *
 * Renders the score, level, every contributing factor, every missing factor and the
 * mandatory prototype disclaimer. Nothing here is hidden - a farmer or an expert can
 * see exactly why a score is what it is.
 */

import { useTranslation } from 'react-i18next'
import type { RiskOut } from '@/api/endpoints/observations'
import { cn } from '@/lib/cn'

const LEVEL_STYLES: Record<RiskOut['risk_level'], string> = {
  LOW: 'bg-emerald-50 border-emerald-300 text-emerald-900',
  MEDIUM: 'bg-amber-50 border-amber-300 text-amber-900',
  HIGH: 'bg-red-50 border-red-300 text-red-900',
}

export function RiskCard({ risk }: { risk: RiskOut }) {
  const { t } = useTranslation()

  return (
    <div className={cn('rounded-lg border-2 p-4', LEVEL_STYLES[risk.risk_level])}>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs font-medium tracking-wide uppercase opacity-70">Risk level</p>
          <p className="text-2xl font-bold">{risk.risk_level}</p>
        </div>
        <div className="text-right">
          <p className="text-xs font-medium tracking-wide uppercase opacity-70">Score</p>
          <p className="text-2xl font-bold tabular-nums">{risk.risk_score.toFixed(0)}/100</p>
        </div>
      </div>

      {risk.uncertainty !== null && (
        <p className="mt-2 text-xs opacity-70">
          Uncertainty: {(risk.uncertainty * 100).toFixed(0)}%
          {risk.weather_is_stale && ' - weather data is stale'}
        </p>
      )}

      {risk.contributing_factors.length > 0 && (
        <div className="mt-3">
          <p className="text-xs font-medium tracking-wide uppercase opacity-70">
            Contributing factors
          </p>
          <ul className="mt-1 space-y-1">
            {risk.contributing_factors.map((f) => (
              <li key={f.factor} className="flex items-center justify-between text-sm">
                <span>{f.factor.replaceAll('_', ' ').toLowerCase()}</span>
                <span className="tabular-nums opacity-70">+{f.contribution.toFixed(1)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {risk.missing_factors.length > 0 && (
        <div className="mt-3">
          <p className="text-xs font-medium tracking-wide uppercase opacity-70">
            Missing inputs
          </p>
          <ul className="mt-1 space-y-0.5 text-sm opacity-80">
            {risk.missing_factors.map((m) => (
              <li key={m.factor}>
                {m.factor.replaceAll('_', ' ').toLowerCase()} - {m.reason.toLowerCase()}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Mandatory: this is prototype decision-support logic, never validated science. */}
      <p className="mt-3 border-t border-current/20 pt-2 text-xs opacity-60">
        {t('risk.disclaimer', 'Prototype decision-support logic - not scientifically validated.')}
      </p>
    </div>
  )
}
