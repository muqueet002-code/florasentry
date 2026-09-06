/**
 * Route guards (TRD 13.3).
 *
 * IMPORTANT: these are UX only. They keep a user out of a screen that would fail
 * anyway. Every rule they express is enforced independently on the server - a
 * client-side guard is not a security control and must never be treated as one.
 */

import type { ReactNode } from 'react'
import { Navigate, Outlet, useLocation } from 'react-router-dom'
import type { UserRole } from '@/api/types'
import { ROLE_HOME } from '@/app/roleHome'
import { useAuthStore } from '@/stores/auth'

export function RequireAuth({ children }: { children?: ReactNode }) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated())
  const location = useLocation()

  if (!isAuthenticated) {
    // Preserve the intended destination so login can return the user to it.
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }
  return children ? <>{children}</> : <Outlet />
}

export function RequireRole({ roles, children }: { roles: UserRole[]; children?: ReactNode }) {
  const user = useAuthStore((s) => s.user)
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated())
  const location = useLocation()

  if (!isAuthenticated || !user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }
  if (!roles.includes(user.role)) {
    // Send them to their own area rather than showing a dead end.
    return <Navigate to={ROLE_HOME[user.role]} replace />
  }
  return children ? <>{children}</> : <Outlet />
}

/** `/` and `/login` when already signed in: bounce to the role's home. */
export function RedirectIfAuthenticated({ children }: { children: ReactNode }) {
  const user = useAuthStore((s) => s.user)
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated())

  if (isAuthenticated && user) return <Navigate to={ROLE_HOME[user.role]} replace />
  return <>{children}</>
}

export function RoleHomeRedirect() {
  const user = useAuthStore((s) => s.user)
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated())

  if (!isAuthenticated || !user) return <Navigate to="/login" replace />
  return <Navigate to={ROLE_HOME[user.role]} replace />
}
