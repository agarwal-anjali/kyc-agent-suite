import { Shield, BookOpen, ShieldCheck, AlertCircle, FileSearch } from 'lucide-react'
import { SUGGESTIONS } from '../../constants'

const ICONS = {
  book:   BookOpen,
  shield: ShieldCheck,
  alert:  AlertCircle,
  file:   FileSearch,
}

export default function WelcomeScreen({ onSuggestion }) {
  return (
    <div style={{
      flex: 1, display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center',
      padding: '0 24px 60px',
    }}>
      {/* Icon */}
      <div style={{
        width: 56, height: 56, borderRadius: 16, marginBottom: 20,
        background: 'var(--gold-dim)', border: '1px solid var(--gold-glow)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}
        className="animate-fade-up"
      >
        <Shield size={26} style={{ color: 'var(--gold)' }} />
      </div>

      {/* Heading */}
      <h1
        className="font-display animate-fade-up"
        style={{
          fontSize: 32, fontWeight: 400, color: 'var(--text-primary)',
          marginBottom: 8, textAlign: 'center',
          animationDelay: '0.05s',
        }}
      >
        KYC Intelligence Suite
      </h1>

      <p
        className="animate-fade-up"
        style={{
          fontSize: 14, color: 'var(--text-secondary)', textAlign: 'center',
          maxWidth: 380, lineHeight: 1.7, marginBottom: 36,
          animationDelay: '0.1s',
        }}
      >
        Ask compliance related questions, review documents, or run full KYC checks and get detailed structured response with references.
      </p>

      {/* Suggestions */}
      <div
        className="animate-fade-up"
        style={{
          display: 'grid', gridTemplateColumns: '1fr 1fr',
          gap: 10, width: '100%', maxWidth: 520,
          animationDelay: '0.15s',
        }}
      >
        {SUGGESTIONS.map((s, i) => {
          const Icon = ICONS[s.icon] || Shield
          return (
            <button
              key={i}
              onClick={() => onSuggestion(s.text)}
              style={{
                textAlign: 'left', padding: '12px 14px',
                background: 'var(--bg-card)', border: '1px solid var(--border)',
                borderRadius: 'var(--radius-md)', cursor: 'pointer',
                transition: 'border-color 0.2s, background 0.2s',
                display: 'flex', alignItems: 'flex-start', gap: 10,
              }}
              onMouseEnter={e => {
                e.currentTarget.style.borderColor = 'var(--gold)'
                e.currentTarget.style.background  = 'var(--bg-hover)'
              }}
              onMouseLeave={e => {
                e.currentTarget.style.borderColor = 'var(--border)'
                e.currentTarget.style.background  = 'var(--bg-card)'
              }}
            >
              <Icon size={14} style={{ color: 'var(--gold)', marginTop: 1, flexShrink: 0 }} />
              <span style={{ fontSize: 14, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                {s.text}
              </span>
            </button>
          )
        })}
      </div>
    </div>
  )
}
