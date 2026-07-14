import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import AdminConsole from '../src/pages/AdminConsole'

// Mock fetch globally
const mockFetch = vi.fn()
globalThis.fetch = mockFetch as any

function renderConsole() {
  return render(
    <MemoryRouter>
      <AdminConsole />
    </MemoryRouter>
  )
}

describe('AdminConsole', () => {
  beforeEach(() => {
    vi.clearAllMocks()

    // Default mock: healthy system
    mockFetch.mockResolvedValue({
      json: () =>
        Promise.resolve({
          database: 'healthy',
          middleware: 'healthy',
          pulseEngine: 'running',
        }),
    })
  })

  it('renders the admin console title', async () => {
    renderConsole()
    await waitFor(() => {
      expect(screen.getByText('Admin Console')).toBeInTheDocument()
    })
  })

  it('has JWT Configuration section', async () => {
    renderConsole()
    await waitFor(() => {
      expect(screen.getByText('🔐 JWT Configuration')).toBeInTheDocument()
    })
  })

  it('has Signal Processing section with EMA slider', async () => {
    renderConsole()
    await waitFor(() => {
      expect(screen.getByText('📊 Signal Processing')).toBeInTheDocument()
      expect(screen.getByText(/EMA Alpha/)).toBeInTheDocument()
    })
  })

  it('has Pulse Engine section with restart button', async () => {
    renderConsole()
    await waitFor(() => {
      expect(screen.getByText('⚙️ Pulse Engine')).toBeInTheDocument()
      expect(screen.getByText('Restart Engine')).toBeInTheDocument()
    })
  })

  it('has System Status section', async () => {
    renderConsole()
    await waitFor(() => {
      expect(screen.getByText('🖥️ System Status')).toBeInTheDocument()
    })
  })

  it('shows healthy system status indicators', async () => {
    renderConsole()
    await waitFor(() => {
      // Both Database and Middleware show "✓ Healthy"
      const healthyBadges = screen.getAllByText('✓ Healthy')
      expect(healthyBadges.length).toBe(2)
      expect(screen.getByText('✓ Running')).toBeInTheDocument()
    })
  })

  it('shows degraded status when API returns degraded', async () => {
    mockFetch.mockResolvedValue({
      json: () =>
        Promise.resolve({
          database: 'degraded',
          middleware: 'degraded',
          pulseEngine: 'degraded',
        }),
    })

    renderConsole()
    await waitFor(() => {
      expect(screen.getAllByText('⚠ Degraded').length).toBe(3)
    })
  })

  it('Rotate Keys button exists', async () => {
    renderConsole()
    await waitFor(() => {
      expect(screen.getByText('Rotate Keys')).toBeInTheDocument()
    })
  })

  it('Update Parameter button exists', async () => {
    renderConsole()
    await waitFor(() => {
      expect(screen.getByText('Update Parameter')).toBeInTheDocument()
    })
  })

  it('has JWT secret password input', async () => {
    renderConsole()
    await waitFor(() => {
      const input = screen.getByPlaceholderText('Enter new JWT secret')
      expect(input).toBeInTheDocument()
      expect(input).toHaveAttribute('type', 'password')
    })
  })

  it('has token expiry number input with default 24', async () => {
    renderConsole()
    await waitFor(() => {
      // Find the number input by its label proximity
      const inputs = screen.getAllByRole('spinbutton')
      // There's one spinbutton: the concurrent patients input
      // The token expiry input has type=number but is wrapped in a label without htmlFor
      const tokenInput = screen.getByDisplayValue('24')
      expect(tokenInput).toBeInTheDocument()
      // Also find concurrent patients (default 10)
      expect(screen.getByDisplayValue('10')).toBeInTheDocument()
    })
  })

  it('EMA slider starts at 0.5', async () => {
    renderConsole()
    await waitFor(() => {
      const slider = screen.getByRole('slider')
      expect(slider).toBeInTheDocument()
      // min=0.1, max=1.0 → default value 0.5
      expect(screen.getByText('0.5')).toBeInTheDocument()
    })
  })

  it('polls health endpoint every 30 seconds', async () => {
    vi.useFakeTimers()
    mockFetch.mockClear()

    mockFetch.mockResolvedValue({
      json: () =>
        Promise.resolve({
          database: 'healthy',
          middleware: 'healthy',
          pulseEngine: 'running',
        }),
    })

    renderConsole()

    // Flush initial useEffect fetch
    await vi.advanceTimersToNextTimerAsync()
    // Verify at least one fetch happened
    expect(mockFetch).toHaveBeenCalled()

    const beforeAdvance = mockFetch.mock.calls.length

    // Advance 30s to trigger setInterval
    vi.advanceTimersByTime(30000)
    await vi.advanceTimersToNextTimerAsync()

    // At least one more call was made after the interval fired
    expect(mockFetch.mock.calls.length).toBeGreaterThan(beforeAdvance)
    vi.useRealTimers()
  })
})
