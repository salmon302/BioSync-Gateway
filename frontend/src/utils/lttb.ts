// SPDX-License-Identifier: MIT
/**
 * Largest-Triangle-Three-Buckets (LTTB) Downsampling Utility
 * Implements SRS FR-3.1.2 — 60 fps at 100k pts/s via downsampling.
 *
 * LTTB reduces the number of data points in a time-series while preserving
 * visual peaks and troughs (anomalies). This allows the chart to render
 * high-frequency telemetry streams at 60 fps without destroying clinical
 * signal integrity.
 *
 * Reference: S. Schubert et al., "Largest-Triangle-Three-Buckets
 * Algorithm for Line Chart Simplification," 2014.
 */

export interface DataPoint {
  timestamp: number
  value: number
}

/**
 * Downsample a time-series using the LTTB algorithm.
 *
 * @param data - Array of [timestamp, value] pairs, sorted by timestamp.
 * @param threshold - Maximum number of points to retain.
 * @returns Downsampled array of [timestamp, value] pairs.
 */
export function lttb(
  data: [number, number][],
  threshold: number
): [number, number][] {
  const n = data.length
  if (threshold >= n || threshold < 2) {
    return data.slice()
  }

  const bucketCount = threshold - 2 // -2 for first and last points
  const bucketSize = (n - 2) / bucketCount

  const resultIndices: number[] = [0]

  for (let i = 0; i < bucketCount; i++) {
    const bucketStart = Math.floor(1 + i * bucketSize)
    let bucketEnd = Math.floor(1 + (i + 1) * bucketSize)
    if (bucketEnd >= n) {
      bucketEnd = n - 1
    }
    if (bucketStart >= bucketEnd) {
      continue
    }

    // Previous selected point
    const prevIdx = resultIndices[resultIndices.length - 1]
    const prevX = data[prevIdx][0]
    const prevY = data[prevIdx][1]

    // Next bucket center of mass
    let nextBucketStart = Math.floor(1 + (i + 1) * bucketSize)
    let nextBucketEnd = Math.floor(1 + (i + 2) * bucketSize)
    if (nextBucketEnd >= n) {
      nextBucketEnd = n - 1
    }
    if (nextBucketStart >= nextBucketEnd) {
      nextBucketStart = Math.max(0, nextBucketEnd - 1)
    }

    let nextAvgX = 0
    let nextAvgY = 0
    for (let j = nextBucketStart; j <= nextBucketEnd; j++) {
      nextAvgX += data[j][0]
      nextAvgY += data[j][1]
    }
    const nextCount = nextBucketEnd - nextBucketStart + 1
    nextAvgX /= nextCount
    nextAvgY /= nextCount

    // Find point in current bucket that maximizes triangle area
    let maxArea = -1
    let maxIdx = bucketStart

    for (let j = bucketStart; j <= bucketEnd; j++) {
      const x1 = prevX
      const y1 = prevY
      const x2 = data[j][0]
      const y2 = data[j][1]
      const x3 = nextAvgX
      const y3 = nextAvgY
      const area = Math.abs((x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2)) / 2.0)
      if (area > maxArea) {
        maxArea = area
        maxIdx = j
      }
    }

    resultIndices.push(maxIdx)
  }

  // Always include last point
  resultIndices.push(n - 1)

  return resultIndices.map(i => data[i])
}

/**
 * Downsample telemetry data points for chart rendering.
 * Each data point has timestamp + optional channel values.
 *
 * @param data - Array of telemetry data points.
 * @param threshold - Maximum number of points to retain.
 * @returns Downsampled array of data points.
 */
export function downsampleTelemetry<T extends { timestamp: number }>(
  data: T[],
  threshold: number
): T[] {
  if (data.length <= threshold) {
    return data.slice()
  }

  // Use timestamps as the x-axis for LTTB
  const points: [number, number][] = data.map(d => [d.timestamp, 0])
  const downsampled = lttb(points, threshold)

  // Map back to original data points by timestamp
  const downsampledTimestamps = new Set(downsampled.map(p => p[0]))
  return data.filter(d => downsampledTimestamps.has(d.timestamp))
}
