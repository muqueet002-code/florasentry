import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'

import { ApiError } from '@/api/client'
import { authApi } from '@/api/endpoints/auth'
import { Button } from '@/components/ui/Button'
import { TextField } from '@/components/ui/Field'
import { ErrorState } from '@/components/ui/States'
import { ROLE_HOME } from '@/app/roleHome'
import { useAuthStore } from '@/stores/auth'
import { useLanguageStore } from '@/stores/language'
import { AuthBackground } from '@/components/layout/AuthBackground'

const schema = z.object({
  full_name: z.string().min(2).max(150),
  phone: z
    .string()
    .regex(/^\+?[0-9]{7,15}$/, 'invalid_phone')
    .transform((v) => v.replace(/[\s-]/g, '')),
  password: z.string().min(8).max(128),
  village: z.string().max(120).optional().or(z.literal('')),
  taluka: z.string().max(120).optional().or(z.literal('')),
})
type FormValues = z.input<typeof schema>

export function RegisterPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const language = useLanguageStore((s) => s.language)
  const setSession = useAuthStore((s) => s.setSession)
  const [formError, setFormError] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) })

  async function onSubmit(values: FormValues) {
    setFormError(null)
    try {
      const parsed = schema.parse(values)
      const result = await authApi.register({
        full_name: parsed.full_name,
        phone: parsed.phone,
        password: parsed.password,
        preferred_language: language,
        village: parsed.village || null,
        taluka: parsed.taluka || null,
      })
      setSession(result.user, result.tokens.access_token, result.tokens.refresh_token)
      navigate(ROLE_HOME[result.user.role], { replace: true })
    } catch (error) {
      setFormError(
        error instanceof ApiError ? t(error.messageKey, error.message) : t('errors.internal'),
      )
    }
  }

  return (
    <AuthBackground>
      <h1 className="text-2xl font-semibold text-slate-900">{t('auth.signUp')}</h1>
      {/* Stated up front: self-registration cannot create a privileged role. */}
      <p className="mt-2 rounded-lg bg-slate-100 p-3 text-xs text-slate-600">
        {t('auth.registerNote')}
      </p>

      <form onSubmit={handleSubmit(onSubmit)} className="mt-6 space-y-4" noValidate>
        <TextField
          label={t('auth.fullName')}
          autoComplete="name"
          error={errors.full_name && t('common.required')}
          {...register('full_name')}
        />
        <TextField
          label={t('auth.phone')}
          type="tel"
          autoComplete="tel"
          error={errors.phone && t('common.required')}
          {...register('phone')}
        />
        <TextField
          label={t('auth.password')}
          type="password"
          autoComplete="new-password"
          error={errors.password && t('errors.password_too_short')}
          {...register('password')}
        />
        <TextField label={t('auth.village')} {...register('village')} />
        <TextField label={t('auth.taluka')} {...register('taluka')} />

        {formError && <ErrorState message={formError} />}

        <Button type="submit" disabled={isSubmitting} className="w-full">
          {isSubmitting ? t('auth.creatingAccount') : t('auth.signUp')}
        </Button>
      </form>

      <p className="mt-6 text-center text-sm text-slate-600">
        {t('auth.haveAccount')}{' '}
        <Link to="/login" className="font-medium text-brand hover:underline">
          {t('auth.signIn')}
        </Link>
      </p>
    </AuthBackground>
  )
}
