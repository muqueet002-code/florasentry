/**
 * Application shell: hamburger-triggered navigation drawer, top bar, language
 * switcher (TRD 7.3).
 *
 * There is no persistent sidebar rail: the drawer is an overlay at every breakpoint,
 * opened and closed by the same menu button (click again, or click the backdrop, to
 * close). On the farmer dashboard the header floats transparently over the hero
 * image instead of sitting in a solid white bar, so the photo reaches the very top of
 * the page; every other screen keeps the plain white header untouched.
 */

import { useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import type { UserRole } from '@/api/types'
import { authApi } from '@/api/endpoints/auth'
import { useAuthStore } from '@/stores/auth'
import { SUPPORTED_LANGUAGES, useLanguageStore, type LanguageCode } from '@/stores/language'
import { cn } from '@/lib/cn'

interface NavItem {
  to: string
  labelKey: string
  icon: string
  end?: boolean
}

const NAV_BY_ROLE: Record<UserRole, NavItem[]> = {
  FARMER: [
    { to: '/app', labelKey: 'nav.home', icon: '🏠', end: true },
    { to: '/app/check', labelKey: 'nav.checkHealth', icon: '➕' },
    { to: '/app/observations', labelKey: 'nav.myObservations', icon: '📋' },
    { to: '/app/fields', labelKey: 'nav.fields', icon: '🌾' },
    { to: '/app/map', labelKey: 'nav.map', icon: '🗺️' },
  ],
  EXTENSION_WORKER: [
    { to: '/expert', labelKey: 'nav.home', icon: '🏠', end: true },
    { to: '/expert/queue', labelKey: 'nav.queue', icon: '🔍' },
    { to: '/expert/map', labelKey: 'nav.map', icon: '🗺️' },
  ],
  LAB_EXPERT: [
    { to: '/expert', labelKey: 'nav.home', icon: '🏠', end: true },
    { to: '/expert/queue', labelKey: 'nav.queue', icon: '🔍' },
  ],
  OFFICIAL: [
    { to: '/official', labelKey: 'nav.home', icon: '🏠', end: true },
    { to: '/official/map', labelKey: 'nav.map', icon: '🗺️' },
    { to: '/official/hotspots', labelKey: 'nav.hotspots', icon: '📍' },
    { to: '/official/trends', labelKey: 'nav.trends', icon: '📈' },
  ],
  ADMIN: [
    { to: '/admin', labelKey: 'nav.home', icon: '🏠', end: true },
    { to: '/admin/users', labelKey: 'nav.users', icon: '👥' },
    { to: '/admin/catalog', labelKey: 'nav.catalog', icon: '📚' },
    { to: '/admin/data-sources', labelKey: 'nav.dataSources', icon: '🗄️' },
  ],
}

/** Each role's profile page lives under its own route prefix (same pattern as
 * `ROLE_HOME`), so the one shared `ProfilePage` component is reachable from every
 * role without a top-level route that would fall outside every `RequireRole` guard. */
const PROFILE_PATH: Record<UserRole, string> = {
  FARMER: '/app/profile',
  EXTENSION_WORKER: '/expert/profile',
  LAB_EXPERT: '/expert/profile',
  OFFICIAL: '/official/profile',
  ADMIN: '/admin/profile',
}

function LanguageSwitcher({ transparent = false }: { transparent?: boolean }) {
  const { t } = useTranslation()
  const { language, setLanguage } = useLanguageStore()
  return (
    <label className="flex items-center gap-1 text-sm">
      <span className="sr-only">{t('language.select')}</span>
      {/* The closed control is transparent (icon-like, blends into whatever's behind
          it); the dropdown's own option list stays the browser's native opaque
          rendering - that part can't be (and doesn't need to be) transparent. */}
      <select
        value={language}
        onChange={(e) => setLanguage(e.target.value as LanguageCode)}
        className={cn(
          'rounded-lg border bg-transparent px-2 py-1.5 text-sm',
          transparent
            ? 'border-white/50 text-white [color-scheme:dark]'
            : 'border-slate-300 text-slate-700',
        )}
      >
        {SUPPORTED_LANGUAGES.map((code) => (
          <option key={code} value={code} className="text-slate-900">
            {t(`language.${code}`)}
          </option>
        ))}
      </select>
    </label>
  )
}

/** The drawer's contents - always rendered at full width/labels, since it is only
 * ever shown as an overlay now, never as a persistent collapsed rail. */
function DrawerContent({ items, onClose }: { items: NavItem[]; onClose: () => void }) {
  const { t } = useTranslation()
  return (
    <div className="flex h-full flex-col bg-olive text-white">
      <div className="flex items-center justify-between gap-2 border-b border-white/10 px-4 py-4">
        <div className="min-w-0">
          <p className="flex items-center gap-2 text-lg font-semibold">🌿 {t('app.name')}</p>
          <p className="mt-0.5 truncate text-xs text-white/70">{t('app.tagline')}</p>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label={t('nav.closeMenu')}
          className="rounded-lg px-2.5 py-1.5 text-white/80 transition-colors hover:bg-olive-light hover:text-white"
        >
          ✕
        </button>
      </div>

      <nav className="flex-1 overflow-y-auto p-3">
        <ul className="space-y-1">
          {items.map((item) => (
            <li key={item.to}>
              <NavLink
                to={item.to}
                end={item.end}
                onClick={onClose}
                className={({ isActive }) =>
                  cn(
                    'flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors',
                    isActive
                      ? 'bg-white text-olive-dark shadow-sm'
                      : 'text-white/85 hover:bg-olive-light hover:text-white',
                  )
                }
              >
                <span aria-hidden>{item.icon}</span>
                <span className="truncate">{t(item.labelKey)}</span>
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>

      <div className="border-t border-white/10 px-4 py-3 text-xs text-white/60">
        SIH26131 · Team ASTRIX (S83)
      </div>
    </div>
  )
}

/** Compact profile control: identity + role, with sign-out inside rather than a bare
 * button in the bar. No new route - the app has no profile screen to link to yet.
 * Kept on a translucent white pill regardless of what's behind it, so it reads
 * equally well on the plain header and floating over the hero photo. */
function ProfileMenu({
  name,
  role,
  onLogout,
}: {
  name: string
  role: string
  onLogout: () => void
}) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const initial = name.trim().charAt(0).toUpperCase() || '?'

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        className="flex items-center gap-2 rounded-full border border-slate-300 bg-white/95 py-1 pr-3 pl-1 shadow-sm backdrop-blur-sm hover:bg-white"
      >
        <span className="flex h-7 w-7 items-center justify-center rounded-full bg-olive text-sm font-semibold text-white">
          {initial}
        </span>
        <span className="hidden max-w-32 truncate text-sm text-slate-700 sm:inline">{name}</span>
      </button>

      {open && (
        <>
          <button
            type="button"
            aria-label="Close profile menu"
            className="fixed inset-0 z-10 cursor-default"
            onClick={() => setOpen(false)}
          />
          <div
            role="menu"
            className="absolute right-0 z-20 mt-2 w-56 rounded-lg border border-slate-200 bg-white p-2 shadow-lg"
          >
            <div className="border-b border-slate-100 px-3 py-2">
              <p className="truncate text-sm font-medium text-slate-900">{name}</p>
              <p className="text-xs text-slate-500">{role.replaceAll('_', ' ').toLowerCase()}</p>
            </div>
            <button
              type="button"
              onClick={onLogout}
              className="mt-1 w-full rounded px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-50"
            >
              {t('nav.logout')}
            </button>
          </div>
        </>
      )}
    </div>
  )
}

export function AppShell() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const location = useLocation()
  const user = useAuthStore((s) => s.user)
  const refreshToken = useAuthStore((s) => s.refreshToken)
  const clear = useAuthStore((s) => s.clear)
  const [drawerOpen, setDrawerOpen] = useState(false)

  const items = user ? NAV_BY_ROLE[user.role] : []
  // Quick jumps mirrored into the top bar so the two screens a farmer bounces
  // between stay one click away without opening the drawer.
  const quickLinks = items.filter((i) =>
    ['nav.map', 'nav.myObservations', 'nav.queue', 'nav.hotspots'].includes(i.labelKey),
  )

  // Only the farmer dashboard's own index route carries a hero photo; every other
  // screen (including every other farmer page) keeps the normal solid header.
  const isHeroPage = location.pathname === '/app'

  // Each screen gets a real tab title (SIH demo polish) rather than a static
  // "FloraSentry" everywhere - the nav item whose path is the longest prefix
  // match of the current URL is the current screen.
  useEffect(() => {
    const roleItems = user ? NAV_BY_ROLE[user.role] : []
    const current = [...roleItems]
      .sort((a, b) => b.to.length - a.to.length)
      .find((item) => location.pathname.startsWith(item.to))
    document.title = current ? `${t(current.labelKey)} - ${t('app.name')}` : t('app.name')
  }, [location.pathname, user, t])

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
    <div className="relative flex min-h-screen flex-col">
      {/* Navigation drawer - an overlay at every breakpoint. The same button that
          opened it closes it; so does the backdrop. */}
      {drawerOpen && (
        <div className="fixed inset-0 z-40">
          <button
            type="button"
            aria-label={t('nav.closeMenu')}
            className="absolute inset-0 bg-black/40"
            onClick={() => setDrawerOpen(false)}
          />
          <div className="absolute top-0 bottom-0 left-0 w-72 max-w-[85vw] shadow-xl">
            <DrawerContent items={items} onClose={() => setDrawerOpen(false)} />
          </div>
        </div>
      )}

      <header
        className={cn(
          'z-20 w-full',
          isHeroPage
            ? 'absolute inset-x-0 top-0 bg-transparent'
            : 'relative border-b border-slate-200 bg-white',
        )}
      >
        <div className="flex items-center justify-between gap-3 px-4 py-2.5">
          {/* Left: menu toggle + product mark */}
          <div className="flex min-w-0 items-center gap-2">
            <button
              type="button"
              onClick={() => setDrawerOpen((v) => !v)}
              aria-label={drawerOpen ? t('nav.closeMenu') : t('nav.openMenu')}
              aria-expanded={drawerOpen}
              className="rounded-lg border border-slate-300 bg-white/95 px-2.5 py-1.5 text-sm shadow-sm backdrop-blur-sm hover:bg-white"
            >
              ☰
            </button>
            <Link to="/" className="flex min-w-0 items-center gap-2">
              <span className="text-xl" aria-hidden>
                🌿
              </span>
              <span
                className={cn(
                  'truncate font-semibold',
                  isHeroPage ? 'text-white drop-shadow-md' : 'text-brand',
                )}
              >
                {t('app.name')}
              </span>
            </Link>
          </div>

          {/* Middle: quick jumps */}
          <nav className="flex items-center gap-1">
            {quickLinks.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                title={t(item.labelKey)}
                className={({ isActive }) =>
                  cn(
                    'flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-sm transition-colors',
                    isHeroPage
                      ? isActive
                        ? 'border-white bg-white/25 text-white'
                        : 'border-white/50 text-white/90 backdrop-blur-sm hover:bg-white/15'
                      : isActive
                        ? 'border-brand bg-emerald-50 text-brand-dark'
                        : 'border-slate-200 text-slate-600 hover:bg-slate-50',
                  )
                }
              >
                <span aria-hidden>{item.icon}</span>
                <span className="hidden lg:inline">{t(item.labelKey)}</span>
              </NavLink>
            ))}
          </nav>

          {/* Right: language + profile */}
          <div className="flex items-center gap-2">
            <LanguageSwitcher />
            {user && (
              <ProfileMenu
                name={user.full_name}
                role={user.role}
                onLogout={() => void handleLogout()}
              />
            )}
          </div>
        </div>
      </header>

      <main className={cn('w-full min-w-0 flex-1', isHeroPage ? '' : 'px-4 py-6')}>
        <div className={cn(isHeroPage ? '' : 'mx-auto w-full max-w-6xl')}>
          <Outlet />
        </div>
      </main>

      <footer className="border-t border-slate-200 bg-white px-4 py-3 text-center text-xs text-slate-500">
        FloraSentry · {t('app.tagline')}
      </footer>
    </div>
  )
}
