import { useEffect, useRef } from 'react'
import { init, use as registerEChartsModules } from 'echarts/core'
import type { ECharts, EChartsCoreOption } from 'echarts/core'
import { LineChart, PieChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

registerEChartsModules([LineChart, PieChart, GridComponent, LegendComponent, TooltipComponent, CanvasRenderer])

export function EChart({ option, height, label }: { option: EChartsCoreOption; height: number; label: string }) {
  const element = useRef<HTMLDivElement>(null)
  const chart = useRef<ECharts | null>(null)
  useEffect(() => {
    if (!element.current) return
    chart.current = init(element.current)
    const observer = new ResizeObserver(() => chart.current?.resize())
    observer.observe(element.current)
    return () => { observer.disconnect(); chart.current?.dispose(); chart.current = null }
  }, [])
  useEffect(() => { chart.current?.setOption(option, { notMerge: true }) }, [option])
  return <div ref={element} role="img" aria-label={label} style={{ height }} />
}
