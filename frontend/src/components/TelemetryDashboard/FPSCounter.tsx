// SPDX-License-Identifier: MIT
import React, { useEffect, useRef, useState, useCallback } from 'react'

/**
 * FPSCounter Component
 * Implements SRS NFR-P2 — WebGL rendering frame rate ≥ 60 fps sustained.
 *
 * Features:
 * - Measures FPS via requestAnimationFrame for accurate frame timing.
 * - Tracks frame-time variance and P95 frame time.
 * - Color-coded status: green (≥60 fps), yellow (55–59 fps), red (<55 fps).
 * - Configurable target FPS and sample window.
 */

export interface FPSCounterProps {
  /** Target frame rate (default 60 per SRS NFR-P2). */
  targetFps?: number
  /** Number of recent frame times to retain for P95 calculation (default 120). */
  sampleSize?: number
  /** Optional CSS class name for the container. */
  className?: string
  /** Whether to render the counter (default true). */
  visible?: boolean
}

export interface FPSMetrics {
  fps: number
  avgFrameTimeMs: number
  p95FrameTimeMs: number
  minFrameTimeMs: number
  maxFrameTimeMs: number
  status: 'good' | 'warning' | 'critical'
}

const DEFAULT_TARGET_FPS = 60
const DEFAULT_SAMPLE_SIZE = 120
const WARNING_FPS = 55
const CRITICAL_FPS = 30

/**
 * Hook that measures frame rate using requestAnimationFrame.
 * Returns current FPS metrics and a ref to attach to the render loop.
 */
export function useFPSCounter(
  targetFps: number = DEFAULT_TARGET_FPS,
  sampleSize: number = DEFAULT_SAMPLE_SIZE,
): FPSMetrics & { frameRef: React.MutableRefObject<number | null> } {
  const [metrics, setMetrics] = useState<FPSMetrics>({
    fps: 0,
    avgFrameTimeMs: 0,
    p95FrameTimeMs: 0,
    minFrameTimeMs: 0,
    maxFrameTimeMs: 0,
    status: 'critical',
  })

  const frameTimesRef = useRef<number[]>([])
  const lastFrameTimeRef = useRef<number>(0)
  const frameCountRef = useRef<number>(0)
  const lastFpsUpdateRef = useRef<number>(0)
  const frameRef = useRef<number | null>(null)

  const updateMetrics = useCallback(() => {
    const now = performance.now()
    const delta = now - lastFrameTimeRef.current

    if (delta > 0 && delta < 1000) {
      frameTimesRef.current.push(delta)
      if (frameTimesRef.current.length > sampleSize) {
        frameTimesRef.current.shift()
      }
    }

    lastFrameTimeRef.current = now
    frameCountRef.current += 1

    // Update FPS display once per second
    if (now - lastFpsUpdateRef.current >= 1000) {
      const times = frameTimesRef.current
      if (times.length > 0) {
        const sorted = [...times].sort((a, b) => a - b)
        const avg = times.reduce((a, b) => a + b, 0) / times.length
        const p95Index = Math.min(
          Math.floor(sorted.length * 0.95),
          sorted.length - 1,
        )
        const p95 = sorted[p95Index]
        const fps = 1000 / avg

        let status: 'good' | 'warning' | 'critical'
        if (fps >= targetFps) {
          status = 'good'
        } else if (fps >= WARNING_FPS) {
          status = 'warning'
        } else if (fps >= CRITICAL_FPS) {
          status = 'critical'
        } else {
          status = 'critical'
        }

        setMetrics({
          fps: Math.round(fps * 10) / 10,
          avgFrameTimeMs: Math.round(avg * 100) / 100,
          p95FrameTimeMs: Math.round(p95 * 100) / 100,
          minFrameTimeMs: Math.round(sorted[0] * 100) / 100,
          maxFrameTimeMs: Math.round(sorted[sorted.length - 1] * 100) / 100,
          status,
        })
      }

      frameCountRef.current = 0
      lastFpsUpdateRef.current = now
    }

    frameRef.current = requestAnimationFrame(updateMetrics)
  }, [targetFps, sampleSize])

  useEffect(() => {
    lastFrameTimeRef.current = performance.now()
    lastFpsUpdateRef.current = performance.now()
    frameRef.current = requestAnimationFrame(updateMetrics)

    return () => {
      if (frameRef.current !== null) {
        cancelAnimationFrame(frameRef.current)
      }
    }
  }, [updateMetrics])

  return { ...metrics, frameRef }
}

/**
 * FPSCounter Component
 *
 * Displays real-time FPS with color-coded status indicators.
 * Integrates with the TelemetryDashboard for NFR-P2 compliance monitoring.
 */
const FPSCounter: React.FC<FPSCounterProps> = ({
  targetFps = DEFAULT_TARGET_FPS,
  sampleSize = DEFAULT_SAMPLE_SIZE,
  className = '',
  visible = true,
}) => {
  const { fps, avgFrameTimeMs, p95FrameTimeMs, status } = useFPSCounter(
    targetFps,
    sampleSize,
  )

  if (!visible) return null

  const statusColor = {
    good: '#28a745',
    warning: '#ffc107',
    critical: '#dc3545',
  }[status]

  const targetMet = fps >= targetFps

  return (
    <div
      className={`fps-counter ${className}`}
      style={{
        position: 'absolute',
        top: '10px',
        right: '10px',
        padding: '8px 12px',
        borderRadius: '6px',
        backgroundColor: 'rgba(0, 0, 0, 0.7)',
        color: '#fff',
        fontSize: '13px',
        fontFamily: 'monospace',
        zIndex: 1000,
        minWidth: '140px',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
        <span
          style={{
            width: '8px',
            height: '8px',
            borderRadius: '50%',
            backgroundColor: statusColor,
            boxShadow: `0 0 6px ${statusColor}`,
          }}
        />
        <span style={{ fontWeight: 'bold' }}>{fps.toFixed(1)} fps</span>
      </div>
      <div style={{ fontSize: '11px', color: '#aaa', marginTop: '2px' }}>
        P95: {p95FrameTimeMs.toFixed(1)}ms | Avg: {avgFrameTimeMs.toFixed(1)}ms
      </div>
      <div style={{ fontSize: '11px', marginTop: '2px' }}>
        Target: {targetFps} fps —{' '}
        <span style={{ color: targetMet ? statusColor : '#dc3545' }}>
          {targetMet ? 'MET' : 'NOT MET'}
        </span>
      </div>
    </div>
  )
}

export default FPSCounter
