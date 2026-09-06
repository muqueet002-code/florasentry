/**
 * Translation-completeness test (TRD 22.3).
 *
 * Fails the build when `hi` or `mr` is missing a key present in `en`, so a language
 * cannot silently rot as new strings are added.
 */
import { describe, expect, it } from 'vitest'
import en from '@/i18n/locales/en/common.json'
import hi from '@/i18n/locales/hi/common.json'
import mr from '@/i18n/locales/mr/common.json'

type Json = Record<string, unknown>

function flatten(obj: Json, prefix = ''): string[] {
  return Object.entries(obj).flatMap(([key, value]) => {
    // Keys prefixed with _ are translator notes, not user-facing strings.
    if (key.startsWith('_')) return []
    const path = prefix ? `${prefix}.${key}` : key
    return value && typeof value === 'object' && !Array.isArray(value)
      ? flatten(value as Json, path)
      : [path]
  })
}

const enKeys = flatten(en as Json)

describe('translation completeness', () => {
  it('en has a meaningful number of keys', () => {
    expect(enKeys.length).toBeGreaterThan(50)
  })

  it.each([
    ['hi', hi],
    ['mr', mr],
  ])('%s covers every en key', (_lang, bundle) => {
    const keys = new Set(flatten(bundle as Json))
    const missing = enKeys.filter((k) => !keys.has(k))
    expect(missing).toEqual([])
  })

  it.each([
    ['hi', hi],
    ['mr', mr],
  ])('%s has no keys that en lacks', (_lang, bundle) => {
    const enSet = new Set(enKeys)
    const extra = flatten(bundle as Json).filter((k) => !enSet.has(k))
    expect(extra).toEqual([])
  })

  it('every error message_key the backend can send has a translation', () => {
    // These mirror app/core/errors.py. A backend error must never surface raw.
    const backendKeys = [
      'errors.validation',
      'errors.auth_required',
      'errors.auth_invalid_credentials',
      'errors.auth_token_expired',
      'errors.auth_account_inactive',
      'errors.forbidden_role',
      'errors.forbidden_ownership',
      'errors.not_found',
      'errors.internal',
      'errors.not_implemented',
      'errors.coordinates_out_of_bounds',
      'errors.geometry_invalid',
      'errors.crop_context_mismatch',
    ]
    const enSet = new Set(enKeys)
    expect(backendKeys.filter((k) => !enSet.has(k))).toEqual([])
  })
})
