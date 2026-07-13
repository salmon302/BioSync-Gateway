import { useEffect, useRef } from 'react'

/**
 * Human Factors Metrics Collection Hook
 * Implements SRS FR-3.9.1 - Passive metrics collector for uFMEA
 * 
 * Phase 0: Stub implementation
 * Full implementation in Phase 3
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

export const useHumanFactors = (sessionId: string) => {
  const sessionIdRef = useRef(sessionId)

  useEffect(() => {
    sessionIdRef.current = sessionId
  }, [sessionId])

  /**
   * Track selection latency (time-to-acknowledge)
   * SRS FR-3.9.1: Time-to-acknowledge (ms) recorded
   */
  const trackSelectionLatency = (
    startTime: number,
    component: string,
    metadata?: any
  ) => {
    const latencyMs = Date.now() - startTime
    const event: HumanFactorsEvent = {
      sessionId: sessionIdRef.current,
      eventType: 'selection_latency',
      timestamp: Date.now(),
      latencyMs,
      component,
      metadata
    }
    console.log('Human Factors Event:', event)
    // Future: Send to backend /api/human-factors endpoint
  }

  /**
   * Track input adjustment steps
   * SRS FR-3.9.1: Steps-per-adjustment recorded
   */
  const trackInputSteps = (
    stepsCount: number,
    component: string,
    metadata?: any
  ) => {
    const event: HumanFactorsEvent = {
      sessionId: sessionIdRef.current,
      eventType: 'input_steps',
      timestamp: Date.now(),
      stepsCount,
      component,
      metadata
    }
    console.log('Human Factors Event:', event)
    // Future: Send to backend
  }

  /**
   * Track general user interaction
   */
  const trackInteraction = (
    eventType: string,
    component: string,
    metadata?: any
  ) => {
    const event: HumanFactorsEvent = {
      sessionId: sessionIdRef.current,
      eventType,
      timestamp: Date.now(),
      component,
      metadata
    }
    console.log('Human Factors Event:', event)
    // Future: Send to backend
  }

  return {
    trackSelectionLatency,
    trackInputSteps,
    trackInteraction
  }
}

export default useHumanFactors
