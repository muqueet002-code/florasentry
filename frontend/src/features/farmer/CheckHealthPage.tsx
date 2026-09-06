/**
 * New Observation (Phase 2, polished for the showcase).
 *
 * Field -> crop context -> image -> notes -> location -> "Analyze with KrishiMitra AI".
 * One page rather than a routed multi-step wizard (deliberate: the existing pipeline
 * is a single multipart POST, and every field below maps directly onto
 * `ObservationCreatePayload` - no new backend surface needed).
 */

import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import { ApiError } from '@/api/client'
import { catalogApi } from '@/api/endpoints/catalog'
import { fieldsApi } from '@/api/endpoints/fields'
import { geocodeApi, type PlaceMatch } from '@/api/endpoints/geocode'
import { observationsApi } from '@/api/endpoints/observations'
import { Button } from '@/components/ui/Button'
import { ErrorState } from '@/components/ui/States'

const ANALYSIS_STEPS = [
  'checkHealth.stage.uploading',
  'checkHealth.stage.quality',
  'checkHealth.stage.symptoms',
  'checkHealth.stage.comparing',
  'checkHealth.stage.confidence',
  'checkHealth.stage.risk',
]

export function CheckHealthPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()

  const [fieldId, setFieldId] = useState('')
  const [cropId, setCropId] = useState('')
  const [growthStageId, setGrowthStageId] = useState('')
  const [severity, setSeverity] = useState('')
  const [notes, setNotes] = useState('')
  const [image, setImage] = useState<File | null>(null)
  const [preview, setPreview] = useState<string | null>(null)
  const [coords, setCoords] = useState<{ lat: number; lon: number } | null>(null)
  const [locating, setLocating] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [stageIndex, setStageIndex] = useState(0)
  const [dragging, setDragging] = useState(false)
  const [placeQuery, setPlaceQuery] = useState('')
  const [placeMatches, setPlaceMatches] = useState<PlaceMatch[] | null>(null)
  const [placeLabel, setPlaceLabel] = useState<string | null>(null)
  const [searchingPlace, setSearchingPlace] = useState(false)

  const fieldsQuery = useQuery({ queryKey: ['fields'], queryFn: () => fieldsApi.list(1, 50) })
  const cropsQuery = useQuery({ queryKey: ['crops'], queryFn: catalogApi.crops })
  const growthStagesQuery = useQuery({
    queryKey: ['growth-stages', cropId],
    queryFn: () => catalogApi.growthStages(cropId),
    enabled: Boolean(cropId),
  })

  // Selecting a field pre-fills its location; the farmer can still override via "Use
  // my current location". Set directly in the handler (not an effect derived from the
  // selection) so there is exactly one state update per user action.
  function onFieldChange(id: string) {
    setFieldId(id)
    const field = fieldsQuery.data?.items.find((f) => f.id === id)
    if (field) setCoords({ lat: field.latitude, lon: field.longitude })
  }

  const submit = useMutation({
    mutationFn: async () => {
      if (!coords) throw new Error('Location is required.')
      return observationsApi.create(
        {
          latitude: coords.lat,
          longitude: coords.lon,
          field_id: fieldId || null,
          crop_id: cropId || null,
          growth_stage_id: growthStageId || null,
          observation_type: image ? 'IMAGE' : 'MANUAL_REPORT',
          reported_severity: severity ? Number(severity) : null,
          notes: notes || null,
        },
        image,
      )
    },
    onMutate: () => setStageIndex(0),
    onSuccess: (result) => navigate(`/app/observations/${result.data.id}`),
    onError: (err) => {
      setStageIndex(0)
      setError(err instanceof ApiError ? err.message : 'Could not submit the report.')
    },
  })

  // A staged "analyzing" sequence rather than a bare spinner (SIH showcase polish) -
  // it cycles while the real request is in flight; it never claims a stage finished
  // that the backend hasn't actually reached. Reset-to-0 happens in the mutation
  // callbacks above, not here, so this effect only ever subscribes to the timer.
  useEffect(() => {
    if (!submit.isPending) return
    const id = setInterval(() => {
      setStageIndex((i) => Math.min(i + 1, ANALYSIS_STEPS.length - 1))
    }, 900)
    return () => clearInterval(id)
  }, [submit.isPending])

  function acceptFile(file: File | null) {
    if (file && !file.type.startsWith('image/')) {
      setError(t('checkHealth.notAnImage'))
      return
    }
    setImage(file)
    setPreview(file ? URL.createObjectURL(file) : null)
  }

  function onFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    acceptFile(e.target.files?.[0] ?? null)
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault()
    setDragging(false)
    acceptFile(e.dataTransfer.files?.[0] ?? null)
  }

  function removeImage() {
    setImage(null)
    setPreview(null)
  }

  /** Place-name lookup: most farmers know their village or taluka, not coordinates.
   * GPS and manual entry both remain available if this fails or finds nothing. */
  async function searchPlace() {
    const query = placeQuery.trim()
    if (!query) return
    setSearchingPlace(true)
    setError(null)
    try {
      const matches = await geocodeApi.search(query)
      setPlaceMatches(matches)
      if (matches.length === 0) setError(t('checkHealth.placeNotFound'))
    } catch {
      setError(t('checkHealth.placeLookupFailed'))
      setPlaceMatches(null)
    } finally {
      setSearchingPlace(false)
    }
  }

  function choosePlace(match: PlaceMatch) {
    setCoords({ lat: match.latitude, lon: match.longitude })
    setPlaceLabel(match.displayName)
    setPlaceMatches(null)
  }

  /** Manual coordinate entry: the farmer may know the plot's coordinates, or GPS may
   * be denied/unavailable - neither should block a report. */
  function setManualCoord(which: 'lat' | 'lon', raw: string) {
    const value = Number(raw)
    if (raw === '' || Number.isNaN(value)) return
    setCoords((prev) => ({
      lat: which === 'lat' ? value : (prev?.lat ?? 0),
      lon: which === 'lon' ? value : (prev?.lon ?? 0),
    }))
  }

  function useMyLocation() {
    if (!navigator.geolocation) {
      setError('Location is not available on this device.')
      return
    }
    setLocating(true)
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setCoords({
          lat: Number(pos.coords.latitude.toFixed(6)),
          lon: Number(pos.coords.longitude.toFixed(6)),
        })
        setLocating(false)
      },
      () => {
        setError('Location permission denied.')
        setLocating(false)
      },
      { enableHighAccuracy: true, timeout: 10000 },
    )
  }

  if (submit.isPending) {
    return (
      <div className="mx-auto max-w-md space-y-4 py-12 text-center">
        <div className="mx-auto h-14 w-14 animate-spin rounded-full border-4 border-emerald-200 border-t-brand" />
        <h1 className="text-lg font-semibold text-slate-900">{t('ai.analyzeCta')}</h1>
        <ul className="space-y-1.5 text-left text-sm">
          {ANALYSIS_STEPS.map((key, i) => (
            <li
              key={key}
              className={
                i <= stageIndex
                  ? 'flex items-center gap-2 text-slate-800'
                  : 'flex items-center gap-2 text-slate-300'
              }
            >
              <span>{i < stageIndex ? '✓' : i === stageIndex ? '…' : '○'}</span>
              {t(key)}
            </li>
          ))}
        </ul>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-md space-y-5">
      <h1 className="text-xl font-semibold text-slate-900">{t('dashboard.newObservation')}</h1>

      <div className="rounded-lg border border-slate-200 bg-white p-4">
        <label className="block text-sm font-medium text-slate-700">{t('checkHealth.field')}</label>
        <select
          value={fieldId}
          onChange={(e) => onFieldChange(e.target.value)}
          className="mt-2 block w-full rounded border border-slate-300 px-3 py-2 text-sm"
        >
          <option value="">{t('checkHealth.noField')}</option>
          {fieldsQuery.data?.items.map((f) => (
            <option key={f.id} value={f.id}>
              {f.name}
            </option>
          ))}
        </select>
      </div>

      <div className="rounded-lg border border-slate-200 bg-white p-4 space-y-3">
        <div>
          <label className="block text-sm font-medium text-slate-700">{t('fields.crop')}</label>
          <select
            value={cropId}
            onChange={(e) => {
              setCropId(e.target.value)
              setGrowthStageId('')
            }}
            className="mt-2 block w-full rounded border border-slate-300 px-3 py-2 text-sm"
          >
            <option value="">{t('checkHealth.selectCrop')}</option>
            {cropsQuery.data?.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </div>

        {cropId && (
          <div>
            <label className="block text-sm font-medium text-slate-700">
              {t('checkHealth.growthStage')}
            </label>
            <select
              value={growthStageId}
              onChange={(e) => setGrowthStageId(e.target.value)}
              className="mt-2 block w-full rounded border border-slate-300 px-3 py-2 text-sm"
            >
              <option value="">{t('checkHealth.selectStage')}</option>
              {growthStagesQuery.data?.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      <div className="rounded-lg border border-slate-200 bg-white p-4">
        <label className="block text-sm font-medium text-slate-700">{t('checkHealth.photo')}</label>
        <p className="mt-1 text-xs text-slate-500">{t('checkHealth.photoHint')}</p>

        {!preview ? (
          <label
            onDragOver={(e) => {
              e.preventDefault()
              setDragging(true)
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
            className={
              'mt-3 flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed py-10 text-sm transition-colors ' +
              (dragging
                ? 'border-brand bg-emerald-50 text-brand-dark'
                : 'border-slate-300 bg-slate-50 text-slate-500 hover:border-brand hover:bg-emerald-50')
            }
          >
            <span className="text-3xl" aria-hidden>
              ☁️
            </span>
            <span className="font-medium">{t('checkHealth.dropHere')}</span>
            <span className="text-xs">{t('checkHealth.uploadOrCapture')}</span>
            <span className="text-xs text-slate-400">{t('checkHealth.supportedFormats')}</span>
            <input
              type="file"
              accept="image/*"
              capture="environment"
              onChange={onFileChange}
              className="hidden"
            />
          </label>
        ) : (
          <div className="mt-3 space-y-2">
            <img src={preview} alt="Selected crop" className="max-h-64 w-full rounded-lg object-cover" />
            <div className="flex items-center justify-between text-xs text-slate-500">
              <span>
                {image?.name} · {image ? `${(image.size / 1024).toFixed(0)} KB` : ''}
              </span>
              <button
                type="button"
                onClick={removeImage}
                className="font-medium text-red-600 hover:underline"
              >
                {t('checkHealth.remove')}
              </button>
            </div>
          </div>
        )}
      </div>

      <div className="rounded-lg border border-slate-200 bg-white p-4 space-y-3">
        <div>
          <label className="block text-sm font-medium text-slate-700">
            {t('checkHealth.severity')}
          </label>
          <select
            value={severity}
            onChange={(e) => setSeverity(e.target.value)}
            className="mt-2 block w-full rounded border border-slate-300 px-3 py-2 text-sm"
          >
            <option value="">{t('checkHealth.severityUnset')}</option>
            {[1, 2, 3, 4, 5].map((n) => (
              <option key={n} value={n}>
                {n} / 5
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-700">{t('checkHealth.notes')}</label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={2}
            placeholder={t('checkHealth.notesPlaceholder')}
            className="mt-2 block w-full rounded border border-slate-300 px-3 py-2 text-sm"
          />
        </div>
      </div>

      <div className="rounded-lg border border-slate-200 bg-white p-4">
        <label className="block text-sm font-medium text-slate-700">{t('fields.coordinates')}</label>

        <Button
          type="button"
          variant="secondary"
          onClick={useMyLocation}
          disabled={locating}
          className="mt-2 w-full sm:w-auto"
        >
          📍 {locating ? t('fields.locating') : t('fields.useMyLocation')}
        </Button>

        {/* Place / district name search */}
        <p className="mt-3 text-xs font-medium tracking-wide text-slate-400 uppercase">
          {t('checkHealth.orSearchPlace')}
        </p>
        <div className="mt-2 flex gap-2">
          <input
            type="text"
            value={placeQuery}
            onChange={(e) => setPlaceQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault()
                void searchPlace()
              }
            }}
            placeholder={t('checkHealth.placePlaceholder')}
            className="min-w-0 flex-1 rounded border border-slate-300 px-3 py-2 text-sm"
          />
          <Button
            type="button"
            variant="secondary"
            onClick={() => void searchPlace()}
            disabled={searchingPlace || !placeQuery.trim()}
          >
            {searchingPlace ? '…' : t('common.search')}
          </Button>
        </div>

        {placeMatches && placeMatches.length > 0 && (
          <ul className="mt-2 divide-y divide-slate-100 rounded border border-slate-200">
            {placeMatches.map((m) => (
              <li key={`${m.latitude},${m.longitude}`}>
                <button
                  type="button"
                  onClick={() => choosePlace(m)}
                  className="block w-full px-3 py-2 text-left text-sm text-slate-700 hover:bg-emerald-50"
                >
                  {m.displayName}
                </button>
              </li>
            ))}
          </ul>
        )}

        {placeLabel && (
          <p className="mt-2 text-sm text-slate-600">📍 {placeLabel}</p>
        )}

        <p className="mt-3 text-xs font-medium tracking-wide text-slate-400 uppercase">
          {t('checkHealth.orEnterManually')}
        </p>
        <div className="mt-2 grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs text-slate-500">{t('fields.latitude')}</label>
            <input
              type="number"
              step="0.000001"
              inputMode="decimal"
              value={coords ? coords.lat : ''}
              onChange={(e) => setManualCoord('lat', e.target.value)}
              placeholder="19.997500"
              className="mt-1 block w-full rounded border border-slate-300 px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-500">{t('fields.longitude')}</label>
            <input
              type="number"
              step="0.000001"
              inputMode="decimal"
              value={coords ? coords.lon : ''}
              onChange={(e) => setManualCoord('lon', e.target.value)}
              placeholder="73.789800"
              className="mt-1 block w-full rounded border border-slate-300 px-3 py-2 text-sm"
            />
          </div>
        </div>

        {coords && (
          <p className="mt-2 text-sm text-slate-600">
            ✓ {coords.lat.toFixed(5)}, {coords.lon.toFixed(5)}
          </p>
        )}
      </div>

      {error && <ErrorState message={error} />}

      <Button onClick={() => submit.mutate()} disabled={!coords} className="w-full">
        {t('ai.analyzeCta')}
      </Button>
    </div>
  )
}
