/**
 * Authentication state (TRD 7.4, 13.4).
 *
 * IMPLEMENTATION DECISION - refresh-token storage.
 * TRD 13.4 records this as REQUIRES DECISION with two options: (a) an httpOnly cookie,
 * or (b) localStorage. Phase 1 implements (b) because it needs no cookie/CSRF plumbing
 * and works across origins during development.
 *
 * The tradeoff is stated rather than hidden: a refresh token in localStorage is
 * readable by any injected script. Option (a) is the recommendation for anything
 * beyond the demo. Everything needed to switch lives in this one file plus the
 * client's refresh call - no component reads the token directly.
 */

import { create } from 'zustand'
import { configureApiClient } from '@/api/client'
import type { User, UserRole } from '@/api/types'

const ACCESS_KEY = 'florasentry.access_token'
const REFRESH_KEY = 'florasentry.refresh_token'
const USER_KEY = 'florasentry.user'

function readStored<T>(key: string): T | null {
  try {
    const raw = localStorage.getItem(key)
    return raw ? (JSON.parse(raw) as T) : null
  } catch {
    // Private browsing or blocked site data: degrade to an unauthenticated session
    // rather than crashing the app on boot.
    return null
  }
}

function writeStored(key: string, value: unknown): void {
  try {
    if (value === null || value === undefined) localStorage.removeItem(key)
    else localStorage.setItem(key, JSON.stringify(value))
  } catch {
    /* storage unavailable - the session simply will not survive a reload */
  }
}

interface AuthState {
  user: User | null
  accessToken: string | null
  refreshToken: string | null
  permissions: string[]
  isHydrated: boolean

  setSession: (user: User, accessToken: string, refreshToken: string) => void
  setUser: (user: User, permissions: string[]) => void
  updateTokens: (accessToken: string, refreshToken: string) => void
  clear: () => void

  isAuthenticated: () => boolean
  hasRole: (...roles: UserRole[]) => boolean
  can: (permission: string) => boolean
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: readStored<User>(USER_KEY),
  accessToken: readStored<string>(ACCESS_KEY),
  refreshToken: readStored<string>(REFRESH_KEY),
  permissions: [],
  isHydrated: true,

  setSession: (user, accessToken, refreshToken) => {
    writeStored(USER_KEY, user)
    writeStored(ACCESS_KEY, accessToken)
    writeStored(REFRESH_KEY, refreshToken)
    set({ user, accessToken, refreshToken })
  },

  setUser: (user, permissions) => {
    writeStored(USER_KEY, user)
    set({ user, permissions })
  },

  updateTokens: (accessToken, refreshToken) => {
    writeStored(ACCESS_KEY, accessToken)
    writeStored(REFRESH_KEY, refreshToken)
    set({ accessToken, refreshToken })
  },

  clear: () => {
    writeStored(USER_KEY, null)
    writeStored(ACCESS_KEY, null)
    writeStored(REFRESH_KEY, null)
    set({ user: null, accessToken: null, refreshToken: null, permissions: [] })
  },

  isAuthenticated: () => Boolean(get().accessToken && get().user),
  hasRole: (...roles) => {
    const role = get().user?.role
    return role ? roles.includes(role) : false
  },
  // Client-side permission checks drive UI affordances ONLY. Every rule is
  // independently enforced server-side - a client guard is not a security control.
  can: (permission) => get().permissions.includes(permission),
}))

// Bridge the store into the API client without the client importing the store.
configureApiClient({
  getAccessToken: () => useAuthStore.getState().accessToken,
  getRefreshToken: () => useAuthStore.getState().refreshToken,
  onRefreshed: (accessToken, refreshToken) =>
    useAuthStore.getState().updateTokens(accessToken, refreshToken),
  onAuthFailure: () => useAuthStore.getState().clear(),
})
