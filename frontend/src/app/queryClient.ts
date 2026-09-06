import { QueryClient } from '@tanstack/react-query'
import { ApiError } from '@/api/client'

/** Shared server-state cache (TRD 7.4). Separate module so providers.tsx stays components-only. */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      retry: (failureCount, error) => {
        // Never retry a client error: a 401/403/404/422/501 will not fix itself,
        // and retrying a 501 stub just delays an honest message.
        if (error instanceof ApiError && error.status >= 400 && error.status < 500) return false
        return failureCount < 2
      },
    },
    mutations: { retry: false },
  },
})
