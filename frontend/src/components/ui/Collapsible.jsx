import { useState } from 'react'
import { ChevronDown } from 'lucide-react'

export default function Collapsible({ title, children, defaultOpen = false, icon: Icon }) {
  const [open, setOpen] = useState(defaultOpen)

  return (
    <div style={{
      border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)',
      overflow: 'hidden', marginTop: 10,
    }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          width: '100%', display: 'flex', alignItems: 'center',
          justifyContent: 'space-between', padding: '7px 12px',
          background: 'var(--bg-card)', borderBottom: open ? '1px solid var(--border)' : 'none',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          {Icon && <Icon size={12} style={{ color: 'var(--gold)' }} />}
          <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', letterSpacing: '0.08em' }}>
            {title}
          </span>
        </div>
        <ChevronDown size={12} style={{
          color: 'var(--text-muted)',
          transform: open ? 'rotate(180deg)' : 'none',
          transition: 'transform 0.2s',
        }} />
      </button>
      {open && (
        <div style={{ padding: '10px 12px', background: 'var(--bg-surface)' }}
          className="animate-fade-in">
          {children}
        </div>
      )}
    </div>
  )
}