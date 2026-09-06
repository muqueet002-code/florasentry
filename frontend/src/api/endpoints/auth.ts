/** Authentication endpoint bindings (TRD 12.1). */
import { apiGet, apiPost } from '@/api/client'
import type { TokenPair, User } from '@/api/types'

export interface LoginPayload {
  identifier: string
  password: string
}

export interface RegisterPayload {
  full_name: string
  phone: string
  password: string
  preferred_language?: string
  village?: string | null
  taluka?: string | null
}

export type LoginResponse = TokenPair & { user: User }

export const authApi = {
  login: (payload: LoginPayload) => apiPost<LoginResponse>('/auth/login', payload),

  register: (payload: RegisterPayload) =>
    apiPost<{ user: User; tokens: TokenPair }>('/auth/register', payload),

  me: () => apiGet<{ user: User; farmer_id: string | null; permissions: string[] }>('/auth/me'),

  logout: (refreshToken: string) => apiPost<void>('/auth/logout', { refresh_token: refreshToken }),

  changePassword: (currentPassword: string, newPassword: string) =>
    apiPost<{ changed: boolean }>('/auth/change-password', {
      current_password: currentPassword,
      new_password: newPassword,
    }),
}
