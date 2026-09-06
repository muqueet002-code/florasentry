/**
 * Advisory display (Phase 6).
 *
 * Renders section KEYS through i18n, exactly like RiskCard renders `explanation_key`
 * and the catalogue renders `name_en/hi/mr` - the wording lives in the translation
 * bundles, not here, so the same advisory record renders in en/hi/mr without a
 * second request. The tier label is always shown alongside the guidance so a farmer
 * can never mistake an unconfirmed AI assessment for expert-confirmed advice.
 */

import { useTranslation } from 'react-i18next'
import type { AdvisoryOut } from '@/api/endpoints/advisory'
import { cn } from '@/lib/cn'

const TIER_STYLES: Record<AdvisoryOut['tier'], string> = {
  confirmed: 'border-emerald-300 bg-emerald-50',
  ai_unconfirmed: 'border-amber-300 bg-amber-50',
  awaiting_review: 'border-blue-300 bg-blue-50',
  rejected: 'border-slate-300 bg-slate-50',
  unavailable: 'border-slate-300 bg-slate-50',
}

export function AdvisoryCard({ advisory }: { advisory: AdvisoryOut }) {
  const { t } = useTranslation()

  return (
    <div className={cn('rounded-lg border-2 p-4', TIER_STYLES[advisory.tier])}>
      <div className="flex items-center justify-between">
        <h2 className="font-semibold text-slate-900">🤖 {t('ai.advisory')}</h2>
        <span className="rounded-full bg-white/70 px-2 py-0.5 text-xs font-medium text-slate-700">
          {t(`advisory.tierLabel.${advisory.tier}`)}
        </span>
      </div>

      {advisory.agent_name && (
        <p className="mt-2 text-sm font-medium text-slate-800">
          {advisory.agent_name}
          {advisory.match_basis === 'PREDICTED_AGENT' && (
            <span className="ml-1 font-normal text-slate-500">
              ({t('verification.PREDICTED')})
            </span>
          )}
        </p>
      )}

      {advisory.risk_level && (
        <p className="mt-1 text-xs text-slate-600">
          {t('advisory.riskContext', { risk_level: advisory.risk_level })}
        </p>
      )}

      {advisory.sections.length > 0 ? (
        <ul className="mt-3 space-y-2">
          {advisory.sections.map((section) => (
            <li key={section.key} className="text-sm text-slate-800">
              {t(section.key, section.params)}
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-3 text-sm text-slate-600">{t('advisory.empty')}</p>
      )}

      <p className="mt-3 border-t border-current/20 pt-2 text-xs opacity-60">
        {t('advisory.disclaimer')}
      </p>
    </div>
  )
}
