/**
 * Placeholder screen for a module that ships in a later phase.
 *
 * It renders the phase it is waiting for and NOTHING ELSE. No fake charts, no sample
 * rows, no mock numbers. A screen that shows plausible-looking data it did not compute
 * is worse than a screen that admits it is empty.
 */
import { useTranslation } from 'react-i18next'
import { NotImplementedState } from '@/components/ui/States'

export function PlannedPage({ titleKey, phase }: { titleKey: string; phase: string }) {
  const { t } = useTranslation()
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-slate-900">{t(titleKey)}</h1>
      <NotImplementedState phase={phase} />
    </div>
  )
}
