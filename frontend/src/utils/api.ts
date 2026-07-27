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

/** Create a scenario specification (SRS FR-3.16.1). */
export async function createScenario(spec: any): Promise<any> {
  return apiFetch<any>('/scenarios', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(spec),
  })
}

/** List scenario specifications (FR-3.16.1). */
export async function listScenarios(): Promise<any> {
  return apiFetch<any>('/scenarios')
}

/** Fetch a scenario specification by UID (FR-3.16.1). */
export async function getScenario(uid: string): Promise<any> {
  return apiFetch<any>(`/scenarios/${encodeURIComponent(uid)}`)
}

/** Execute a scenario and return the populated run (FR-3.16.2/3.16.3). */
export async function runScenario(uid: string): Promise<any> {
  return apiFetch<any>(`/scenarios/${encodeURIComponent(uid)}/run`, {
    method: 'POST',
  })
}

/** Fetch a scenario run by UID (FR-3.16.2/3.16.4). */
export async function getScenarioRun(runUid: string): Promise<any> {
  return apiFetch<any>(`/runs/${encodeURIComponent(runUid)}`)
}

/** List recent scenario runs (FR-3.16.2). */
export async function listScenarioRuns(): Promise<any> {
  return apiFetch<any>('/runs')
}

/** Read-only: list recent PK/PD worklists (FR-3.11). */
export async function listPkpdWorklists(limit: number = 50): Promise<any> {
  return apiFetch<any>(`/simulation/pkpd/worklists?limit=${limit}`)
}

/** Read-only: list recent clinical chemistry profiles (FR-3.12). */
export async function listChemistryProfiles(limit: number = 50): Promise<any> {
  return apiFetch<any>(`/simulation/chemistry/profiles?limit=${limit}`)
}

/** Read-only: list recent digital-then cohorts (FR-3.13). */
export async function listCohorts(limit: number = 50): Promise<any> {
  return apiFetch<any>(`/simulation/cohorts?limit=${limit}`)
}

/** Read-only: list recent MRD / cfDNA sandbox runs (FR-3.14). */
export async function listMrdRuns(limit: number = 50): Promise<any> {
  return apiFetch<any>(`/simulation/mrd/runs?limit=${limit}`)
}

/** Fetch a FHIR Observation resource by its UID (SRS FR-3.2.3 / FR-3.7.3). */
export async function fetchObservation(uid: string): Promise<any> {
  return apiFetch<any>(`/fhir/Observation/${encodeURIComponent(uid)}`)
}
