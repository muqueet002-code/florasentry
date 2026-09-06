/** Language preference (TRD 22.2). Persisted locally and mirrored to the server. */
import { create } from 'zustand'
import { configureApiClient } from '@/api/client'

export const SUPPORTED_LANGUAGES = ['en', 'hi', 'mr'] as const
export type LanguageCode = (typeof SUPPORTED_LANGUAGES)[number]

const KEY = 'florasentry.language'

function initial(): LanguageCode {
  try {
    const stored = localStorage.getItem(KEY) as LanguageCode | null
    if (stored && SUPPORTED_LANGUAGES.includes(stored)) return stored
  } catch {
    /* storage blocked - fall through to the default */
  }
  const browser = navigator.language?.split('-')[0] as LanguageCode | undefined
  if (browser && SUPPORTED_LANGUAGES.includes(browser)) return browser
  return (import.meta.env.VITE_DEFAULT_LANGUAGE as LanguageCode) ?? 'en'
}

interface LanguageState {
  language: LanguageCode
  setLanguage: (language: LanguageCode) => void
}

export const useLanguageStore = create<LanguageState>((set) => ({
  language: initial(),
  setLanguage: (language) => {
    try {
      localStorage.setItem(KEY, language)
    } catch {
      /* ignore */
    }
    set({ language })
  },
}))

// The API client sends this as Accept-Language on every request.
configureApiClient({ getLanguage: () => useLanguageStore.getState().language })
