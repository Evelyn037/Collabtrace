import { useEffect, useRef } from 'react'
import type { PropsWithChildren } from 'react'
import { X } from 'lucide-react'

export function Modal({ open, title, onClose, children, wide = false }: PropsWithChildren<{
  open: boolean; title: string; onClose: () => void; wide?: boolean
}>) {
  const panel = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) return
    const prior = document.activeElement as HTMLElement | null
    panel.current?.focus()
    const keydown = (event: KeyboardEvent) => { if (event.key === 'Escape') onClose() }
    document.addEventListener('keydown', keydown)
    return () => { document.removeEventListener('keydown', keydown); prior?.focus() }
  }, [open, onClose])
  if (!open) return null
  return <div className="modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose() }}>
    <div className={`modal-panel ${wide ? 'wide' : ''}`} role="dialog" aria-modal="true" aria-labelledby="modal-title" tabIndex={-1} ref={panel}>
      <div className="modal-heading"><h2 id="modal-title">{title}</h2><button className="icon-button" onClick={onClose} aria-label="关闭"><X /></button></div>
      {children}
    </div>
  </div>
}
