import { useState } from 'react'
import { Shield, Plus, MessageSquare, ChevronLeft, ChevronRight, Trash2 } from 'lucide-react'
import { USE_MOCK } from '../../constants'
import { formatDate } from '../../lib/utils'

export default function Sidebar({ sessions, activeSessionId, onNewChat, onSelectSession, onDeleteSession }) {
  const [collapsed, setCollapsed] = useState(false)

  // Group sessions by date
  const grouped = sessions.reduce((acc, s) => {
    const label = s.dateLabel || formatDate(s.createdAt)
    if (!acc[label]) acc[label] = []
    acc[label].push(s)
    return acc
  }, {})

  return (
    <aside style={{
      width: collapsed ? 56 : 300, flexShrink: 0,
      background: 'var(--bg-surface)', borderRight: '1px solid var(--border)',
      display: 'flex', flexDirection: 'column',
      transition: 'width 0.25s cubic-bezier(0.4,0,0.2,1)',
      overflow: 'hidden',
    }}>

      {/* Logo row */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: collapsed ? 'center' : 'space-between',
        padding: collapsed ? '16px 0' : '16px 14px',
        borderBottom: '1px solid var(--border)',
      }}>
        {!collapsed && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Shield size={15} style={{ color: 'var(--gold)' }} />
            <span className="font-display" style={{ fontSize: 20, fontWeight: 500, color: 'var(--text-primary)', whiteSpace: 'nowrap' }}>
              KYC Intelligence Suite
            </span>
          </div>
        )}
        {collapsed && <Shield size={15} style={{ color: 'var(--gold)' }} />}

        {!collapsed && (
          <button onClick={() => setCollapsed(true)} style={{ color: 'var(--text-muted)', padding: 2 }}>
            <ChevronLeft size={14} />
          </button>
        )}
      </div>

      {/* Expand button when collapsed */}
      {collapsed && (
        <button
          onClick={() => setCollapsed(false)}
          style={{
            padding: '10px 0', display: 'flex', justifyContent: 'center',
            color: 'var(--text-muted)', borderBottom: '1px solid var(--border)',
          }}
        >
          <ChevronRight size={14} />
        </button>
      )}

      {/* New chat */}
      <div style={{ padding: collapsed ? '10px 8px' : '10px 10px' }}>
        <button
          onClick={onNewChat}
          title="New chat"
          style={{
            width: '100%', display: 'flex', alignItems: 'center',
            justifyContent: collapsed ? 'center' : 'flex-start',
            gap: 8, padding: collapsed ? '8px 0' : '8px 10px',
            background: 'var(--gold-dim)', border: '1px solid var(--gold-glow)',
            borderRadius: 'var(--radius-sm)', color: 'var(--gold)',
            fontSize: 14, fontFamily: 'var(--font-mono)',
            transition: 'background 0.2s',
            whiteSpace: 'nowrap', overflow: 'hidden',
          }}
          onMouseEnter={e => { e.currentTarget.style.background = 'var(--gold-glow)' }}
          onMouseLeave={e => { e.currentTarget.style.background = 'var(--gold-dim)' }}
        >
          <Plus size={13} style={{ flexShrink: 0 }} />
          {!collapsed && 'New Chat'}
        </button>
      </div>

      {/* Session list */}
      {!collapsed && (
        <div style={{ flex: 1, overflowY: 'auto', padding: '0 8px' }}>
          {Object.entries(grouped).map(([date, group]) => (
            <div key={date}>
              <p style={{
                fontSize: 12, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)',
                letterSpacing: '0.06em', padding: '10px 6px 4px', textTransform: 'uppercase',
              }}>
                {date}
              </p>
              {group.map(s => (
                <div
                  key={s.id}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 6,
                    borderRadius: 'var(--radius-sm)', marginBottom: 1,
                    background: s.id === activeSessionId ? 'var(--bg-active)' : 'transparent',
                    transition: 'background 0.15s',
                  }}
                  onMouseEnter={e => {
                    if (s.id !== activeSessionId)
                      e.currentTarget.style.background = 'var(--bg-hover)'
                  }}
                  onMouseLeave={e => {
                    if (s.id !== activeSessionId)
                      e.currentTarget.style.background = 'transparent'
                  }}
                >
                  <button
                    onClick={() => onSelectSession(s.id)}
                    style={{
                      flex: 1, display: 'flex', alignItems: 'center', gap: 7,
                      padding: '7px 8px', textAlign: 'left',
                    }}
                  >
                    <MessageSquare size={11} style={{
                      color: s.id === activeSessionId ? 'var(--gold)' : 'var(--text-muted)',
                      flexShrink: 0,
                    }} />
                    <span style={{
                      fontSize: 14, lineHeight: 1.45,
                      color: s.id === activeSessionId ? 'var(--text-primary)' : 'var(--text-secondary)',
                      overflow: 'hidden',
                      display: '-webkit-box',
                      WebkitLineClamp: 2,
                      WebkitBoxOrient: 'vertical',
                      wordBreak: 'break-word',
                    }}>
                      {s.preview}
                    </span>
                  </button>
                  <button
                    onClick={e => { e.stopPropagation(); onDeleteSession(s.id) }}
                    style={{ padding: '7px 6px', color: 'var(--text-muted)', opacity: 0, transition: 'opacity 0.15s' }}
                    onMouseEnter={e => { e.currentTarget.style.opacity = '1'; e.currentTarget.style.color = 'var(--danger)' }}
                    onMouseLeave={e => { e.currentTarget.style.opacity = '0'; e.currentTarget.style.color = 'var(--text-muted)' }}
                  >
                    <Trash2 size={11} />
                  </button>
                </div>
              ))}
            </div>
          ))}

          {sessions.length === 0 && (
            <p style={{ fontSize: 12, color: 'var(--text-muted)', textAlign: 'center', padding: '20px 0', fontFamily: 'var(--font-mono)' }}>
              No chats yet
            </p>
          )}
        </div>
      )}

      {/* Footer */}
      {!collapsed && (
        <div style={{
          padding: '10px 14px', borderTop: '1px solid var(--border)',
          display: 'flex', alignItems: 'center', gap: 6,
        }}>
          <div style={{
            width: 6, height: 6, borderRadius: '50%',
            background: USE_MOCK ? 'var(--warning)' : 'var(--success)',
          }} />
          <span style={{ fontSize: 12, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
            {USE_MOCK ? 'Mock mode' : 'Live'}
          </span>
        </div>
      )}
    </aside>
  )
}
