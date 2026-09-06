/**
 * Localisation (TRD 22).
 *
 * Rule: no user-facing string literal in a component. Everything goes through a key,
 * so adding a language is a translation task, not a code change.
 *
 * `en` is the fallback. A missing key logs in development so gaps are visible during
 * the work rather than discovered at the demo.
 */
import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'

import en from './locales/en/common.json'
import hi from './locales/hi/common.json'
import mr from './locales/mr/common.json'
import { useLanguageStore } from '@/stores/language'

void i18n.use(initReactI18next).init({
  resources: {
    en: { common: en },
    hi: { common: hi },
    mr: { common: mr },
  },
  lng: useLanguageStore.getState().language,
  fallbackLng: 'en',
  defaultNS: 'common',
  interpolation: { escapeValue: false }, // React already escapes
  saveMissing: import.meta.env.DEV,
  missingKeyHandler: (_lngs, ns, key) => {
    if (import.meta.env.DEV) console.warn(`[i18n] missing key: ${ns}:${key}`)
  },
})

// Keep i18next in step with the store.
useLanguageStore.subscribe((state) => {
  if (i18n.language !== state.language) void i18n.changeLanguage(state.language)
})

export default i18n
