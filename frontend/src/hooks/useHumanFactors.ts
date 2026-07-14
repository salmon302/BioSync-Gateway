import { useEffect, useRef, useState, useCallback } from 'react'

/**
 * Human Factors Metrics Collection Hook
 * Implements SRS FR-3.9.1 - Passive metrics collector for uFMEA
 * 
 * Features:
 * - Selection latency tracking (time-to-acknowledge)
 * - Input adjustment step counter
 * - JSON export for uFMEA ingestion (SRS FR-3.9.2)
 */

export interface HumanFactorsEvent {
  sessionId: string
  eventType: string
  timestamp: number
  latencyMs?: number
  stepsCount?: number
  component?: string
  metadata?: any
}

export interface HumanFactorsData {
  sessionId: string
  events: HumanFactorsEvent[]
  exportedAt: string
}

export const useHumanFactors = (sessionId: string) => {
  const sessionIdRef = useRef(sessionId)
  const [events, setEvents] = useState<HumanFactorsEvent[]>([])
  const [isCollecting, setIsCollecting] = useState(true)

  useEffect(() => {
    sessionIdRef.current = sessionId
  }, [sessionId])

  /**
   * Track selection latency (time-to-acknowledge)
   * SRS FR-3.9.1: Time-to-acknowledge (ms) recorded
   */
  const trackSelectionLatency = useCallback(
    (startTime: number, component: string, metadata?: any) => {
      const latencyMs = Date.now() - startTime
      const event: HumanFactorsEvent = {
        sessionId: sessionIdRef.current,
        eventType: 'selection_latency',
        timestamp: Date.now(),
        latencyMs,
        component,
        metadata
      }
      setEvents(prev => [...prev, event])
      console.log('Human Factors Event:', event)
    },
    []
  )

  /**
   * Track input adjustment steps
   * SRS FR-3.9.1: Steps-per-adjustment recorded
   */
  const trackInputSteps = useCallback(
    (stepsCount: number, component: string, metadata?: any) => {
      const event: HumanFactorsEvent = {
        sessionId: sessionIdRef.current,
        eventType: 'input_steps',
        timestamp: Date.now(),
        stepsCount,
        component,
        metadata
      }
      setEvents(prev => [...prev, event])
      console.log('Human Factors Event:', event)
    },
    []
  )

  /**
   * Track general user interaction
   */
  const trackInteraction = useCallback(
    (eventType: string, component: string, metadata?: any) => {
      const event: HumanFactorsEvent = {
        sessionId: sessionIdRef.current,
        eventType,
        timestamp: Date.now(),
        component,
        metadata
      }
      setEvents(prev => [...prev, event])
      console.log('Human Factors Event:', event)
    },
    []
  )

  /**
   * Export metrics as JSON for uFMEA ingestion
   * SRS FR-3.9.2: JSON export endpoint
   */
  const exportMetrics = useCallback((): string => {
    const data: HumanFactorsData = {
      sessionId: sessionIdRef.current,
      events,
      exportedAt: new Date().toISOString()
    }
    return JSON.stringify(data, null, 2)
  }, [events])

  /**
   * Download metrics as JSON file
   */
  const downloadMetrics = useCallback(() => {
    const json = exportMetrics()
    const blob = new Blob([json], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `human-factors-${sessionIdRef.current}.json`
    a.click()
    URL.revokeObjectURL(url)
  }, [exportMetrics, sessionIdRef])

  /**
   * Clear collected events
   */
  const clearEvents = useCallback(() => {
    setEvents([])
  }, [])

  return {
    events,
    isCollecting,
    setIsCollecting,
    trackSelectionLatency,
    trackInputSteps,
    trackInteraction,
    exportMetrics,
    downloadMetrics,
    clearEvents
  }
}

export default useHumanFactors
