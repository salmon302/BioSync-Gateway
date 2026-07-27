import React, { createContext, useContext, ReactNode } from 'react'
import * as echarts from 'echarts'

/**
 * Chart Provider Abstraction
 * Implements SRS FR-3.1.3 - Chart provider abstraction (ECharts-only)
 *
 * Approved deviation from SRS FR-3.1.3: SciChart backend removed.
 * ECharts (Apache ECharts 5) is the sole rendering backend. The provider
 * abstraction interface is retained for future swappability, but only
 * the 'echarts' type is supported at runtime.
 * See: REMAINING_WORK.md §0 (deviation log), DEVELOPMENT_PLAN.md §2
 */

export interface ChartConfig {
  type: 'echarts'
  options?: any
}

export interface ChartInstance {
  createChart: (container: HTMLElement, options?: any) => any
  updateData: (chart: any, data: any) => void
  dispose: (chart: any) => void
}

interface ChartProviderContextType {
  config: ChartConfig
  createChart: (container: HTMLElement, options?: any) => any
  updateData: (chart: any, data: any) => void
  dispose: (chart: any) => void
}

const ChartProviderContext = createContext<ChartProviderContextType | undefined>(undefined)

/**
 * Chart Provider Component
 * Wraps the application and provides chart abstraction context
 */
export const ChartProvider: React.FC<{
  config?: ChartConfig
  children: ReactNode
}> = ({ config = { type: 'echarts' }, children }) => {
  const chartInstance: ChartInstance = {
    createChart: (container: HTMLElement, options?: any) => {
      const chart = echarts.init(container)
      if (options) {
        chart.setOption(options)
      }
      return chart
    },
    
    updateData: (chart: any, data: any) => {
      chart.setOption(data)
    },
    
    dispose: (chart: any) => {
      chart.dispose()
    }
  }

  return (
    <ChartProviderContext.Provider
      value={{
        config,
        createChart: chartInstance.createChart,
        updateData: chartInstance.updateData,
        dispose: chartInstance.dispose
      }}
    >
      {children}
    </ChartProviderContext.Provider>
  )
}

/**
 * Hook to use chart provider
 */
export const useChart = (): ChartProviderContextType => {
  const context = useContext(ChartProviderContext)
  if (!context) {
    throw new Error('useChart must be used within a ChartProvider')
  }
  return context
}

export default ChartProvider
