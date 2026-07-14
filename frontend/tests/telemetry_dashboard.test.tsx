import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ChartProvider } from '../src/providers/chart-provider'
import { HumanFactorsProvider } from '../src/providers/human-factors-provider'
import TelemetryDashboard from '../src/pages/TelemetryDashboard'

// Mock echarts — chart-provider uses `import * as echarts`
vi.mock('echarts', () => ({
  init: vi.fn(() => ({
    setOption: vi.fn(),
    dispose: vi.fn(),
    dispatchAction: vi.fn(),
  })),
}))

// Mock WebSocket
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

describe('TelemetryDashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    globalThis.WebSocket = MockWebSocket as any
  })

  afterEach(() => {
    globalThis.WebSocket = originalWebSocket
  })

  it('renders the dashboard title', () => {
    renderDashboard()
    expect(screen.getByText('Telemetry Dashboard')).toBeInTheDocument()
  })

  it('shows disconnected status initially', () => {
    renderDashboard()
    expect(screen.getByText('Disconnected')).toBeInTheDocument()
    const indicator = document.querySelector('.status-indicator.disconnected')
    expect(indicator).toBeInTheDocument()
  })

  it('has a Start Stream button', () => {
    renderDashboard()
    expect(screen.getByText('Start Stream')).toBeInTheDocument()
  })

  it('has a Reset Zoom button', () => {
    renderDashboard()
    expect(screen.getByText('Reset Zoom')).toBeInTheDocument()
  })

  it('has a disabled Export Data button when no data', () => {
    renderDashboard()
    const exportBtn = screen.getByText('Export Data')
    expect(exportBtn).toBeDisabled()
  })

  it('shows channel information', () => {
    renderDashboard()
    expect(screen.getByText('Channels: Pressure, Flow, HR, SpO₂')).toBeInTheDocument()
    expect(screen.getByText('Data Points: 0')).toBeInTheDocument()
  })

  it('starts streaming when Start Stream is clicked', async () => {
    const user = userEvent.setup()
    renderDashboard()

    await user.click(screen.getByText('Start Stream'))

    // Button text should change
    expect(screen.getByText('Stop Stream')).toBeInTheDocument()
  })

  it('renders the chart container', () => {
    renderDashboard()
    const chartContainer = document.querySelector('.chart-container')
    expect(chartContainer).toBeInTheDocument()
  })

  it('does not show alarm indicator when no alarms', () => {
    renderDashboard()
    const alarmIndicator = document.querySelector('.alarm-indicator')
    expect(alarmIndicator).not.toBeInTheDocument()
  })
})
