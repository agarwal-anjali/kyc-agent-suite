const CONFIG = {
  PASS:  { color: 'var(--success)', bg: 'var(--success-dim)' },
  REFER: { color: 'var(--warning)', bg: 'var(--warning-dim)' },
  FAIL:  { color: 'var(--danger)',  bg: 'var(--danger-dim)'  },
}

export default function VerdictBadge({ verdict }) {
  const c = CONFIG[verdict]
  if (!c) return null
  return (
    <span style={{
      color: c.color, background: c.bg,
      border: `1px solid ${c.color}40`,
      borderRadius: 4, padding: '2px 8px',
      fontSize: 10, fontFamily: 'var(--font-mono)',
      letterSpacing: '0.1em', fontWeight: 500,
    }}>
      {verdict}
    </span>
  )
}