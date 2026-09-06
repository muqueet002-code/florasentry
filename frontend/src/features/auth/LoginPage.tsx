import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
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

const schema = z.object({
  identifier: z.string().min(3),
  password: z.string().min(1),
})
type FormValues = z.infer<typeof schema>

export function LoginPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const location = useLocation()
  const setSession = useAuthStore((s) => s.setSession)
  const setUser = useAuthStore((s) => s.setUser)
  const [formError, setFormError] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) })

  async function onSubmit(values: FormValues) {
    setFormError(null)
    try {
      const result = await authApi.login(values)
      setSession(result.user, result.access_token, result.refresh_token)

      // Fetch the effective permission set so the UI can hide affordances the
      // server would reject anyway.
      try {
        const me = await authApi.me()
        setUser(me.user, me.permissions)
      } catch {
        /* non-fatal: the session is valid, permissions just stay empty */
      }

      const from = (location.state as { from?: string } | null)?.from
      navigate(from ?? ROLE_HOME[result.user.role], { replace: true })
    } catch (error) {
      // Render the localised key, not the raw server string (TRD 11.3).
      setFormError(
        error instanceof ApiError ? t(error.messageKey, error.message) : t('errors.internal'),
      )
    }
  }

  return (
    <div className="mx-auto flex min-h-full max-w-md flex-col justify-center px-4 py-10">
      <h1 className="text-2xl font-semibold text-slate-900">{t('app.name')}</h1>
      <p className="mt-1 text-sm text-slate-600">{t('app.tagline')}</p>

      <form onSubmit={handleSubmit(onSubmit)} className="mt-8 space-y-4" noValidate>
        <TextField
          label={t('auth.identifier')}
          hint={t('auth.identifierHint')}
          type="tel"
          autoComplete="username"
          error={errors.identifier && t('common.required')}
          {...register('identifier')}
        />
        <TextField
          label={t('auth.password')}
          type="password"
          autoComplete="current-password"
          error={errors.password && t('common.required')}
          {...register('password')}
        />

        {formError && <ErrorState message={formError} />}

        <Button type="submit" disabled={isSubmitting} className="w-full">
          {isSubmitting ? t('auth.signingIn') : t('auth.signIn')}
        </Button>
      </form>

      <p className="mt-6 text-center text-sm text-slate-600">
        {t('auth.noAccount')}{' '}
        <Link to="/register" className="font-medium text-brand hover:underline">
          {t('auth.signUp')}
        </Link>
      </p>
    </div>
  )
}
