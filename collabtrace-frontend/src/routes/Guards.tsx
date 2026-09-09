import type { PropsWithChildren } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { PageLoader } from '../components/feedback/Feedback'
import { useAuth } from '../contexts/AuthContext'
import { useRepositories } from '../contexts/RepositoryContext'

export function ProtectedRoute({ children }: PropsWithChildren) {
  const { user, loading } = useAuth(); const location = useLocation()
  if (loading) return <PageLoader label="正在恢复登录状态…" />
  if (!user) return <Navigate to="/auth" state={{ from: location }} replace />
  return children
}
export function RepositoryAdminRoute({ children }: PropsWithChildren) {
  const { selected, loading } = useRepositories()
  if (loading) return <PageLoader label="正在读取 Repository 权限…" />
  if (selected?.current_user_role !== 'ADMIN') return <Navigate to="/403" replace />
  return children
}

export function SystemAdminRoute({ children }: PropsWithChildren) {
  const { user, loading } = useAuth()
  if (loading) return <PageLoader label="正在读取系统权限…" />
  if (user?.role !== 'ADMIN') return <Navigate to="/403" replace />
  return children
}
