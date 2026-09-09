type MedalRank = 1 | 2 | 3

const toneByRank = { 1: 'gold', 2: 'silver', 3: 'bronze' } as const

export function RankMedal({ rank }: { rank: number }) {
  if (rank < 1 || rank > 3) return null
  const medalRank = rank as MedalRank
  const tone = toneByRank[medalRank]
  return <span className={`rank-medal rank-medal-${tone}`} data-rank-medal={tone} data-rank-number={medalRank} aria-hidden="true">
    <svg viewBox="0 0 48 58" focusable="false">
      <g className="medal-ribbons">
        <path d="M14 35 L23 38 L19 56 L13 49 L6 51 Z"/>
        <path d="M34 35 L25 38 L29 56 L35 49 L42 51 Z"/>
      </g>
      <path className="medal-rosette" d="M24 1 L27.3 5.6 L32.1 3.3 L33.6 8.6 L39 8.2 L38.6 13.6 L44 15.1 L41.1 19.8 L46 23 L41.1 26.2 L44 30.9 L38.6 32.4 L39 37.8 L33.6 37.4 L32.1 42.7 L27.3 40.4 L24 45 L20.7 40.4 L15.9 42.7 L14.4 37.4 L9 37.8 L9.4 32.4 L4 30.9 L6.9 26.2 L2 23 L6.9 19.8 L4 15.1 L9.4 13.6 L9 8.2 L14.4 8.6 L15.9 3.3 L20.7 5.6 Z"/>
      <circle className="medal-body" cx="24" cy="23" r="16.5"/>
      <circle className="medal-ring" cx="24" cy="23" r="12.5"/>
      <text className="medal-number" x="24" y="28" textAnchor="middle">{medalRank}</text>
    </svg>
  </span>
}
