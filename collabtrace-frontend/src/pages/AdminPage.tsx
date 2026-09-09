import { useCallback, useEffect, useState } from 'react'
import { ArrowRight, Bot, Check, GitBranch, LoaderCircle, RefreshCw, UserRound, UsersRound } from 'lucide-react'
import { Navigate, useNavigate, useSearchParams } from 'react-router-dom'
import { adminApi } from '../api/admin'
import { contributorApi } from '../api/contributors'
import { errorMessage } from '../api/client'
import { repositoryApi } from '../api/repositories'
import { AnalyzeRepositoryModal } from '../components/common/AnalyzeRepositoryModal'
import { Modal } from '../components/common/Modal'
import { EmptyState, InlineFeedback, PageError, PageLoader } from '../components/feedback/Feedback'
import { useAuth } from '../contexts/AuthContext'
import { useRepositories } from '../contexts/RepositoryContext'
import type { Contributor, Member, Repository, RepositoryAccess, Role, SyncRecord } from '../types'

type Tab = 'repositories' | 'mapping' | 'access' | 'syncs'
const tabLabels: Record<Tab, string> = { repositories: 'Repositories', mapping: 'Member Mapping', access: 'Access', syncs: 'Sync History' }

function RepositoryTab({ openAnalyze }: { openAnalyze: () => void }) {
  const { repositories, selectRepository } = useRepositories(); const navigate = useNavigate()
  const [details, setDetails] = useState<Record<number, Repository>>({}); const [syncing, setSyncing] = useState<number | null>(null); const [message, setMessage] = useState('')
  useEffect(() => { Promise.all(repositories.map((repo) => repositoryApi.detail(repo.id))).then((items) => setDetails(Object.fromEntries(items.map((item) => [item.id, item])))).catch(() => undefined) }, [repositories])
  const sync = async (id: number) => { setSyncing(id); setMessage(''); try { const result = await repositoryApi.sync(id); setMessage(`Sync complete · Fetched ${result.fetched} · Updated ${result.updated}`); setDetails((current) => ({ ...current, [id]: { ...current[id], last_sync_at: result.finished_at } })) } catch (reason) { setMessage(errorMessage(reason)) } finally { setSyncing(null) } }
  return <div className="admin-section"><div className="admin-toolbar"><div><h2>已分析 Repository</h2><p>查看所有协作图景；管理操作按各 Repository Role 显示。</p></div><button className="button primary" onClick={openAnalyze}>+ 分析 Repository</button></div>{message && <InlineFeedback kind="info">{message}</InlineFeedback>}{repositories.length ? <div className="repository-grid">{repositories.map((repo) => <article className="repository-card" key={repo.id}><div className="repo-icon"><GitBranch/></div><span className={`role-pill ${repo.current_user_role.toLowerCase()}`}>{repo.current_user_role}</span><h3>{repo.full_name}</h3><p>{repo.description || 'No repository description.'}</p><div className="repo-meta"><span><b>{details[repo.id]?.event_count ?? '—'}</b> Events</span><span><b>{details[repo.id]?.member_count ?? '—'}</b> Members</span></div><small>Last sync · {repo.last_sync_at ? new Date(repo.last_sync_at).toLocaleString('zh-CN') : 'Never'}</small><div className="card-actions"><button className="button secondary" onClick={() => { selectRepository(repo.id); navigate('/dashboard') }}>Open Dashboard <ArrowRight size={16}/></button>{repo.current_user_role === 'ADMIN' && <button className="icon-button" aria-label={`同步 ${repo.full_name}`} onClick={() => void sync(repo.id)} disabled={syncing === repo.id}>{syncing === repo.id ? <LoaderCircle className="spin"/> : <RefreshCw/>}</button>}</div></article>)}</div> : <EmptyState title="暂无 Repository" message="分析一个公开 GitHub Repository 开始使用。" action={<button className="button primary" onClick={openAnalyze}>分析 Repository</button>}/>}</div>
}

function MappingTab() {
  const { selected } = useRepositories(); const [contributors, setContributors] = useState<Contributor[]>([]); const [users, setUsers] = useState<RepositoryAccess[]>([]); const [members, setMembers] = useState<Member[]>([])
  const [target, setTarget] = useState<Contributor | null>(null); const [userId, setUserId] = useState(''); const [displayName, setDisplayName] = useState(''); const [loading, setLoading] = useState(true); const [error, setError] = useState(''); const [message, setMessage] = useState('')
  const load = useCallback(async () => { if (!selected) return; setLoading(true); setError(''); try { const [stats, nextUsers, nextMembers] = await Promise.all([contributorApi.stats(selected.id, false), adminApi.access(selected.id), contributorApi.members(selected.id)]); setContributors(stats); setUsers(nextUsers); setMembers(nextMembers) } catch (reason) { setError(errorMessage(reason)) } finally { setLoading(false) } }, [selected])
  useEffect(() => { void load() }, [load])
  const open = (contributor: Contributor) => { if (contributor.is_bot) return; const linked = members.find((member) => member.id === contributor.member_id); const initialUser = linked?.user_id ?? users.find((user) => user.is_active)?.user_id; setTarget(contributor); setUserId(initialUser ? String(initialUser) : ''); setDisplayName(contributor.is_mapped ? contributor.display_name : users.find((user) => user.user_id === initialUser)?.display_name || '') }
  const link = async (event: React.FormEvent) => { event.preventDefault(); if (!selected || !target) return; try { if (target.member_id) await adminApi.updateMapping(selected.id, target.member_id, { display_name: displayName }); else await adminApi.createMapping(selected.id, { display_name: displayName, github_username: target.github_username, user_id: Number(userId) }); setTarget(null); setMessage('Identity linked successfully.'); await load() } catch (reason) { setError(errorMessage(reason)) } }
  if (!selected) return <EmptyState title="暂无 Repository" message="请先分析并选择一个 Repository。" />
  if (loading) return <PageLoader label="正在读取 GitHub Contributors…" />
  if (error && !contributors.length) return <PageError message={error} retry={() => void load()} />
  return <div className="admin-section"><div className="admin-toolbar"><div><h2>Member Mapping</h2><p>{selected.full_name} · Mapping 仅增强身份，不改变活动统计。</p></div><span className="status-badge">{contributors.length} DISCOVERED</span></div>{message && <InlineFeedback kind="success">{message}</InlineFeedback>}<div className="mapping-grid">{contributors.map((contributor) => <article className={`mapping-card ${contributor.is_bot ? 'bot' : ''}`} key={contributor.github_username}><span className="mapping-avatar">{contributor.is_bot ? <Bot/> : <UserRound/>}</span><div><h3>@{contributor.github_username}</h3><p>{contributor.total_events} Events · Rank #{contributor.rank}</p></div>{contributor.is_bot ? <><span className="bot-label">BOT</span><small>Excluded from activity ranking</small><button className="button secondary" disabled>不可关联</button></> : contributor.is_mapped ? <><span className="linked"><Check size={15}/>Linked to {contributor.display_name}</span><button className="button secondary" onClick={() => open(contributor)}>Edit Link</button></> : <><span className="muted">No CollabTrace account linked.</span><button className="button primary" onClick={() => open(contributor)}>Link Account <ArrowRight size={16}/></button></>}</article>)}</div>
    <Modal open={Boolean(target)} title="关联 CollabTrace 账号" onClose={() => setTarget(null)}><form className="stack-form" onSubmit={link}><div className="target-contributor"><span>GitHub Contributor</span><strong>@{target?.github_username}</strong><small>{target?.total_events} Events</small></div>{!target?.is_mapped && <label>CollabTrace User<select value={userId} onChange={(event) => { setUserId(event.target.value); const selectedUser = users.find((user) => user.user_id === Number(event.target.value)); if (selectedUser) setDisplayName(selectedUser.display_name) }} required><option value="">选择用户</option>{users.filter((user) => user.is_active).map((user) => <option key={user.user_id} value={user.user_id}>{user.display_name} · @{user.username}</option>)}</select></label>}<label>Display Name<input value={displayName} onChange={(event) => setDisplayName(event.target.value)} required/></label>{error && <InlineFeedback>{error}</InlineFeedback>}<button className="button primary full">Confirm Mapping</button></form></Modal></div>
}

function AccessTab() {
  const { selected, refreshRepositories } = useRepositories()
  const [entries, setEntries] = useState<RepositoryAccess[]>([])
  const [saving, setSaving] = useState<number | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const load = useCallback(async () => {
    if (!selected) return
    setLoading(true); setError('')
    try { setEntries(await adminApi.access(selected.id)) }
    catch (reason) { setError(errorMessage(reason)) }
    finally { setLoading(false) }
  }, [selected])
  useEffect(() => { void load() }, [load])
  const update = async (entry: RepositoryAccess, role: Role) => {
    if (!selected || role === entry.role) return
    setSaving(entry.user_id); setError('')
    try {
      const updated = await adminApi.updateAccess(selected.id, entry.user_id, role)
      setEntries((current) => current.map((item) => item.user_id === updated.user_id ? updated : item))
      await refreshRepositories()
    } catch (reason) { setError(errorMessage(reason)) }
    finally { setSaving(null) }
  }
  if (!selected) return <EmptyState title="暂无 Repository" message="请先选择一个 Repository。"/>
  if (loading) return <PageLoader label="正在读取 Repository Access…"/>
  const administrators = entries.filter((entry) => entry.role === 'ADMIN')
  return <div className="admin-section"><div className="admin-toolbar"><div><h2>Repository Access</h2><p><strong>{selected.full_name}</strong> · 管理当前 Repository 的访问权限。</p><small>此处角色仅影响当前 Repository。</small></div><span className="status-badge">{administrators.length} ADMIN</span></div>{!administrators.length && <InlineFeedback>Repository has no administrator.</InlineFeedback>}{error && <InlineFeedback>{error}</InlineFeedback>}<div className="user-list"><div className="user-row header"><span>Name</span><span>Email</span><span>Repository Role</span><span>Source</span><span/></div>{entries.map((entry) => <div className="user-row" key={entry.user_id}><span><strong>{entry.display_name}</strong><small>@{entry.username}</small></span><span>{entry.email || 'No email'}</span><span><select aria-label={`Repository role for ${entry.username}`} value={entry.role} onChange={(event) => void update(entry, event.target.value as Role)} disabled={!entry.is_active || saving === entry.user_id}><option value="MEMBER">MEMBER</option><option value="ADMIN">ADMIN</option></select></span><span className={`status-dot ${entry.is_active ? 'active' : ''}`} title={!entry.explicit ? 'No explicit access record. Defaults to read-only MEMBER.' : 'Explicit RepositoryAccess record.'}>{entry.explicit ? 'Explicit' : 'Default'}{!entry.is_active ? ' · Disabled' : ''}</span>{saving === entry.user_id ? <LoaderCircle className="spin" size={17}/> : <span/>}</div>)}</div></div>
}

function SyncHistoryTab() {
  const { selected } = useRepositories(); const [records, setRecords] = useState<SyncRecord[]>([]); const [loading, setLoading] = useState(true); const [error, setError] = useState('')
  const load = useCallback(async () => { if (!selected) return; setLoading(true); try { setRecords(await repositoryApi.syncs(selected.id)) } catch (reason) { setError(errorMessage(reason)) } finally { setLoading(false) } }, [selected]); useEffect(() => { void load() }, [load])
  if (!selected) return <EmptyState title="暂无 Repository" message="请先选择一个 Repository。"/>; if (loading) return <PageLoader label="正在读取 Sync History…" />; if (error) return <PageError message={error} retry={() => void load()}/>
  return <div className="admin-section"><div className="admin-toolbar"><div><h2>Sync History</h2><p>{selected.full_name} · 每次同步的真实执行记录。</p></div></div>{records.length ? <div className="sync-list">{records.map((record) => <article className="sync-row" key={record.id}><span className={`sync-status ${record.status.toLowerCase()}`}>{record.status}</span><div><strong>{new Date(record.started_at).toLocaleString('zh-CN')}</strong><small>{record.finished_at ? `Finished ${new Date(record.finished_at).toLocaleString('zh-CN')}` : 'In progress'}</small></div><div className="sync-counts"><span>Fetched<b>{record.fetched_count}</b></span><span>Inserted<b>{record.inserted_count}</b></span><span>Updated<b>{record.updated_count}</b></span><span>Unchanged<b>{record.unchanged_count}</b></span><span>Mapped<b>{record.mapped_count}</b></span><span>Unmapped<b>{record.unmapped_count}</b></span></div>{record.error_message && <p>{record.error_message}</p>}</article>)}</div> : <EmptyState title="暂无同步记录" message="分析或同步 Repository 后会在这里留下记录。"/>}</div>
}

export function AdminPage() {
  const { user } = useAuth()
  const [params, setParams] = useSearchParams(); const requestedValue = params.get('tab'); const requested = requestedValue as Tab | null
  const [tab, setTab] = useState<Tab>(requested && requested in tabLabels ? requested : 'repositories'); const [analyzeOpen, setAnalyzeOpen] = useState(false)
  const selectTab = (next: Tab) => { setTab(next); setParams({ tab: next }) }
  if (requestedValue === 'system-users' || requestedValue === 'users') return <Navigate to={user?.role === 'ADMIN' ? '/system/users' : '/403'} replace/>
  const tabs = Object.keys(tabLabels) as Tab[]
  const content = tab === 'repositories' ? <RepositoryTab openAnalyze={() => setAnalyzeOpen(true)}/> : tab === 'mapping' ? <MappingTab/> : tab === 'access' ? <AccessTab/> : <SyncHistoryTab/>
  return <div className="admin-page page-stack"><section className="admin-hero"><div><span className="eyebrow">REPOSITORY ADMIN CENTER</span><h1>管理中心</h1><p>管理当前 Repository。成员身份、访问权限与同步记录均只属于当前 Repository。</p></div><UsersRound/></section><div className="admin-tabs" role="tablist">{tabs.map((item) => <button role="tab" aria-selected={tab === item} className={tab === item ? 'active' : ''} key={item} onClick={() => selectTab(item)}>{tabLabels[item]}</button>)}</div><section className="bento-card admin-workspace">{content}</section><AnalyzeRepositoryModal open={analyzeOpen} onClose={() => setAnalyzeOpen(false)}/></div>
}
