import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { fieldsApi } from '@/api/endpoints/fields'
import { useAuthStore } from '@/stores/auth'
import { Button } from '@/components/ui/Button'

export function FarmerHome() {
  const { t } = useTranslation()
  const user = useAuthStore((s) => s.user)
  const fieldsQuery = useQuery({ queryKey: ['fields'], queryFn: () => fieldsApi.list() })

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">
          {t('dashboard.welcome', { name: user?.full_name ?? '' })}
        </h1>
        <p className="mt-1 text-sm text-slate-600">{t('dashboard.phase1Notice')}</p>
      </div>

      <div className="rounded-lg border border-slate-200 bg-white p-4">
        <p className="text-sm text-slate-500">{t('dashboard.fieldCount')}</p>
        <p className="mt-1 text-3xl font-semibold text-slate-900">
          {fieldsQuery.isLoading ? '—' : (fieldsQuery.data?.meta.pagination?.total_items ?? 0)}
        </p>
        <Link to="/app/fields" className="mt-4 inline-block">
          <Button variant="secondary">{t('nav.fields')}</Button>
        </Link>
      </div>
    </div>
  )
}
