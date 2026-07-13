import React, { createContext, useContext, ReactNode } from 'react'
import * as echarts from 'echarts'

/**
 * Chart Provider Abstraction
 * Implements SRS FR-3.1.3 - Chart provider abstraction for swappable ECharts ↔ SciChart
 * 
 * Phase 0: ECharts implementation
 * Future: Add SciChart provider option
 */

export interface ChartConfig {
  type: 'echarts' | 'scichart'
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
      if (config.type === 'echarts') {
        const chart = echarts.init(container)
        if (options) {
          chart.setOption(options)
        }
        return chart
      }
      // Future: Add SciChart initialization
      throw new Error(`Chart type ${config.type} not yet implemented`)
    },
    
    updateData: (chart: any, data: any) => {
      if (config.type === 'echarts') {
        chart.setOption(data)
      }
      // Future: Add SciChart update
    },
    
    dispose: (chart: any) => {
      if (config.type === 'echarts') {
        chart.dispose()
      }
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
