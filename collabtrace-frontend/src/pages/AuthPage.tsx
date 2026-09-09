import { useEffect, useState } from 'react'
import { ArrowRight, Eye, GitCommitHorizontal, LoaderCircle, Mail, Mountain, ShieldCheck } from 'lucide-react'
import { Navigate, useNavigate } from 'react-router-dom'
import { authApi } from '../api/auth'
import { errorMessage } from '../api/client'
import { InlineFeedback } from '../components/feedback/Feedback'
import { useAuth } from '../contexts/AuthContext'

type MainTab = 'login' | 'register'
type LoginMode = 'password' | 'code'

function CodeButton({ email, purpose }: { email: string; purpose: 'LOGIN' | 'REGISTER' }) {
  const [seconds, setSeconds] = useState(0)
  const [error, setError] = useState('')
  useEffect(() => { if (!seconds) return; const timer = window.setInterval(() => setSeconds((value) => Math.max(0, value - 1)), 1000); return () => clearInterval(timer) }, [seconds])
  const send = async () => {
    setError('')
    try { await authApi.sendCode(email, purpose); setSeconds(60) }
    catch (reason) { setError(errorMessage(reason)) }
  }
  return <div className="code-action"><button type="button" className="button secondary code-button" onClick={send} disabled={!email || seconds > 0}>{seconds ? `重新发送 ${seconds}s` : '发送验证码'}</button>{error && <small className="field-error">{error}</small>}</div>
}

export function AuthPage() {
  const { user, completeLogin } = useAuth()
  const navigate = useNavigate()
  const [tab, setTab] = useState<MainTab>('login')
  const [mode, setMode] = useState<LoginMode>('password')
  const [form, setForm] = useState({ identifier: '', email: '', username: '', code: '', password: '', confirm: '' })
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
    event.preventDefault(); setLoading(true); setFeedback(null)
    try {
      if (tab === 'register') {
        await authApi.register({ username: form.username, email: form.email, verification_code: form.code, password: form.password, confirm_password: form.confirm })
        setFeedback({ kind: 'success', text: '注册成功。请登录 CollabTrace。' }); setTab('login'); setMode('password')
      } else {
        const response = mode === 'password'
          ? await authApi.passwordLogin(form.identifier, form.password)
          : await authApi.codeLogin(form.email, form.code)
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
        {tab === 'login' && <div className="sub-tabs"><button className={mode === 'password' ? 'active' : ''} onClick={() => setMode('password')}>密码登录</button><button className={mode === 'code' ? 'active' : ''} onClick={() => setMode('code')}>邮箱验证码登录</button></div>}
        <form className="stack-form" onSubmit={submit}>
          {tab === 'register' && <label>用户名<input aria-label="用户名" value={form.username} onChange={set('username')} placeholder="collab-member" required /></label>}
          {tab === 'login' && mode === 'password' ? <>
            <label>用户名 / 邮箱<input aria-label="用户名 / 邮箱" value={form.identifier} onChange={set('identifier')} placeholder="username@example.com" required autoComplete="username" /></label>
            <label>密码<span className="input-icon"><input aria-label="密码" value={form.password} onChange={set('password')} type="password" required autoComplete="current-password"/><Eye size={17}/></span></label>
          </> : <>
            <label>邮箱<span className="input-icon"><input aria-label="邮箱" value={form.email} onChange={set('email')} type="email" placeholder="you@example.com" required/><Mail size={17}/></span></label>
            <label>验证码<span className="input-with-button"><input aria-label="验证码" value={form.code} onChange={set('code')} inputMode="numeric" maxLength={6} placeholder="6 位验证码" required/><CodeButton email={form.email} purpose={tab === 'register' ? 'REGISTER' : 'LOGIN'}/></span></label>
            {tab === 'register' && <><label>密码<input aria-label="注册密码" value={form.password} onChange={set('password')} type="password" minLength={8} required autoComplete="new-password"/></label><label>确认密码<input aria-label="确认密码" value={form.confirm} onChange={set('confirm')} type="password" minLength={8} required autoComplete="new-password"/></label></>}
          </>}
          {feedback && <InlineFeedback kind={feedback.kind}>{feedback.text}</InlineFeedback>}
          <button className="button primary full auth-submit" disabled={loading}>{loading && <LoaderCircle className="spin" size={17}/>} {tab === 'register' ? '创建账号' : '进入 CollabTrace'} <ArrowRight size={18}/></button>
        </form>
      </div>
      <p className="auth-footnote">Contribution Activity Ranking 衡量活动数量，不代表质量或绩效。</p>
    </section>
  </main>
}
