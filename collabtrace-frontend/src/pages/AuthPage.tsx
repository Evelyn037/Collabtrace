import { useState } from 'react'
import { ArrowRight, Eye, GitCommitHorizontal, LoaderCircle, Mountain, ShieldCheck } from 'lucide-react'
import { Navigate, useNavigate } from 'react-router-dom'
import { authApi } from '../api/auth'
import { errorMessage } from '../api/client'
import { InlineFeedback } from '../components/feedback/Feedback'
import { useAuth } from '../contexts/AuthContext'

type MainTab = 'login' | 'register'

export function AuthPage() {
  const { user, completeLogin } = useAuth()
  const navigate = useNavigate()
  const [tab, setTab] = useState<MainTab>('login')
  const [form, setForm] = useState({ identifier: '', email: '', username: '', password: '', confirm: '' })
  const [loading, setLoading] = useState(false)
  const [feedback, setFeedback] = useState<{ kind: 'error' | 'success'; text: string } | null>(() => {
    const notice = sessionStorage.getItem('collabtrace_auth_notice')
    if (!notice) return null
    sessionStorage.removeItem('collabtrace_auth_notice')
    return { kind: 'error', text: notice }
  })
  if (user) return <Navigate to="/dashboard" replace />
  const set = (key: keyof typeof form) => (event: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, [key]: event.target.value })
  const submit = async (event: React.FormEvent) => {
    event.preventDefault(); setFeedback(null)
    if (tab === 'register' && form.password !== form.confirm) {
      setFeedback({ kind: 'error', text: '两次输入的密码不一致。' })
      return
    }
    setLoading(true)
    try {
      if (tab === 'register') {
        await authApi.register({ username: form.username, email: form.email, password: form.password, confirm_password: form.confirm })
        setFeedback({ kind: 'success', text: '注册成功。请使用昵称或邮箱登录 CollabTrace。' }); setTab('login')
      } else {
        const response = await authApi.passwordLogin(form.identifier, form.password)
        completeLogin(response); navigate('/dashboard')
      }
    } catch (reason) { setFeedback({ kind: 'error', text: errorMessage(reason) }) }
    finally { setLoading(false) }
  }
  return <main className="auth-page">
    <section className="auth-hero">
      <div className="auth-brand"><span className="logo-mark dark-logo">C</span><span>CollabTrace<small>协作透镜</small></span></div>
      <span className="hero-kicker">GITHUB COLLABORATION · MADE VISIBLE</span>
      <h1>Make teamwork<br/>visible.<br/><span>Trace every</span><br/>contribution.</h1>
      <p>用真实 GitHub 协作记录，看见每一次 Commit、Pull Request、Issue 与 Code Review。</p>
      <div className="hero-trail"><span><GitCommitHorizontal/>真实活动</span><span><Mountain/>动态山峰</span><span><ShieldCheck/>证据可溯</span></div>
      <div className="hero-orbit orbit-one"/><div className="hero-orbit orbit-two"/>
    </section>
    <section className="auth-panel">
      <div className="auth-card">
        <span className="eyebrow">WELCOME TO COLLABTRACE</span>
        <h2>{tab === 'login' ? '继续你的协作视野' : '创建协作透镜账号'}</h2>
        <p className="muted">{tab === 'login' ? '登录后查看真实 Repository 贡献图景。' : '公开注册账号将安全创建为 MEMBER。'}</p>
        <div className="segmented" role="tablist"><button className={tab === 'login' ? 'active' : ''} onClick={() => { setTab('login'); setFeedback(null) }}>登录</button><button className={tab === 'register' ? 'active' : ''} onClick={() => { setTab('register'); setFeedback(null) }}>注册</button></div>
        <form className="stack-form" onSubmit={submit}>
          {tab === 'register' ? <>
            <label>昵称<input aria-label="昵称" value={form.username} onChange={set('username')} placeholder="collab-member" required /></label>
            <label>邮箱<input aria-label="邮箱" value={form.email} onChange={set('email')} type="email" placeholder="you@example.com" required autoComplete="email" /></label>
            <label>密码<input aria-label="注册密码" value={form.password} onChange={set('password')} type="password" minLength={8} required autoComplete="new-password"/></label>
            <label>确认密码<input aria-label="确认密码" value={form.confirm} onChange={set('confirm')} type="password" minLength={8} required autoComplete="new-password"/></label>
          </> : <>
            <label>昵称或邮箱<input aria-label="昵称或邮箱" value={form.identifier} onChange={set('identifier')} placeholder="请输入昵称或邮箱" required autoComplete="username" /></label>
            <label>密码<span className="input-icon"><input aria-label="密码" value={form.password} onChange={set('password')} type="password" required autoComplete="current-password"/><Eye size={17}/></span></label>
          </>}
          {feedback && <InlineFeedback kind={feedback.kind}>{feedback.text}</InlineFeedback>}
          <button className="button primary full auth-submit" disabled={loading}>{loading && <LoaderCircle className="spin" size={17}/>} {tab === 'register' ? '创建账号' : '进入 CollabTrace'} <ArrowRight size={18}/></button>
        </form>
      </div>
      <p className="auth-footnote">Contribution Activity Ranking 衡量活动数量，不代表质量或绩效。</p>
    </section>
  </main>
}
