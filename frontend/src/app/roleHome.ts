import type { UserRole } from '@/api/types'

/**
 * Landing route for each role: used after login and for the `/` redirect.
 *
 * Kept out of `guards.tsx` so that file exports components only, which is what
 * React Fast Refresh requires.
 */
export const ROLE_HOME: Record<UserRole, string> = {
  FARMER: '/app',
  EXTENSION_WORKER: '/expert',
  LAB_EXPERT: '/expert',
  OFFICIAL: '/official',
  ADMIN: '/admin',
}
