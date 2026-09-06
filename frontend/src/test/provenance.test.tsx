/**
 * Provenance rendering tests.
 *
 * These guard the single most important UI property of this product: a viewer must
 * never mistake simulated data for real, or an AI prediction for a confirmed
 * diagnosis (TRD 10.4).
 */

import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { I18nextProvider } from 'react-i18next'

import i18n from '@/i18n'
import {
  DemoDataBanner,
  ProvenanceBadge,
  VerificationChip,
} from '@/components/provenance/ProvenanceBadge'
import type { Provenance } from '@/api/types'

const realProvenance: Provenance = {
  source_type: 'FIELD_OBSERVATION',
  created_by: 'user-1',
  created_at: '2026-09-05T10:00:00Z',
}

const demoProvenance: Provenance = {
  ...realProvenance,
  source_type: 'DEMO_SIMULATION',
}

function renderWithI18n(ui: React.ReactElement) {
  return render(<I18nextProvider i18n={i18n}>{ui}</I18nextProvider>)
}

describe('ProvenanceBadge', () => {
  it('labels a real field observation as such', () => {
    renderWithI18n(<ProvenanceBadge provenance={realProvenance} />)
    expect(screen.getByText('Field observation')).toBeInTheDocument()
  })

  it('labels simulated data explicitly and visibly', () => {
    renderWithI18n(<ProvenanceBadge provenance={demoProvenance} />)
    expect(screen.getByText('Simulated demo data')).toBeInTheDocument()
    expect(
      screen.getByText('Simulated demo data - not a real field observation'),
    ).toBeInTheDocument()
  })

  it('never renders demo data with the same styling as real data', () => {
    const { container: real } = renderWithI18n(<ProvenanceBadge provenance={realProvenance} />)
    const { container: demo } = renderWithI18n(<ProvenanceBadge provenance={demoProvenance} />)

    const realChip = real.querySelector('[data-source-type]')
    const demoChip = demo.querySelector('[data-source-type]')
    expect(realChip?.className).not.toEqual(demoChip?.className)
  })

  it('shows the model version when a prediction is involved', () => {
    renderWithI18n(
      <ProvenanceBadge
        provenance={{ ...realProvenance, model_version: 'crop-clf-v0.1.0' }}
        verificationStatus="PREDICTED"
        confidence={0.61}
      />,
    )
    expect(screen.getByText(/crop-clf-v0\.1\.0/)).toBeInTheDocument()
    expect(screen.getByText('61%')).toBeInTheDocument()
  })
})

describe('VerificationChip', () => {
  it('describes a prediction as unconfirmed', () => {
    renderWithI18n(<VerificationChip status="PREDICTED" />)
    expect(screen.getByText('AI prediction - not confirmed')).toBeInTheDocument()
  })

  it('describes a confirmation as expert-confirmed', () => {
    renderWithI18n(<VerificationChip status="CONFIRMED" />)
    expect(screen.getByText('Expert confirmed')).toBeInTheDocument()
  })

  it('styles predicted and confirmed differently', () => {
    const { container: predicted } = renderWithI18n(<VerificationChip status="PREDICTED" />)
    const { container: confirmed } = renderWithI18n(<VerificationChip status="CONFIRMED" />)
    expect(
      predicted.querySelector('[data-verification-status]')?.className,
    ).not.toEqual(confirmed.querySelector('[data-verification-status]')?.className)
  })
})

describe('DemoDataBanner', () => {
  it('appears when any visible record is simulated', () => {
    renderWithI18n(<DemoDataBanner visible />)
    expect(screen.getByRole('note')).toBeInTheDocument()
  })

  it('stays hidden when all data is real', () => {
    renderWithI18n(<DemoDataBanner visible={false} />)
    expect(screen.queryByRole('note')).not.toBeInTheDocument()
  })
})
