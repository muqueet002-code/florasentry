/**
 * API client (TRD 7.5).
 *
 * One axios instance with three responsibilities:
 *   1. attach the bearer token and the negotiated language;
 *   2. unwrap the success envelope, and convert the error envelope into a typed
 *      ApiError the UI can localise via `message_key`;
 *   3. a single-flight 401 handler that refreshes once and replays queued requests.
 */

import axios, {
  AxiosError,
  type AxiosInstance,
  type AxiosRequestConfig,
  type InternalAxiosRequestConfig,
} from 'axios'
import type { ApiWarning, ErrorEnvelope, SuccessEnvelope } from './types'

export const API_BASE_URL: string =
  import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1'

/** Absolute URL for a server-rooted path the API hands back (e.g. an image's
 * `/api/v1/images/{id}`). `API_BASE_URL` already carries the `/api/v1` prefix, so
 * concatenating the two directly would double it - strip the path part and keep the
 * origin. */
export function serverUrl(path: string): string {
  try {
    return new URL(path, API_BASE_URL).href
  } catch {
    return path
  }
}

/** Typed error carrying the backend's machine-readable code and localisation key. */
export class ApiError extends Error {
  // Declared as fields rather than constructor parameter properties: the project
  // builds with `erasableSyntaxOnly`, which forbids the parameter-property shorthand.
  readonly code: string
  readonly messageKey: string
  readonly details: Array<Record<string, unknown>>
  readonly retriable: boolean
  readonly status: number
  readonly traceId?: string

  constructor(
    code: string,
    message: string,
    messageKey: string,
    details: Array<Record<string, unknown>> = [],
    retriable = false,
    status = 0,
    traceId?: string,
  ) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.messageKey = messageKey
    this.details = details
    this.retriable = retriable
    this.status = status
    this.traceId = traceId
  }

  /** A route boundary for a module that ships in a later phase (HTTP 501). */
  get isNotImplemented(): boolean {
    return this.code === 'NOT_IMPLEMENTED'
  }

  get plannedPhase(): string | null {
    const detail = this.details[0] as { planned_phase?: string } | undefined
    return detail?.planned_phase ?? null
  }
}

/** Warnings from the most recent call, so a screen can render degraded state. */
let lastWarnings: ApiWarning[] = []
export const getLastWarnings = (): ApiWarning[] => lastWarnings

type TokenAccessors = {
  getAccessToken: () => string | null
  getRefreshToken: () => string | null
  onRefreshed: (accessToken: string, refreshToken: string) => void
  onAuthFailure: () => void
  getLanguage: () => string
}

// Wired up by the auth store at module init, which keeps the client free of a
// direct dependency on the store (and therefore easy to test).
let tokens: TokenAccessors = {
  getAccessToken: () => null,
  getRefreshToken: () => null,
  onRefreshed: () => {},
  onAuthFailure: () => {},
  getLanguage: () => 'en',
}

export function configureApiClient(accessors: Partial<TokenAccessors>): void {
  tokens = { ...tokens, ...accessors }
}

export const http: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 20000,
  headers: { 'Content-Type': 'application/json' },
})

http.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = tokens.getAccessToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  config.headers['Accept-Language'] = tokens.getLanguage()
  return config
})

// --- single-flight refresh ---------------------------------------------------
let refreshPromise: Promise<string> | null = null

async function refreshAccessToken(): Promise<string> {
  const refreshToken = tokens.getRefreshToken()
  if (!refreshToken) throw new Error('no refresh token')

  // A bare axios call, not `http`: using the instance would recurse through this
  // same interceptor if the refresh itself 401s.
  const response = await axios.post<SuccessEnvelope<{
    access_token: string
    refresh_token: string
  }>>(`${API_BASE_URL}/auth/refresh`, { refresh_token: refreshToken })

  const { access_token, refresh_token } = response.data.data
  tokens.onRefreshed(access_token, refresh_token)
  return access_token
}

http.interceptors.response.use(
  (response) => {
    lastWarnings = (response.data as SuccessEnvelope<unknown>)?.warnings ?? []
    return response
  },
  async (error: AxiosError<ErrorEnvelope>) => {
    const original = error.config as (AxiosRequestConfig & { _retried?: boolean }) | undefined
    const envelope = error.response?.data
    const code = envelope?.error?.code

    // Expired access token: refresh once, then replay. Any other 401 is terminal.
    if (
      error.response?.status === 401 &&
      code === 'AUTH_TOKEN_EXPIRED' &&
      original &&
      !original._retried &&
      tokens.getRefreshToken()
    ) {
      original._retried = true
      try {
        refreshPromise = refreshPromise ?? refreshAccessToken()
        const newToken = await refreshPromise
        refreshPromise = null
        original.headers = { ...original.headers, Authorization: `Bearer ${newToken}` }
        return http.request(original)
      } catch {
        refreshPromise = null
        tokens.onAuthFailure()
      }
    }

    if (error.response?.status === 401 && code !== 'AUTH_INVALID_CREDENTIALS') {
      tokens.onAuthFailure()
    }

    if (envelope?.error) {
      throw new ApiError(
        envelope.error.code,
        envelope.error.message,
        envelope.error.message_key,
        envelope.error.details,
        envelope.error.retriable,
        error.response?.status ?? 0,
        envelope.meta?.trace_id,
      )
    }

    // No envelope: the server is unreachable or returned a non-JSON body.
    throw new ApiError(
      'NETWORK_ERROR',
      error.message || 'Could not reach the server.',
      'errors.network',
      [],
      true,
      error.response?.status ?? 0,
    )
  },
)

/** Unwrap `{success, data, meta}` so callers deal in domain objects. */
export async function apiGet<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
  const { data } = await http.get<SuccessEnvelope<T>>(url, config)
  return data.data
}

export async function apiPost<T>(
  url: string,
  body?: unknown,
  config?: AxiosRequestConfig,
): Promise<T> {
  const { data } = await http.post<SuccessEnvelope<T>>(url, body, config)
  return data.data
}

export async function apiPatch<T>(url: string, body?: unknown): Promise<T> {
  const { data } = await http.patch<SuccessEnvelope<T>>(url, body)
  return data.data
}

export async function apiDelete(url: string): Promise<void> {
  await http.delete(url)
}

/** Paginated GET: returns both rows and the pagination block. */
export async function apiGetPaginated<T>(
  url: string,
  config?: AxiosRequestConfig,
): Promise<{ items: T[]; meta: SuccessEnvelope<T[]>['meta'] }> {
  const { data } = await http.get<SuccessEnvelope<T[]>>(url, config)
  return { items: data.data, meta: data.meta }
}
