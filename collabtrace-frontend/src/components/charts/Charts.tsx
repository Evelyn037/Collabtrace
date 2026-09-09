import { useEffect, useMemo, useState } from 'react'
import type { EChartsCoreOption } from 'echarts/core'
import type { Contributor, RCIContributor, TimelinePoint } from '../../types'
import { EChart } from './EChart'

const colors = ['#e8ff3f', '#66784d', '#91a865', '#cdc9bc']

export function ContributionDonut({ contributor }: { contributor: Contributor | RCIContributor }) {
  const reducedMotion = typeof window !== 'undefined' && typeof window.matchMedia === 'function' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
  const compact = typeof window !== 'undefined' && window.innerWidth <= 600
  const [revealed, setRevealed] = useState(reducedMotion)
  const isRCI = 'composition' in contributor
  const data = useMemo(() => isRCI ? [
    { name: 'Code Implementation', value: contributor.composition.code },
    { name: 'Pull Request', value: contributor.composition.pr },
    { name: 'Issue', value: contributor.composition.issue },
    { name: 'Code Review', value: contributor.composition.review },
  ] : [
    { name: 'Commit', value: contributor.commits }, { name: 'Pull Request', value: contributor.pull_requests },
    { name: 'Issue', value: contributor.issues }, { name: 'Code Review', value: contributor.reviews },
  ], [contributor, isRCI])
  useEffect(() => {
    if (reducedMotion) { setRevealed(true); return }
    let timer = 0
    const frame = window.requestAnimationFrame(() => { timer = window.setTimeout(() => setRevealed(true), 120) })
    return () => { window.cancelAnimationFrame(frame); window.clearTimeout(timer) }
  }, [contributor.github_username, reducedMotion])
  const animatedData = useMemo(() => data.map((item) => ({ ...item, value: revealed ? item.value : 0 })), [data, revealed])
  const option = useMemo<EChartsCoreOption>(() => ({
    animation: !reducedMotion,
    animationDuration: 0,
    animationDurationUpdate: reducedMotion ? 0 : 760,
    animationEasingUpdate: 'cubicOut',
    color: colors, tooltip: { trigger: 'item' }, legend: compact
      ? { orient: 'horizontal', left: 'center', bottom: 0, itemWidth: 12, textStyle: { fontSize: 10 } }
      : { orient: 'vertical', right: 4, top: 'center' },
    series: [{ type: 'pie', animationType: 'expansion', radius: compact ? ['34%', '54%'] : ['52%', '75%'], center: compact ? ['50%', '38%'] : ['35%', '50%'], avoidLabelOverlap: true,
      label: { show: true, position: 'center', formatter: isRCI ? 'Contribution\nMix' : `${contributor.total_events}\nEvents`, fontSize: compact ? 13 : 16, fontWeight: 700 },
      data: animatedData }],
  }), [animatedData, compact, contributor.total_events, isRCI, reducedMotion])
  return <div className="chart-with-summary" data-reduced-motion={reducedMotion} data-reveal-state={revealed ? 'complete' : 'collapsed'}><EChart height={250} option={option} label={isRCI ? '未加权贡献构成' : `贡献构成，总计 ${contributor.total_events} 次活动`}/><ul className="chart-a11y">{data.map((item) => <li key={item.name}>{item.name} {item.value}</li>)}</ul></div>
}

export function ActivityTimeline({ data, compact = false }: { data: TimelinePoint[]; compact?: boolean }) {
  return <EChart height={compact ? 260 : 330} label="每日贡献活动折线图" option={{
    color: ['#66784d', '#e8ff3f'],
    tooltip: { trigger: 'axis' },
    grid: { left: 42, right: 18, top: 24, bottom: 36 },
    xAxis: { type: 'category', data: data.map((point) => point.date), axisLine: { lineStyle: { color: '#cdc9bc' } }, axisLabel: { color: '#817f78' } },
    yAxis: { type: 'value', minInterval: 1, splitLine: { lineStyle: { color: '#efede7' } }, axisLabel: { color: '#817f78' } },
    series: [{ name: 'Total', type: 'line', smooth: true, symbolSize: 8, areaStyle: { color: 'rgba(145,168,101,.16)' }, lineStyle: { width: 3 }, data: data.map((point) => point.total) }],
  }} />
}
