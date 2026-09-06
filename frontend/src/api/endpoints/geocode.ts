/**
 * Place-name lookup for the observation form.
 *
 * Uses OpenStreetMap's Nominatim - the same data source as the map's base tiles - so
 * a farmer can type "Nashik" or "Sinnar taluka" instead of coordinates. It is called
 * directly from the browser rather than proxied: the query is a public place name,
 * carries no observation data, and the backend has no geocoder of its own (the
 * `admin_regions` table ships empty pending a licensed boundary dataset, TRD D7).
 *
 * Results are biased to India and capped at 5. A failure is never fatal - the form
 * still accepts GPS or manually typed coordinates.
 */

const NOMINATIM_URL = 'https://nominatim.openstreetmap.org/search'

export interface PlaceMatch {
  displayName: string
  latitude: number
  longitude: number
}

interface NominatimResult {
  display_name: string
  lat: string
  lon: string
}

export const geocodeApi = {
  search: async (query: string, signal?: AbortSignal): Promise<PlaceMatch[]> => {
    const params = new URLSearchParams({
      q: query,
      format: 'jsonv2',
      addressdetails: '0',
      limit: '5',
      countrycodes: 'in',
    })
    const response = await fetch(`${NOMINATIM_URL}?${params.toString()}`, {
      signal,
      headers: { Accept: 'application/json' },
    })
    if (!response.ok) throw new Error(`Place lookup failed: ${response.status}`)
    const results = (await response.json()) as NominatimResult[]
    return results.map((r) => ({
      displayName: r.display_name,
      latitude: Number(Number(r.lat).toFixed(6)),
      longitude: Number(Number(r.lon).toFixed(6)),
    }))
  },
}
