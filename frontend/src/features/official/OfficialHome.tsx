import { useTranslation } from 'react-i18next'
import { NotImplementedState } from '@/components/ui/States'

export function OfficialHome() {
  const { t } = useTranslation()
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-slate-900">{t('dashboard.official')}</h1>
      {/* Surveillance metrics are Phase 8; they depend on GIS (Phase 4). */}
      <NotImplementedState phase="Phase 8" />
    </div>
  )
}
