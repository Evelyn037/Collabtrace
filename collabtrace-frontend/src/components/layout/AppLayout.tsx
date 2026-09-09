import { useEffect, useRef, useState } from 'react'
import { BarChart3, ChevronDown, LogOut, Settings, ShieldCheck, UsersRound } from 'lucide-react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../../contexts/AuthContext'
import { useRepositories } from '../../contexts/RepositoryContext'
import type { User } from '../../types'

function ProfileMenu({ user, logout }: { user: User; logout: () => void }) {
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)
  const navigate = useNavigate()

  useEffect(() => {
    if (!open) return
    menuRef.current?.querySelector<HTMLElement>('[role="menuitem"]')?.focus()
    const closeOutside = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false)
    }
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { setOpen(false); triggerRef.current?.focus() }
    }
    document.addEventListener('mousedown', closeOutside)
    document.addEventListener('keydown', closeOnEscape)
    return () => {
      document.removeEventListener('mousedown', closeOutside)
      document.removeEventListener('keydown', closeOnEscape)
    }
  }, [open])

  const menuKeyboard = (event: React.KeyboardEvent) => {
    if (!['ArrowDown', 'ArrowUp'].includes(event.key)) return
    event.preventDefault()
    const items = [...(menuRef.current?.querySelectorAll<HTMLElement>('[role="menuitem"]') ?? [])]
    const current = items.indexOf(document.activeElement as HTMLElement)
    const direction = event.key === 'ArrowDown' ? 1 : -1
    items[(current + direction + items.length) % items.length]?.focus()
  }
  const leave = (destination: string) => { setOpen(false); navigate(destination) }

  return <div className="profile-menu" ref={rootRef}>
    <button ref={triggerRef} className="profile-trigger" aria-label="用户菜单" aria-haspopup="menu" aria-expanded={open} aria-controls="profile-menu-panel" onClick={() => setOpen((value) => !value)}>
      <span className="profile-avatar">{user.display_name.slice(0, 1).toUpperCase()}</span>
      <span className="profile-copy"><b>{user.display_name}</b><small>{user.role === 'ADMIN' ? 'SYSTEM ADMIN' : 'STANDARD USER'}</small></span>
      <ChevronDown className={open ? 'open' : ''} size={15}/>
    </button>
    {open && <div id="profile-menu-panel" className="profile-dropdown" role="menu" ref={menuRef} onKeyDown={menuKeyboard}>
      <div className="profile-summary"><span className="profile-avatar large">{user.display_name.slice(0, 1).toUpperCase()}</span><span><strong>{user.display_name}</strong><small>@{user.username}</small></span>{user.role === 'ADMIN' && <b className="system-role-badge admin"><ShieldCheck size={12}/>SYSTEM ADMIN</b>}</div>
      <div className="profile-menu-items">
        {user.role === 'ADMIN' && <button role="menuitem" onClick={() => leave('/system/users')}><UsersRound size={17}/><span>System Users<small>System-level accounts</small></span></button>}
        <button role="menuitem" onClick={() => { setOpen(false); logout(); navigate('/auth') }}><LogOut size={17}/><span>Logout</span></button>
      </div>
    </div>}
  </div>
}

export function AppLayout() {
  const { user, logout } = useAuth()
  const { repositories, selected, selectRepository } = useRepositories()
  const navigate = useNavigate()
  const location = useLocation()
  const canManage = selected?.current_user_role === 'ADMIN'
  return <div className="app-shell">
    <header className="app-header">
      <button className="brand" onClick={() => navigate('/dashboard')} aria-label="CollabTrace 首页"><span className="logo-mark">C</span><span>CollabTrace<small>协作透镜</small></span></button>
      <nav className="nav-pills" aria-label="主导航">
        <NavLink to="/dashboard"><BarChart3 size={16}/>情况总览</NavLink>
        {canManage && <NavLink to="/admin"><Settings size={16}/>管理中心</NavLink>}
      </nav>
      <div className="header-actions">
        <label className="repository-select"><span className="sr-only">选择 Repository</span><select value={selected?.id ?? ''} onChange={(event) => { selectRepository(Number(event.target.value)); if (location.pathname !== '/system/users') navigate('/dashboard') }} disabled={!repositories.length}>{repositories.length ? repositories.map((repository) => <option key={repository.id} value={repository.id}>{repository.full_name} — {repository.current_user_role}</option>) : <option value="">暂无 Repository</option>}</select><ChevronDown size={15}/></label>
        {selected && <span className={`repository-role role-pill ${selected.current_user_role.toLowerCase()}`}>{selected.current_user_role}</span>}
        {user && <ProfileMenu user={user} logout={logout}/>}
      </div>
    </header>
    <main className="page-container"><Outlet /></main>
  </div>
}
