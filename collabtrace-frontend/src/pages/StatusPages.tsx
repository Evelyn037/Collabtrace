import { ArrowLeft, ShieldX } from 'lucide-react'
import { Link } from 'react-router-dom'

export function ForbiddenPage() { return <div className="status-page"><ShieldX/><span className="eyebrow">ERROR 403</span><h1>没有操作权限</h1><p>You do not have permission to perform this action.</p><Link className="button primary" to="/dashboard"><ArrowLeft size={17}/>返回情况总览</Link></div> }
export function NotFoundPage() { return <div className="status-page"><span className="status-number">404</span><h1>页面没有留下协作轨迹</h1><p>请检查地址，或返回团队贡献概览。</p><Link className="button primary" to="/dashboard">返回情况总览</Link></div> }
