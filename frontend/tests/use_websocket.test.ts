import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useWebSocket } from '../src/hooks/useWebSocket'
import { renderHook, act } from '@testing-library/react'

const wsInstances: MockWebSocket[] = []

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
    wsInstances.push(this)
  }

  send(_data: string) {
    // no-op
  }

  close() {
    this.readyState = MockWebSocket.CLOSED
    this.onclose?.({ code: 1000 } as any)
  }
}

const originalWebSocket = globalThis.WebSocket

describe('useWebSocket', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    wsInstances.length = 0
    ;(globalThis as any).WebSocket = MockWebSocket
  })

  afterEach(() => {
    vi.useRealTimers()
    globalThis.WebSocket = originalWebSocket
  })

  it('connects on mount', () => {
    const { result } = renderHook(() => useWebSocket('ws://localhost:8000/ws'))

    expect(wsInstances.length).toBe(1)
    expect(wsInstances[0].url).toBe('ws://localhost:8000/ws')
    expect(result.current.isConnected).toBe(false)
  })

  it('receives and parses JSON messages', () => {
    const { result } = renderHook(() => useWebSocket('ws://localhost:8000/ws'))

    act(() => {
      const ws = wsInstances[0]
      ws.onopen?.({} as any)
      ws.readyState = MockWebSocket.OPEN
    })

    act(() => {
      wsInstances[0].onmessage?.({
        data: JSON.stringify({ type: 'telemetry', payload: { value: 42 } }),
      } as any)
    })

    expect(result.current.messages).toHaveLength(1)
    expect(result.current.messages[0].type).toBe('telemetry')
    expect(result.current.messages[0].payload.value).toBe(42)
  })

  it('handles non-JSON messages gracefully', () => {
    const { result } = renderHook(() => useWebSocket('ws://localhost:8000/ws'))

    act(() => {
      wsInstances[0].onopen?.({} as any)
      wsInstances[0].onmessage?.({
        data: 'plain text not json',
      } as any)
    })

    expect(result.current.messages).toHaveLength(1)
    expect(result.current.messages[0].type).toBe('data')
    expect(result.current.messages[0].payload).toBe('plain text not json')
  })

  it('sends messages without error', () => {
    const { result } = renderHook(() => useWebSocket('ws://localhost:8000/ws'))

    act(() => {
      wsInstances[0].onopen?.({} as any)
      wsInstances[0].readyState = MockWebSocket.OPEN
    })

    expect(() =>
      act(() => {
        result.current.sendMessage({ type: 'subscribe', channels: ['pressure'] })
      })
    ).not.toThrow()
  })

  it('calls disconnect to close websocket', () => {
    const { result } = renderHook(() => useWebSocket('ws://localhost:8000/ws'))

    act(() => {
      result.current.disconnect()
    })

    expect(wsInstances[0].readyState).toBe(MockWebSocket.CLOSED)
  })

  it('clears accumulated messages', () => {
    const { result } = renderHook(() => useWebSocket('ws://localhost:8000/ws'))

    act(() => {
      wsInstances[0].onopen?.({} as any)
      wsInstances[0].onmessage?.({
        data: JSON.stringify({ type: 'test', payload: 'hello' }),
      } as any)
    })

    expect(result.current.messages).toHaveLength(1)

    act(() => {
      result.current.clearMessages()
    })

    expect(result.current.messages).toHaveLength(0)
  })

  it('triggers auto-reconnect on close', () => {
    const { result } = renderHook(() => useWebSocket('ws://localhost:8000/ws'))

    act(() => {
      wsInstances[0].onopen?.({} as any)
      wsInstances[0].onclose?.({ code: 1006 } as any)
    })

    expect(result.current.isConnected).toBe(false)

    // setTimeout fires reconnect
    act(() => {
      vi.advanceTimersByTime(2000)
    })

    expect(wsInstances.length).toBe(2)
  })
})
