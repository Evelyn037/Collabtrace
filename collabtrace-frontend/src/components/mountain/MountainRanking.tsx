import { ArrowUpRight, UserRound } from 'lucide-react'
import type { RCIContributor } from '../../types'
import { RankMedal } from './RankMedal'

const VIEWBOX_WIDTH = 1200
const VIEWBOX_HEIGHT = 520

export const rankedPeakLayout = {
  1: { x: 820, peakY: 54, markerY: 116 },
  2: { x: 468, peakY: 126, markerY: 183 },
  3: { x: 214, peakY: 190, markerY: 247 },
  4: { x: 990, peakY: 236, markerY: 293 },
} as const

function markerPosition(rank: keyof typeof rankedPeakLayout) {
  const anchor = rankedPeakLayout[rank]
  return { left: `clamp(58px, ${anchor.x / VIEWBOX_WIDTH * 100}%, calc(100% - 58px))`, top: `${anchor.markerY / VIEWBOX_HEIGHT * 100}%` }
}

function MountainLandscape() {
  return <svg viewBox={`0 0 ${VIEWBOX_WIDTH} ${VIEWBOX_HEIGHT}`} aria-hidden="true" preserveAspectRatio="none">
    <defs>
      <linearGradient id="mountain-sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#f5f2e9"/><stop offset="1" stopColor="#e8e6dc"/></linearGradient>
    </defs>
    <rect width="1200" height="520" fill="url(#mountain-sky)"/>
    <path className="range range-far" d="M0 398 L108 286 L182 326 L292 207 L378 306 L488 241 L570 332 L690 211 L780 301 L902 161 L1012 282 L1100 220 L1200 321 V520 H0 Z"/>
    <path className="range range-far-facet" d="M0 398 L108 286 L182 326 L292 207 L250 357 L378 306 L488 241 L458 365 L570 332 L690 211 L650 375 L780 301 L902 161 L855 374 L1012 282 L1100 220 L1060 380 L1200 321 V520 H0 Z"/>
    <path className="range range-mid" d="M0 442 L142 311 L232 361 L350 171 L462 341 L574 261 L680 362 L820 136 L942 341 L1060 231 L1200 390 V520 H0 Z"/>
    <path className="range range-mid-facet" d="M142 311 L232 361 L350 171 L320 411 L462 341 L574 261 L548 415 L680 362 L820 136 L782 416 L942 341 L1060 231 L1030 420 L1200 390 V520 H0 Z"/>
    <g className="ranked-peak peak-3" data-ranking-peak="3"><path d="M28 452 L122 314 L214 190 L302 300 L402 452 Z"/><path className="peak-facet" d="M214 190 L302 300 L402 452 L238 401 Z"/><path className="snowcap" d="M173 246 L214 190 L253 242 L232 231 L217 248 L202 225 L190 244 Z"/></g>
    <g className="ranked-peak peak-2" data-ranking-peak="2"><path d="M228 456 L344 286 L468 126 L590 287 L714 456 Z"/><path className="peak-facet" d="M468 126 L590 287 L714 456 L498 398 Z"/><path className="snowcap" d="M416 193 L468 126 L519 193 L495 181 L474 205 L453 173 L438 195 Z"/></g>
    <g className="ranked-peak peak-1" data-ranking-peak="1"><path d="M548 462 L678 265 L820 54 L963 265 L1098 462 Z"/><path className="peak-facet" d="M820 54 L963 265 L1098 462 L849 388 Z"/><path className="peak-light" d="M548 462 L678 265 L820 54 L786 354 Z"/><path className="snowcap" d="M756 149 L820 54 L881 146 L852 132 L828 157 L807 116 L785 150 Z"/></g>
    <g className="ranked-peak peak-4" data-ranking-peak="4"><path d="M812 458 L898 335 L990 236 L1076 329 L1200 399 V520 H812 Z"/><path className="peak-facet" d="M990 236 L1076 329 L1200 399 V520 L1012 411 Z"/></g>
    <path className="range range-foreground" d="M0 443 C125 415 228 449 340 420 C456 389 546 439 655 410 C769 379 860 432 972 407 C1060 388 1138 412 1200 397 V520 H0 Z"/>
    <path className="foreground-accent" d="M0 456 C155 431 252 465 368 438 C490 410 575 456 695 428 C816 400 918 451 1030 424 C1101 407 1155 414 1200 410"/>
  </svg>
}

export function MountainRanking({ contributors, onSelect, mode, actions }: { contributors: RCIContributor[]; onSelect: (contributor: RCIContributor) => void; mode: 'RESEARCH_BASELINE' | 'CUSTOM_WEIGHTS'; actions?: React.ReactNode }) {
  const top = contributors.slice(0, 4)
  return <section className="mountain-card" aria-labelledby="mountain-title">
    <div className="section-heading"><div><span className="eyebrow">RCI CONTRIBUTION LANDSCAPE</span><h2 id="mountain-title">领先 TOP4 成员</h2><p>RCI 综合贡献排名 · 基于可验证 GitHub 行为</p></div><div className="ranking-actions"><span className="status-badge">{mode === 'CUSTOM_WEIGHTS' ? 'Custom Weights' : 'Research Baseline'}</span>{actions}</div></div>
    <div className="mountain-scene">
      <MountainLandscape/>
      {top.map((contributor, index) => {
        const visualRank = (index + 1) as keyof typeof rankedPeakLayout
        const anchor = rankedPeakLayout[visualRank]
        return <button key={contributor.github_username} className={`mountain-marker rank-${visualRank}`} style={markerPosition(visualRank)} data-peak-anchor={`${anchor.x},${anchor.peakY}`} onClick={() => onSelect(contributor)} aria-label={`查看 ${contributor.display_name}，RCI 第 ${contributor.rci_rank} 名，${contributor.rci.toFixed(1)}%`}>
          <RankMedal rank={contributor.rci_rank}/><span className="marker-avatar"><UserRound/></span><strong>{contributor.is_mapped ? contributor.display_name : `@${contributor.github_username}`}</strong>
          {contributor.is_mapped && <small>@{contributor.github_username}</small>}<em>RCI {contributor.rci.toFixed(1)}% · #{contributor.rci_rank}</em>
        </button>
      })}
      {!top.length && <div className="mountain-empty"><strong>暂无贡献者数据</strong><span>同步后，真实 Contributor 会出现在山峰上。</span></div>}
    </div>
    {contributors.length > 4 && <div className="rank-list"><div className="rank-list-title"><h3>第 5 名及之后</h3><span>{contributors.length - 4} Contributors</span></div>{contributors.slice(4).map((contributor) => {
      const max = contributors[4]?.rci || 1
      return <button className="rank-row" key={contributor.github_username} onClick={() => onSelect(contributor)}><b>{String(contributor.rci_rank).padStart(2, '0')}</b><span className="rank-person"><strong>{contributor.is_mapped ? contributor.display_name : `@${contributor.github_username}`}</strong>{contributor.is_mapped && <small>@{contributor.github_username}</small>}</span><span className="rank-track"><i style={{ width: `${Math.max(4, contributor.rci / max * 100)}%` }}/></span><strong>{contributor.rci.toFixed(1)}%</strong><ArrowUpRight size={17}/></button>
    })}</div>}
  </section>
}
