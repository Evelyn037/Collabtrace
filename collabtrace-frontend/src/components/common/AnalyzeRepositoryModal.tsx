import { useState } from 'react'
import axios from 'axios'
import { ArrowRight, Check, LoaderCircle } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { repositoryApi } from '../../api/repositories'
import { errorMessage } from '../../api/client'
import type { AnalysisResult, Repository } from '../../types'
import { useRepositories } from '../../contexts/RepositoryContext'
import { Modal } from './Modal'
import { InlineFeedback } from '../feedback/Feedback'

export function AnalyzeRepositoryModal({ open, onClose, onComplete }: { open: boolean; onClose: () => void; onComplete?: (result: AnalysisResult) => void }) {
  const [value, setValue] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState<AnalysisResult | null>(null)
  const [readOnlyRepository, setReadOnlyRepository] = useState<Repository | null>(null)
  const { refreshRepositories, selectRepository } = useRepositories()
  const navigate = useNavigate()

  const analyze = async (event: React.FormEvent) => {
    event.preventDefault(); setLoading(true); setError(''); setResult(null); setReadOnlyRepository(null)
    try {
      const next = await repositoryApi.analyze(value)
      setResult(next)
      await refreshRepositories()
      selectRepository(next.repository.id)
      onComplete?.(next)
    } catch (reason) {
      if (axios.isAxiosError(reason) && reason.response?.status === 403) {
        const repositories = await refreshRepositories()
        const normalized = value.replace(/^https?:\/\/(www\.)?github\.com\//i, '').replace(/\.git\/?$/i, '').replace(/^\/|\/$/g, '').toLowerCase()
        const existing = repositories.find((repository) => repository.full_name.toLowerCase() === normalized)
        if (existing) { setReadOnlyRepository(existing); return }
      }
      setError(errorMessage(reason))
    }
    finally { setLoading(false) }
  }
  const close = () => { if (!loading) { onClose(); setResult(null); setReadOnlyRepository(null); setError('') } }
  return <Modal open={open} title="分析 GitHub Repository" onClose={close}>
    {readOnlyRepository ? <div className="analysis-result read-only-result">
      <h3>This repository has already been analyzed.</h3>
      <p className="muted">You have read-only access. Refresh requires Repository ADMIN permission.</p>
      <strong className="result-repository">{readOnlyRepository.full_name}</strong>
      <button className="button primary full" onClick={() => { selectRepository(readOnlyRepository.id); close(); navigate('/dashboard') }}>Open Dashboard <ArrowRight size={17}/></button>
    </div> : result ? <div className="analysis-result">
      <div className="success-orb"><Check /></div><h3>Analysis complete</h3>
      <p className="muted">Latest synchronized GitHub activity.</p>
      <strong className="result-repository">{result.repository.full_name}</strong>
      <div className="result-grid">
        <span>Fetched<b>{result.sync.fetched}</b></span><span>Inserted<b>{result.sync.inserted}</b></span>
        <span>Updated<b>{result.sync.updated}</b></span><span>Unchanged<b>{result.sync.unchanged}</b></span>
      </div>
      <button className="button primary full" onClick={() => { close(); navigate('/dashboard') }}>打开仪表盘 <ArrowRight size={17}/></button>
    </div> : <form onSubmit={analyze} className="stack-form">
      <p className="muted">粘贴任意公开 GitHub Repository URL，或输入 owner/repo。</p>
      <label>Repository
        <input value={value} onChange={(event) => setValue(event.target.value)} placeholder="https://github.com/pallets/flask" required autoFocus />
      </label>
      {error && <InlineFeedback>{error}</InlineFeedback>}
      {loading && <div className="analysis-loading"><span className="indeterminate"/><strong>Analyzing repository...</strong><small>Verifying repository and synchronizing GitHub activity.</small></div>}
      <button className="button primary full" disabled={loading}>{loading ? <LoaderCircle className="spin" size={17}/> : null}Analyze <ArrowRight size={17}/></button>
    </form>}
  </Modal>
}
