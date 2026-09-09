import { useCallback, useEffect, useMemo, useState } from 'react'
import { ArrowLeft, ArrowUpRight, GitCommitHorizontal, GitPullRequest, MessageSquareCode, Tickets } from 'lucide-react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { contributorApi } from '../api/contributors'
import { errorMessage } from '../api/client'
import { ActivityTimeline } from '../components/charts/Charts'
import { EmptyState, PageError, PageLoader } from '../components/feedback/Feedback'
import type { ContributionEvent, Contributor, EventType, TimelinePoint } from '../types'

const labels: Record<EventType, string> = { COMMIT: 'Commit', PULL_REQUEST: 'Pull Request', ISSUE: 'Issue', REVIEW: 'Code Review' }
const icons: Record<EventType, React.ReactNode> = { COMMIT: <GitCommitHorizontal/>, PULL_REQUEST: <GitPullRequest/>, ISSUE: <Tickets/>, REVIEW: <MessageSquareCode/> }

function metadataLabel(event: ContributionEvent) {
  const metadata = event.metadata
  if (event.event_type === 'COMMIT' && typeof metadata.sha === 'string') return String(metadata.sha).slice(0, 7)
  if ((event.event_type === 'ISSUE' || event.event_type === 'PULL_REQUEST') && metadata.number) return `#${String(metadata.number)}`
  if (event.event_type === 'REVIEW' && metadata.state) return String(metadata.state)
  return null
}

export function ContributorPage() {
  const params = useParams(); const navigate = useNavigate()
  const repositoryId = Number(params.repositoryId); const username = decodeURIComponent(params.githubUsername ?? '')
  const [detail, setDetail] = useState<Contributor | null>(null); const [contributors, setContributors] = useState<Contributor[]>([])
  const [timeline, setTimeline] = useState<TimelinePoint[]>([]); const [events, setEvents] = useState<ContributionEvent[]>([])
  const [eventTotal, setEventTotal] = useState(0); const [filter, setFilter] = useState<EventType | undefined>()
  const [loading, setLoading] = useState(true); const [eventsLoading, setEventsLoading] = useState(false); const [error, setError] = useState('')
  const loadProfile = useCallback(async () => {
    setLoading(true); setError('')
    try {
      const [nextDetail, nextContributors, nextTimeline] = await Promise.all([
        contributorApi.detail(repositoryId, username), contributorApi.stats(repositoryId, true), contributorApi.timeline(repositoryId, username),
      ])
      setDetail(nextDetail); setContributors(nextContributors); setTimeline(nextTimeline)
    } catch (reason) { setError(errorMessage(reason)) }
    finally { setLoading(false) }
  }, [repositoryId, username])
  const loadEvents = useCallback(async (reset = true) => {
    setEventsLoading(true)
    try {
      const offset = reset ? 0 : events.length
      const page = await contributorApi.events(repositoryId, username, filter, 20, offset)
      setEvents((current) => reset ? page.items : [...current, ...page.items]); setEventTotal(page.total)
    } catch (reason) { setError(errorMessage(reason)) }
    finally { setEventsLoading(false) }
  }, [repositoryId, username, filter, events.length])
  useEffect(() => { void loadProfile() }, [loadProfile])
  useEffect(() => { void loadEvents(true) }, [repositoryId, username, filter]) // eslint-disable-line react-hooks/exhaustive-deps
  const composition = useMemo(() => detail ? [
    ['Commit', detail.commits, 'lime'], ['Code Review', detail.reviews, 'moss'], ['Pull Request', detail.pull_requests, 'olive'], ['Issue', detail.issues, 'sage'],
  ] as const : [], [detail])
  if (loading) return <PageLoader label="正在读取 Contributor 档案…" />
  if (error && !detail) return <PageError message={error === '请求的数据不存在。' ? 'Contributor not found.' : error} retry={() => void loadProfile()} />
  if (!detail) return null
  return <div className="contributor-page page-stack">
    <div className="back-row"><Link to="/dashboard"><ArrowLeft size={17}/>返回情况总览</Link><label>切换 Contributor<select aria-label="切换 Contributor" value={detail.github_username} onChange={(event) => navigate(`/repositories/${repositoryId}/contributors/${encodeURIComponent(event.target.value)}`)}>{contributors.map((item) => <option key={item.github_username} value={item.github_username}>{item.is_mapped ? `${item.display_name} · @${item.github_username}` : `@${item.github_username}`}</option>)}</select></label></div>
    <section className="contributor-hero">
      <span className="profile-initial large">{(detail.display_name || detail.github_username)[0].toUpperCase()}</span>
      <div className="contributor-title"><span className="eyebrow">CONTRIBUTOR PROFILE</span><h1>{detail.is_mapped ? detail.display_name : `@${detail.github_username}`}</h1>{detail.is_mapped && <p>@{detail.github_username}</p>}<span className="status-badge">{detail.is_mapped ? 'Team Member' : 'GitHub Contributor'}</span></div>
      <div className="hero-stat"><strong>{detail.total_events}</strong><span>Total Events</span></div><div className="hero-stat accent"><strong>#{detail.rank}</strong><span>Activity Rank</span></div>
    </section>
    <section className="detail-grid"><div className="bento-card composition-card"><div className="section-heading"><div><span className="eyebrow">CONTRIBUTION COMPOSITION</span><h2>活动构成</h2></div></div><div className="composition-list">{composition.map(([label, value, tone]) => <div className="composition-row" key={label}><span>{label}</span><div><i className={tone} style={{ width: `${detail.total_events ? Math.max(3, value / detail.total_events * 100) : 0}%` }}/></div><strong>{value}</strong></div>)}</div></div>
      <div className="bento-card breakdown-card"><div className="mini-stat"><GitCommitHorizontal/><span>Commits</span><strong>{detail.commits}</strong></div><div className="mini-stat"><GitPullRequest/><span>Pull Requests</span><strong>{detail.pull_requests}</strong></div><div className="mini-stat"><Tickets/><span>Issues</span><strong>{detail.issues}</strong></div><div className="mini-stat"><MessageSquareCode/><span>Code Reviews</span><strong>{detail.reviews}</strong></div></div></section>
    <section className="bento-card timeline-card"><div className="section-heading"><div><span className="eyebrow">ACTIVITY OVER TIME</span><h2>Contributor Timeline</h2><p>每日真实 GitHub 活动趋势。</p></div></div>{timeline.length ? <ActivityTimeline data={timeline}/> : <EmptyState title="暂无时间线数据" message="该 Contributor 暂无可用时间点。"/>}</section>
    <section className="bento-card evidence-card"><div className="section-heading"><div><span className="eyebrow">CONTRIBUTION EVIDENCE</span><h2>贡献证据</h2><p>每条记录均可追溯至真实 GitHub 活动。</p></div><span>{eventTotal} Records</span></div>
      <div className="filter-pills" aria-label="Evidence 类型筛选"><button className={!filter ? 'active' : ''} onClick={() => setFilter(undefined)}>All</button>{(Object.keys(labels) as EventType[]).map((type) => <button key={type} className={filter === type ? 'active' : ''} onClick={() => setFilter(type)}>{labels[type]}</button>)}</div>
      {events.length ? <div className="evidence-list">{events.map((event) => <article className="evidence-row" key={event.id}><span className={`event-icon ${event.event_type.toLowerCase()}`}>{icons[event.event_type]}</span><div><span className="event-type">{labels[event.event_type]} {metadataLabel(event) && <b>· {metadataLabel(event)}</b>}</span><h3>{event.title}</h3><time>{event.event_created_at ? new Date(event.event_created_at).toLocaleString('zh-CN') : '时间不可用'}</time></div>{event.github_url ? <a href={event.github_url} target="_blank" rel="noopener noreferrer">View on GitHub <ArrowUpRight size={16}/></a> : <span className="unavailable">Evidence link unavailable</span>}</article>)}</div> : !eventsLoading && <EmptyState title="暂无贡献证据" message="此筛选条件下没有 GitHub 活动记录。"/>}
      {eventsLoading && <div className="inline-loader">正在加载证据…</div>}{events.length < eventTotal && <button className="button secondary load-more" onClick={() => void loadEvents(false)} disabled={eventsLoading}>Load More</button>}
    </section>
  </div>
}
