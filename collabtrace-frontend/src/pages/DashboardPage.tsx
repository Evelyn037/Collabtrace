import { useCallback, useEffect, useMemo, useState } from 'react'
import { ArrowRight, BookOpen, GitCommitHorizontal, GitPullRequest, LoaderCircle, MessageSquareCode, Plus, RefreshCw, Settings2, Tickets } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { errorMessage } from '../api/client'
import { repositoryApi } from '../api/repositories'
import { AnalyzeRepositoryModal } from '../components/common/AnalyzeRepositoryModal'
import { Modal } from '../components/common/Modal'
import { ActivityTimeline, ContributionDonut } from '../components/charts/Charts'
import { EmptyState, PageError, PageLoader } from '../components/feedback/Feedback'
import { MountainRanking } from '../components/mountain/MountainRanking'
import { useAuth } from '../contexts/AuthContext'
import { useRepositories } from '../contexts/RepositoryContext'
import type { ContributionIndex, Overview, RCIDimension, RCIContributor, RCIWeights, TimelinePoint } from '../types'

const DIMENSIONS: { key: RCIDimension; label: string }[] = [
  { key: 'code', label: 'Code Implementation' }, { key: 'pr', label: 'Pull Request' },
  { key: 'issue', label: 'Issue' }, { key: 'review', label: 'Code Review' },
]
const DEFAULT_WEIGHTS: RCIWeights = { code: 1, pr: 1, issue: 1, review: 1 }

export function rciWeightStorageKey(userId: number, repositoryId: number) {
  return `collabtrace:rci-weights:user:${userId}:repository:${repositoryId}`
}

function Metric({ label, value, icon }: { label: string; value: number; icon: React.ReactNode }) {
  return <div className="metric-card"><span>{icon}</span><div><small>{label}</small><strong>{value.toLocaleString()}</strong></div></div>
}

function QuickView({ contributor, repositoryId, canManage, mode, open, onClose }: { contributor: RCIContributor | null; repositoryId: number; canManage: boolean; mode: ContributionIndex['mode']; open: boolean; onClose: () => void }) {
  const navigate = useNavigate()
  const [whyOpen, setWhyOpen] = useState(false)
  useEffect(() => { if (!open) setWhyOpen(false) }, [open])
  if (!contributor) return null
  return <Modal open={open} title="Contributor Quick View" onClose={onClose} wide>
    <div className="quick-profile"><span className="profile-initial">{(contributor.display_name || contributor.github_username).slice(0, 1).toUpperCase()}</span><div><h3>{contributor.is_mapped ? contributor.display_name : `@${contributor.github_username}`}</h3>{contributor.is_mapped && <p>@{contributor.github_username}</p>}<span className="status-badge">{mode === 'CUSTOM_WEIGHTS' ? 'Custom Weights' : 'Research Baseline'}</span></div><strong className="quick-rank">{contributor.rci.toFixed(1)}%<small>Current View RCI · #{contributor.rci_rank}</small></strong></div>
    <div className="quick-facts"><span><small>Activity Events</small><strong>{contributor.total_events}</strong></span><span><small>Activity Rank</small><strong>#{contributor.activity_rank}</strong></span><span><small>RCI Rank</small><strong>#{contributor.rci_rank}</strong></span></div>
    <div className="donut-wrap"><ContributionDonut contributor={contributor}/><p className="donut-helper">Contribution Composition uses unweighted normalized dimensions and does not change with personal weights.</p></div>
    <button className="why-toggle" onClick={() => setWhyOpen((value) => !value)} aria-expanded={whyOpen}>Why this RCI? <ArrowRight size={16}/></button>
    {whyOpen && <section className="why-rci" aria-label="Why this RCI"><h3>Why this RCI</h3><p>Each dimension is normalized within this repository, then multiplied by the current effective weight.</p>{DIMENSIONS.map(({ key, label }) => <div className="why-row" key={key}><span>{label}<small>relative {Math.round(contributor.dimension_scores[key] * 100)}%</small></span><b>{contributor.weighted_contributions[key].toFixed(1)} RCI pts</b></div>)}<div className="raw-metrics"><span>{contributor.raw_metrics.effective_commits}/{contributor.raw_metrics.raw_commits} effective commits</span><span>{contributor.raw_metrics.filtered_churn} filtered churn</span><span>{contributor.raw_metrics.merged_prs} merged PRs</span><span>{contributor.raw_metrics.effective_issues} effective issues</span><span>{contributor.raw_metrics.effective_reviews} effective reviews</span></div></section>}
    <div className="quick-actions">{canManage && !contributor.is_mapped && <button className="button secondary" onClick={() => navigate(`/admin?tab=mapping&contributor=${encodeURIComponent(contributor.github_username)}`)}>关联成员</button>}<button className="button primary" onClick={() => navigate(`/repositories/${repositoryId}/contributors/${encodeURIComponent(contributor.github_username)}`)}>查看完整档案 <ArrowRight size={17}/></button></div>
  </Modal>
}

function WeightsModal({ open, index, initial, onClose, onApply, onReset }: { open: boolean; index: ContributionIndex; initial: RCIWeights; onClose: () => void; onApply: (weights: RCIWeights) => void; onReset: () => void }) {
  const [draft, setDraft] = useState(initial)
  useEffect(() => { if (open) setDraft(initial) }, [initial, open])
  const activeTotal = index.active_dimensions.reduce((sum, key) => sum + draft[key], 0)
  const preview = (key: RCIDimension) => index.active_dimensions.includes(key) && activeTotal > 0 ? draft[key] / activeTotal * 100 : 0
  const change = (key: RCIDimension, value: string) => setDraft((current) => ({ ...current, [key]: Math.max(0, Math.min(100, Number(value) || 0)) }))
  return <Modal open={open} title="Personal RCI Weights" onClose={onClose} wide><p className="modal-intro">Adjust how the four normalized dimensions are combined in your current view. This preference is private to this browser session and does not change repository data.</p><div className="weight-list">{DIMENSIONS.map(({ key, label }) => { const active = index.active_dimensions.includes(key); return <label className={!active ? 'inactive' : ''} key={key}><span><strong>{label}</strong><small>{active ? `${preview(key).toFixed(1)}% effective` : 'Inactive — no eligible activity'}</small></span><input aria-label={`${label} slider`} type="range" min="0" max="100" value={draft[key]} disabled={!active} onChange={(event) => change(key, event.target.value)}/><input aria-label={`${label} weight`} type="number" min="0" max="100" value={draft[key]} disabled={!active} onChange={(event) => change(key, event.target.value)}/></label> })}</div>{activeTotal <= 0 && <div className="feedback error">At least one active dimension must have a weight greater than zero.</div>}<div className="quick-actions"><button className="button secondary" onClick={onClose}>Cancel</button><button className="button secondary" onClick={onReset}>Reset baseline</button><button className="button primary" disabled={activeTotal <= 0} onClick={() => onApply(draft)}>Apply weights</button></div></Modal>
}

function MethodologyModal({ open, index, onClose }: { open: boolean; index: ContributionIndex; onClose: () => void }) {
  const partial = Object.values(index.metric_coverage).some((value) => value < 1)
  return <Modal open={open} title="RCI Methodology · RCI_V1" onClose={onClose} wide><div className="methodology-content">{partial && <div className="feedback info">部分指标基于当前可获取数据计算。</div>}<section><h3>Relative Contribution Index</h3><p>RCI(d) = 100 × Σ effective_weight(m) × R_m(d), calculated only across active dimensions.</p></section><section><h3>Four dimensions</h3><p>Code Implementation, Pull Request, Issue, and Code Review. Each is normalized against the current repository team.</p></section><section><h3>Code formula</h3><p>Code combines 50% effective commit share and 50% robust churn share. If one signal is unavailable, the available signal receives 100%.</p></section><section><h3>High-confidence filters</h3><p>Bots, merge/no-op commits, drafts and unmerged PRs, not-planned issues, self/dismissed/empty reviews, duplicate review snapshots, vendor/generated/minified/map/lock/binary churn are excluded from RCI only. Raw evidence remains available.</p></section><section><h3>Robust churn</h3><p>Additions + deletions are filtered by file path/type, then log(1 + x) limits the influence of unusually large changes.</p></section><section><h3>Active dimensions & coverage</h3><p>Active: {index.active_dimensions.join(', ') || 'none'}. Coverage: code {Math.round(index.metric_coverage.code_churn_coverage * 100)}%, PR {Math.round(index.metric_coverage.pr_status_coverage * 100)}%, issue {Math.round(index.metric_coverage.issue_state_reason_coverage * 100)}%, review {Math.round(index.metric_coverage.review_metadata_coverage * 100)}%.</p></section><section><h3>Scope & disclaimer</h3><p>{index.analysis_scope.description}. RCI describes team-relative, verifiable GitHub collaboration in the synchronized scope. It is not a measure of ability, code quality, performance, hours worked, or absolute labor value.</p></section><section><h3>Research references</h3><p>刘玉辉、王忠杰，《GitHub 开源软件项目团队协作过程评价》；GitHub REST API documentation. The paper informs the multi-indicator framework; RCI_V1 is CollabTrace's transparent implementation.</p></section></div></Modal>
}

export function DashboardPage() {
  const { selected, loading: repositoriesLoading } = useRepositories(); const { user } = useAuth()
  const [overview, setOverview] = useState<Overview | null>(null); const [index, setIndex] = useState<ContributionIndex | null>(null); const [timeline, setTimeline] = useState<TimelinePoint[]>([]); const [weights, setWeights] = useState<RCIWeights | undefined>()
  const [loading, setLoading] = useState(false); const [error, setError] = useState(''); const [analyzeOpen, setAnalyzeOpen] = useState(false); const [quick, setQuick] = useState<RCIContributor | null>(null); const [weightsOpen, setWeightsOpen] = useState(false); const [methodologyOpen, setMethodologyOpen] = useState(false); const [syncing, setSyncing] = useState(false); const [notice, setNotice] = useState('')
  const canManage = selected?.current_user_role === 'ADMIN'; const storageKey = useMemo(() => user && selected ? rciWeightStorageKey(user.id, selected.id) : '', [selected, user])
  useEffect(() => { if (!storageKey) { setWeights(undefined); return } try { setWeights(JSON.parse(sessionStorage.getItem(storageKey) || 'null') || undefined) } catch { setWeights(undefined) } }, [storageKey])
  const load = useCallback(async () => { if (!selected) return; setLoading(true); setError(''); try { const [nextOverview, nextIndex, nextTimeline] = await Promise.all([repositoryApi.overview(selected.id), repositoryApi.contributionIndex(selected.id, weights), repositoryApi.timeline(selected.id)]); setOverview(nextOverview); setIndex(nextIndex); setTimeline(nextTimeline) } catch (reason) { setError(errorMessage(reason)) } finally { setLoading(false) } }, [selected, weights])
  useEffect(() => { void load() }, [load])
  const applyWeights = (next: RCIWeights) => { if (storageKey) sessionStorage.setItem(storageKey, JSON.stringify(next)); setWeights(next); setWeightsOpen(false) }
  const resetWeights = () => { if (storageKey) sessionStorage.removeItem(storageKey); setWeights(undefined); setWeightsOpen(false) }
  const sync = async () => { if (!selected) return; setSyncing(true); setNotice(''); try { const result = await repositoryApi.sync(selected.id); setNotice(`Sync complete · Fetched ${result.fetched} · Inserted ${result.inserted} · Updated ${result.updated}`); await load() } catch (reason) { setNotice(errorMessage(reason)) } finally { setSyncing(false) } }
  if (repositoriesLoading) return <PageLoader label="正在读取 Repository…" />
  if (!selected) return <><EmptyState title="暂无 Repository" message="分析任意公开 GitHub Repository，创建你的第一个协作空间。" action={<button className="button primary" onClick={() => setAnalyzeOpen(true)}>Analyze your first repository <ArrowRight size={17}/></button>}/><AnalyzeRepositoryModal open={analyzeOpen} onClose={() => setAnalyzeOpen(false)}/></>
  if (loading && !overview) return <PageLoader label="正在生成团队贡献图景…" />
  if (error && !overview) return <PageError message={error} retry={() => void load()} />
  return <div className="dashboard-page page-stack"><section className="repository-hero"><div><span className="eyebrow">TEAM CONTRIBUTION</span><h1>团队贡献概览</h1><p>基于最新同步的 GitHub 协作活动。</p></div><div className="repository-identity"><span>Repository</span><a href={selected.html_url} target="_blank" rel="noopener noreferrer">{selected.full_name}</a><small>{overview?.totals.events.toLocaleString()} contribution events · Last sync {overview?.last_sync_at ? new Date(overview.last_sync_at).toLocaleString('zh-CN') : '尚未同步'}</small></div><div className="hero-actions"><button className="button secondary" onClick={() => setAnalyzeOpen(true)}><Plus size={17}/>分析 Repository</button>{canManage && <button className="button dark" onClick={sync} disabled={syncing}>{syncing ? <LoaderCircle className="spin" size={17}/> : <RefreshCw size={17}/>}Sync Now</button>}</div></section>{notice && <div className="feedback info">{notice}</div>}{overview && <section className="metrics-row" aria-label="Repository 活动汇总"><Metric label="Total Events" value={overview.totals.events} icon={<span className="metric-total">Σ</span>}/><Metric label="Commits" value={overview.totals.commits} icon={<GitCommitHorizontal/>}/><Metric label="Pull Requests" value={overview.totals.pull_requests} icon={<GitPullRequest/>}/><Metric label="Issues" value={overview.totals.issues} icon={<Tickets/>}/><Metric label="Code Reviews" value={overview.totals.reviews} icon={<MessageSquareCode/>}/></section>}{index && <MountainRanking contributors={index.contributors} mode={index.mode} onSelect={setQuick} actions={<><button className="button secondary compact" onClick={() => setMethodologyOpen(true)}><BookOpen size={15}/>Methodology</button><button className="button dark compact" onClick={() => setWeightsOpen(true)}><Settings2 size={15}/>Weights</button></>}/>}<section className="bento-card timeline-card"><div className="section-heading"><div><span className="eyebrow">REPOSITORY TIMELINE</span><h2>协作活动趋势</h2><p>所有 Contributor 的每日活动总量。</p></div></div>{timeline.length ? <ActivityTimeline data={timeline}/> : <EmptyState title="暂无时间线数据" message="同步到带时间戳的 GitHub 活动后，这里将显示趋势。"/>}</section>{index && <QuickView contributor={quick} repositoryId={selected.id} canManage={canManage} mode={index.mode} open={Boolean(quick)} onClose={() => setQuick(null)}/>} {index && <WeightsModal open={weightsOpen} index={index} initial={weights || DEFAULT_WEIGHTS} onClose={() => setWeightsOpen(false)} onApply={applyWeights} onReset={resetWeights}/>} {index && <MethodologyModal open={methodologyOpen} index={index} onClose={() => setMethodologyOpen(false)}/>}<AnalyzeRepositoryModal open={analyzeOpen} onClose={() => setAnalyzeOpen(false)} onComplete={() => void load()}/></div>
}
