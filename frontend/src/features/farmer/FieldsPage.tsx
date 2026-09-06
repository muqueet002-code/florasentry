/**
 * My Fields (TRD 12.4).
 *
 * The only fully-wired data screen in Phase 1. It exists to prove the whole chain
 * works end to end: auth -> API client -> PostGIS write -> provenance -> render.
 */

import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'

import { ApiError } from '@/api/client'
import { fieldsApi } from '@/api/endpoints/fields'
import { Button } from '@/components/ui/Button'
import { TextField } from '@/components/ui/Field'
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/States'
import { DemoDataBanner, ProvenanceBadge } from '@/components/provenance/ProvenanceBadge'

const schema = z.object({
  name: z.string().min(1).max(120),
  latitude: z.coerce.number().min(-90).max(90),
  longitude: z.coerce.number().min(-180).max(180),
  area_ha: z.coerce.number().positive().optional().or(z.literal('')),
  soil_type: z.string().max(60).optional().or(z.literal('')),
})
type FormValues = z.input<typeof schema>

export function FieldsPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [locating, setLocating] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)

  const fieldsQuery = useQuery({
    queryKey: ['fields'],
    queryFn: () => fieldsApi.list(),
  })

  const {
    register,
    handleSubmit,
    setValue,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) })

  const createField = useMutation({
    mutationFn: fieldsApi.create,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['fields'] })
      setShowForm(false)
      reset()
    },
  })

  function useMyLocation() {
    if (!navigator.geolocation) {
      setFormError(t('fields.locationUnavailable'))
      return
    }
    setLocating(true)
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        // 6 decimal places (~0.11 m); more is false precision for phone GPS.
        setValue('latitude', Number(pos.coords.latitude.toFixed(6)))
        setValue('longitude', Number(pos.coords.longitude.toFixed(6)))
        setLocating(false)
      },
      () => {
        // Denied or unavailable: fall back to manual entry rather than blocking.
        setFormError(t('fields.locationDenied'))
        setLocating(false)
      },
      { enableHighAccuracy: true, timeout: 10000 },
    )
  }

  async function onSubmit(values: FormValues) {
    setFormError(null)
    try {
      const parsed = schema.parse(values)
      await createField.mutateAsync({
        name: parsed.name,
        latitude: parsed.latitude,
        longitude: parsed.longitude,
        area_ha: parsed.area_ha === '' ? null : (parsed.area_ha as number | undefined) ?? null,
        soil_type: parsed.soil_type || null,
      })
    } catch (error) {
      setFormError(
        error instanceof ApiError ? t(error.messageKey, error.message) : t('errors.internal'),
      )
    }
  }

  const fields = fieldsQuery.data?.items ?? []
  const hasDemoData = fields.some((f) => f.provenance.source_type === 'DEMO_SIMULATION')

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-slate-900">{t('fields.title')}</h1>
        <Button onClick={() => setShowForm((v) => !v)}>
          {showForm ? t('common.cancel') : t('fields.add')}
        </Button>
      </div>

      {/* Shown whenever any visible record is simulated (TRD 27.5). */}
      <DemoDataBanner visible={hasDemoData} />

      {showForm && (
        <form
          onSubmit={handleSubmit(onSubmit)}
          className="space-y-4 rounded-lg border border-slate-200 bg-white p-4"
          noValidate
        >
          <TextField
            label={t('fields.name')}
            error={errors.name && t('common.required')}
            {...register('name')}
          />
          <div className="grid grid-cols-2 gap-3">
            <TextField
              label={t('fields.latitude')}
              type="number"
              step="0.000001"
              error={errors.latitude && t('common.required')}
              {...register('latitude')}
            />
            <TextField
              label={t('fields.longitude')}
              type="number"
              step="0.000001"
              error={errors.longitude && t('common.required')}
              {...register('longitude')}
            />
          </div>
          <Button type="button" variant="secondary" onClick={useMyLocation} disabled={locating}>
            {locating ? t('fields.locating') : t('fields.useMyLocation')}
          </Button>

          <div className="grid grid-cols-2 gap-3">
            <TextField
              label={t('fields.areaHa')}
              type="number"
              step="0.001"
              {...register('area_ha')}
            />
            <TextField label={t('fields.soilType')} {...register('soil_type')} />
          </div>

          {formError && <ErrorState message={formError} />}

          <Button type="submit" disabled={isSubmitting}>
            {t('common.save')}
          </Button>
        </form>
      )}

      {fieldsQuery.isLoading && <LoadingState />}

      {fieldsQuery.isError && (
        <ErrorState
          message={
            fieldsQuery.error instanceof ApiError
              ? t(fieldsQuery.error.messageKey, fieldsQuery.error.message)
              : t('errors.internal')
          }
          onRetry={() => void fieldsQuery.refetch()}
        />
      )}

      {fieldsQuery.isSuccess && fields.length === 0 && (
        <EmptyState title={t('fields.empty')} hint={t('fields.emptyHint')} />
      )}

      <ul className="space-y-3">
        {fields.map((field) => (
          <li key={field.id} className="rounded-lg border border-slate-200 bg-white p-4">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="font-medium text-slate-900">{field.name}</p>
                <p className="mt-0.5 text-sm text-slate-500">
                  {t('fields.coordinates')}: {field.latitude.toFixed(5)},{' '}
                  {field.longitude.toFixed(5)}
                  {field.area_ha ? ` · ${field.area_ha} ha` : ''}
                </p>
              </div>
            </div>
            {/* Provenance is mandatory on every record-bearing row (TRD 10.4). */}
            <ProvenanceBadge provenance={field.provenance} className="mt-3" />
          </li>
        ))}
      </ul>
    </div>
  )
}
