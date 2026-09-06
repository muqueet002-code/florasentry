import { useTranslation } from 'react-i18next'
import { NotImplementedState } from '@/components/ui/States'

export function ExpertHome() {
  const { t } = useTranslation()
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-slate-900">{t('dashboard.expert')}</h1>
      {/* The review queue is Phase 5. Nothing is shown until it exists. */}
      <NotImplementedState phase="Phase 5" />
    </div>
  )
}
