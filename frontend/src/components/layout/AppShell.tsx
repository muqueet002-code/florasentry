/** Application shell: header, role-aware navigation, language switcher (TRD 7.3). */

import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import type { UserRole } from '@/api/types'
import { authApi } from '@/api/endpoints/auth'
import { useAuthStore } from '@/stores/auth'
import { SUPPORTED_LANGUAGES, useLanguageStore, type LanguageCode } from '@/stores/language'
import { cn } from '@/lib/cn'

interface NavItem {
  to: string
  labelKey: string
  end?: boolean
}

const NAV_BY_ROLE: Record<UserRole, NavItem[]> = {
  FARMER: [
    { to: '/app', labelKey: 'nav.home', end: true },
    { to: '/app/fields', labelKey: 'nav.fields' },
    { to: '/app/check', labelKey: 'nav.checkHealth' },
    { to: '/app/reports', labelKey: 'nav.reports' },
    { to: '/app/alerts', labelKey: 'nav.alerts' },
  ],
  EXTENSION_WORKER: [
    { to: '/expert', labelKey: 'nav.home', end: true },
    { to: '/expert/queue', labelKey: 'nav.queue' },
    { to: '/expert/map', labelKey: 'nav.map' },
  ],
  LAB_EXPERT: [
    { to: '/expert', labelKey: 'nav.home', end: true },
    { to: '/expert/queue', labelKey: 'nav.queue' },
  ],
  OFFICIAL: [
    { to: '/official', labelKey: 'nav.home', end: true },
    { to: '/official/map', labelKey: 'nav.map' },
    { to: '/official/hotspots', labelKey: 'nav.hotspots' },
    { to: '/official/trends', labelKey: 'nav.trends' },
  ],
  ADMIN: [
    { to: '/admin', labelKey: 'nav.home', end: true },
    { to: '/admin/users', labelKey: 'nav.users' },
    { to: '/admin/catalog', labelKey: 'nav.catalog' },
    { to: '/admin/data-sources', labelKey: 'nav.dataSources' },
  ],
}

function LanguageSwitcher() {
  const { t } = useTranslation()
  const { language, setLanguage } = useLanguageStore()
  return (
    <label className="flex items-center gap-1 text-sm">
      <span className="sr-only">{t('language.select')}</span>
      <select
        value={language}
        onChange={(e) => setLanguage(e.target.value as LanguageCode)}
        className="rounded border border-slate-300 bg-white px-2 py-1 text-sm"
      >
        {SUPPORTED_LANGUAGES.map((code) => (
          <option key={code} value={code}>
            {t(`language.${code}`)}
          </option>
        ))}
      </select>
    </label>
  )
}

export function AppShell() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const user = useAuthStore((s) => s.user)
  const refreshToken = useAuthStore((s) => s.refreshToken)
  const clear = useAuthStore((s) => s.clear)

  const items = user ? NAV_BY_ROLE[user.role] : []

  async function handleLogout() {
    try {
      if (refreshToken) await authApi.logout(refreshToken)
    } catch {
      // Even if the server call fails, drop the local session.
    } finally {
      clear()
      navigate('/login', { replace: true })
    }
  }

  return (
    <div className="flex min-h-full flex-col">
      {/* Phase honesty: the build states its own scope at the top of every screen. */}
      <div className="bg-amber-100 px-4 py-1.5 text-center text-xs text-amber-900">
        {t('app.phaseBanner')}
      </div>

      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3">
          <div className="flex items-center gap-2">
            <span className="text-lg font-semibold text-brand">{t('app.name')}</span>
            <span className="hidden text-xs text-slate-500 sm:inline">{t('app.tagline')}</span>
          </div>
          <div className="flex items-center gap-3">
            <LanguageSwitcher />
            {user && (
              <>
                <span className="hidden text-sm text-slate-600 sm:inline">{user.full_name}</span>
                <button
                  type="button"
                  onClick={handleLogout}
                  className="rounded border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50"
                >
                  {t('nav.logout')}
                </button>
              </>
            )}
          </div>
        </div>

        <nav className="mx-auto max-w-6xl overflow-x-auto px-4">
          <ul className="flex gap-1 pb-2">
            {items.map((item) => (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  end={item.end}
                  className={({ isActive }) =>
                    cn(
                      'block whitespace-nowrap rounded-lg px-3 py-2 text-sm font-medium',
                      isActive
                        ? 'bg-brand text-white'
                        : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900',
                    )
                  }
                >
                  {t(item.labelKey)}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
      </header>

      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6">
        <Outlet />
      </main>

      <footer className="border-t border-slate-200 bg-white px-4 py-3 text-center text-xs text-slate-500">
        FloraSentry V2 - SIH26131 - Team ASTRIX (S83)
      </footer>
    </div>
  )
}
