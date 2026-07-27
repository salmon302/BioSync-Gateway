// SPDX-License-Identifier: MIT
/**
 * Minimal authenticated API client for the BioSync-Gateway frontend.
 *
 * Centralizes JWT resolution and Bearer-authenticated requests to the
 * middleware. This unblocks FR-3.2.3 (well-click -> FHIR Observation fetch)
 * and provides a single integration point for future API calls.
 *
 * The JWT is expected to be stored by the login flow under `biosync_jwt`
 * (localStorage). When absent, requests are sent without a token and the
 * middleware returns 401, which callers handle gracefully.
 */

const API_BASE: string =
  (import.meta as any).env?.VITE_API_BASE ?? '/api'

export function getAuthToken(): string | null {
  try {
    return localStorage.getItem('biosync_jwt')
  } catch {
    return null
  }
}

export async function apiFetch<T = any>(
  path: string,
  init: RequestInit = {}
): Promise<T> {
  const token = getAuthToken()
  const headers = new Headers(init.headers)
  headers.set('Accept', 'application/fhir+json')
  if (token) headers.set('Authorization', `Bearer ${token}`)

  const res = await fetch(`${API_BASE}${path}`, { ...init, headers })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`API ${res.status}: ${text.slice(0, 200)}`)
  }
  return (await res.json()) as T
}

/** Fetch a FHIR Observation resource by its UID (SRS FR-3.2.3 / FR-3.7.3). */
export async function fetchObservation(uid: string): Promise<any> {
  return apiFetch<any>(`/fhir/Observation/${encodeURIComponent(uid)}`)
}
