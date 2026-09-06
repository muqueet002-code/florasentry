import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { catalogApi } from '@/api/endpoints/catalog'
import { LoadingState } from '@/components/ui/States'

/** Phase 1 admin view: the live RBAC matrix, served from the backend. Real data. */
export function AdminHome() {
  const { t } = useTranslation()
  const rolesQuery = useQuery({ queryKey: ['roles'], queryFn: catalogApi.roles })

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-slate-900">{t('dashboard.admin')}</h1>
      {rolesQuery.isLoading && <LoadingState rows={2} />}
      {rolesQuery.isSuccess && (
        <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-50 text-left">
              <tr>
                <th className="px-4 py-2 font-medium text-slate-700">Role</th>
                <th className="px-4 py-2 font-medium text-slate-700">Permissions</th>
              </tr>
            </thead>
            <tbody>
              {rolesQuery.data.map((row) => (
                <tr key={row.role} className="border-t border-slate-100 align-top">
                  <td className="px-4 py-2 font-medium whitespace-nowrap">{row.role}</td>
                  <td className="px-4 py-2 text-slate-600">{row.permissions.join(', ')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
