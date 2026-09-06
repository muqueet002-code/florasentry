/**
 * Loading / empty / error / degraded states (TRD 7.8).
 *
 * Every data-bound view implements all four. Degraded is a first-class state in this
 * product because the backend deliberately degrades (stale weather, AI unavailable)
 * rather than failing outright.
 */
import { useTranslation } from 'react-i18next'
import { cn } from '@/lib/cn'

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn('animate-pulse rounded bg-slate-200', className)} />
}

export function LoadingState({ rows = 3 }: { rows?: number }) {
  const { t } = useTranslation()
  return (
    <div className="space-y-3" role="status" aria-label={t('states.loading')}>
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-20 w-full" />
      ))}
    </div>
  )
}

export function EmptyState({
  title,
  hint,
  action,
}: {
  title: string
  hint?: string
  action?: React.ReactNode
}) {
  return (
    <div className="rounded-lg border border-dashed border-slate-300 bg-white p-8 text-center">
      <p className="text-base font-medium text-slate-700">{title}</p>
      {hint && <p className="mt-1 text-sm text-slate-500">{hint}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  const { t } = useTranslation()
  return (
    <div className="rounded-lg border border-red-200 bg-red-50 p-4" role="alert">
      <p className="text-sm font-medium text-red-800">{t('states.errorTitle')}</p>
      <p className="mt-1 text-sm text-red-700">{message}</p>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-3 rounded border border-red-300 bg-white px-3 py-1.5 text-sm font-medium text-red-800 hover:bg-red-100"
        >
          {t('common.retry')}
        </button>
      )}
    </div>
  )
}

/** A module that ships in a later phase. Shows NO data - that is the point. */
export function NotImplementedState({ phase }: { phase: string }) {
  const { t } = useTranslation()
  return (
    <div className="rounded-lg border border-amber-200 bg-amber-50 p-6">
      <p className="text-sm font-semibold text-amber-900">{t('states.notImplementedTitle')}</p>
      <p className="mt-2 text-sm text-amber-800">{t('states.notImplementedBody', { phase })}</p>
    </div>
  )
}
