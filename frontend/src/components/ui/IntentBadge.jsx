import { INTENT_CONFIG } from '../../constants'

export default function IntentBadge({ intent }) {
  const cfg = INTENT_CONFIG[intent]
  if (!cfg) return null
  return (
    <span style={{
      color: cfg.color,
      background: `${cfg.color}18`,
      border: `1px solid ${cfg.color}30`,
      borderRadius: 4, padding: '2px 8px',
      fontSize: 10, fontFamily: 'var(--font-mono)',
      letterSpacing: '0.08em', textTransform: 'uppercase',
    }}>
      {cfg.label}
    </span>
  )
}