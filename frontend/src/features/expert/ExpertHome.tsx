import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'

import { reviewsApi } from '@/api/endpoints/reviews'
import { Button } from '@/components/ui/Button'

export function ExpertHome() {
  const { t } = useTranslation()
  // A lightweight count only - the review queue page itself is the real work surface;
  // this is a landing screen, not a second dashboard (out of scope for this phase).
  const queueQuery = useQuery({
    queryKey: ['review-queue', 1],
    queryFn: () => reviewsApi.queue(1, 1),
  })

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-slate-900">{t('dashboard.expert')}</h1>

      <div className="rounded-lg border border-slate-200 bg-white p-4">
        <p className="text-sm text-slate-500">{t('dashboard.pendingReviews')}</p>
        <p className="mt-1 text-3xl font-semibold text-slate-900">
          {queueQuery.isLoading ? '—' : (queueQuery.data?.meta.pagination?.total_items ?? 0)}
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          <Link to="/expert/queue">
            <Button>{t('nav.queue')}</Button>
          </Link>
          <Link to="/expert/map">
            <Button variant="secondary">{t('nav.map')}</Button>
          </Link>
        </div>
      </div>
    </div>
  )
}
