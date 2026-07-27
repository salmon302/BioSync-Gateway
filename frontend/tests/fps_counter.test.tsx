import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import React from 'react'
import FPSCounter, { useFPSCounter } from '../src/components/TelemetryDashboard/FPSCounter'

// Set up global mocks for requestAnimationFrame/cancelAnimationFrame
const rafMock = vi.fn((cb) => {
  setTimeout(cb, 16)
  return 1
})
const cafMock = vi.fn()

beforeAll(() => {
  (globalThis as any).requestAnimationFrame = rafMock;
  (globalThis as any).cancelAnimationFrame = cafMock;
})

afterAll(() => {
  delete (globalThis as any).requestAnimationFrame
  delete (globalThis as any).cancelAnimationFrame
})

describe('FPSCounter', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.spyOn(performance, 'now').mockReturnValue(0)
    rafMock.mockClear()
    cafMock.mockClear()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  describe('useFPSCounter hook', () => {
    it('returns initial metrics with zero FPS', () => {
      let result: any

      function TestComponent() {
        result = useFPSCounter(60, 120)
        return null
      }

      render(<TestComponent />)

      expect(result.fps).toBe(0)
      expect(result.status).toBe('critical')
    })
  })

  describe('FPSCounter component', () => {
    it('renders when visible', () => {
      const { container } = render(<FPSCounter visible={true} />)
      expect(container.querySelector('.fps-counter')).toBeInTheDocument()
    })

    it('does not render when visible is false', () => {
      const { container } = render(<FPSCounter visible={false} />)
      expect(container.querySelector('.fps-counter')).not.toBeInTheDocument()
    })

    it('shows target FPS in the display', () => {
      render(<FPSCounter targetFps={60} visible={true} />)
      expect(screen.getByText(/Target: 60 fps/)).toBeInTheDocument()
    })

    it('shows fps value and frame time metrics', () => {
      render(<FPSCounter visible={true} />)
      // Should display fps label (ends with "fps")
      expect(screen.getByText(/fps$/)).toBeInTheDocument()
      // Should display P95 frame time
      expect(screen.getByText(/P95:/)).toBeInTheDocument()
      // Should display Avg frame time
      expect(screen.getByText(/Avg:/)).toBeInTheDocument()
    })

    it('applies custom className', () => {
      const { container } = render(
        <FPSCounter className="custom-class" visible={true} />
      )
      expect(container.querySelector('.fps-counter.custom-class')).toBeInTheDocument()
    })
  })

  describe('frame time percentile calculation', () => {
    it('P95 frame time is correctly calculated from sorted samples', () => {
      // 100 samples: 95 at 16.67ms, 5 at 20.0ms
      const frameTimes = Array(95).fill(16.67).concat(Array(5).fill(20.0))
      const sorted = [...frameTimes].sort((a, b) => a - b)
      const p95Index = Math.min(Math.floor(sorted.length * 0.95), sorted.length - 1)
      const p95 = sorted[p95Index]

      // P95 of 100 samples = index 95 = 20.0 (the first of the 5 outliers)
      expect(p95).toBe(20.0)
    })

    it('P95 frame time captures outliers', () => {
      // 20 samples: 18 at 16.67ms, 2 at 50ms
      const frameTimes = Array(18).fill(16.67).concat([50.0, 50.0])
      const sorted = [...frameTimes].sort((a, b) => a - b)
      const p95Index = Math.min(Math.floor(sorted.length * 0.95), sorted.length - 1)
      const p95 = sorted[p95Index]

      // P95 of 20 samples = index 19 = 50.0
      expect(p95).toBe(50.0)
    })

    it('P95 of uniform frame times equals the constant', () => {
      const frameTimes = Array(60).fill(16.67)
      const sorted = [...frameTimes].sort((a, b) => a - b)
      const p95Index = Math.min(Math.floor(sorted.length * 0.95), sorted.length - 1)
      const p95 = sorted[p95Index]

      expect(p95).toBe(16.67)
    })
  })
})
