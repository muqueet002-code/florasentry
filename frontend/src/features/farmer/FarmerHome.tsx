/**
 * FloraSentry farmer dashboard.
 *
 * Order is deliberate: act first (new observation, over the field hero), then see the
 * most recent result, then the running totals, then the full history. Every number
 * here is a real read of the farmer's own observations (`observationsApi.list`) -
 * nothing is invented to make the dashboard look fuller.
 */

import { useMemo } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import { serverUrl } from '@/api/client'
import { advisoryApi } from '@/api/endpoints/advisory'
import { catalogApi } from '@/api/endpoints/catalog'
import { fieldsApi } from '@/api/endpoints/fields'
import { observationsApi, type ObservationOut } from '@/api/endpoints/observations'
import { weatherApi } from '@/api/endpoints/weather'
import { useAuthStore } from '@/stores/auth'
import { useLanguageStore } from '@/stores/language'
import { Button } from '@/components/ui/Button'
import { AdvisoryCard } from '@/components/provenance/AdvisoryCard'
import { VerificationChip } from '@/components/provenance/ProvenanceBadge'
import { LoadingState } from '@/components/ui/States'
import { AuthedImage } from '@/features/farmer/ObservationResultPage'

const HIGH_RISK = new Set(['HIGH'])
const RESOLVED_STATUSES = new Set(['CONFIRMED', 'CORRECTED', 'REJECTED'])
const PENDING_STATUSES = new Set(['PENDING_REVIEW', 'LAB_REFERRED'])

function MetricCard({
  icon,
  label,
  value,
  tone,
}: {
  icon: string
  label: string
  value: number
  tone?: string
}) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-center gap-2 text-xs font-medium tracking-wide text-slate-500 uppercase">
        <span aria-hidden>{icon}</span>
        <span className="truncate">{label}</span>
      </div>
      <p className={`mt-1 text-2xl font-bold tabular-nums ${tone ?? 'text-slate-900'}`}>{value}</p>
    </div>
  )
}

function predictionLabel(o: ObservationOut): string {
  if (!o.prediction) return '—'
  return o.prediction.predicted_class.replaceAll('_', ' ')
}

export function FarmerHome() {
  const { t } = useTranslation()
  const user = useAuthStore((s) => s.user)
  const accessToken = useAuthStore((s) => s.accessToken)
  const language = useLanguageStore((s) => s.language)

  const fieldsQuery = useQuery({
    queryKey: ['fields'],
    queryFn: () => fieldsApi.list(1, 5),
  })
  const observationsQuery = useQuery({
    queryKey: ['observations', 'dashboard'],
    queryFn: () => observationsApi.list(1, 50),
  })
  const cropsQuery = useQuery({
    queryKey: ['crops'],
    queryFn: catalogApi.crops,
  })

  const firstField = fieldsQuery.data?.items[0]
  const weatherQuery = useQuery({
    queryKey: ['weather', firstField?.id],
    queryFn: () => weatherApi.current(firstField!.latitude, firstField!.longitude),
    enabled: Boolean(firstField),
    retry: false,
  })

  const observationsData = observationsQuery.data
  const observations = useMemo(() => observationsData?.items ?? [], [observationsData])
  const metrics = useMemo(() => {
    let highRisk = 0
    let pending = 0
    let resolved = 0
    for (const o of observations) {
      if (o.risk && HIGH_RISK.has(o.risk.risk_level)) highRisk += 1
      if (PENDING_STATUSES.has(o.verification_status)) pending += 1
      if (RESOLVED_STATUSES.has(o.verification_status)) resolved += 1
    }
    return {
      total: observationsData?.meta.pagination?.total_items ?? 0,
      highRisk,
      pending,
      resolved,
    }
  }, [observations, observationsData])

  const latest = observations[0]
  // Advisory for the most recent case - the same endpoint the result screen calls.
  const advisoryQuery = useQuery({
    queryKey: ['advisory', latest?.id, language],
    queryFn: () => advisoryApi.get(latest!.id, language),
    enabled: Boolean(latest) && latest?.status !== 'PROCESSING',
    retry: false,
  })

  const cropName = (cropId: string | null) =>
    cropId ? (cropsQuery.data?.find((c) => c.id === cropId)?.name ?? null) : null
  const weather = weatherQuery.data

  return (
    <div>
      {/* Field hero, full-bleed and first on the page: the header floats transparent
          on top of it (see AppShell's `isHeroPage`), so the photograph reaches the
          very top of the viewport with no seam. `100vw` centred via a negative margin
          is the standard robust full-bleed technique - no sidebar-width bookkeeping
          needed now that navigation is a drawer, not a persistent rail. The extra top
          padding clears the floating header/menu button. Two background layers: the
          photograph, with the bundled SVG beneath as a fallback so the frame is never
          blank. */}
      <section
        className="relative w-screen overflow-hidden bg-olive-dark"
        style={{
          marginLeft: 'calc(50% - 50vw)',
          backgroundImage: "url('/hero-field.jpg'), url('/hero-field.svg')",
          backgroundSize: 'cover, cover',
          backgroundPosition: 'center, center',
          backgroundRepeat: 'no-repeat, no-repeat',
        }}
      >
        {/* Full first screen: the photo fills the whole viewport height on load
            (same width behaviour as before), so it reads as a real landing hero
            rather than a strip. `100dvh` accounts for mobile browser chrome. */}
        <div className="flex min-h-screen items-center justify-center bg-gradient-to-b from-black/50 via-black/35 to-black/60 px-5 pt-24 pb-16 text-center [min-height:100dvh] sm:px-8 sm:pt-28">
          <div className="max-w-xl">
            <p className="text-xs font-semibold tracking-[0.2em] text-white/80 uppercase drop-shadow">
              {t('app.name')}
            </p>
            <h2 className="mt-3 text-3xl font-bold text-white drop-shadow-md sm:text-5xl">
              {t('dashboard.newObservation')}
            </h2>
            <p className="mx-auto mt-4 max-w-md text-sm text-white/90 drop-shadow sm:text-base">
              {t('dashboard.newObservationHint')}
            </p>
            <Link to="/app/check" className="mt-7 inline-block">
              <Button className="px-8 py-3 text-base shadow-xl">
                {t('dashboard.startObservation')}
              </Button>
            </Link>
          </div>
        </div>
      </section>

      <div className="mx-auto w-full max-w-6xl space-y-6 px-4 py-6">
        {/* Greeting + compact climate strip */}
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h1 className="text-xl font-semibold text-slate-900">
              {t('dashboard.welcome', { name: user?.full_name ?? '' })}
            </h1>
            <p className="mt-1 text-sm text-slate-600">{t('dashboard.phase1Notice')}</p>
          </div>

          <div className="flex items-center gap-3 rounded-lg border border-sky-200 bg-sky-50 px-3 py-2">
            <span className="text-xl" aria-hidden>
              {weather ? '☀️' : '🌤️'}
            </span>
            <div className="text-sm leading-tight">
              {weather ? (
                <p className="font-semibold text-slate-900">
                  {weather.temperature_c !== null ? `${weather.temperature_c}°C` : '—'}
                  {weather.humidity_pct !== null && (
                    <span className="ml-2 font-normal text-slate-600">
                      {t('dashboard.humidityShort')} {weather.humidity_pct}%
                    </span>
                  )}
                </p>
              ) : (
                <p className="font-medium text-slate-500">{t('dashboard.weatherUnavailable')}</p>
              )}
              <p className="text-xs text-slate-500">
                {new Date().toLocaleDateString(undefined, {
                  weekday: 'short',
                  day: 'numeric',
                  month: 'short',
                })}
                {firstField && ` · ${firstField.name}`}
              </p>
            </div>
          </div>
        </div>

        {/* Latest observation */}
        <section className="rounded-lg border border-slate-200 bg-white p-4">
          <div className="flex items-center justify-between gap-2">
            <h2 className="font-semibold text-slate-900">{t('dashboard.latestObservation')}</h2>
            <Link
              to="/app/observations"
              className="text-sm text-brand underline decoration-dotted hover:text-brand-dark"
            >
              {t('nav.myObservations')}
            </Link>
          </div>

          {observationsQuery.isLoading && <LoadingState rows={2} />}
          {!observationsQuery.isLoading && !latest && (
            <p className="mt-2 text-sm text-slate-500">{t('dashboard.empty')}</p>
          )}

          {latest && (
            <div className="mt-3 grid gap-4 sm:grid-cols-[minmax(0,200px)_1fr]">
              {latest.image ? (
                <AuthedImage
                  src={serverUrl(latest.image.thumbnail_url ?? latest.image.url)}
                  token={accessToken}
                  className="h-40 w-full rounded-lg object-cover"
                  skeletonClassName="h-40 w-full animate-pulse rounded-lg bg-slate-200"
                />
              ) : (
                <div className="flex h-40 items-center justify-center rounded-lg bg-slate-100 text-3xl">
                  🌱
                </div>
              )}

              <div className="min-w-0 space-y-2">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-base font-semibold text-slate-900">
                    {cropName(latest.crop_id) ?? t('dashboard.cropUnknown')}
                  </p>
                  <VerificationChip status={latest.verification_status as never} />
                </div>

                <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
                  <dt className="text-slate-500">{t('ai.brand')}</dt>
                  <dd className="text-slate-800">{predictionLabel(latest)}</dd>
                  {latest.prediction && (
                    <>
                      <dt className="text-slate-500">{t('ai.confidence')}</dt>
                      <dd className="text-slate-800">
                        {(latest.prediction.confidence * 100).toFixed(0)}%
                      </dd>
                    </>
                  )}
                  <dt className="text-slate-500">{t('dashboard.riskLabel')}</dt>
                  <dd className="font-medium text-slate-800">{latest.risk?.risk_level ?? '—'}</dd>
                  <dt className="text-slate-500">{t('dashboard.table.date')}</dt>
                  <dd className="text-slate-800">
                    {new Date(latest.observed_at).toLocaleString()}
                  </dd>
                </dl>

                <Link to={`/app/observations/${latest.id}`} className="inline-block pt-1">
                  <Button variant="secondary">{t('dashboard.viewDetails')}</Button>
                </Link>
              </div>
            </div>
          )}
        </section>

        {/* Running totals */}
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <MetricCard icon="🌿" label={t('dashboard.metric.total')} value={metrics.total} />
          <MetricCard
            icon="⚠️"
            label={t('dashboard.metric.highRisk')}
            value={metrics.highRisk}
            tone="text-red-700"
          />
          <MetricCard
            icon="◷"
            label={t('dashboard.farmerMetric.pending')}
            value={metrics.pending}
            tone="text-blue-700"
          />
          <MetricCard
            icon="✓"
            label={t('dashboard.farmerMetric.resolved')}
            value={metrics.resolved}
            tone="text-emerald-700"
          />
        </div>

        {/* Recent observations, with the advisory for the latest case alongside */}
        <div className="grid gap-4 lg:grid-cols-3">
          <section className="rounded-lg border border-slate-200 bg-white p-4 lg:col-span-2">
            <div className="flex items-center justify-between gap-2">
              <h2 className="font-semibold text-slate-900">{t('dashboard.recentObservations')}</h2>
              <Link
                to="/app/fields"
                className="text-sm text-brand underline decoration-dotted hover:text-brand-dark"
              >
                {t('nav.fields')} ({fieldsQuery.data?.meta.pagination?.total_items ?? 0})
              </Link>
            </div>

            {observations.length === 0 ? (
              <p className="mt-2 text-sm text-slate-500">{t('dashboard.empty')}</p>
            ) : (
              <div className="mt-3 -mx-4 overflow-x-auto px-4">
                <table className="w-full min-w-[560px] text-left text-sm">
                  <thead>
                    <tr className="border-b border-slate-200 text-xs tracking-wide text-slate-500 uppercase">
                      <th className="py-2 pr-3">{t('dashboard.table.crop')}</th>
                      <th className="py-2 pr-3">{t('dashboard.table.prediction')}</th>
                      <th className="py-2 pr-3">{t('dashboard.table.risk')}</th>
                      <th className="py-2 pr-3">{t('dashboard.table.status')}</th>
                      <th className="py-2 pr-3">{t('dashboard.table.date')}</th>
                      <th className="py-2"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {observations.slice(0, 8).map((o) => (
                      <tr key={o.id} className="border-b border-slate-100 last:border-0">
                        <td className="py-2 pr-3">{cropName(o.crop_id) ?? '—'}</td>
                        <td className="py-2 pr-3">{predictionLabel(o)}</td>
                        <td className="py-2 pr-3">{o.risk?.risk_level ?? '—'}</td>
                        <td className="py-2 pr-3">
                          <VerificationChip status={o.verification_status as never} />
                        </td>
                        <td className="py-2 pr-3 whitespace-nowrap text-slate-500">
                          {new Date(o.observed_at).toLocaleDateString()}
                        </td>
                        <td className="py-2 text-right whitespace-nowrap">
                          <Link
                            to={`/app/observations/${o.id}`}
                            className="text-brand underline decoration-dotted hover:text-brand-dark"
                          >
                            {t('dashboard.viewDetails')}
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          {/* Advisory for the most recent case, alongside the history. Reuses the same
            AdvisoryCard the result screen renders, so the tier styling and the
            mandatory disclaimer are identical wherever advice appears. */}
          <section className="space-y-2">
            {advisoryQuery.data ? (
              <AdvisoryCard advisory={advisoryQuery.data} />
            ) : (
              <div className="rounded-lg border border-slate-200 bg-white p-4">
                <h2 className="font-semibold text-slate-900">🤖 {t('ai.advisory')}</h2>
                <p className="mt-2 text-sm text-slate-500">
                  {latest ? t('dashboard.advisoryLoading') : t('dashboard.advisoryEmpty')}
                </p>
              </div>
            )}
            {latest && (
              <Link
                to={`/app/observations/${latest.id}`}
                className="inline-block text-sm text-brand underline decoration-dotted hover:text-brand-dark"
              >
                {t('dashboard.viewDetails')}
              </Link>
            )}
          </section>
        </div>
      </div>
    </div>
  )
}
