/**
 * Official/extension monitoring dashboard (Phase 8).
 *
 * Answers "what is happening, where, how serious, where should attention go?" using
 * only data Phases 1-7 already produce - a single `GET /dashboards/official` call.
 * Opening a case reuses the same observation/advisory/follow-up endpoints the farmer
 * and expert screens use (see OfficialObservationDetailPage), so this is monitoring
 * and prioritisation, not a second copy of the data.
 */

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import { ApiError } from '@/api/client'
import { dashboardsApi } from '@/api/endpoints/dashboards'
import { DemoDataBanner, VerificationChip } from '@/components/provenance/ProvenanceBadge'
import { ErrorState, LoadingState } from '@/components/ui/States'
import { cn } from '@/lib/cn'

const RISK_STYLES: Record<'LOW' | 'MEDIUM' | 'HIGH', string> = {
  LOW: 'bg-emerald-50 text-emerald-800 border-emerald-300',
  MEDIUM: 'bg-amber-50 text-amber-800 border-amber-300',
  HIGH: 'bg-red-50 text-red-800 border-red-300',
}

const HOTSPOT_STYLES: Record<'CONFIRMED' | 'SIGNAL' | 'PREDICTED', string> = {
  CONFIRMED: 'bg-emerald-100 text-emerald-900 border-emerald-400',
  SIGNAL: 'bg-amber-100 text-amber-900 border-amber-400',
  PREDICTED: 'bg-slate-100 text-slate-700 border-slate-300',
}

function MetricCard({ label, value, tone }: { label: string; value: number; tone?: string }) {
  return (
    <div className={cn('rounded-lg border bg-white p-4', tone)}>
      <p className="text-xs font-medium tracking-wide text-slate-500 uppercase">{label}</p>
      <p className="mt-1 text-2xl font-bold tabular-nums text-slate-900">{value}</p>
    </div>
  )
}

function SectionCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <h2 className="mb-3 font-semibold text-slate-900">{title}</h2>
      {children}
    </div>
  )
}

export function OfficialHome() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [includeDemo, setIncludeDemo] = useState(false)

  const query = useQuery({
    queryKey: ['official-dashboard', includeDemo],
    queryFn: () => dashboardsApi.official(includeDemo),
  })

  if (query.isLoading) return <LoadingState rows={6} />
  if (query.isError) {
    return (
      <ErrorState
        message={query.error instanceof ApiError ? query.error.message : 'Something went wrong.'}
        onRetry={() => void query.refetch()}
      />
    )
  }

  const data = query.data!
  const { overview, disease_pest_summary: summary, priority_areas, recent_activity } = data

  const goToObservation = (id: string) => navigate(`/official/observations/${id}`)

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-semibold text-slate-900">{t('dashboard.official')}</h1>
        <label className="flex items-center gap-1.5 text-sm text-slate-700">
          <input
            type="checkbox"
            checked={includeDemo}
            onChange={(e) => setIncludeDemo(e.target.checked)}
          />
          {t('dashboard.includeDemo')}
        </label>
      </div>

      <DemoDataBanner visible={data.includes_demo_data} />

      {/* ---- Overview ---- */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <MetricCard label={t('dashboard.metric.total')} value={overview.total_observations} />
        <MetricCard
          label={t('dashboard.metric.highRisk')}
          value={overview.high_risk_observations}
          tone="border-red-200"
        />
        <MetricCard
          label={t('dashboard.metric.pendingReview')}
          value={overview.pending_expert_reviews}
          tone="border-blue-200"
        />
        <MetricCard
          label={t('dashboard.metric.confirmed')}
          value={overview.confirmed_cases}
          tone="border-emerald-200"
        />
        <MetricCard label={t('dashboard.metric.hotspots')} value={overview.active_hotspots} />
        <MetricCard
          label={t('dashboard.metric.followupsAttention')}
          value={overview.followups_requiring_attention}
          tone="border-amber-200"
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {/* ---- Disease / pest summary ---- */}
        <SectionCard title={t('dashboard.section.threats')}>
          {summary.top_threats.length === 0 ? (
            <p className="text-sm text-slate-500">{t('dashboard.empty')}</p>
          ) : (
            <ul className="space-y-2">
              {summary.top_threats.map((th) => (
                <li
                  key={th.agent_id}
                  className="flex items-center justify-between text-sm"
                >
                  <span className="text-slate-800">
                    {th.agent_name ?? th.agent_code ?? th.agent_id}
                    {th.kind && <span className="ml-1 text-xs text-slate-400">({th.kind})</span>}
                  </span>
                  <span className="tabular-nums text-slate-600">
                    {th.total_observations} ({th.confirmed_observations} {t('verification.CONFIRMED')})
                  </span>
                </li>
              ))}
            </ul>
          )}

          <h3 className="mt-4 mb-1 text-xs font-medium tracking-wide text-slate-500 uppercase">
            {t('dashboard.section.affectedCrops')}
          </h3>
          {summary.affected_crops.length === 0 ? (
            <p className="text-sm text-slate-500">{t('dashboard.empty')}</p>
          ) : (
            <ul className="space-y-1">
              {summary.affected_crops.map((c) => (
                <li key={c.crop_id} className="flex items-center justify-between text-sm">
                  <span className="text-slate-800">{c.crop_name ?? c.crop_code ?? c.crop_id}</span>
                  <span className="tabular-nums text-slate-600">{c.total_observations}</span>
                </li>
              ))}
            </ul>
          )}

          <h3 className="mt-4 mb-1 text-xs font-medium tracking-wide text-slate-500 uppercase">
            {t('dashboard.section.riskDistribution')}
          </h3>
          <div className="flex gap-2">
            {(['LOW', 'MEDIUM', 'HIGH'] as const).map((level) => (
              <span
                key={level}
                className={cn(
                  'rounded border px-2 py-1 text-xs font-medium',
                  RISK_STYLES[level],
                )}
              >
                {level}: {summary.risk_distribution[level]}
              </span>
            ))}
          </div>

          <p className="mt-3 text-xs text-slate-500">
            {t('dashboard.section.diagnosisBasis')}:{' '}
            {summary.diagnosis_basis.confirmed} {t('verification.CONFIRMED').toLowerCase()},{' '}
            {summary.diagnosis_basis.ai_predicted_only} {t('dashboard.aiOnly')}
          </p>
        </SectionCard>

        {/* ---- Priority areas ---- */}
        <SectionCard title={t('dashboard.section.priorityAreas')}>
          {priority_areas.length === 0 ? (
            <p className="text-sm text-slate-500">{t('dashboard.section.noPriorityAreas')}</p>
          ) : (
            <ul className="space-y-2">
              {priority_areas.map((area) => (
                <li
                  key={area.cluster_id}
                  className="rounded border border-slate-200 p-2 text-sm"
                >
                  <div className="flex items-center justify-between">
                    <span
                      className={cn(
                        'rounded-full border px-2 py-0.5 text-xs font-medium',
                        HOTSPOT_STYLES[area.hotspot_type],
                      )}
                    >
                      {area.label}
                    </span>
                    <span className="tabular-nums text-slate-600">
                      {area.observation_count} {t('dashboard.reports')}
                    </span>
                  </div>
                  <p className="mt-1 text-slate-700">
                    {area.dominant_agent_name ?? t('dashboard.unidentified')}
                    {area.avg_severity !== null && (
                      <span className="ml-1 text-xs text-slate-500">
                        · {t('dashboard.avgSeverity')} {area.avg_severity}
                      </span>
                    )}
                  </p>
                  {area.includes_demo_data && (
                    <p className="mt-1 text-xs text-fuchsia-700">
                      {t('provenance.DEMO_SIMULATION')}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          )}
          <p className="mt-3 text-xs text-slate-500">{t('hotspot.disclaimer')}</p>
        </SectionCard>
      </div>

      {/* ---- Recent activity ---- */}
      <SectionCard title={t('dashboard.section.recentActivity')}>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <h3 className="mb-2 text-xs font-medium tracking-wide text-slate-500 uppercase">
              {t('dashboard.section.newObservations')}
            </h3>
            <ActivityList
              items={recent_activity.observations}
              onOpen={goToObservation}
              t={t}
            />
          </div>
          <div>
            <h3 className="mb-2 text-xs font-medium tracking-wide text-slate-500 uppercase">
              {t('dashboard.section.expertValidations')}
            </h3>
            <ActivityList
              items={recent_activity.expert_validations}
              onOpen={goToObservation}
              t={t}
            />
          </div>
          <div>
            <h3 className="mb-2 text-xs font-medium tracking-wide text-slate-500 uppercase">
              {t('dashboard.section.highRiskCases')}
            </h3>
            <ActivityList
              items={recent_activity.high_risk_cases}
              onOpen={goToObservation}
              t={t}
            />
          </div>
          <div>
            <h3 className="mb-2 text-xs font-medium tracking-wide text-slate-500 uppercase">
              {t('dashboard.section.worseningFollowups')}
            </h3>
            {recent_activity.worsening_followups.length === 0 ? (
              <p className="text-sm text-slate-500">{t('dashboard.empty')}</p>
            ) : (
              <ul className="space-y-1.5">
                {recent_activity.worsening_followups.map((f) => (
                  <li key={f.id}>
                    <button
                      type="button"
                      onClick={() => goToObservation(f.parent_observation_id)}
                      className="text-left text-sm text-red-700 underline decoration-dotted hover:text-red-900"
                    >
                      {f.outcome && t(`followup.outcome.${f.outcome}`)} -{' '}
                      {f.submitted_at ? new Date(f.submitted_at).toLocaleDateString() : ''}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </SectionCard>

      <p className="text-xs text-slate-500">{t('dashboard.disclaimer')}</p>
    </div>
  )
}

function ActivityList({
  items,
  onOpen,
  t,
}: {
  items: {
    id: string
    observed_at: string
    verification_status: string
    source_type?: string
  }[]
  onOpen: (id: string) => void
  t: (key: string) => string
}) {
  if (items.length === 0) {
    return <p className="text-sm text-slate-500">{t('dashboard.empty')}</p>
  }
  return (
    <ul className="space-y-1.5">
      {items.map((o) => (
        <li key={o.id} className="flex items-center justify-between gap-2">
          <button
            type="button"
            onClick={() => onOpen(o.id)}
            className="text-left text-sm text-brand underline decoration-dotted hover:text-brand-dark"
          >
            {new Date(o.observed_at).toLocaleDateString()}
            {/* Never let a simulated row read as a real one, even in a compact list. */}
            {o.source_type === 'DEMO_SIMULATION' && (
              <span className="ml-1 text-xs font-semibold text-fuchsia-700">
                ({t('provenance.DEMO_SIMULATION')})
              </span>
            )}
          </button>
          <VerificationChip status={o.verification_status as never} />
        </li>
      ))}
    </ul>
  )
}
