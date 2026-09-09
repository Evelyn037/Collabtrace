import { AlertCircle, LoaderCircle, RotateCcw } from 'lucide-react'

export function PageLoader({ label = '正在加载真实数据…' }: { label?: string }) {
  return <div className="state-card" role="status"><LoaderCircle className="spin" /><strong>{label}</strong><span>请稍候</span></div>
}
export function EmptyState({ title, message, action }: { title: string; message: string; action?: React.ReactNode }) {
  return <div className="state-card"><span className="empty-mark">C</span><strong>{title}</strong><span>{message}</span>{action}</div>
}
export function PageError({ message, retry }: { message: string; retry?: () => void }) {
  return <div className="state-card error-state" role="alert"><AlertCircle /><strong>加载失败</strong><span>{message}</span>{retry && <button className="button secondary" onClick={retry}><RotateCcw size={16}/>重试</button>}</div>
}
export function InlineFeedback({ kind = 'error', children }: { kind?: 'error' | 'success' | 'info'; children: React.ReactNode }) {
  return <div className={`feedback ${kind}`} role={kind === 'error' ? 'alert' : 'status'}>{children}</div>
}
