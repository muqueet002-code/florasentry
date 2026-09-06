/**
 * Basic profile page: the identity fields already on the authenticated user, plus a
 * best-effort "location" - a farmer's first registered field (real coordinates, not
 * invented), or the assigned district for every other role. No new backend endpoint:
 * everything here comes from `/auth/me` (already loaded into the auth store) and the
 * existing `GET /fields` list.
 */

import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import { fieldsApi } from '@/api/endpoints/fields'
import { useAuthStore } from '@/stores/auth'
import { LoadingState } from '@/components/ui/States'

function DetailRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-slate-100 py-3 last:border-0">
      <dt className="text-sm text-slate-500">{label}</dt>
      <dd className="text-right text-sm font-medium text-slate-900">{value}</dd>
    </div>
  )
}

export function ProfilePage() {
  const { t } = useTranslation()
  const user = useAuthStore((s) => s.user)

  const fieldsQuery = useQuery({
    queryKey: ['fields', 'profile'],
    queryFn: () => fieldsApi.list(1, 1),
    enabled: user?.role === 'FARMER',
  })

  if (!user) return <LoadingState rows={3} />

  const initial = user.full_name.trim().charAt(0).toUpperCase() || '?'
  const firstField = fieldsQuery.data?.items[0]

  let location: React.ReactNode
  if (user.role === 'FARMER') {
    if (fieldsQuery.isLoading) {
      location = '…'
    } else if (firstField) {
      location = `${firstField.name} · ${firstField.latitude.toFixed(4)}, ${firstField.longitude.toFixed(4)}`
    } else {
      location = t('profile.noFieldYet')
    }
  } else {
    location = user.district_code ?? t('profile.notSet')
  }

  return (
    <div className="mx-auto max-w-lg space-y-4">
      <h1 className="text-xl font-semibold text-slate-900">{t('profile.title')}</h1>

      <div className="rounded-lg border border-slate-200 bg-white p-5">
        <div className="flex items-center gap-4">
          <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-olive text-xl font-semibold text-white">
            {initial}
          </span>
          <div className="min-w-0">
            <p className="truncate text-lg font-semibold text-slate-900">{user.full_name}</p>
            <p className="text-sm text-slate-500">
              {t(`profile.role.${user.role}`, user.role.replaceAll('_', ' '))}
            </p>
          </div>
        </div>

        <dl className="mt-5">
          <DetailRow label={t('profile.name')} value={user.full_name} />
          <DetailRow label={t('profile.phone')} value={user.phone ?? t('profile.notSet')} />
          <DetailRow label={t('profile.email')} value={user.email ?? t('profile.notSet')} />
          <DetailRow label={t('profile.location')} value={location} />
          <DetailRow
            label={t('profile.language')}
            value={t(`language.${user.preferred_language}`, user.preferred_language)}
          />
          <DetailRow
            label={t('profile.memberSince')}
            value={new Date(user.created_at).toLocaleDateString()}
          />
        </dl>
      </div>
    </div>
  )
}
