import { useEffect, useRef, useState, useCallback } from 'react'

/**
 * WebSocket Hook with Auto-Reconnect and Message Replay
 * Implements SRS NFR-R4 - WebSocket with auto-reconnect
 * 
 * Phase 0: Stub implementation
 * Full implementation in Phase 3
 */

export interface WebSocketMessage {
  type: string
  payload: any
  timestamp: number
}

export interface UseWebSocketReturn {
  isConnected: boolean
  messages: WebSocketMessage[]
  sendMessage: (message: any) => void
  connect: () => void
  disconnect: () => void
}

export const useWebSocket = (url: string): UseWebSocketReturn => {
  const [isConnected, setIsConnected] = useState(false)
  const [messages, setMessages] = useState<WebSocketMessage[]>([])
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectAttempts = useRef(0)
  const maxReconnectAttempts = 5

  const connect = useCallback(() => {
    try {
      wsRef.current = new WebSocket(url)

      wsRef.current.onopen = () => {
        console.log('WebSocket connected')
        setIsConnected(true)
        reconnectAttempts.current = 0
      }

      wsRef.current.onmessage = (event) => {
        const message: WebSocketMessage = {
          type: 'data',
          payload: event.data,
          timestamp: Date.now()
        }
        setMessages((prev) => [...prev, message])
      }

      wsRef.current.onclose = () => {
        console.log('WebSocket disconnected')
        setIsConnected(false)
        
        // Auto-reconnect logic
        if (reconnectAttempts.current < maxReconnectAttempts) {
          reconnectAttempts.current++
          setTimeout(connect, 1000 * reconnectAttempts.current)
        }
      }

      wsRef.current.onerror = (error) => {
        console.error('WebSocket error:', error)
      }
    } catch (error) {
      console.error('Failed to connect WebSocket:', error)
    }
  }, [url])

  const disconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
  }, [])

  const sendMessage = useCallback((message: any) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message))
    }
  }, [])

  useEffect(() => {
    // Auto-connect on mount
    connect()

    // Cleanup on unmount
    return () => {
      disconnect()
    }
  }, [connect, disconnect])

  return {
    isConnected,
    messages,
    sendMessage,
    connect,
    disconnect
  }
}

export default useWebSocket
