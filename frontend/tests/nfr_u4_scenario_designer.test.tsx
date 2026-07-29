// SPDX-License-Identifier: MIT
/**
 * NFR-U4 end-to-end UI test — Scenario Designer assembly + execution in <=5
 * user interactions (SRS FR-3.16.5 / NFR-U4).
 *
 * Exercises the real ScenarioDesigner component (and the real app Navigation
 * "main console") with the API boundary mocked, driving genuine DOM user
 * interactions and counting them to assert the SRS NFR-U4 interaction budget.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import App from '../src/App'
import ScenarioDesigner from '../src/ScenarioDesigner/ScenarioDesigner'
import { ChartProvider } from '../src/providers/chart-provider'
import { HumanFactorsProvider } from '../src/providers/human-factors-provider'

// Mock echarts (pulled in transitively by App's TelemetryDashboard route).
vi.mock('echarts', () => ({
  init: vi.fn(() => ({
    setOption: vi.fn(),
    dispose: vi.fn(),
    dispatchAction: vi.fn(),
  })),
}))

// Mock the API boundary so the scenario create/run is deterministic & offline.
vi.mock('../src/utils/api', () => ({
  createScenario: vi.fn(async (spec: any) => ({
    scenario_uid: 'SCN-TEST-001',
    ...spec,
  })),
  runScenario: vi.fn(async () => ({
    run_uid: 'RUN-TEST-001',
    status: 'completed',
    aggregated_outputs: { pk_pd: { worklist_uid: 'WL-1' } },
    output_hashes: { pk_pd: 'sha256:abc123' },
    downstream_results: [],
  })),
  listScenarios: vi.fn(async () => []),
  getScenario: vi.fn(async () => ({})),
  getScenarioRun: vi.fn(async () => ({})),
  listScenarioRuns: vi.fn(async () => []),
  listPkpdWorklists: vi.fn(async () => []),
  listChemistryProfiles: vi.fn(async () => []),
  listCohorts: vi.fn(async () => []),
  listMrdRuns: vi.fn(async () => []),
  fetchObservation: vi.fn(async () => ({})),
}))

import * as api from '../src/utils/api'

// Minimal mock WebSocket so App's TelemetryDashboard route does not crash.
class MockWebSocket {
  url: string
  onopen: ((ev: any) => void) | null = null
  onclose: ((ev: any) => void) | null = null
  onmessage: ((ev: any) => void) | null = null
  onerror: ((ev: any) => void) | null = null
  readyState: number = 0
  static CONNECTING = 0
  static OPEN = 1
  static CLOSING = 2
  static CLOSED = 3
  constructor(url: string) {
    this.url = url
  }
  send(_data: string) {}
  close() {
    this.readyState = MockWebSocket.CLOSED
    this.onclose?.({ code: 1000 } as any)
  }
}
const originalWebSocket = globalThis.WebSocket

function renderConsole() {
  return render(
    <MemoryRouter initialEntries={['/telemetry']}>
      <ChartProvider>
        <HumanFactorsProvider>
          <App />
        </HumanFactorsProvider>
      </ChartProvider>
    </MemoryRouter>
  )
}

describe('NFR-U4 — Scenario Designer assembled & executed in <=5 interactions', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    globalThis.WebSocket = MockWebSocket as any
    localStorage.clear()
  })
  afterEach(() => {
    globalThis.WebSocket = originalWebSocket
  })

  it('minimal path: a single click on "Create & Run" executes the default scenario', async () => {
    const user = userEvent.setup()
    let interactions = 0

    render(<ScenarioDesigner />)

    // Modules are pre-selected by default, so a single interaction suffices.
    interactions++
    await user.click(screen.getByText('Create & Run Scenario'))

    await waitFor(() =>
      expect(screen.getByText(/completed with status: completed/)).toBeInTheDocument()
    )

    // Results pane rendered end-to-end (FR-3.16.2/3.16.4).
    expect(screen.getByText('Aggregated outputs (FR-3.16.2)')).toBeInTheDocument()
    expect(screen.getByText('Determinism hashes (FR-3.16.4)')).toBeInTheDocument()

    expect(interactions).toBeLessThanOrEqual(5)
    expect(api.createScenario).toHaveBeenCalledTimes(1)
    expect(api.runScenario).toHaveBeenCalledTimes(1)
  })

  it('tightest valid custom subset (1 module): 4 deselects + run = 5 interactions', async () => {
    const user = userEvent.setup()
    let interactions = 0

    render(<ScenarioDesigner />)

    // Default selection is all 5 modules. Selecting exactly 1 module requires
    // deselecting the other 4 (the mathematically tightest valid case).
    const checkboxes = await screen.findAllByRole('checkbox')
    expect(checkboxes).toHaveLength(5)
    for (let i = 0; i < 4; i++) {
      interactions++
      await user.click(checkboxes[i])
    }

    interactions++
    await user.click(screen.getByText('Create & Run Scenario'))

    await waitFor(() =>
      expect(screen.getByText(/completed with status: completed/)).toBeInTheDocument()
    )

    // Budget proof: even the tightest valid custom assembly stays within <=5.
    expect(interactions).toBe(5)
    expect(interactions).toBeLessThanOrEqual(5)
  })

  it('from the main console: navigate via Navigation then run = 2 interactions', async () => {
    const user = userEvent.setup()
    let interactions = 0

    renderConsole()
    // App redirects "/" -> "/telemetry"; Navigation (the "main console") is shown.
    expect(screen.getByText('BioSync-Gateway')).toBeInTheDocument()

    // 1 interaction: click the Scenario Designer nav link.
    interactions++
    await user.click(screen.getByText('Scenario Designer'))

    await waitFor(() =>
      expect(screen.getByText('Create & Run Scenario')).toBeInTheDocument()
    )

    // 2 interaction: execute from within the designer.
    interactions++
    await user.click(screen.getByText('Create & Run Scenario'))

    await waitFor(() =>
      expect(screen.getByText(/completed with status: completed/)).toBeInTheDocument()
    )

    expect(interactions).toBeLessThanOrEqual(5)
  })

  it('full assembly (name + seed + downstream + run) stays within the budget', async () => {
    const user = userEvent.setup()
    let interactions = 0

    render(<ScenarioDesigner />)

    interactions++
    await user.type(screen.getByPlaceholderText('e.g. Validation Batch A'), 'Batch Z')

    interactions++
    fireEvent.change(screen.getByPlaceholderText('{"default": 1}'), {
      target: { value: '{"default": 7}' },
    })

    interactions++
    await user.type(
      screen.getByPlaceholderText('https://…/ingest'),
      'https://lims.example/ingest'
    )

    interactions++
    await user.click(screen.getByText('Create & Run Scenario'))

    await waitFor(() =>
      expect(screen.getByText(/completed with status: completed/)).toBeInTheDocument()
    )

    expect(interactions).toBe(4)
    expect(interactions).toBeLessThanOrEqual(5)
    // Downstream endpoint config was forwarded to the create call.
    expect(api.createScenario).toHaveBeenCalledWith(
      expect.objectContaining({
        name: 'Batch Z',
        config: expect.objectContaining({
          downstream_endpoints: [
            expect.objectContaining({ url: 'https://lims.example/ingest' }),
          ],
        }),
      })
    )
  })
})
