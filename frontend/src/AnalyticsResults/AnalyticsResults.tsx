// SPDX-License-Identifier: MIT
/**
 * Analytics Results — read-only viewers for the four advanced simulation
 * module outputs (FR-3.11 PK/PD, FR-3.12 chemistry, FR-3.13 digital twin,
 * FR-3.14 MRD). Implements the Phase 3 "module promotion" visibility item:
 * lets validators/operators inspect generated outputs without altering them.
 */
import { useEffect, useState } from 'react'
import {
  listPkpdWorklists,
  listChemistryProfiles,
  listCohorts,
  listMrdRuns,
} from '../utils/api'
import './AnalyticsResults.css'

type AnyObj = Record<string, any>

export default function AnalyticsResults() {
  const [data, setData] = useState<{
    pkpd: AnyObj[]
    chemistry: AnyObj[]
    cohorts: AnyObj[]
    mrd: AnyObj[]
  }>({ pkpd: [], chemistry: [], cohorts: [], mrd: [] })
  const [status, setStatus] = useState('Loading…')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const [pk, ch, co, mr] = await Promise.all([
          listPkpdWorklists(20),
          listChemistryProfiles(20),
          listCohorts(20),
          listMrdRuns(20),
        ])
        if (!cancelled) {
          setData({
            pkpd: pk.worklists || [],
            chemistry: ch.profiles || [],
            cohorts: co.cohorts || [],
            mrd: mr.runs || [],
          })
          setStatus('Loaded')
        }
      } catch (e: any) {
        if (!cancelled) {
          setError(e.message)
          setStatus('Error')
        }
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <div className="analytics-results">
      <h2>Analytics Results</h2>
      <p className="hint">
        Read-only view of outputs from the advanced simulation modules
        (FR-3.11–FR-3.14).
      </p>
      {error && <div className="error">Error: {error}</div>}
      {!error && <div className="status">{status}</div>}

      <section>
        <h3>PK/PD Worklists (FR-3.11)</h3>
        <Table rows={data.pkpd} cols={['worklist_uid', 'substance_name', 'well_count', 'created_at']} />
      </section>

      <section>
        <h3>Clinical Chemistry Profiles (FR-3.12)</h3>
        <Table
          rows={data.chemistry}
          cols={['profile_uid', 'patient_id', 'has_clinvar', 'has_lims_response', 'created_at']}
        />
      </section>

      <section>
        <h3>Digital Twin Cohorts (FR-3.13)</h3>
        <Table rows={data.cohorts} cols={['cohort_uid', 'name', 'size', 'created_at']} />
      </section>

      <section>
        <h3>MRD / cfDNA Sandbox Runs (FR-3.14)</h3>
        <Table
          rows={data.mrd}
          cols={['run_uid', 'detection_result', 'scenario_run_id', 'created_at']}
        />
      </section>
    </div>
  )
}

function Table({ rows, cols }: { rows: AnyObj[]; cols: string[] }) {
  if (!rows.length) return <p className="empty">No records yet.</p>
  return (
    <table className="results-table">
      <thead>
        <tr>
          {cols.map((c) => (
            <th key={c}>{c}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((r, i) => (
          <tr key={i}>
            {cols.map((c) => (
              <td key={c}>{fmt(r[c])}</td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function fmt(v: any): string {
  if (v === null || v === undefined) return '—'
  if (typeof v === 'boolean') return v ? 'yes' : 'no'
  return String(v)
}
