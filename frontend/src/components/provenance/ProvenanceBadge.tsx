/**
 * Provenance display (TRD 10.4).
 *
 * This component is MANDATORY on: observation cards, observation detail, every map
 * popup, the expert case view, and every dashboard list row. A judge asking "is this
 * real data?" must be able to answer from the screen alone.
 *
 * The styling map below is the single source of truth for how each trust state looks,
 * so no screen can render a confirmed case like a predicted one by accident.
 */

import { useTranslation } from 'react-i18next'
import type { Provenance, SourceType, VerificationStatus } from '@/api/types'
import { cn } from '@/lib/cn'

const SOURCE_STYLES: Record<SourceType, string> = {
  FIELD_OBSERVATION: 'bg-slate-100 text-slate-700 border-slate-300',
  PUBLIC_DATA: 'bg-sky-50 text-sky-800 border-sky-300',
  GOVERNMENT_DATA: 'bg-indigo-50 text-indigo-800 border-indigo-300',
  EXPERT_VALIDATION: 'bg-emerald-50 text-emerald-800 border-emerald-300',
  // Distinct colour AND a stripe pattern, so the distinction survives greyscale
  // printing and colour-blind viewers (TRD 27.5).
  DEMO_SIMULATION:
    'bg-fuchsia-50 text-fuchsia-900 border-fuchsia-400 [background-image:repeating-linear-gradient(45deg,transparent,transparent_4px,rgba(192,38,211,0.12)_4px,rgba(192,38,211,0.12)_8px)]',
}

const VERIFICATION_STYLES: Record<VerificationStatus, string> = {
  CONFIRMED: 'bg-emerald-100 text-emerald-900 border-emerald-400',
  CORRECTED: 'bg-emerald-100 text-emerald-900 border-emerald-400',
  PREDICTED: 'bg-amber-100 text-amber-900 border-amber-400 border-dashed',
  PENDING_REVIEW: 'bg-blue-100 text-blue-900 border-blue-400 border-dashed',
  REJECTED: 'bg-slate-100 text-slate-600 border-slate-300',
  LAB_REFERRED: 'bg-violet-100 text-violet-900 border-violet-400',
}

const chip = 'inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium'

export function SourceTypeChip({ sourceType }: { sourceType: SourceType }) {
  const { t } = useTranslation()
  return (
    <span className={cn(chip, SOURCE_STYLES[sourceType])} data-source-type={sourceType}>
      {t(`provenance.${sourceType}`)}
    </span>
  )
}

export function VerificationChip({ status }: { status: VerificationStatus }) {
  const { t } = useTranslation()
  return (
    <span className={cn(chip, VERIFICATION_STYLES[status])} data-verification-status={status}>
      {t(`verification.${status}`)}
    </span>
  )
}

/** Confidence is always shown WITH the verification status, never on its own. */
export function ConfidenceMeter({ confidence }: { confidence: number }) {
  const percent = Math.round(confidence * 100)
  return (
    <span className="inline-flex items-center gap-2" title={`${percent}%`}>
      <span className="h-1.5 w-16 overflow-hidden rounded-full bg-slate-200">
        <span
          className="block h-full rounded-full bg-amber-500"
          style={{ width: `${percent}%` }}
        />
      </span>
      <span className="text-xs tabular-nums text-slate-600">{percent}%</span>
    </span>
  )
}

export function ProvenanceBadge({
  provenance,
  verificationStatus,
  confidence,
  className,
}: {
  provenance: Provenance
  verificationStatus?: VerificationStatus
  confidence?: number
  className?: string
}) {
  const { t } = useTranslation()
  const isDemo = provenance.source_type === 'DEMO_SIMULATION'

  return (
    <div className={cn('flex flex-wrap items-center gap-2', className)}>
      <SourceTypeChip sourceType={provenance.source_type} />
      {verificationStatus && <VerificationChip status={verificationStatus} />}
      {confidence !== undefined && <ConfidenceMeter confidence={confidence} />}

      {isDemo && (
        <span className="text-xs font-semibold text-fuchsia-800">
          {t('provenance.demoWarning')}
        </span>
      )}
      {provenance.model_version && (
        <span className="text-xs text-slate-500">
          {t('provenance.modelVersion')}: {provenance.model_version}
        </span>
      )}
      {provenance.verified_at && (
        <span className="text-xs text-slate-500">
          {t('provenance.verifiedBy')}: {new Date(provenance.verified_at).toLocaleDateString()}
        </span>
      )}
    </div>
  )
}

/**
 * Page-level banner shown whenever ANY visible record is simulated (TRD 27.5).
 * Per-record chips are not enough on their own: a viewer scanning a list must see
 * the caveat without inspecting each row.
 */
export function DemoDataBanner({ visible }: { visible: boolean }) {
  const { t } = useTranslation()
  if (!visible) return null
  return (
    <div
      role="note"
      className="mb-4 rounded-lg border-2 border-fuchsia-400 bg-fuchsia-50 px-4 py-3 text-sm text-fuchsia-900"
    >
      <strong className="font-semibold">{t('provenance.DEMO_SIMULATION')}:</strong>{' '}
      {t('provenance.demoBanner')}
    </div>
  )
}
