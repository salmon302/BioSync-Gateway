import { describe, it, expect, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useHumanFactors } from '../src/hooks/useHumanFactors'

describe('useHumanFactors', () => {
  const sessionId = 'test-session-123'

  beforeEach(() => {
    // Reset Date.now predictability
  })

  it('tracks selection latency events', () => {
    const { result } = renderHook(() => useHumanFactors(sessionId))

    const startTime = Date.now() - 350 // 350ms ago

    act(() => {
      result.current.trackSelectionLatency(startTime, 'MicroplateEditor', {
        row: 2,
        col: 5,
      })
    })

    expect(result.current.events).toHaveLength(1)
    const event = result.current.events[0]
    expect(event.eventType).toBe('selection_latency')
    expect(event.sessionId).toBe(sessionId)
    expect(event.component).toBe('MicroplateEditor')
    expect(event.latencyMs).toBeGreaterThanOrEqual(350)
    expect(event.metadata).toEqual({ row: 2, col: 5 })
  })

  it('tracks input step events', () => {
    const { result } = renderHook(() => useHumanFactors(sessionId))

    act(() => {
      result.current.trackInputSteps(7, 'AdminConsole', { field: 'emaAlpha' })
    })

    expect(result.current.events).toHaveLength(1)
    const event = result.current.events[0]
    expect(event.eventType).toBe('input_steps')
    expect(event.stepsCount).toBe(7)
    expect(event.component).toBe('AdminConsole')
  })

  it('tracks generic interaction events', () => {
    const { result } = renderHook(() => useHumanFactors(sessionId))

    act(() => {
      result.current.trackInteraction('csv_import', 'MicroplateEditor', {
        wellsImported: 48,
      })
    })

    expect(result.current.events).toHaveLength(1)
    expect(result.current.events[0].eventType).toBe('csv_import')
  })

  it('accumulates multiple events in order', () => {
    const { result } = renderHook(() => useHumanFactors(sessionId))

    act(() => {
      result.current.trackSelectionLatency(Date.now() - 100, 'CompA', null)
    })
    act(() => {
      result.current.trackInteraction('click', 'CompB', null)
    })
    act(() => {
      result.current.trackInputSteps(3, 'CompC', null)
    })

    expect(result.current.events).toHaveLength(3)
    expect(result.current.events[0].eventType).toBe('selection_latency')
    expect(result.current.events[1].eventType).toBe('click')
    expect(result.current.events[2].eventType).toBe('input_steps')
  })

  it('exports metrics as valid JSON', () => {
    const { result } = renderHook(() => useHumanFactors(sessionId))

    act(() => {
      result.current.trackSelectionLatency(Date.now() - 200, 'Test', null)
    })

    const json = result.current.exportMetrics()
    const parsed = JSON.parse(json)

    expect(parsed.sessionId).toBe(sessionId)
    expect(parsed.events).toHaveLength(1)
    expect(parsed.exportedAt).toBeDefined()
    expect(new Date(parsed.exportedAt).getTime()).not.toBeNaN()
  })

  it('clearEvents empties the event list', () => {
    const { result } = renderHook(() => useHumanFactors(sessionId))

    act(() => {
      result.current.trackInteraction('click', 'Test', null)
    })
    expect(result.current.events).toHaveLength(1)

    act(() => {
      result.current.clearEvents()
    })
    expect(result.current.events).toHaveLength(0)
  })

  it('updates sessionId when prop changes', () => {
    const { result, rerender } = renderHook(
      ({ sid }) => useHumanFactors(sid),
      { initialProps: { sid: 'session-a' } }
    )

    act(() => {
      result.current.trackInteraction('test', 'Comp', null)
    })

    const jsonA = JSON.parse(result.current.exportMetrics())
    expect(jsonA.sessionId).toBe('session-a')

    rerender({ sid: 'session-b' })

    act(() => {
      result.current.trackInteraction('test', 'Comp', null)
    })

    const jsonB = JSON.parse(result.current.exportMetrics())
    expect(jsonB.sessionId).toBe('session-b')
  })

  it('downloadMetrics creates a download link', () => {
    const { result } = renderHook(() => useHumanFactors(sessionId))

    // Mock URL.createObjectURL and revokeObjectURL
    const createObjectURL = vi
      .spyOn(URL, 'createObjectURL')
      .mockReturnValue('blob:test')
    const revokeObjectURL = vi.spyOn(URL, 'revokeObjectURL')

    // Mock document.createElement for the anchor
    const mockAnchor = {
      href: '',
      download: '',
      click: vi.fn(),
    } as any
    const createElement = vi
      .spyOn(document, 'createElement')
      .mockReturnValue(mockAnchor)

    act(() => {
      result.current.downloadMetrics()
    })

    expect(createObjectURL).toHaveBeenCalled()
    expect(mockAnchor.download).toContain('human-factors-test-session-123')
    expect(mockAnchor.click).toHaveBeenCalled()
    expect(revokeObjectURL).toHaveBeenCalled()

    createObjectURL.mockRestore()
    revokeObjectURL.mockRestore()
    createElement.mockRestore()
  })
})
