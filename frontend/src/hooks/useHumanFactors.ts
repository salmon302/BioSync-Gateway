import { useEffect, useRef, useState, useCallback } from 'react'

/**
 * Human Factors Metrics Collection Hook
 * Implements SRS FR-3.9.1 - Passive metrics collector for uFMEA
 * Implements SRS FR-3.9.2 - uFMEA JSON export
 *
 * Features:
 * - Selection latency tracking (time-to-acknowledge)
 * - Input adjustment step counter
 * - JSON export for uFMEA ingestion (SRS FR-3.9.2)
 * - Debounced/batched POST to backend /api/human-factors/events
 *   so the export endpoint has meaningful data
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

/** Batch size threshold — flush when this many events accumulate. */
const BATCH_SIZE_THRESHOLD = 10
/** Debounce interval (ms) — flush after this many ms of inactivity. */
const DEBOUNCE_MS = 5000

export const useHumanFactors = (sessionId: string) => {
  const sessionIdRef = useRef(sessionId)
  const [events, setEvents] = useState<HumanFactorsEvent[]>([])
  const [isCollecting, setIsCollecting] = useState(true)

  /** Buffer of events queued for backend POST (not yet sent). */
  const batchRef = useRef<HumanFactorsEvent[]>([])
  /** Timer handle for the debounce flush. */
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    sessionIdRef.current = sessionId
  }, [sessionId])

  // --- Backend ingestion --------------------------------------------------

  /**
   * POST the current batch to the backend /api/human-factors/events endpoint.
   * Converts camelCase frontend fields to snake_case backend fields.
   * Silently swallows network errors so UI instrumentation never breaks UX.
   */
  const postEvents = useCallback(async (batch: HumanFactorsEvent[]) => {
    if (batch.length === 0) return

    const token = typeof window !== 'undefined'
      ? localStorage.getItem('biosync_token')
      : null

    const payload = {
      events: batch.map(ev => ({
        session_id: ev.sessionId,
        event_type: ev.eventType,
        timestamp: ev.timestamp,
        ...(ev.latencyMs !== undefined && { latency_ms: ev.latencyMs }),
        ...(ev.stepsCount !== undefined && { steps_count: ev.stepsCount }),
        ...(ev.component !== undefined && { component: ev.component }),
        ...(ev.metadata !== undefined && { metadata: ev.metadata }),
      })),
    }

    try {
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      }
      if (token) {
        headers['Authorization'] = `Bearer ${token}`
      }

      const resp = await fetch('/api/human-factors/events', {
        method: 'POST',
        headers,
        body: JSON.stringify(payload),
      })

      if (!resp.ok) {
        console.warn(
          `[useHumanFactors] Backend ingest returned ${resp.status} — ` +
          `events remain in local state only.`
        )
      }
    } catch (err) {
      // Network error or backend down — events are still in local state.
      // This is intentional: human-factors collection must never break the UI.
      console.debug('[useHumanFactors] Backend ingest failed:', err)
    }
  }, [])

  /**
   * Flush the current batch to the backend immediately and clear the
   * debounce timer.
   */
  const flushEvents = useCallback(() => {
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current)
      debounceTimerRef.current = null
    }
    const batch = batchRef.current.splice(0)
    if (batch.length > 0) {
      void postEvents(batch)
    }
  }, [postEvents])

  /**
   * Queue an event into the batch buffer. If the batch reaches the
   * size threshold, flush immediately. Otherwise, (re)start the debounce
   * timer.
   */
  const enqueueEvent = useCallback((event: HumanFactorsEvent) => {
    batchRef.current.push(event)

    if (batchRef.current.length >= BATCH_SIZE_THRESHOLD) {
      void flushEvents()
    } else {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current)
      }
      debounceTimerRef.current = setTimeout(() => {
        void flushEvents()
      }, DEBOUNCE_MS)
    }
  }, [flushEvents])

  // Flush on page unload using sendBeacon for best-effort delivery
  useEffect(() => {
    const handleBeforeUnload = () => {
      const batch = batchRef.current.splice(0)
      if (batch.length === 0) return

      const token = typeof window !== 'undefined'
        ? localStorage.getItem('biosync_token')
        : null

      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      }
      if (token) {
        headers['Authorization'] = `Bearer ${token}`
      }

      const payload = JSON.stringify({
        events: batch.map(ev => ({
          session_id: ev.sessionId,
          event_type: ev.eventType,
          timestamp: ev.timestamp,
          ...(ev.latencyMs !== undefined && { latency_ms: ev.latencyMs }),
          ...(ev.stepsCount !== undefined && { steps_count: ev.stepsCount }),
          ...(ev.component !== undefined && { component: ev.component }),
          ...(ev.metadata !== undefined && { metadata: ev.metadata }),
        })),
      })

      // sendBeacon is best-effort and works during page teardown
      const blob = new Blob([payload], { type: 'application/json' })
      navigator.sendBeacon('/api/human-factors/events', blob)
    }

    window.addEventListener('beforeunload', handleBeforeUnload)
    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload)
    }
  }, [])

  // Cleanup debounce timer on unmount
  useEffect(() => {
    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current)
      }
    }
  }, [])

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
      enqueueEvent(event)
    },
    [enqueueEvent]
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
      enqueueEvent(event)
    },
    [enqueueEvent]
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
      enqueueEvent(event)
    },
    [enqueueEvent]
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
    clearEvents,
    flushEvents,
  }
}

export default useHumanFactors
