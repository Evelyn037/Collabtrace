import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { PropsWithChildren } from 'react'
import { repositoryApi } from '../api/repositories'
import type { Repository } from '../types'
import { useAuth } from './AuthContext'

const REPOSITORY_KEY = 'collabtrace_repository_id'
interface RepositoryState {
  repositories: Repository[]; selected: Repository | null; loading: boolean; error: string | null
  selectRepository: (id: number) => void; refreshRepositories: () => Promise<Repository[]>
}
const RepositoryContext = createContext<RepositoryState | null>(null)

export function RepositoryProvider({ children }: PropsWithChildren) {
  const { user } = useAuth()
  const [repositories, setRepositories] = useState<Repository[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(() => {
    const stored = sessionStorage.getItem(REPOSITORY_KEY)
    return stored ? Number(stored) : null
  })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refreshRepositories = useCallback(async () => {
    if (!user) { setRepositories([]); return [] }
    setLoading(true); setError(null)
    try {
      const data = await repositoryApi.list()
      setRepositories(data)
      setSelectedId((current) => data.some((repo) => repo.id === current) ? current : (data[0]?.id ?? null))
      return data
    } catch { setError('Repository 列表加载失败。'); return [] }
    finally { setLoading(false) }
  }, [user])

  useEffect(() => { void refreshRepositories() }, [refreshRepositories])
  useEffect(() => {
    if (selectedId) sessionStorage.setItem(REPOSITORY_KEY, String(selectedId))
    else sessionStorage.removeItem(REPOSITORY_KEY)
  }, [selectedId])

  const selectRepository = useCallback((id: number) => setSelectedId(id), [])
  const selected = repositories.find((repo) => repo.id === selectedId) ?? null
  const value = useMemo(() => ({ repositories, selected, loading, error, selectRepository, refreshRepositories }), [repositories, selected, loading, error, selectRepository, refreshRepositories])
  return <RepositoryContext.Provider value={value}>{children}</RepositoryContext.Provider>
}

export function useRepositories() {
  const value = useContext(RepositoryContext)
  if (!value) throw new Error('useRepositories must be used within RepositoryProvider')
  return value
}
