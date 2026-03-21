export default function ScoreBar({ label, value }) {
  const pct   = Math.round((value ?? 0) * 100)
  const color = pct >= 80 ? 'var(--success)' : pct >= 60 ? 'var(--warning)' : 'var(--danger)'

  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
        <span style={{ fontSize: 11, color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>
          {label}
        </span>
        <span style={{ fontSize: 11, color, fontFamily: 'var(--font-mono)', fontWeight: 500 }}>
          {pct}%
        </span>
      </div>
      <div style={{ height: 2, background: 'var(--border-bright)', borderRadius: 2, overflow: 'hidden' }}>
        <div style={{
          height: '100%', width: `${pct}%`, background: color,
          borderRadius: 2, transition: 'width 0.9s cubic-bezier(0.4,0,0.2,1)',
        }} />
      </div>
    </div>
  )
}