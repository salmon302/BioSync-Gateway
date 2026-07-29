// SPDX-License-Identifier: MIT
/**
 * NFR-R (reliability) end-to-end UI tests.
 *
 * Covers the reliability behaviors that have a UI surface:
 *   - NFR-R2  Graceful degradation: the dashboard stays usable (no crash,
 *             controls intact, live device telemetry still renders) when the
 *             telemetry WebSocket is unavailable/fails.
 *   - NFR-R4  WebSocket auto-reconnect (visible at the UI) + message replay of
 *             missed data points (FR-3.16 / SRS NFR-R4).
 *
 * NFR-R1 (99.9% uptime) and NFR-R3 (DB-pool reconnect with exponential
 * backoff) are backend-only and are NOT UI-exercisable here — see the Phase 4
 * implementation log (SNDEV/docs/impl-2026-07-29-phase4-nfr-hardening.md).
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, act, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ChartProvider } from '../src/providers/chart-provider'
import { HumanFactorsProvider } from '../src/providers/human-factors-provider'
import TelemetryDashboard from '../src/pages/TelemetryDashboard'
import { useWebSocket } from '../src/hooks/useWebSocket'

vi.mock('echarts', () => ({
  init: vi.fn(() => ({
    setOption: vi.fn(),
    dispose: vi.fn(),
    dispatchAction: vi.fn(),
  })),
}))

// Controllable WebSocket mock: the test drives server-side open/close/deliver.
const wsInstances: MockWebSocket[] = []
class MockWebSocket {
  url: string
  onopen: ((ev: any) => void) | null = null
  onclose: ((ev: any) => void) | null = null
  onmessage: ((ev: any) => void) | null = null
  onerror: ((ev: any) => void) | null = null
  readyState: number = 0
  _sent: string[] = []
  static CONNECTING = 0
  static OPEN = 1
  static CLOSING = 2
  static CLOSED = 3
  constructor(url: string) {
    this.url = url
    wsInstances.push(this)
  }
  send(data: string) {
    this._sent.push(data)
  }
  close() {
    this.readyState = MockWebSocket.CLOSED
    this.onclose?.({ code: 1000 } as any)
  }
  // --- test helpers (simulate the server) ---
  open() {
    this.readyState = MockWebSocket.OPEN
    this.onopen?.({})
  }
  fail() {
    this.readyState = MockWebSocket.CLOSED
    this.onerror?.({})
    this.onclose?.({ code: 1006 } as any)
  }
  deliver(data: any) {
    this.onmessage?.({ data: typeof data === 'string' ? data : JSON.stringify(data) } as any)
  }
}
const originalWebSocket = globalThis.WebSocket

function renderDashboard() {
  return render(
    <MemoryRouter>
      <ChartProvider>
        <HumanFactorsProvider>
          <TelemetryDashboard />
        </HumanFactorsProvider>
      </ChartProvider>
    </MemoryRouter>
  )
}

const HR_OBS = {
  effectiveDateTime: '2026-07-29T12:00:00Z',
  valueQuantity: { value: 88 },
  code: { coding: [{ code: '8867-4' }] },
}

describe('NFR-R2 — graceful degradation', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    wsInstances.length = 0
    globalThis.WebSocket = MockWebSocket as any
  })
  afterEach(() => {
    globalThis.WebSocket = originalWebSocket
  })

  it('remains fully usable when the telemetry WebSocket never connects', () => {
    renderDashboard()
    // No connection established -> explicit degraded ("Disconnected") state.
    expect(screen.getByText('Disconnected')).toBeInTheDocument()
    const indicator = document.querySelector('.status-indicator.disconnected')
    expect(indicator).toBeInTheDocument()
    // Core controls remain present and interactive (no crash / blank screen).
    expect(screen.getByText('Start Stream')).toBeInTheDocument()
    expect(screen.getByText('Reset Zoom')).toBeInTheDocument()
    expect(screen.getByText('Telemetry Dashboard')).toBeInTheDocument()
  })

  it('does not crash and recovers to a degraded state when the connection fails mid-stream', async () => {
    const user = userEvent.setup()
    renderDashboard()

    await user.click(screen.getByText('Start Stream'))
    // The second socket is the one the Start Stream interaction opens.
    expect(wsInstances.length).toBeGreaterThanOrEqual(2)
    const streamSocket = wsInstances[wsInstances.length - 1]
    act(() => streamSocket.fail())

    expect(screen.getByText('Disconnected')).toBeInTheDocument()
    // Controls still present -> operator can retry; UI did not lock up.
    // (The button now reads "Stop Stream" because the start interaction
    // flipped isStreaming; the key point is it remains rendered & interactive.)
    expect(screen.getByText('Stop Stream')).toBeInTheDocument()
  })

  it('renders live device telemetry once the stream delivers observations (data path independent of Pulse)', async () => {
    renderDashboard()
    act(() => wsInstances[0].open())
    act(() => wsInstances[0].deliver({ type: 'telemetry', payload: { observations: [HR_OBS] } }))

    await waitFor(() => expect(screen.getByText('Data Points: 1')).toBeInTheDocument())
    expect(screen.getByText('Connected')).toBeInTheDocument()
  })
})

describe('NFR-R4 — WebSocket auto-reconnect + message replay', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    wsInstances.length = 0
    globalThis.WebSocket = MockWebSocket as any
  })
  afterEach(() => {
    globalThis.WebSocket = originalWebSocket
    vi.useRealTimers()
  })

  it('auto-reconnects after a server drop and continues receiving telemetry at the UI', () => {
    vi.useFakeTimers()
    renderDashboard()

    // 1) Establish connection and receive a point.
    act(() => wsInstances[0].open())
    act(() => wsInstances[0].deliver({ type: 'telemetry', payload: { observations: [HR_OBS] } }))
    expect(screen.getByText('Connected')).toBeInTheDocument()

    // 2) Server drops the connection -> degraded state.
    act(() => wsInstances[0].fail())
    expect(screen.getByText('Disconnected')).toBeInTheDocument()

    // 3) Hook reconnects on its own (exponential backoff timer fires).
    act(() => {
      vi.advanceTimersByTime(2000)
    })
    expect(wsInstances.length).toBe(2) // a new socket was created
    act(() => wsInstances[1].open())
    expect(screen.getByText('Connected')).toBeInTheDocument()

    // 4) Continuity: new socket keeps streaming into the same dashboard.
    act(() => wsInstances[1].deliver({ type: 'telemetry', payload: { observations: [HR_OBS] } }))
    expect(screen.getByText('Data Points: 2')).toBeInTheDocument()
  })

  it('replays messages queued while disconnected on the next open (NFR-R4)', () => {
    function ReplayHarness() {
      const { isConnected, sendMessage } = useWebSocket('ws://localhost/api/telemetry/stream')
      return (
        <div>
          <span data-testid="conn">{isConnected ? 'up' : 'down'}</span>
          <button onClick={() => sendMessage({ type: 'subscribe', channels: ['pressure'] })}>
            Send while disconnected
          </button>
        </div>
      )
    }

    render(<ReplayHarness />)
    expect(screen.getByTestId('conn').textContent).toBe('down')

    // Send while the socket is down -> should be buffered, not lost.
    fireEvent.click(screen.getByText('Send while disconnected'))
    expect(wsInstances[0]._sent).toHaveLength(0)

    // Re-open -> the hook flushes the replay buffer.
    act(() => wsInstances[0].open())
    expect(wsInstances[0]._sent).toContain(
      JSON.stringify({ type: 'subscribe', channels: ['pressure'] })
    )
  })
})
