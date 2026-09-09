import { useCallback, useEffect, useState } from 'react'
import { ArrowLeft, ArrowRight, ShieldCheck, UsersRound } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { adminApi } from '../api/admin'
import { errorMessage } from '../api/client'
import { Modal } from '../components/common/Modal'
import { InlineFeedback, PageError, PageLoader } from '../components/feedback/Feedback'
import { useAuth } from '../contexts/AuthContext'
import type { ManagedUser, Role } from '../types'

const systemRoleLabel = (role: Role) => role === 'ADMIN' ? 'SYSTEM ADMIN' : 'STANDARD USER'

export function SystemUsersPage() {
  const navigate = useNavigate()
  const { user: current, refreshUser } = useAuth()
  const [users, setUsers] = useState<ManagedUser[]>([])
  const [editing, setEditing] = useState<ManagedUser | null>(null)
  const [role, setRole] = useState<Role>('MEMBER')
  const [active, setActive] = useState(true)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true); setError('')
    try { setUsers(await adminApi.users()) }
    catch (reason) { setError(errorMessage(reason)) }
    finally { setLoading(false) }
  }, [])
  useEffect(() => { void load() }, [load])

  const edit = (managed: ManagedUser) => {
    setEditing(managed); setRole(managed.role); setActive(managed.is_active); setError('')
  }
  const save = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!editing) return
    try {
      await adminApi.updateUser(editing.id, { role, is_active: active })
      const editingCurrentUser = editing.id === current?.id
      setEditing(null)
      await load()
      if (editingCurrentUser) await refreshUser()
    } catch (reason) { setError(errorMessage(reason)) }
  }

  if (loading) return <PageLoader label="正在读取系统账号…" />
  return <div className="system-users-page page-stack">
    <button className="back-link" onClick={() => navigate('/dashboard')}><ArrowLeft size={16}/> Back to Dashboard</button>
    <section className="system-users-hero">
      <div><span className="eyebrow">SYSTEM-LEVEL ADMINISTRATION</span><h1>系统账号</h1><p>管理 CollabTrace 系统级账号、状态与维护权限。</p><small>Repository 权限请前往对应 Repository 的 Access 页面管理。</small></div>
      <div className="system-hero-mark"><ShieldCheck/><span>SYSTEM ADMIN</span></div>
    </section>
    <section className="bento-card system-users-workspace">
      <div className="admin-toolbar"><div><h2>System Users</h2><p>System role affects platform-level maintenance permissions. Repository roles are managed separately.</p></div><span className="status-badge">{users.length} ACCOUNTS</span></div>
      {error && !editing && <PageError message={error} retry={() => void load()}/>}
      <div className="system-user-list">
        <div className="system-user-row header"><span>User</span><span>Email</span><span>System Role</span><span>Account Status</span><span>Action</span></div>
        {users.map((managed) => <button className="system-user-row" key={managed.id} onClick={() => edit(managed)}>
          <span className="system-user-identity"><span className="system-user-avatar">{managed.display_name.slice(0, 1).toUpperCase()}</span><span><strong>{managed.display_name} {managed.id === current?.id && <em>Self</em>}</strong><small>@{managed.username}</small></span></span>
          <span>{managed.email || 'No email'}</span>
          <span><b className={`system-role-badge ${managed.role === 'ADMIN' ? 'admin' : 'standard'}`}>{systemRoleLabel(managed.role)}</b></span>
          <span className={`account-status ${managed.is_active ? 'active' : 'disabled'}`}>{managed.is_active ? 'Active' : 'Disabled'}</span>
          <ArrowRight size={17}/>
        </button>)}
      </div>
    </section>
    <Modal open={Boolean(editing)} title="编辑系统账号" onClose={() => setEditing(null)}>
      <form className="stack-form" onSubmit={save}>
        <div className="target-contributor"><span>System User</span><strong>{editing?.display_name}</strong><small>@{editing?.username}</small></div>
        <div className="system-role-note"><ShieldCheck size={17}/><span>System role affects platform-level maintenance permissions.<small>Repository roles are managed separately.</small></span></div>
        <label>System Role<select value={role} onChange={(event) => setRole(event.target.value as Role)} disabled={editing?.id === current?.id}><option value="MEMBER">STANDARD USER</option><option value="ADMIN">SYSTEM ADMIN</option></select></label>
        <label className="toggle-line"><input type="checkbox" checked={active} onChange={(event) => setActive(event.target.checked)} disabled={editing?.id === current?.id}/><span><strong>Account active</strong><small>{editing?.id === current?.id ? '为避免锁定当前会话，不能停用自己。' : 'Disabled 用户无法登录。'}</small></span></label>
        {editing?.id === current?.id && <InlineFeedback kind="info">System Admin 的自锁操作已被保护。</InlineFeedback>}
        {error && <InlineFeedback>{error}</InlineFeedback>}
        <button className="button primary full">保存系统账号</button>
      </form>
    </Modal>
  </div>
}
