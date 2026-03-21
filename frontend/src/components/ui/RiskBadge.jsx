const CONFIG = {
  LOW:    { color: 'var(--success)', bg: 'var(--success-dim)' },
  MEDIUM: { color: 'var(--warning)', bg: 'var(--warning-dim)' },
  HIGH:   { color: 'var(--danger)',  bg: 'var(--danger-dim)'  },
}

export default function RiskBadge({ tier }) {
  const c = CONFIG[tier] || CONFIG.MEDIUM
  return (
    <span style={{
      color: c.color, background: c.bg,
      border: `1px solid ${c.color}40`,
      borderRadius: 4, padding: '2px 8px',
      fontSize: 10, fontFamily: 'var(--font-mono)',
      letterSpacing: '0.1em',
    }}>
      {tier}
    </span>
  )
}