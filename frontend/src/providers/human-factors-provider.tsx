import React, { createContext, useContext, ReactNode, useMemo } from 'react'
import { useHumanFactors, HumanFactorsEvent } from '../hooks/useHumanFactors'

/**
 * HumanFactorsProvider — wraps the app and exposes human factors metrics collection
 * to all descendant components via context.
 *
 * Implements SRS FR-3.9.1 / FR-3.9.2 — passive session-scoped uFMEA metrics.
 */

interface HumanFactorsContextType {
  trackSelectionLatency: (startTime: number, component: string, metadata?: any) => void
  trackInputSteps: (stepsCount: number, component: string, metadata?: any) => void
  trackInteraction: (eventType: string, component: string, metadata?: any) => void
  events: HumanFactorsEvent[]
  isCollecting: boolean
  exportMetrics: () => string
  downloadMetrics: () => void
}

const HumanFactorsContext = createContext<HumanFactorsContextType | undefined>(undefined)

export const HumanFactorsProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const sessionId = useMemo(
    () => `session-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    []
  )

  const hf = useHumanFactors(sessionId)

  return (
    <HumanFactorsContext.Provider value={hf}>
      {children}
    </HumanFactorsContext.Provider>
  )
}

export const useHumanFactorsContext = (): HumanFactorsContextType => {
  const ctx = useContext(HumanFactorsContext)
  if (!ctx) {
    throw new Error('useHumanFactorsContext must be used within a HumanFactorsProvider')
  }
  return ctx
}

export default HumanFactorsProvider
