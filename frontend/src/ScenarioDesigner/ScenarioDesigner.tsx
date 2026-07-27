// SPDX-License-Identifier: MIT
/**
 * Scenario Designer — SRS FR-3.16.5 / NFR-U4.
 *
 * Lets a user assemble, configure, execute, and inspect an integrated
 * simulation scenario (any subset of FR-3.11–FR-3.15) within <=5 user
 * interactions:
 *   1. Name + module selection
 *   2. Seed (optional JSON)
 *   3. Downstream LIMS/EHR endpoint (optional)
 *   4. "Create & Run" — creates the spec (FR-3.16.1) and executes it (FR-3.16.2)
 *   5. Results (aggregated outputs, determinism hashes, downstream responses)
 */

import { useState } from 'react'
import { createScenario, runScenario } from '../utils/api'
import './ScenarioDesigner.css'

const MODULES: { id: string; label: string }[] = [
  { id: 'pk_pd', label: 'PK/PD Lab Loop (FR-3.11)' },
  { id: 'chemistry', label: 'Clinical Chemistry (FR-3.12)' },
  { id: 'digital_twin', label: 'Digital Twin Cohort (FR-3.13)' },
  { id: 'mrd', label: 'MRD / Liquid Biopsy (FR-3.14)' },
  { id: 'llm', label: 'LLM Narrative (FR-3.15)' },
]

export default function ScenarioDesigner() {
  const [name, setName] = useState('')
  const [modules, setModules] = useState<string[]>(MODULES.map((m) => m.id))
  const [seedText, setSeedText] = useState('')
  const [downstreamUrl, setDownstreamUrl] = useState('')
  const [downstreamType, setDownstreamType] = useState('LIMS')
  const [status, setStatus] = useState('')
  const [result, setResult] = useState<any>(null)
  const [busy, setBusy] = useState(false)

  const toggle = (id: string) =>
    setModules((m) => (m.includes(id) ? m.filter((x) => x !== id) : [...m, id]))

  async function handleCreateAndRun() {
    setBusy(true)
    setStatus('Creating scenario…')
    setResult(null)
    try {
      let seed: any = { default: 1 }
      if (seedText.trim()) {
        try {
          seed = JSON.parse(seedText)
        } catch {
          throw new Error('Seed must be valid JSON')
        }
      }
      const config: any = {}
      if (downstreamUrl.trim()) {
        config.downstream_endpoints = [
          { type: downstreamType, url: downstreamUrl.trim() },
        ]
      }
      const created = await createScenario({
        name: name.trim() || 'Untitled Scenario',
        feature_modules: modules,
        seed,
        config,
      })
      setStatus(`Created ${created.scenario_uid}; executing…`)
      const run = await runScenario(created.scenario_uid)
      setResult(run)
      setStatus(`Run ${run.run_uid} completed with status: ${run.status}`)
    } catch (e: any) {
      setStatus(`Error: ${e.message}`)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="scenario-designer">
      <h2>Scenario Designer</h2>
      <p className="hint">
        Assemble, configure, execute, and inspect integrated simulation
        scenarios end-to-end (FR-3.16).
      </p>

      <label>
        Scenario name
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="e.g. Validation Batch A"
        />
      </label>

      <fieldset>
        <legend>Feature modules (subset of FR-3.11–FR-3.15)</legend>
        {MODULES.map((m) => (
          <label key={m.id} className="module-check">
            <input
              type="checkbox"
              checked={modules.includes(m.id)}
              onChange={() => toggle(m.id)}
            />
            {m.label}
          </label>
        ))}
      </fieldset>

      <label>
        Seed (JSON, optional — drives reproducibility)
        <input
          value={seedText}
          onChange={(e) => setSeedText(e.target.value)}
          placeholder='{"default": 1}'
        />
      </label>

      <fieldset>
        <legend>Downstream validation endpoint (FR-3.16.3, optional)</legend>
        <div className="downstream-row">
          <select
            value={downstreamType}
            onChange={(e) => setDownstreamType(e.target.value)}
          >
            <option value="LIMS">LIMS (FHIR Bundle)</option>
            <option value="EHR">EHR (Narrative)</option>
          </select>
          <input
            value={downstreamUrl}
            onChange={(e) => setDownstreamUrl(e.target.value)}
            placeholder="https://…/ingest"
          />
        </div>
      </fieldset>

      <button
        onClick={handleCreateAndRun}
        disabled={busy || modules.length === 0}
      >
        {busy ? 'Working…' : 'Create & Run Scenario'}
      </button>

      {status && <div className="status">{status}</div>}

      {result && (
        <div className="results">
          <h3>
            Run {result.run_uid} — <span className={`badge ${result.status}`}>{result.status}</span>
          </h3>

          <h4>Aggregated outputs (FR-3.16.2)</h4>
          <pre>{JSON.stringify(result.aggregated_outputs, null, 2)}</pre>

          {result.output_hashes && (
            <>
              <h4>Determinism hashes (FR-3.16.4)</h4>
              <pre>{JSON.stringify(result.output_hashes, null, 2)}</pre>
            </>
          )}

          {result.downstream_results && result.downstream_results.length > 0 && (
            <>
              <h4>Downstream results (FR-3.16.3)</h4>
              <pre>{JSON.stringify(result.downstream_results, null, 2)}</pre>
            </>
          )}

          {result.error && <div className="error">Error: {result.error}</div>}
        </div>
      )}
    </div>
  )
}
